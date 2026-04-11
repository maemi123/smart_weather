"""Retrain Open-Meteo ECMWF bias-correction models for Hangzhou."""

from __future__ import annotations

import json
import os
import pickle
import warnings
from collections import Counter
from datetime import datetime, time, timedelta
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    mean_absolute_error,
    mean_squared_error,
    precision_score,
    recall_score,
)

from forecast_issue_time import infer_issue_time_from_filename
from station_config import (
    HANGZHOU_LAT,
    HANGZHOU_LON,
    HANGZHOU_OBS_FALLBACK_NAME,
    HANGZHOU_STATION_ID,
    HANGZHOU_STATION_NAME,
    HANGZHOU_TIMEZONE,
)

warnings.filterwarnings("ignore")

FORECAST_DIR = Path("data/hangzhou_openmeteo")
MODELS_DIR = Path("models")
DATA_DIR = Path("data")
MAX_LEAD_HOURS = 168
OBS_PRCP_THRESHOLD = 0.1

TRAINING_START = pd.Timestamp("2026-02-15")
FINAL_TEST_START = pd.Timestamp("2026-04-04")
FINAL_TEST_END = pd.Timestamp("2026-04-10")
PRODUCTION_TRAIN_END = FINAL_TEST_END

FOLDS = [
    {
        "name": "fold1",
        "train_start": "2026-02-15",
        "train_end": "2026-03-13",
        "eval_start": "2026-03-14",
        "eval_end": "2026-03-20",
    },
    {
        "name": "fold2",
        "train_start": "2026-02-15",
        "train_end": "2026-03-20",
        "eval_start": "2026-03-21",
        "eval_end": "2026-03-27",
    },
    {
        "name": "fold3",
        "train_start": "2026-02-15",
        "train_end": "2026-03-27",
        "eval_start": "2026-03-28",
        "eval_end": "2026-04-03",
    },
]

FEATURE_COLUMNS = [
    "forecast_temp",
    "forecast_rhum",
    "forecast_wspd",
    "forecast_pres",
    "hour",
    "month",
    "day_of_week",
    "is_day",
    "is_weekend",
    "lead_hours",
    "lead_category",
    "hour_sin",
    "hour_cos",
]

TARGET_COLUMNS = {
    "temp": "obs_temp",
    "rhum": "obs_rhum",
    "wspd": "obs_wspd",
}

LEAD_BUCKETS = [
    (0, 24, "0-24h"),
    (24, 48, "24-48h"),
    (48, 72, "48-72h"),
    (72, 120, "72-120h"),
    (120, 168, "120-168h"),
]


def _to_builtin(value):
    if isinstance(value, (np.floating, np.integer)):
        return value.item()
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat(sep=" ")
    if isinstance(value, (list, tuple)):
        return [_to_builtin(item) for item in value]
    if isinstance(value, dict):
        return {key: _to_builtin(val) for key, val in value.items()}
    return value


def _issue_date_mask(df: pd.DataFrame, start: str, end: str) -> pd.Series:
    start_ts = pd.Timestamp(start)
    end_ts = pd.Timestamp(end)
    return (df["issue_date"] >= start_ts) & (df["issue_date"] <= end_ts)


def _safe_mean(values: Iterable[float]) -> Optional[float]:
    values = list(values)
    if not values:
        return None
    return float(np.mean(values))


def infer_observed_cache_path(start_dt: datetime, end_dt: datetime) -> Path:
    return DATA_DIR / (
        f"hangzhou_observed_{start_dt.strftime('%Y%m%d')}_{end_dt.strftime('%Y%m%d')}.csv"
    )


