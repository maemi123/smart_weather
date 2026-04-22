"""Train V2 ECMWF/Open-Meteo bias-correction models for Hangzhou."""

from __future__ import annotations

import json
import pickle
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier, GradientBoostingRegressor

from ml_features_v2 import FEATURE_COLUMNS_V2, add_v2_features
from station_config import (
    HANGZHOU_LAT,
    HANGZHOU_LON,
    HANGZHOU_STATION_ID,
    HANGZHOU_STATION_NAME,
)
from train_bias_correction import (
    FINAL_TEST_END,
    FINAL_TEST_START,
    FOLDS,
    FORECAST_DIR,
    LEAD_BUCKETS,
    OBS_PRCP_THRESHOLD,
    PRODUCTION_TRAIN_END,
    TARGET_COLUMNS,
    TRAINING_START,
    _issue_date_mask,
    _safe_mean,
    _to_builtin,
    align_data,
    build_training_manifest,
    evaluate_lead_buckets,
    evaluate_precip_models,
    evaluate_regression,
    load_forecast_data,
    load_or_fetch_observed_data,
    prepare_precip_frames,
    run_precip_folds,
    save_json,
    summarize_fold_metrics,
)


MODELS_DIR_V2 = Path("models_v2")
BACKEND_NAME = "sklearn_gradient_boosting"
SPLIT_POLICY = "issue_time_split_with_target_time_embargo"


def build_feature_frame(aligned_df: pd.DataFrame) -> pd.DataFrame:
    feature_df = add_v2_features(aligned_df)
    for column in FEATURE_COLUMNS_V2:
        if column not in feature_df.columns:
            feature_df[column] = 0
    return feature_df


def _strict_train_eval_split(
    df: pd.DataFrame,
    train_start: str,
    train_end: str,
    eval_start: str,
    eval_end: str,
) -> Tuple[pd.DataFrame, pd.DataFrame, dict]:
    train_mask = _issue_date_mask(df, train_start, train_end)
    eval_mask = _issue_date_mask(df, eval_start, eval_end)
    train_df = df.loc[train_mask].copy()
    eval_df = df.loc[eval_mask].copy()
    if eval_df.empty:
        return train_df.iloc[0:0].copy(), eval_df, {
            "policy": SPLIT_POLICY,
            "target_overlap_count": 0,
            "target_overlap_ratio_eval": None,
            "embargo_applied": False,
        }

    eval_min_target = eval_df["target_time"].min()
    embargo_train_df = train_df.loc[train_df["target_time"] < eval_min_target].copy()
    train_targets = set(pd.to_datetime(embargo_train_df["target_time"]).astype(str))
    eval_targets = set(pd.to_datetime(eval_df["target_time"]).astype(str))
    overlap = train_targets & eval_targets
    audit = {
        "policy": SPLIT_POLICY,
        "eval_min_target_time": eval_min_target.isoformat(sep=" "),
        "target_overlap_count": len(overlap),
        "target_overlap_ratio_eval": float(len(overlap) / len(eval_targets)) if eval_targets else None,
        "embargo_applied": True,
        "train_rows_before_embargo": int(len(train_df)),
        "train_rows_after_embargo": int(len(embargo_train_df)),
        "eval_rows": int(len(eval_df)),
    }
    return embargo_train_df, eval_df, audit


def _final_test_train_end() -> str:
    return (FINAL_TEST_START - timedelta(days=1)).strftime("%Y-%m-%d")


def _make_regressor() -> object:
    try:
        from catboost import CatBoostRegressor  # type: ignore

        return CatBoostRegressor(
            depth=6,
            learning_rate=0.05,
            iterations=500,
            loss_function="MAE",
            verbose=False,
            random_seed=42,
        )
    except Exception:
        pass

    try:
        from lightgbm import LGBMRegressor  # type: ignore

        return LGBMRegressor(
            n_estimators=350,
            learning_rate=0.05,
            max_depth=6,
            num_leaves=31,
            random_state=42,
        )
    except Exception:
        pass

    return GradientBoostingRegressor(
        loss="absolute_error",
        learning_rate=0.05,
        max_depth=6,
        n_estimators=350,
        min_samples_leaf=20,
        subsample=0.9,
        random_state=42,
    )


