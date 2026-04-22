"""Feature engineering shared by V2 training and runtime correction."""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

import numpy as np
import pandas as pd


MAX_LEAD_HOURS = 168

FEATURE_COLUMNS_V2 = [
    "forecast_temp",
    "forecast_rhum",
    "forecast_wspd",
    "forecast_pres",
    "forecast_prcp",
    "hour",
    "month",
    "day_of_week",
    "is_day",
    "is_weekend",
    "lead_hours",
    "lead_category",
    "hour_sin",
    "hour_cos",
    "issue_cycle_code",
    "season_code",
    "lead_cycle_interaction",
    "temp_change_3h",
    "rhum_change_3h",
    "wspd_change_3h",
    "prcp_sum_3h",
    "temp_change_6h",
    "rhum_change_6h",
    "wspd_change_6h",
    "prcp_sum_6h",
]


def infer_issue_cycle(issue_time: Optional[datetime]) -> str:
    if issue_time is None:
        return "unknown"
    if issue_time.hour == 8:
        return "00Z"
    if issue_time.hour == 20:
        return "12Z"
    return "unknown"


def add_v2_features(df: pd.DataFrame, issue_time: Optional[datetime] = None) -> pd.DataFrame:
    df = df.copy()
    df["target_time"] = pd.to_datetime(df["target_time"])
    if issue_time is not None:
        df["issue_time"] = pd.to_datetime(issue_time)
    elif "issue_time" in df.columns:
        df["issue_time"] = pd.to_datetime(df["issue_time"])
    else:
        df["issue_time"] = df["target_time"].min()

    df = df.sort_values(["issue_time", "target_time"]).reset_index(drop=True)
    df["hour"] = df["target_time"].dt.hour
    df["month"] = df["target_time"].dt.month
    df["day_of_week"] = df["target_time"].dt.dayofweek
    df["is_day"] = ((df["hour"] >= 6) & (df["hour"] < 18)).astype(int)
    df["is_weekend"] = (df["day_of_week"] >= 5).astype(int)
    df["lead_hours"] = (
        df["target_time"] - df["issue_time"]
    ).dt.total_seconds() / 3600
    df["lead_hours"] = df["lead_hours"].clip(lower=0, upper=MAX_LEAD_HOURS)
    df["lead_category"] = pd.cut(
        df["lead_hours"],
        bins=[-1, 24, 48, 72, 120, MAX_LEAD_HOURS],
        labels=[0, 1, 2, 3, 4],
    ).astype(int)
    df["hour_sin"] = np.sin(2 * np.pi * df["hour"] / 24)
    df["hour_cos"] = np.cos(2 * np.pi * df["hour"] / 24)

    df["issue_cycle"] = df["issue_time"].dt.hour.map({8: "00Z", 20: "12Z"}).fillna("unknown")
    df["issue_cycle_code"] = df["issue_cycle"].map({"00Z": 0, "12Z": 1}).fillna(-1).astype(int)
    season_map = {
        12: 0, 1: 0, 2: 0,
        3: 1, 4: 1, 5: 1,
        6: 2, 7: 2, 8: 2,
        9: 3, 10: 3, 11: 3,
    }
    df["season_code"] = df["month"].map(season_map).astype(int)
    df["lead_cycle_interaction"] = df["lead_category"] * 10 + df["issue_cycle_code"]

    group_cols = ["issue_time"]
    for source_col, out_col in [
        ("forecast_temp", "temp_change"),
        ("forecast_rhum", "rhum_change"),
        ("forecast_wspd", "wspd_change"),
    ]:
        df[f"{out_col}_3h"] = df.groupby(group_cols)[source_col].diff(3).fillna(0)
        df[f"{out_col}_6h"] = df.groupby(group_cols)[source_col].diff(6).fillna(0)

    df["prcp_sum_3h"] = (
        df.groupby(group_cols)["forecast_prcp"]
        .rolling(window=3, min_periods=1)
        .sum()
        .reset_index(level=0, drop=True)
    )
    df["prcp_sum_6h"] = (
        df.groupby(group_cols)["forecast_prcp"]
        .rolling(window=6, min_periods=1)
        .sum()
        .reset_index(level=0, drop=True)
    )

    for column in FEATURE_COLUMNS_V2:
        if column not in df.columns:
            df[column] = 0
    return df


def runtime_frame(data: List[Dict], issue_time: Optional[datetime] = None) -> pd.DataFrame:
    df = pd.DataFrame(data)
    if "datetime" in df.columns:
        df["target_time"] = pd.to_datetime(df["datetime"])
    elif "time" in df.columns:
        df["target_time"] = pd.to_datetime(df["time"])
    else:
        raise ValueError("forecast data missing datetime/time")

    rename_map = {
        "temperature_2m": "forecast_temp",
        "relative_humidity_2m": "forecast_rhum",
        "wind_speed_10m": "forecast_wspd",
        "pressure_msl": "forecast_pres",
        "precipitation": "forecast_prcp",
    }
    for old_name, new_name in rename_map.items():
        if old_name in df.columns and new_name not in df.columns:
            df[new_name] = df[old_name]

    if "forecast_prcp" not in df.columns:
        df["forecast_prcp"] = 0.0
    if "forecast_pres" not in df.columns:
        df["forecast_pres"] = 1013.0

    if issue_time is not None and isinstance(issue_time, str):
        issue_time = pd.to_datetime(issue_time).to_pydatetime()
    if issue_time is None:
        embedded_issue_time = None
        for candidate in ("issue_time", "issue_time_estimated"):
            if candidate in df.columns and df[candidate].notna().any():
                embedded_issue_time = pd.to_datetime(df[candidate].dropna().iloc[0]).to_pydatetime()
                break
        issue_time = embedded_issue_time or df["target_time"].min().to_pydatetime()

    return add_v2_features(df, issue_time)