def fetch_meteostat_observations(start_dt: datetime, end_dt: datetime) -> pd.DataFrame:
    """Fetch hourly observations from Meteostat as the current fallback truth source."""
    meteostat_dir = DATA_DIR / ".meteostat_cache"
    meteostat_dir.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("MS_CACHE_DIRECTORY", str(meteostat_dir))
    os.environ.setdefault("MS_STATIONS_DB_FILE", str(meteostat_dir / "stations.db"))

    try:
        from meteostat import Hourly  # type: ignore
    except Exception:
        import meteostat  # type: ignore

        Hourly = getattr(meteostat, "Hourly", None) or getattr(meteostat, "hourly", None)
        if Hourly is None:
            raise RuntimeError("Meteostat is not available in this environment")

    for attempt in range(3):
        try:
            hourly = Hourly(HANGZHOU_STATION_ID, start_dt, end_dt)
            df = hourly.fetch()
            if df is None or df.empty:
                raise RuntimeError("Meteostat returned no hourly observations")
            break
        except Exception:
            if attempt == 2:
                raise

    df = df.copy()
    df.index = pd.to_datetime(df.index)
    if getattr(df.index, "tz", None) is None:
        df.index = df.index.tz_localize("UTC")
    df.index = df.index.tz_convert(HANGZHOU_TIMEZONE).tz_localize(None)
    df = df.reset_index()
    df = df.rename(columns={"time": "datetime", "index": "datetime"})
    df["datetime"] = pd.to_datetime(df["datetime"]).dt.floor("h")
    df = df.rename(
        columns={
            "temp": "obs_temp",
            "rhum": "obs_rhum",
            "prcp": "obs_prcp",
            "wspd": "obs_wspd",
            "pres": "obs_pres",
            "wdir": "obs_wdir",
            "cldc": "obs_cldc",
            "coco": "obs_coco",
        }
    )

    required_cols = [
        "datetime",
        "obs_temp",
        "obs_rhum",
        "obs_prcp",
        "obs_wspd",
        "obs_pres",
        "obs_wdir",
        "obs_cldc",
        "obs_coco",
    ]
    for column in required_cols:
        if column not in df.columns:
            df[column] = pd.NA

    full_range = pd.date_range(
        start=datetime.combine(start_dt.date(), time(0, 0)),
        end=datetime.combine(end_dt.date(), time(23, 0)),
        freq="h",
    )
    df = pd.DataFrame({"datetime": full_range}).merge(df[required_cols], on="datetime", how="left")
    return df


def load_or_fetch_observed_data(start_dt: datetime, end_dt: datetime) -> Tuple[pd.DataFrame, dict]:
    cache_path = infer_observed_cache_path(start_dt, end_dt)
    source_name = HANGZHOU_OBS_FALLBACK_NAME
    source_type = "meteostat_fallback"

    if cache_path.exists():
        observed_df = pd.read_csv(cache_path)
        observed_df["datetime"] = pd.to_datetime(observed_df["datetime"])
    else:
        observed_df = fetch_meteostat_observations(start_dt, end_dt)
        observed_df.to_csv(cache_path, index=False, encoding="utf-8")

    metadata = {
        "source_name": source_name,
        "source_type": source_type,
        "station_id": HANGZHOU_STATION_ID,
        "station_name": HANGZHOU_STATION_NAME,
        "latitude": HANGZHOU_LAT,
        "longitude": HANGZHOU_LON,
        "timezone": HANGZHOU_TIMEZONE,
        "fallback_note": "Using Meteostat 58457 as the current best available hourly truth source.",
        "cache_path": str(cache_path),
        "time_range": {
            "start": observed_df["datetime"].min().isoformat(sep=" "),
            "end": observed_df["datetime"].max().isoformat(sep=" "),
        },
        "rows": int(len(observed_df)),
        "non_null_ratio": {
            column: float(observed_df[column].notna().mean())
            for column in observed_df.columns
            if column.startswith("obs_")
        },
        "missing_hours": int(observed_df["obs_temp"].isna().sum()),
    }
    return observed_df, metadata