def _make_classifier() -> object:
    try:
        from catboost import CatBoostClassifier  # type: ignore

        return CatBoostClassifier(
            depth=6,
            learning_rate=0.05,
            iterations=450,
            loss_function="Logloss",
            verbose=False,
            random_seed=42,
        )
    except Exception:
        pass

    try:
        from lightgbm import LGBMClassifier  # type: ignore

        return LGBMClassifier(
            n_estimators=300,
            learning_rate=0.05,
            max_depth=6,
            num_leaves=31,
            random_state=42,
        )
    except Exception:
        pass

    return GradientBoostingClassifier(
        learning_rate=0.05,
        max_depth=6,
        n_estimators=300,
        min_samples_leaf=20,
        subsample=0.9,
        random_state=42,
    )


def _fit(model: object, X: pd.DataFrame, y: pd.Series) -> object:
    model.fit(X, y)
    return model


def train_regression_model_v2(X_train: pd.DataFrame, y_train: pd.Series) -> object:
    return _fit(_make_regressor(), X_train, y_train)


def train_precip_classifier_v2(X_train: pd.DataFrame, y_train: pd.Series) -> object:
    return _fit(_make_classifier(), X_train, y_train)


def train_precip_regressor_v2(X_train: pd.DataFrame, y_train: pd.Series) -> object:
    return _fit(_make_regressor(), X_train, y_train)


def evaluate_regression_v2(model: object, test_df: pd.DataFrame, target_var: str) -> dict:
    truth_col = TARGET_COLUMNS[target_var]
    forecast_col = f"forecast_{target_var}"
    eval_df = test_df.dropna(subset=FEATURE_COLUMNS_V2 + [truth_col, forecast_col]).copy()
    if eval_df.empty:
        raise RuntimeError(f"No evaluation samples available for {target_var}")

    eval_df["predicted"] = model.predict(eval_df[FEATURE_COLUMNS_V2])
    if target_var == "rhum":
        eval_df["predicted"] = eval_df["predicted"].clip(0, 100)
    if target_var == "wspd":
        eval_df["predicted"] = eval_df["predicted"].clip(lower=0)

    original_mae = float(np.mean(np.abs(eval_df[truth_col] - eval_df[forecast_col])))
    corrected_mae = float(np.mean(np.abs(eval_df[truth_col] - eval_df["predicted"])))
    original_rmse = float(np.sqrt(np.mean((eval_df[truth_col] - eval_df[forecast_col]) ** 2)))
    corrected_rmse = float(np.sqrt(np.mean((eval_df[truth_col] - eval_df["predicted"]) ** 2)))
    original_bias = float(np.mean(eval_df[forecast_col] - eval_df[truth_col]))
    corrected_bias = float(np.mean(eval_df["predicted"] - eval_df[truth_col]))
    improvement_pct = float(((original_mae - corrected_mae) / original_mae * 100) if original_mae else 0.0)

    return {
        "samples": int(len(eval_df)),
        "original_mae": original_mae,
        "corrected_mae": corrected_mae,
        "original_rmse": original_rmse,
        "corrected_rmse": corrected_rmse,
        "original_bias": original_bias,
        "corrected_bias": corrected_bias,
        "improvement_pct": improvement_pct,
        "lead_buckets": evaluate_lead_buckets(eval_df, truth_col, forecast_col, "predicted"),
    }


