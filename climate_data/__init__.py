"""
气候态数据模块
提供不同时期的气候态数据
"""

from .climatology_8110 import HANGZHOU_8110_CLIMATOLOGY, get_monthly_climate as get_monthly_8110, get_annual_climate as get_annual_8110
from .climatology_9120 import HANGZHOU_9120_CLIMATOLOGY, get_monthly_climate as get_monthly_9120, get_annual_climate as get_annual_9120

def get_climatology(period="8110"):
    """获取指定时期的气候态数据"""
    if period == "8110":
        return {
            "monthly": get_monthly_8110,
            "annual": get_annual_8110,
            "data": HANGZHOU_8110_CLIMATOLOGY
        }
    elif period == "9120":
        return {
            "monthly": get_monthly_9120,
            "annual": get_annual_9120,
            "data": HANGZHOU_9120_CLIMATOLOGY
        }
    else:
        raise ValueError(f"不支持的气候态时期: {period}")