def load_forecast_data() -> Tuple[pd.DataFrame, dict]:
    records: List[pd.DataFrame] = []
    audit_entries: List[dict] = []
    file_time_counter: Counter = Counter()

    files = sorted(FORECAST_DIR.glob("HZ_forecast_*.csv"))
    if not files:
        raise FileNotFoundError(f"No forecast files found in {FORECAST_DIR}")

    for path in files:
        estimate = infer_issue_time_from_filename(path.name)
        file_time_counter[path.stem.split("_")[-1][:4]] += 1
        audit_entry = {
            "file": path.name,
            "status": "ok" if estimate.valid else "skipped",
            "issue_cycle": estimate.issue_cycle,
            "issue_time_local": estimate.issue_time_local.isoformat(sep=" ")
            if estimate.issue_time_local
            else None,
            "reason": estimate.reason,
            "used_tolerance": estimate.used_tolerance,
        }
        if not estimate.valid:
            audit_entries.append(audit_entry)
            continue

        df = pd.read_csv(path)
        if df.empty:
            audit_entry["status"] = "empty"
            audit_entries.append(audit_entry)
            continue

        df["target_time"] = pd.to_datetime(df["datetime_beijing"])
        df["issue_time"] = estimate.issue_time_local
        df["issue_cycle"] = estimate.issue_cycle
        df["collection_file"] = path.name
        df["lead_hours"] = (df["target_time"] - df["issue_time"]).dt.total_seconds() / 3600
        df = df[(df["lead_hours"] >= 0) & (df["lead_hours"] <= MAX_LEAD_HOURS)].copy()
        df = df.rename(
            columns={
                "temperature_2m": "forecast_temp",
                "relative_humidity_2m": "forecast_rhum",
                "wind_speed_10m": "forecast_wspd",
                "pressure_msl": "forecast_pres",
                "wind_direction_10m": "forecast_wdir",
                "precipitation": "forecast_prcp",
            }
        )
        records.append(df)
        audit_entry["status"] = "loaded"
        audit_entry["rows"] = int(len(df))
        audit_entries.append(audit_entry)

    if not records:
        raise RuntimeError("No valid forecast files remained after issue-time filtering")

    combined = pd.concat(records, ignore_index=True)
    combined = combined.sort_values(["issue_time", "target_time", "collection_file"])
    combined = combined.drop_duplicates(subset=["issue_time", "target_time"], keep="last")
    combined["issue_date"] = combined["issue_time"].dt.floor("D")

    audit = {
        "forecast_dir": str(FORECAST_DIR),
        "file_count": int(len(files)),
        "loaded_file_count": int(sum(item["status"] == "loaded" for item in audit_entries)),
        "skipped_file_count": int(sum(item["status"] != "loaded" for item in audit_entries)),
        "collection_time_counts": dict(sorted(file_time_counter.items())),
        "invalid_files": [item for item in audit_entries if item["status"] != "loaded"],
        "loaded_files": [item for item in audit_entries if item["status"] == "loaded"],
        "aligned_target_range": {
            "start": combined["target_time"].min().isoformat(sep=" "),
            "end": combined["target_time"].max().isoformat(sep=" "),
        },
        "issue_time_range": {
            "start": combined["issue_time"].min().isoformat(sep=" "),
            "end": combined["issue_time"].max().isoformat(sep=" "),
        },
        "rows": int(len(combined)),
    }
    return combined, audit


def align_data(forecast_df: pd.DataFrame, observed_df: pd.DataFrame) -> pd.DataFrame:
    merged = forecast_df.merge(observed_df, left_on="target_time", right_on="datetime", how="inner")
    merged = merged.drop_duplicates(subset=["issue_time", "target_time"], keep="last")
    return merged


def create_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["hour"] = df["target_time"].dt.hour
    df["month"] = df["target_time"].dt.month
    df["day_of_week"] = df["target_time"].dt.dayofweek
    df["is_day"] = ((df["hour"] >= 6) & (df["hour"] < 18)).astype(int)
    df["is_weekend"] = (df["day_of_week"] >= 5).astype(int)
    df["lead_category"] = pd.cut(
        df["lead_hours"],
        bins=[-1, 24, 48, 72, 120, MAX_LEAD_HOURS],
        labels=[0, 1, 2, 3, 4],
    ).astype(int)
    df["hour_sin"] = np.sin(2 * np.pi * df["hour"] / 24)
    df["hour_cos"] = np.cos(2 * np.pi * df["hour"] / 24)
    return df


def train_regression_model(X_train: pd.DataFrame, y_train: pd.Series) -> RandomForestRegressor:
    model = RandomForestRegressor(
        n_estimators=220,
        max_depth=16,
        min_samples_split=5,
        min_samples_leaf=2,
        random_state=42,
        n_jobs=1,
    )
    model.fit(X_train, y_train)
    return model


def train_precip_classifier(X_train: pd.DataFrame, y_train: pd.Series) -> RandomForestClassifier:
    model = RandomForestClassifier(
        n_estimators=220,
        max_depth=12,
        min_samples_split=5,
        min_samples_leaf=2,
        class_weight="balanced",
        random_state=42,
        n_jobs=1,
    )
    model.fit(X_train, y_train)
    return model