def _evaluate_precip_direct(clf_model: object, reg_model: object, test_df: pd.DataFrame) -> dict:
    from sklearn.metrics import accuracy_score, f1_score, mean_absolute_error, precision_score, recall_score

    eval_df = prepare_precip_frames(test_df)
    if eval_df.empty:
        raise RuntimeError("No precipitation evaluation samples available")

    if hasattr(clf_model, "predict_proba"):
        pred_prob = clf_model.predict_proba(eval_df[FEATURE_COLUMNS_V2])[:, 1]
        pred_has = (pred_prob >= 0.5).astype(int)
    else:
        pred_has = clf_model.predict(eval_df[FEATURE_COLUMNS_V2]).astype(int)
        pred_prob = pred_has

    pred_amount = np.where(
        pred_has == 1,
        np.maximum(0.0, reg_model.predict(eval_df[FEATURE_COLUMNS_V2])),
        0.0,
    )
    eval_df["pred_prcp_amount"] = pred_amount

    raw_metrics = {
        "accuracy": float(accuracy_score(eval_df["obs_has_precip"], eval_df["forecast_has_precip"])),
        "precision": float(precision_score(eval_df["obs_has_precip"], eval_df["forecast_has_precip"], zero_division=0)),
        "recall": float(recall_score(eval_df["obs_has_precip"], eval_df["forecast_has_precip"], zero_division=0)),
        "f1": float(f1_score(eval_df["obs_has_precip"], eval_df["forecast_has_precip"], zero_division=0)),
    }
    corrected_metrics = {
        "accuracy": float(accuracy_score(eval_df["obs_has_precip"], pred_has)),
        "precision": float(precision_score(eval_df["obs_has_precip"], pred_has, zero_division=0)),
        "recall": float(recall_score(eval_df["obs_has_precip"], pred_has, zero_division=0)),
        "f1": float(f1_score(eval_df["obs_has_precip"], pred_has, zero_division=0)),
    }

    rainy_eval = eval_df[eval_df["obs_has_precip"] == 1].copy()
    rainy_raw_mae = rainy_corrected_mae = rainy_improvement = None
    if not rainy_eval.empty:
        rainy_pred_amount = eval_df.loc[rainy_eval.index, "pred_prcp_amount"]
        rainy_raw_mae = float(mean_absolute_error(rainy_eval["obs_prcp"], rainy_eval["forecast_prcp"]))
        rainy_corrected_mae = float(mean_absolute_error(rainy_eval["obs_prcp"], rainy_pred_amount))
        rainy_improvement = float(((rainy_raw_mae - rainy_corrected_mae) / rainy_raw_mae * 100) if rainy_raw_mae else 0.0)

    overall_raw_mae = float(mean_absolute_error(eval_df["obs_prcp"], eval_df["forecast_prcp"]))
    overall_corrected_mae = float(mean_absolute_error(eval_df["obs_prcp"], pred_amount))
    overall_improvement = float(((overall_raw_mae - overall_corrected_mae) / overall_raw_mae * 100) if overall_raw_mae else 0.0)

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


def run_regression_folds_v2(feature_df: pd.DataFrame, target_var: str) -> List[dict]:
    truth_col = TARGET_COLUMNS[target_var]
    forecast_col = f"forecast_{target_var}"
    valid_df = feature_df.dropna(subset=FEATURE_COLUMNS_V2 + [truth_col, forecast_col]).copy()
    results = []
    for fold in FOLDS:
        train_df, eval_df, split_audit = _strict_train_eval_split(
            valid_df,
            fold["train_start"],
            fold["train_end"],
            fold["eval_start"],
            fold["eval_end"],
        )
        if train_df.empty or eval_df.empty:
            results.append({"name": fold["name"], "skipped": True, "reason": "insufficient_samples"})
            continue
        model = train_regression_model_v2(train_df[FEATURE_COLUMNS_V2].fillna(0), train_df[truth_col])
        fold_metrics = evaluate_regression_v2(model, eval_df, target_var)
        fold_metrics["name"] = fold["name"]
        fold_metrics["train_rows"] = int(len(train_df))
        fold_metrics["eval_rows"] = int(len(eval_df))
        fold_metrics["split_audit"] = split_audit
        results.append(fold_metrics)
    return results


