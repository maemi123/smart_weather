"""
机器学习误差校正模块
加载训练好的随机森林模型，对预报数据进行校正
"""
import os
import pickle
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MODELS_DIR = 'models'

FEATURE_COLUMNS = [
    'forecast_temp', 'forecast_rhum', 'forecast_wspd', 'forecast_pres',
    'hour', 'month', 'day_of_week', 'is_day', 'is_weekend',
    'lead_hours', 'lead_category',
    'hour_sin', 'hour_cos'
]

class MLCorrector:
    """机器学习误差校正器"""
    
    _instance = None
    
    def __new__(cls, models_dir: str = MODELS_DIR):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self, models_dir: str = MODELS_DIR):
        if self._initialized:
            return
        
        self.models_dir = models_dir
        self.models = {}
        self._load_models()
        self._initialized = True
    
    def _load_models(self):
        """加载所有模型"""
        model_files = {
            'temp': 'rf_temp.pkl',
            'rhum': 'rf_rhum.pkl',
            'wspd': 'rf_wspd.pkl',
            'precip_clf': 'rf_precip_clf.pkl',
            'precip_reg': 'rf_precip_reg.pkl'
        }
        
        for name, filename in model_files.items():
            filepath = os.path.join(self.models_dir, filename)
            if os.path.exists(filepath):
                try:
                    with open(filepath, 'rb') as f:
                        self.models[name] = pickle.load(f)
                    logger.info(f"已加载模型: {name}")
                except Exception as e:
                    logger.error(f"加载模型 {name} 失败: {e}")
            else:
                logger.warning(f"模型文件不存在: {filepath}")
    
    def is_loaded(self) -> bool:
        """检查模型是否加载成功"""
        return len(self.models) >= 3
    
    def create_features(self, data: List[Dict], issue_time: Optional[datetime] = None) -> pd.DataFrame:
        """
        创建特征
        
        Args:
            data: 预报数据列表，每个元素包含:
                - datetime: 预报时间 (str or datetime)
                - temperature_2m: 温度预报
                - relative_humidity_2m: 湿度预报
                - wind_speed_10m: 风速预报
                - pressure_msl: 气压预报
            issue_time: 起报时间，如果不提供则自动推断
        
        Returns:
            DataFrame with features
        """
        df = pd.DataFrame(data)
        
        if 'datetime' in df.columns:
            df['target_time'] = pd.to_datetime(df['datetime'])
        elif 'time' in df.columns:
            df['target_time'] = pd.to_datetime(df['time'])
        else:
            raise ValueError("数据中缺少时间字段 (datetime 或 time)")
        
        if issue_time is not None and isinstance(issue_time, str):
            issue_time = pd.to_datetime(issue_time).to_pydatetime()

        if issue_time is None:
            embedded_issue_time = None
            for candidate in ('issue_time', 'issue_time_estimated'):
                if candidate in df.columns and df[candidate].notna().any():
                    embedded_issue_time = pd.to_datetime(df[candidate].dropna().iloc[0]).to_pydatetime()
                    break
            issue_time = embedded_issue_time or df['target_time'].min().to_pydatetime()
        
        df['hour'] = df['target_time'].dt.hour
        df['month'] = df['target_time'].dt.month
        df['day_of_week'] = df['target_time'].dt.dayofweek
        df['is_day'] = ((df['hour'] >= 6) & (df['hour'] < 18)).astype(int)
        df['is_weekend'] = (df['day_of_week'] >= 5).astype(int)
        
        df['lead_hours'] = (df['target_time'] - issue_time).dt.total_seconds() / 3600
        df['lead_hours'] = df['lead_hours'].clip(lower=0)
        
        def categorize_lead(hours):
            if hours <= 24:
                return 0
            elif hours <= 48:
                return 1
            elif hours <= 72:
                return 2
            elif hours <= 120:
                return 3
            else:
                return 4
        
        df['lead_category'] = df['lead_hours'].apply(categorize_lead)
        
        df['hour_sin'] = np.sin(2 * np.pi * df['hour'] / 24)
        df['hour_cos'] = np.cos(2 * np.pi * df['hour'] / 24)
        
        rename_map = {
            'temperature_2m': 'forecast_temp',
            'relative_humidity_2m': 'forecast_rhum',
            'wind_speed_10m': 'forecast_wspd',
            'pressure_msl': 'forecast_pres'
        }
        for old_name, new_name in rename_map.items():
            if old_name in df.columns and new_name not in df.columns:
                df[new_name] = df[old_name]
        
        return df
    
    def correct(self, data: List[Dict], issue_time: Optional[datetime] = None) -> List[Dict]:
        """
        对预报数据进行校正
        
        Args:
            data: 预报数据列表
            issue_time: 起报时间
        
        Returns:
            校正后的数据列表
        """
        if not self.is_loaded():
            logger.warning("模型未加载，返回原始数据")
            return data
        
        try:
            df = self.create_features(data, issue_time)
            
            missing_features = [f for f in FEATURE_COLUMNS if f not in df.columns]
            if missing_features:
                logger.error(f"缺少特征列: {missing_features}")
                return data
            
            X = df[FEATURE_COLUMNS].fillna(0)
            
            corrected_data = []
            for i, row in df.iterrows():
                corrected_item = data[i].copy() if isinstance(data, list) else dict(row)
                
                X_row = X.iloc[[i]] if hasattr(X, 'iloc') else X[i:i+1]
                
                if 'temp' in self.models:
                    corrected_item['temperature_2m_corrected'] = float(self.models['temp'].predict(X_row)[0])
                
                if 'rhum' in self.models:
                    corrected_item['relative_humidity_2m_corrected'] = float(self.models['rhum'].predict(X_row)[0])
                
                if 'wspd' in self.models:
                    corrected_item['wind_speed_10m_corrected'] = float(self.models['wspd'].predict(X_row)[0])
                
                if 'precip_clf' in self.models and 'precip_reg' in self.models:
                    has_precip = self.models['precip_clf'].predict(X_row)[0]
                    if has_precip:
                        precip_amount = self.models['precip_reg'].predict(X_row)[0]
                        corrected_item['precipitation_corrected'] = max(0, float(precip_amount))
                    else:
                        corrected_item['precipitation_corrected'] = 0.0
                
                corrected_data.append(corrected_item)
            
            return corrected_data
            
        except Exception as e:
            logger.error(f"校正过程出错: {e}")
            import traceback
            traceback.print_exc()
            return data
    
    def correct_single_point(self, 
                             forecast_temp: float,
                             forecast_rhum: float,
                             forecast_wspd: float,
                             forecast_pres: float,
                             target_time: datetime,
                             issue_time: Optional[datetime] = None) -> Dict:
        """
        校正单个时间点的预报
        
        Args:
            forecast_temp: 温度预报值
            forecast_rhum: 湿度预报值
            forecast_wspd: 风速预报值
            forecast_pres: 气压预报值
            target_time: 预报时间
            issue_time: 起报时间
        
        Returns:
            校正后的值字典
        """
        if not self.is_loaded():
            return {}
        
        if issue_time is None:
            issue_time = target_time
        
        hour = target_time.hour
        month = target_time.month
        day_of_week = target_time.weekday()
        is_day = 1 if 6 <= hour < 18 else 0
        is_weekend = 1 if day_of_week >= 5 else 0
        
        lead_hours = (target_time - issue_time).total_seconds() / 3600
        lead_hours = max(0, lead_hours)
        
        if lead_hours <= 24:
            lead_category = 0
        elif lead_hours <= 48:
            lead_category = 1
        elif lead_hours <= 72:
            lead_category = 2
        elif lead_hours <= 120:
            lead_category = 3
        else:
            lead_category = 4
        
        hour_sin = np.sin(2 * np.pi * hour / 24)
        hour_cos = np.cos(2 * np.pi * hour / 24)
        
        features = np.array([[
            forecast_temp, forecast_rhum, forecast_wspd, forecast_pres,
            hour, month, day_of_week, is_day, is_weekend,
            lead_hours, lead_category, hour_sin, hour_cos
        ]])
        
        result = {}
        
        if 'temp' in self.models:
            result['temp_corrected'] = float(self.models['temp'].predict(features)[0])
        
        if 'rhum' in self.models:
            result['rhum_corrected'] = float(self.models['rhum'].predict(features)[0])
        
        if 'wspd' in self.models:
            result['wspd_corrected'] = float(self.models['wspd'].predict(features)[0])
        
        if 'precip_clf' in self.models and 'precip_reg' in self.models:
            has_precip = self.models['precip_clf'].predict(features)[0]
            if has_precip:
                precip_amount = self.models['precip_reg'].predict(features)[0]
                result['precip_corrected'] = max(0, float(precip_amount))
            else:
                result['precip_corrected'] = 0.0
        
        return result


_corrector_instance = None

def get_corrector() -> MLCorrector:
    """获取全局校正器实例"""
    global _corrector_instance
    if _corrector_instance is None:
        _corrector_instance = MLCorrector()
    return _corrector_instance


def apply_ml_correction(data: List[Dict], issue_time: Optional[datetime] = None) -> List[Dict]:
    """
    应用机器学习误差校正（便捷函数）
    
    Args:
        data: 预报数据列表
        issue_time: 起报时间
    
    Returns:
        校正后的数据列表
    """
    corrector = get_corrector()
    return corrector.correct(data, issue_time)