def train_precip_regressor(X_train: pd.DataFrame, y_train: pd.Series) -> RandomForestRegressor:
    model = RandomForestRegressor(
        n_estimators=180,
        max_depth=12,
        min_samples_split=5,
        min_samples_leaf=2,
        random_state=42,
        n_jobs=1,
    )
    model.fit(X_train, y_train)
    return model


def evaluate_lead_buckets(test_df: pd.DataFrame, truth_col: str, baseline_col: str, pred_col: str) -> List[dict]:
    bucket_results = []
    for start, end, label in LEAD_BUCKETS:
        mask = (test_df["lead_hours"] > start) & (test_df["lead_hours"] <= end)
        if not mask.any():
            continue
        subset = test_df.loc[mask]
        original_mae = mean_absolute_error(subset[truth_col], subset[baseline_col])
        corrected_mae = mean_absolute_error(subset[truth_col], subset[pred_col])
        improvement = ((original_mae - corrected_mae) / original_mae * 100) if original_mae else 0.0
        bucket_results.append(
            {
                "lead_time": label,
                "samples": int(mask.sum()),
                "original_mae": float(original_mae),
                "corrected_mae": float(corrected_mae),
                "improvement_pct": float(improvement),
            }
        )
    return bucket_results


def evaluate_regression(
    model: RandomForestRegressor,
    test_df: pd.DataFrame,
    target_var: str,
) -> dict:
    truth_col = TARGET_COLUMNS[target_var]
    forecast_col = f"forecast_{target_var}"
    eval_df = test_df.dropna(subset=FEATURE_COLUMNS + [truth_col, forecast_col]).copy()
    if eval_df.empty:
        raise RuntimeError(f"No evaluation samples available for {target_var}")

    eval_df["predicted"] = model.predict(eval_df[FEATURE_COLUMNS])
    original_mae = mean_absolute_error(eval_df[truth_col], eval_df[forecast_col])
    corrected_mae = mean_absolute_error(eval_df[truth_col], eval_df["predicted"])
    original_rmse = np.sqrt(mean_squared_error(eval_df[truth_col], eval_df[forecast_col]))
    corrected_rmse = np.sqrt(mean_squared_error(eval_df[truth_col], eval_df["predicted"]))
    original_bias = float(np.mean(eval_df[forecast_col] - eval_df[truth_col]))
    corrected_bias = float(np.mean(eval_df["predicted"] - eval_df[truth_col]))
    improvement_pct = ((original_mae - corrected_mae) / original_mae * 100) if original_mae else 0.0

    return {
        "samples": int(len(eval_df)),
        "original_mae": float(original_mae),
        "corrected_mae": float(corrected_mae),
        "original_rmse": float(original_rmse),
        "corrected_rmse": float(corrected_rmse),
        "original_bias": original_bias,
        "corrected_bias": corrected_bias,
        "improvement_pct": float(improvement_pct),
        "lead_buckets": evaluate_lead_buckets(eval_df, truth_col, forecast_col, "predicted"),
    }


def prepare_precip_frames(feature_df: pd.DataFrame) -> pd.DataFrame:
    df = feature_df.dropna(subset=FEATURE_COLUMNS + ["obs_prcp", "forecast_prcp"]).copy()
    df["obs_has_precip"] = (df["obs_prcp"] > OBS_PRCP_THRESHOLD).astype(int)
    df["forecast_has_precip"] = (df["forecast_prcp"] > OBS_PRCP_THRESHOLD).astype(int)
    return df