def run_precip_folds_v2(feature_df: pd.DataFrame) -> List[dict]:
    valid_df = prepare_precip_frames(feature_df)
    results = []
    for fold in FOLDS:
        train_df, eval_df, split_audit = _strict_train_eval_split(
            valid_df,
            fold["train_start"],
            fold["train_end"],
            fold["eval_start"],
            fold["eval_end"],
        )
        if train_df.empty or eval_df.empty or train_df["obs_has_precip"].nunique() < 2:
            results.append({"name": fold["name"], "skipped": True, "reason": "insufficient_samples"})
            continue
        clf_model = train_precip_classifier_v2(train_df[FEATURE_COLUMNS_V2].fillna(0), train_df["obs_has_precip"])
        rainy_train = train_df[train_df["obs_has_precip"] == 1]
        reg_train = rainy_train if len(rainy_train) >= 10 else train_df
        reg_model = train_precip_regressor_v2(reg_train[FEATURE_COLUMNS_V2].fillna(0), reg_train["obs_prcp"])
        metrics = _evaluate_precip_direct(clf_model, reg_model, eval_df)
        metrics["name"] = fold["name"]
        metrics["train_rows"] = int(len(train_df))
        metrics["eval_rows"] = int(len(eval_df))
        metrics["split_audit"] = split_audit
        results.append(metrics)
    return results


def save_pickle_v2(model: object, name: str) -> None:
    MODELS_DIR_V2.mkdir(parents=True, exist_ok=True)
    with open(MODELS_DIR_V2 / f"boost_{name}.pkl", "wb") as handle:
        pickle.dump(model, handle)


def save_config_v2(name: str, metadata: dict) -> None:
    MODELS_DIR_V2.mkdir(parents=True, exist_ok=True)
    payload = {
        "feature_columns": FEATURE_COLUMNS_V2,
        "target_variable": name,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "backend_preference": ["catboost", "lightgbm", "sklearn_gradient_boosting"],
        "backend_used": metadata.get("backend_used", BACKEND_NAME),
        "version": "v2",
    }
    payload.update(metadata)
    with open(MODELS_DIR_V2 / f"config_{name}.json", "w", encoding="utf-8") as handle:
        json.dump(_to_builtin(payload), handle, ensure_ascii=False, indent=2)


def detect_backend_name() -> str:
    try:
        import catboost  # type: ignore  # noqa: F401

        return "catboost"
    except Exception:
        pass
    try:
        import lightgbm  # type: ignore  # noqa: F401

        return "lightgbm"
    except Exception:
        pass
    return BACKEND_NAME


def build_metrics_report_v2(feature_df: pd.DataFrame) -> dict:
    report = {
        "version": "v2",
        "model_family": detect_backend_name(),
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "split_policy": SPLIT_POLICY,
        "feature_columns": FEATURE_COLUMNS_V2,
        "regression": {},
        "precipitation": {},
    }

    production_train_end_for_test = _final_test_train_end()
    final_test_range = {
        "start": FINAL_TEST_START.strftime("%Y-%m-%d"),
        "end": FINAL_TEST_END.strftime("%Y-%m-%d"),
    }

    for target_var in TARGET_COLUMNS:
        truth_col = TARGET_COLUMNS[target_var]
        forecast_col = f"forecast_{target_var}"
        valid_df = feature_df.dropna(subset=FEATURE_COLUMNS_V2 + [truth_col, forecast_col]).copy()
        train_df, test_df, split_audit = _strict_train_eval_split(
            valid_df,
            TRAINING_START.strftime("%Y-%m-%d"),
            production_train_end_for_test,
            final_test_range["start"],
            final_test_range["end"],
        )
        if train_df.empty or test_df.empty:
            report["regression"][target_var] = {"final_test": {"skipped": True, "reason": "insufficient_samples"}}
            continue

        model = train_regression_model_v2(train_df[FEATURE_COLUMNS_V2].fillna(0), train_df[truth_col])
        cv_metrics = run_regression_folds_v2(feature_df, target_var)
        test_metrics = evaluate_regression_v2(model, test_df, target_var)
        test_metrics["train_rows"] = int(len(train_df))
        test_metrics["test_rows"] = int(len(test_df))
        test_metrics["split_audit"] = split_audit
        report["regression"][target_var] = {
            "cross_validation": cv_metrics,
            "cross_validation_summary": summarize_fold_metrics(
                cv_metrics,
                ["original_mae", "corrected_mae", "improvement_pct", "original_rmse", "corrected_rmse"],
            ),
            "final_test": test_metrics,
        }

    precip_df = prepare_precip_frames(feature_df)
    train_df, test_df, split_audit = _strict_train_eval_split(
        precip_df,
        TRAINING_START.strftime("%Y-%m-%d"),
        production_train_end_for_test,
        final_test_range["start"],
        final_test_range["end"],
    )
    cv_metrics = run_precip_folds_v2(feature_df)
    if train_df.empty or test_df.empty or train_df["obs_has_precip"].nunique() < 2:
        report["precipitation"] = {
            "cross_validation": cv_metrics,
            "final_test": {"skipped": True, "reason": "insufficient_samples"},
        }
    else:
        clf_model = train_precip_classifier_v2(train_df[FEATURE_COLUMNS_V2].fillna(0), train_df["obs_has_precip"])
        rainy_train = train_df[train_df["obs_has_precip"] == 1]
        reg_train = rainy_train if len(rainy_train) >= 10 else train_df
        reg_model = train_precip_regressor_v2(reg_train[FEATURE_COLUMNS_V2].fillna(0), reg_train["obs_prcp"])
        final_test_metrics = _evaluate_precip_direct(clf_model, reg_model, test_df)
        final_test_metrics["train_rows"] = int(len(train_df))
        final_test_metrics["test_rows"] = int(len(test_df))
        final_test_metrics["split_audit"] = split_audit
        report["precipitation"] = {
            "cross_validation": cv_metrics,
            "cross_validation_summary": summarize_fold_metrics(
                cv_metrics,
                ["overall_mae_raw", "overall_mae_corrected", "overall_improvement_pct"],
            ),
            "final_test": final_test_metrics,
        }
    return report


