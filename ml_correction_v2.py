"""V2 ML bias correction runtime loader and inference."""

from __future__ import annotations

import json
import logging
import os
import pickle
from datetime import datetime
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from ml_features_v2 import FEATURE_COLUMNS_V2, runtime_frame

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MODELS_DIR_V2 = "models_v2"


class MLCorrectorV2:
    _instance = None

    def __new__(cls, models_dir: str = MODELS_DIR_V2):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, models_dir: str = MODELS_DIR_V2):
        if self._initialized:
            return
        self.models_dir = models_dir
        self.models: Dict[str, object] = {}
        self.metadata: Dict[str, dict] = {}
        self._load_models()
        self._initialized = True

    def _load_models(self) -> None:
        model_files = {
            "temp": "boost_temp.pkl",
            "rhum": "boost_rhum.pkl",
            "wspd": "boost_wspd.pkl",
            "precip_clf": "boost_precip_clf.pkl",
            "precip_reg": "boost_precip_reg.pkl",
        }
        for name, filename in model_files.items():
            filepath = os.path.join(self.models_dir, filename)
            if not os.path.exists(filepath):
                logger.warning("V2 model missing: %s", filepath)
                continue
            try:
                with open(filepath, "rb") as handle:
                    self.models[name] = pickle.load(handle)
                logger.info("Loaded V2 model: %s", name)
            except Exception as exc:
                logger.error("Failed to load V2 model %s: %s", name, exc)

        manifest_path = os.path.join(self.models_dir, "training_manifest_v2.json")
        if os.path.exists(manifest_path):
            try:
                with open(manifest_path, "r", encoding="utf-8") as handle:
                    self.metadata = json.load(handle)
            except Exception as exc:
                logger.warning("Failed to load V2 manifest: %s", exc)

    def is_loaded(self) -> bool:
        return len(self.models) >= 3

    def correct(self, data: List[Dict], issue_time: Optional[datetime] = None) -> List[Dict]:
        if not self.is_loaded():
            logger.warning("V2 models not loaded, falling back to raw data")
            return data

        try:
            df = runtime_frame(data, issue_time)
            missing = [feature for feature in FEATURE_COLUMNS_V2 if feature not in df.columns]
            if missing:
                logger.error("V2 missing features: %s", missing)
                return data

            X = df[FEATURE_COLUMNS_V2].fillna(0)
            corrected = []
            for idx in range(len(df)):
                item = data[idx].copy()
                row = X.iloc[[idx]]

                if "temp" in self.models:
                    item["temperature_2m_corrected"] = float(self.models["temp"].predict(row)[0])
                if "rhum" in self.models:
                    rh = float(self.models["rhum"].predict(row)[0])
                    item["relative_humidity_2m_corrected"] = float(np.clip(rh, 0, 100))
                if "wspd" in self.models:
                    ws = float(self.models["wspd"].predict(row)[0])
                    item["wind_speed_10m_corrected"] = max(0.0, ws)
                if "precip_clf" in self.models and "precip_reg" in self.models:
                    pred_has = self.models["precip_clf"].predict(row)[0]
                    if int(pred_has) == 1:
                        pred_amount = float(self.models["precip_reg"].predict(row)[0])
                        item["precipitation_corrected"] = max(0.0, pred_amount)
                    else:
                        item["precipitation_corrected"] = 0.0

                corrected.append(item)
            return corrected
        except Exception as exc:
            logger.error("V2 correction failed: %s", exc)
            return data


_corrector_instance_v2 = None


def get_corrector_v2() -> MLCorrectorV2:
    global _corrector_instance_v2
    if _corrector_instance_v2 is None:
        _corrector_instance_v2 = MLCorrectorV2()
    return _corrector_instance_v2


def apply_ml_correction_v2(data: List[Dict], issue_time: Optional[datetime] = None) -> List[Dict]:
    return get_corrector_v2().correct(data, issue_time)