def evaluate_precip_models(
    clf_model: RandomForestClassifier,
    reg_model: RandomForestRegressor,
    test_df: pd.DataFrame,
) -> dict:
    eval_df = prepare_precip_frames(test_df)
    if eval_df.empty:
        raise RuntimeError("No precipitation evaluation samples available")

    eval_df["pred_prob"] = clf_model.predict_proba(eval_df[FEATURE_COLUMNS])[:, 1]
    eval_df["pred_has_precip"] = (eval_df["pred_prob"] >= 0.5).astype(int)
    eval_df["pred_prcp_amount"] = np.where(
        eval_df["pred_has_precip"] == 1,
        reg_model.predict(eval_df[FEATURE_COLUMNS]),
        0.0,
    )

    raw_metrics = {
        "accuracy": float(accuracy_score(eval_df["obs_has_precip"], eval_df["forecast_has_precip"])),
        "precision": float(
            precision_score(eval_df["obs_has_precip"], eval_df["forecast_has_precip"], zero_division=0)
        ),
        "recall": float(recall_score(eval_df["obs_has_precip"], eval_df["forecast_has_precip"], zero_division=0)),
        "f1": float(f1_score(eval_df["obs_has_precip"], eval_df["forecast_has_precip"], zero_division=0)),
    }
    corrected_metrics = {
        "accuracy": float(accuracy_score(eval_df["obs_has_precip"], eval_df["pred_has_precip"])),
        "precision": float(
            precision_score(eval_df["obs_has_precip"], eval_df["pred_has_precip"], zero_division=0)
        ),
        "recall": float(recall_score(eval_df["obs_has_precip"], eval_df["pred_has_precip"], zero_division=0)),
        "f1": float(f1_score(eval_df["obs_has_precip"], eval_df["pred_has_precip"], zero_division=0)),
    }

    rainy_eval = eval_df[eval_df["obs_has_precip"] == 1].copy()
    rainy_raw_mae = None
    rainy_corrected_mae = None
    rainy_improvement = None
    if not rainy_eval.empty:
        rainy_raw_mae = float(mean_absolute_error(rainy_eval["obs_prcp"], rainy_eval["forecast_prcp"]))
        rainy_corrected_mae = float(
            mean_absolute_error(rainy_eval["obs_prcp"], rainy_eval["pred_prcp_amount"])
        )
        rainy_improvement = (
            float((rainy_raw_mae - rainy_corrected_mae) / rainy_raw_mae * 100) if rainy_raw_mae else 0.0
        )

    overall_raw_mae = float(mean_absolute_error(eval_df["obs_prcp"], eval_df["forecast_prcp"]))
    overall_corrected_mae = float(mean_absolute_error(eval_df["obs_prcp"], eval_df["pred_prcp_amount"]))
    overall_improvement = float(
        (overall_raw_mae - overall_corrected_mae) / overall_raw_mae * 100
    ) if overall_raw_mae else 0.0

    return {
        "samples": int(len(eval_df)),
        "rainy_samples": int(len(rainy_eval)),
        "classification_raw": raw_metrics,
        "classification_corrected": corrected_metrics,
        "rainy_mae_raw": rainy_raw_mae,
        "rainy_mae_corrected": rainy_corrected_mae,
        "rainy_improvement_pct": rainy_improvement,
        "overall_mae_raw": overall_raw_mae,
        "overall_mae_corrected": overall_corrected_mae,
        "overall_improvement_pct": overall_improvement,
    }


def run_regression_folds(feature_df: pd.DataFrame, target_var: str) -> List[dict]:
    truth_col = TARGET_COLUMNS[target_var]
    forecast_col = f"forecast_{target_var}"
    valid_df = feature_df.dropna(subset=FEATURE_COLUMNS + [truth_col, forecast_col]).copy()
    results = []
    for fold in FOLDS:
        train_mask = _issue_date_mask(valid_df, fold["train_start"], fold["train_end"])
        eval_mask = _issue_date_mask(valid_df, fold["eval_start"], fold["eval_end"])
        train_df = valid_df.loc[train_mask]
        eval_df = valid_df.loc[eval_mask]
        if train_df.empty or eval_df.empty:
            results.append({"name": fold["name"], "skipped": True, "reason": "insufficient_samples"})
            continue
        model = train_regression_model(train_df[FEATURE_COLUMNS], train_df[truth_col])
        fold_metrics = evaluate_regression(model, eval_df, target_var)
        fold_metrics["name"] = fold["name"]
        fold_metrics["train_rows"] = int(len(train_df))
        fold_metrics["eval_rows"] = int(len(eval_df))
        results.append(fold_metrics)
    return results