def train_production_regression_models_v2(feature_df: pd.DataFrame) -> Dict[str, dict]:
    outputs = {}
    train_mask = _issue_date_mask(
        feature_df,
        TRAINING_START.strftime("%Y-%m-%d"),
        _final_test_train_end(),
    )
    train_df = feature_df.loc[train_mask]
    for target_var, truth_col in TARGET_COLUMNS.items():
        model_df = train_df.dropna(subset=FEATURE_COLUMNS_V2 + [truth_col]).copy()
        if model_df.empty:
            continue
        model = train_regression_model_v2(model_df[FEATURE_COLUMNS_V2].fillna(0), model_df[truth_col])
        save_pickle_v2(model, target_var)
        outputs[target_var] = {"train_rows": int(len(model_df))}
    return outputs


def train_production_precip_models_v2(feature_df: pd.DataFrame) -> Dict[str, dict]:
    train_mask = _issue_date_mask(
        feature_df,
        TRAINING_START.strftime("%Y-%m-%d"),
        _final_test_train_end(),
    )
    train_df = prepare_precip_frames(feature_df.loc[train_mask])
    outputs = {}
    if train_df.empty or train_df["obs_has_precip"].nunique() < 2:
        return outputs

    clf_model = train_precip_classifier_v2(train_df[FEATURE_COLUMNS_V2].fillna(0), train_df["obs_has_precip"])
    rainy_train = train_df[train_df["obs_has_precip"] == 1]
    reg_train = rainy_train if len(rainy_train) >= 10 else train_df
    reg_model = train_precip_regressor_v2(reg_train[FEATURE_COLUMNS_V2].fillna(0), reg_train["obs_prcp"])

    save_pickle_v2(clf_model, "precip_clf")
    save_pickle_v2(reg_model, "precip_reg")
    outputs["precip_clf"] = {"train_rows": int(len(train_df))}
    outputs["precip_reg"] = {"train_rows": int(len(reg_train))}
    return outputs


