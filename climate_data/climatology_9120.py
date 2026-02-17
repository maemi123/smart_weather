"""
杭州萧山站 1991-2020 气候态模拟数据
基于 81-10 数据，叠加气候变暖趋势模拟
"""

HANGZHOU_9120_CLIMATOLOGY = {
    "station_name": "杭州萧山",
    "period": "1991-2020",
    "latitude": 30.23,
    "longitude": 120.17,
    "elevation": 41.7,

    # 月度降水量 (mm) - 模拟：总体略微增加
    "monthly_precipitation": {
        1: 85.0,  2: 95.0,  3: 145.0, 4: 125.0,
        5: 135.0, 6: 220.0, 7: 160.0, 8: 165.0,
        9: 130.0, 10: 70.0, 11: 75.0, 12: 55.0
    },

    # 月平均最高气温 (°C) - 模拟：普遍升高0.5-1.0度
    "monthly_tmax": {
        1: 9.2,  2: 11.5, 3: 16.0, 4: 22.0,
        5: 27.0, 6: 29.8, 7: 34.5, 8: 33.8,
        9: 29.0, 10: 24.0, 11: 18.2, 12: 12.0
    },

    # 月平均最低气温 (°C) - 模拟：冬季升温更明显
    "monthly_tmin": {
        1: 2.5,  2: 4.5,  3: 8.0,  4: 13.5,
        5: 18.5, 6: 22.5, 7: 26.5, 8: 26.0,
        9: 21.8, 10: 16.0, 11: 10.0, 12: 4.5
    },
    
    # 模拟月平均气温 (Tmean ≈ (Tmax + Tmin)/2)
    "monthly_avg_temp": {
        1: 5.6,  2: 7.6,  3: 11.5, 4: 17.2,
        5: 22.2, 6: 25.6, 7: 30.0, 8: 29.4,
        9: 24.9, 10: 19.5, 11: 13.6, 12: 7.8
    },

    # 年度统计
    "annual_stats": {
        "avg_precipitation": 1460.0,  # 略增
        "avg_temperature": 18.0,      # 升高0.8度
        "avg_tmax": 22.8,
        "avg_tmin": 14.5,
        "rainy_days": 158,
        "snow_days": 6.5,            # 减少
        "frost_days": 28,            # 减少
        "hot_days": 45,              # 显著增加
        "sunshine_hours": 1750,
        "avg_wind_speed": 2.2,
        "dominant_wind_direction": "E",
    }
}


def get_monthly_climate(month):
    """获取指定月份的气候态数据"""
    return {
        "precipitation": HANGZHOU_9120_CLIMATOLOGY["monthly_precipitation"][month],
        "tmax": HANGZHOU_9120_CLIMATOLOGY["monthly_tmax"][month],
        "tmin": HANGZHOU_9120_CLIMATOLOGY["monthly_tmin"][month],
        "avg_temp": HANGZHOU_9120_CLIMATOLOGY["monthly_avg_temp"][month]
    }


def get_annual_climate():
    """获取年度气候态数据"""
    return HANGZHOU_9120_CLIMATOLOGY["annual_stats"]