def run_precip_folds(feature_df: pd.DataFrame) -> List[dict]:
    valid_df = prepare_precip_frames(feature_df)
    results = []
    for fold in FOLDS:
        train_mask = _issue_date_mask(valid_df, fold["train_start"], fold["train_end"])
        eval_mask = _issue_date_mask(valid_df, fold["eval_start"], fold["eval_end"])
        train_df = valid_df.loc[train_mask]
        eval_df = valid_df.loc[eval_mask]
        if train_df.empty or eval_df.empty or train_df["obs_has_precip"].nunique() < 2:
            results.append({"name": fold["name"], "skipped": True, "reason": "insufficient_samples"})
            continue
        clf_model = train_precip_classifier(train_df[FEATURE_COLUMNS], train_df["obs_has_precip"])
        rainy_train = train_df[train_df["obs_has_precip"] == 1]
        reg_train = rainy_train if len(rainy_train) >= 10 else train_df
        reg_model = train_precip_regressor(reg_train[FEATURE_COLUMNS], reg_train["obs_prcp"])
        metrics = evaluate_precip_models(clf_model, reg_model, eval_df)
        metrics["name"] = fold["name"]
        metrics["train_rows"] = int(len(train_df))
        metrics["eval_rows"] = int(len(eval_df))
        results.append(metrics)
    return results


def summarize_fold_metrics(fold_metrics: List[dict], metric_keys: List[str]) -> dict:
    valid_metrics = [item for item in fold_metrics if not item.get("skipped")]
    if not valid_metrics:
        return {"completed_folds": 0}

    summary = {"completed_folds": len(valid_metrics)}
    for metric_key in metric_keys:
        values = [item.get(metric_key) for item in valid_metrics if item.get(metric_key) is not None]
        summary[f"{metric_key}_mean"] = _safe_mean(values)
    return summary


def save_pickle(model, name: str) -> None:
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    with open(MODELS_DIR / f"rf_{name}.pkl", "wb") as handle:
        pickle.dump(model, handle)


def save_config(name: str, metadata: dict) -> None:
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "feature_columns": FEATURE_COLUMNS,
        "target_variable": name,
        "max_lead_hours": MAX_LEAD_HOURS,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    payload.update(metadata)
    with open(MODELS_DIR / f"config_{name}.json", "w", encoding="utf-8") as handle:
        json.dump(_to_builtin(payload), handle, ensure_ascii=False, indent=2)


def train_production_regression_models(feature_df: pd.DataFrame) -> Dict[str, dict]:
    outputs = {}
    train_mask = _issue_date_mask(
        feature_df,
        TRAINING_START.strftime("%Y-%m-%d"),
        PRODUCTION_TRAIN_END.strftime("%Y-%m-%d"),
    )
    for target_var, truth_col in TARGET_COLUMNS.items():
        forecast_col = f"forecast_{target_var}"
        train_df = feature_df.loc[train_mask].dropna(subset=FEATURE_COLUMNS + [truth_col, forecast_col]).copy()
        if train_df.empty:
            raise RuntimeError(f"No production training rows available for {target_var}")
        model = train_regression_model(train_df[FEATURE_COLUMNS], train_df[truth_col])
        save_pickle(model, target_var)
        outputs[target_var] = {"model": model, "train_rows": int(len(train_df))}
    return outputs


def train_production_precip_models(feature_df: pd.DataFrame) -> Dict[str, dict]:
    train_mask = _issue_date_mask(
        feature_df,
        TRAINING_START.strftime("%Y-%m-%d"),
        PRODUCTION_TRAIN_END.strftime("%Y-%m-%d"),
    )
    train_df = prepare_precip_frames(feature_df.loc[train_mask])
    if train_df.empty or train_df["obs_has_precip"].nunique() < 2:
        raise RuntimeError("No valid production precipitation training rows available")

    clf_model = train_precip_classifier(train_df[FEATURE_COLUMNS], train_df["obs_has_precip"])
    rainy_train = train_df[train_df["obs_has_precip"] == 1]
    reg_train = rainy_train if len(rainy_train) >= 10 else train_df
    reg_model = train_precip_regressor(reg_train[FEATURE_COLUMNS], reg_train["obs_prcp"])
    save_pickle(clf_model, "precip_clf")
    save_pickle(reg_model, "precip_reg")
    return {
        "precip_clf": {"model": clf_model, "train_rows": int(len(train_df))},
        "precip_reg": {"model": reg_model, "train_rows": int(len(reg_train))},
    }