def _extract_v1_summary() -> Optional[dict]:
    path = Path("models/metrics_report.json")
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as handle:
        payload = json.load(handle)
    summary = {"regression": {}, "precipitation": {}}
    for target_var in TARGET_COLUMNS:
        final_test = payload.get("regression", {}).get(target_var, {}).get("final_test", {})
        if final_test:
            summary["regression"][target_var] = {
                "original_mae": final_test.get("original_mae"),
                "corrected_mae": final_test.get("corrected_mae"),
                "improvement_pct": final_test.get("improvement_pct"),
            }
    precip_test = payload.get("precipitation", {}).get("final_test", {})
    if precip_test:
        summary["precipitation"] = {
            "accuracy_raw": precip_test.get("classification_raw", {}).get("accuracy"),
            "accuracy_corrected": precip_test.get("classification_corrected", {}).get("accuracy"),
            "f1_raw": precip_test.get("classification_raw", {}).get("f1"),
            "f1_corrected": precip_test.get("classification_corrected", {}).get("f1"),
            "overall_mae_raw": precip_test.get("overall_mae_raw"),
            "overall_mae_corrected": precip_test.get("overall_mae_corrected"),
        }
    return summary


def write_comparison_report_v1_v2(metrics_v2: dict) -> None:
    lines = [
        "# V1/V2 机器学习误差校正对比",
        "",
        f"- 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"- V2 模型族：{metrics_v2.get('model_family')}",
        "- 统一真值源：Meteostat 58457（杭州国家基准气候站/馒头山口径）",
        "",
    ]
    metrics_v1 = _extract_v1_summary()
    if metrics_v1:
        lines.append("## 连续变量")
        lines.append("")
        lines.append("| 变量 | V1校正MAE | V2校正MAE | V1改进幅度 | V2改进幅度 |")
        lines.append("| --- | ---: | ---: | ---: | ---: |")
        for target_var, label in [("temp", "温度"), ("rhum", "湿度"), ("wspd", "风速")]:
            v1 = metrics_v1.get("regression", {}).get(target_var, {})
            v2 = metrics_v2.get("regression", {}).get(target_var, {}).get("final_test", {})
            lines.append(
                f"| {label} | {v1.get('corrected_mae', '-')!s} | {round(v2.get('corrected_mae', 0), 3) if v2 else '-'} | "
                f"{round(v1.get('improvement_pct', 0), 1) if v1 else '-'}% | {round(v2.get('improvement_pct', 0), 1) if v2 else '-'}% |"
            )
        lines.extend(["", "## 降水", "", "| 指标 | V1 | V2 |", "| --- | ---: | ---: |"])
        v1p = metrics_v1.get("precipitation", {})
        v2p = metrics_v2.get("precipitation", {}).get("final_test", {})
        rows = [
            ("分类准确率", v1p.get("accuracy_corrected"), v2p.get("classification_corrected", {}).get("accuracy")),
            ("分类F1", v1p.get("f1_corrected"), v2p.get("classification_corrected", {}).get("f1")),
            ("全样本MAE", v1p.get("overall_mae_corrected"), v2p.get("overall_mae_corrected")),
            ("雨样本MAE", "-", v2p.get("rainy_mae_corrected")),
        ]
        for name, v1v, v2v in rows:
            lines.append(f"| {name} | {v1v if v1v is not None else '-'} | {v2v if v2v is not None else '-'} |")
    else:
        lines.append("未找到 V1 指标文件，仅输出 V2 指标。")

    lines.extend(
        [
            "",
            "## 说明",
            "",
            "- V2 保留 V1 默认可回退逻辑，不覆盖 `models/`。",
            "- 真值源仍采用 Meteostat 58457，结果更适合作为工程验证与模型框架有效性说明。",
            "- 若未来可获取更权威的国家站原始小时观测，可在不改变 V2 架构的前提下重新训练。",
        ]
    )
    (MODELS_DIR_V2 / "comparison_report_v1_v2.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    forecast_df, forecast_audit = load_forecast_data()
    observed_start = forecast_df["target_time"].min().to_pydatetime()
    observed_end = forecast_df["target_time"].max().to_pydatetime()
    observed_df, observation_metadata = load_or_fetch_observed_data(observed_start, observed_end)

    aligned_df = align_data(forecast_df, observed_df)
    if aligned_df.empty:
        raise RuntimeError("No aligned forecast/observation rows were produced")

    feature_df = build_feature_frame(aligned_df)
    metrics_report = build_metrics_report_v2(feature_df)
    manifest = build_training_manifest(forecast_audit, observation_metadata, aligned_df)
    final_train_end = _final_test_train_end()
    strict_train_df, strict_test_df, strict_split_audit = _strict_train_eval_split(
        feature_df,
        TRAINING_START.strftime("%Y-%m-%d"),
        final_train_end,
        FINAL_TEST_START.strftime("%Y-%m-%d"),
        FINAL_TEST_END.strftime("%Y-%m-%d"),
    )
    manifest.update(
        {
            "version": "v2",
            "model_family": detect_backend_name(),
            "models_dir": str(MODELS_DIR_V2),
            "split_policy": SPLIT_POLICY,
            "feature_columns": FEATURE_COLUMNS_V2,
            "train_range": {
                "start": TRAINING_START.strftime("%Y-%m-%d"),
                "end": final_train_end,
            },
            "validation_folds": FOLDS,
            "final_test_range": {
                "start": FINAL_TEST_START.strftime("%Y-%m-%d"),
                "end": FINAL_TEST_END.strftime("%Y-%m-%d"),
            },
            "aligned_rows": int(len(aligned_df)),
            "strict_split_audit": {
                **strict_split_audit,
                "strict_train_rows": int(len(strict_train_df)),
                "strict_test_rows": int(len(strict_test_df)),
            },
            "truth_source_note": (
                "本研究以 Meteostat 平台提供的杭州国家基准气候站（站号 58457）逐小时观测数据作为模型训练与评估的统一真值来源。"
                "该站点位于杭州市馒头山，站号明确、空间坐标可追溯，能够满足本研究中站点口径统一与误差校正模型构建的基本需求。"
                "需要说明的是，受数据共享政策及用户权限限制，本研究未能获取国家气象信息中心的原始观测资料，但不影响模型框架有效性的验证。"
            ),
            "limitations": [
                "降水真值与官方统计产品可能存在口径差异。",
                "当前评估更适合作为工程验证和方法探索，不直接等同业务化精度结论。",
            ],
        }
    )

    regression_models = train_production_regression_models_v2(feature_df)
    precip_models = train_production_precip_models_v2(feature_df)
    backend_used = detect_backend_name()

    common_config = {
        "forecast_dir": str(FORECAST_DIR),
        "obs_source": observation_metadata["source_name"],
        "obs_source_type": observation_metadata["source_type"],
        "station_name": HANGZHOU_STATION_NAME,
        "station_id": HANGZHOU_STATION_ID,
        "latitude": HANGZHOU_LAT,
        "longitude": HANGZHOU_LON,
        "train_start": TRAINING_START.strftime("%Y-%m-%d"),
        "train_end": final_train_end,
        "final_test_start": FINAL_TEST_START.strftime("%Y-%m-%d"),
        "final_test_end": FINAL_TEST_END.strftime("%Y-%m-%d"),
        "backend_used": backend_used,
        "version": "v2",
    }

    for target_var, metadata in regression_models.items():
        save_config_v2(target_var, {**common_config, "train_rows": metadata["train_rows"], "model_kind": "regression"})
    for target_var, metadata in precip_models.items():
        save_config_v2(target_var, {**common_config, "train_rows": metadata["train_rows"], "model_kind": "precipitation"})

    save_json(MODELS_DIR_V2 / "training_manifest_v2.json", manifest)
    save_json(MODELS_DIR_V2 / "metrics_report_v2.json", metrics_report)
    write_comparison_report_v1_v2(metrics_report)

    print("=" * 72)
    print("Bias correction V2 training completed")
    print("=" * 72)
    print(f"Forecast rows aligned: {len(aligned_df)}")
    print(f"Observed source: {observation_metadata['source_name']}")
    print(f"Manifest: {MODELS_DIR_V2 / 'training_manifest_v2.json'}")
    print(f"Metrics: {MODELS_DIR_V2 / 'metrics_report_v2.json'}")


if __name__ == "__main__":
    main()