def build_training_manifest(
    forecast_audit: dict,
    observation_metadata: dict,
    aligned_df: pd.DataFrame,
) -> dict:
    return {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "forecast_dir": str(FORECAST_DIR),
        "station": {
            "station_id": HANGZHOU_STATION_ID,
            "station_name": HANGZHOU_STATION_NAME,
            "latitude": HANGZHOU_LAT,
            "longitude": HANGZHOU_LON,
            "timezone": HANGZHOU_TIMEZONE,
        },
        "forecast_audit": forecast_audit,
        "observation": observation_metadata,
        "alignment": {
            "rows": int(len(aligned_df)),
            "issue_time_range": {
                "start": aligned_df["issue_time"].min().isoformat(sep=" "),
                "end": aligned_df["issue_time"].max().isoformat(sep=" "),
            },
            "target_time_range": {
                "start": aligned_df["target_time"].min().isoformat(sep=" "),
                "end": aligned_df["target_time"].max().isoformat(sep=" "),
            },
            "duplicate_issue_target_pairs": int(
                aligned_df.duplicated(subset=["issue_time", "target_time"]).sum()
            ),
        },
        "splits": {
            "folds": FOLDS,
            "final_test": {
                "start": FINAL_TEST_START.strftime("%Y-%m-%d"),
                "end": FINAL_TEST_END.strftime("%Y-%m-%d"),
            },
            "production_train_end": PRODUCTION_TRAIN_END.strftime("%Y-%m-%d"),
        },
        "feature_columns": FEATURE_COLUMNS,
        "max_lead_hours": MAX_LEAD_HOURS,
    }


def build_metrics_report(feature_df: pd.DataFrame) -> dict:
    report = {"generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "regression": {}, "precipitation": {}}
    production_train_end_for_test = (FINAL_TEST_START - timedelta(days=1)).strftime("%Y-%m-%d")
    final_test_range = {
        "start": FINAL_TEST_START.strftime("%Y-%m-%d"),
        "end": FINAL_TEST_END.strftime("%Y-%m-%d"),
    }

    for target_var, truth_col in TARGET_COLUMNS.items():
        forecast_col = f"forecast_{target_var}"
        valid_df = feature_df.dropna(subset=FEATURE_COLUMNS + [truth_col, forecast_col]).copy()
        test_mask = _issue_date_mask(valid_df, final_test_range["start"], final_test_range["end"])
        train_mask = _issue_date_mask(valid_df, TRAINING_START.strftime("%Y-%m-%d"), production_train_end_for_test)
        train_df = valid_df.loc[train_mask]
        test_df = valid_df.loc[test_mask]
        if train_df.empty or test_df.empty:
            report["regression"][target_var] = {
                "cross_validation": run_regression_folds(feature_df, target_var),
                "final_test": {"skipped": True, "reason": "insufficient_samples"},
            }
            continue

        model = train_regression_model(train_df[FEATURE_COLUMNS], train_df[truth_col])
        cv_metrics = run_regression_folds(feature_df, target_var)
        test_metrics = evaluate_regression(model, test_df, target_var)
        test_metrics["train_rows"] = int(len(train_df))
        test_metrics["test_rows"] = int(len(test_df))
        report["regression"][target_var] = {
            "cross_validation": cv_metrics,
            "cross_validation_summary": summarize_fold_metrics(
                cv_metrics,
                ["original_mae", "corrected_mae", "improvement_pct", "original_rmse", "corrected_rmse"],
            ),
            "final_test": test_metrics,
        }

    precip_df = prepare_precip_frames(feature_df)
    train_mask = _issue_date_mask(precip_df, TRAINING_START.strftime("%Y-%m-%d"), production_train_end_for_test)
    test_mask = _issue_date_mask(precip_df, final_test_range["start"], final_test_range["end"])
    train_df = precip_df.loc[train_mask]
    test_df = precip_df.loc[test_mask]
    cv_metrics = run_precip_folds(feature_df)
    if train_df.empty or test_df.empty or train_df["obs_has_precip"].nunique() < 2:
        report["precipitation"] = {
            "cross_validation": cv_metrics,
            "final_test": {"skipped": True, "reason": "insufficient_samples"},
        }
    else:
        clf_model = train_precip_classifier(train_df[FEATURE_COLUMNS], train_df["obs_has_precip"])
        rainy_train = train_df[train_df["obs_has_precip"] == 1]
        reg_train = rainy_train if len(rainy_train) >= 10 else train_df
        reg_model = train_precip_regressor(reg_train[FEATURE_COLUMNS], reg_train["obs_prcp"])
        final_test_metrics = evaluate_precip_models(clf_model, reg_model, test_df)
        final_test_metrics["train_rows"] = int(len(train_df))
        final_test_metrics["test_rows"] = int(len(test_df))
        report["precipitation"] = {
            "cross_validation": cv_metrics,
            "cross_validation_summary": summarize_fold_metrics(
                cv_metrics,
                ["overall_mae_raw", "overall_mae_corrected", "overall_improvement_pct"],
            ),
            "final_test": final_test_metrics,
        }

    return report


def save_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(_to_builtin(payload), handle, ensure_ascii=False, indent=2)


def main() -> None:
    forecast_df, forecast_audit = load_forecast_data()
    observed_start = forecast_df["target_time"].min().to_pydatetime()
    observed_end = forecast_df["target_time"].max().to_pydatetime()
    observed_df, observation_metadata = load_or_fetch_observed_data(observed_start, observed_end)

    aligned_df = align_data(forecast_df, observed_df)
    if aligned_df.empty:
        raise RuntimeError("No aligned forecast/observation rows were produced")

    feature_df = create_features(aligned_df)
    metrics_report = build_metrics_report(feature_df)
    manifest = build_training_manifest(forecast_audit, observation_metadata, aligned_df)

    regression_models = train_production_regression_models(feature_df)
    precip_models = train_production_precip_models(feature_df)

    common_config = {
        "forecast_dir": str(FORECAST_DIR),
        "obs_source": observation_metadata["source_name"],
        "obs_source_type": observation_metadata["source_type"],
        "station_name": HANGZHOU_STATION_NAME,
        "station_id": HANGZHOU_STATION_ID,
        "latitude": HANGZHOU_LAT,
        "longitude": HANGZHOU_LON,
        "train_start": TRAINING_START.strftime("%Y-%m-%d"),
        "train_end": PRODUCTION_TRAIN_END.strftime("%Y-%m-%d"),
        "final_test_start": FINAL_TEST_START.strftime("%Y-%m-%d"),
        "final_test_end": FINAL_TEST_END.strftime("%Y-%m-%d"),
    }

    for target_var, metadata in regression_models.items():
        save_config(
            target_var,
            {
                **common_config,
                "train_rows": metadata["train_rows"],
                "model_kind": "regression",
            },
        )

    for target_var, metadata in precip_models.items():
        save_config(
            target_var,
            {
                **common_config,
                "train_rows": metadata["train_rows"],
                "model_kind": "precipitation",
            },
        )

    save_json(MODELS_DIR / "training_manifest.json", manifest)
    save_json(MODELS_DIR / "metrics_report.json", metrics_report)

    print("=" * 72)
    print("Bias correction retraining completed")
    print("=" * 72)
    print(f"Forecast rows aligned: {len(aligned_df)}")
    print(f"Observed source: {observation_metadata['source_name']}")
    print(f"Manifest: {MODELS_DIR / 'training_manifest.json'}")
    print(f"Metrics: {MODELS_DIR / 'metrics_report.json'}")

    for target_var in TARGET_COLUMNS:
        test_metrics = metrics_report["regression"].get(target_var, {}).get("final_test", {})
        if test_metrics.get("skipped"):
            print(f"{target_var}: final test skipped ({test_metrics.get('reason')})")
            continue
        print(
            f"{target_var}: MAE {test_metrics['original_mae']:.3f} -> "
            f"{test_metrics['corrected_mae']:.3f} "
            f"({test_metrics['improvement_pct']:+.1f}%)"
        )

    precip_test = metrics_report.get("precipitation", {}).get("final_test", {})
    if precip_test and not precip_test.get("skipped"):
        raw = precip_test["classification_raw"]
        corrected = precip_test["classification_corrected"]
        print(
            "precip_classification: "
            f"acc {raw['accuracy']:.3f}->{corrected['accuracy']:.3f}, "
            f"recall {raw['recall']:.3f}->{corrected['recall']:.3f}, "
            f"f1 {raw['f1']:.3f}->{corrected['f1']:.3f}"
        )


if __name__ == "__main__":
    main()
