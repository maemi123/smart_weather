"""
杭州萧山站 1981-2010 气候态数据
数据来源：国家气象信息中心
"""

HANGZHOU_8110_CLIMATOLOGY = {
    "station_name": "杭州萧山",
    "period": "1981-2010",
    "latitude": 30.23,
    "longitude": 120.17,
    "elevation": 41.7,  # 米

    # 月度降水量 (mm)
    "monthly_precipitation": {
        1: 81.8,  # 一月
        2: 89.0,  # 二月
        3: 142.8,  # 三月
        4: 120.5,  # 四月
        5: 130.5,  # 五月
        6: 210.9,  # 六月
        7: 165.7,  # 七月
        8: 157.3,  # 八月
        9: 138.3,  # 九月
        10: 76.5,  # 十月
        11: 74.8,  # 十一月
        12: 52.7  # 十二月
    },

    # 月平均最高气温 (°C)
    "monthly_tmax": {
        1: 8.4, 2: 10.5, 3: 14.9, 4: 21.1,
        5: 26.3, 6: 29.1, 7: 33.6, 8: 32.8,
        9: 28.2, 10: 23.3, 11: 17.5, 12: 11.4
    },

    # 月平均最低气温 (°C)
    "monthly_tmin": {
        1: 1.5, 2: 3.2, 3: 6.7, 4: 12.1,
        5: 17.4, 6: 21.4, 7: 25.3, 8: 24.7,
        9: 20.6, 10: 14.8, 11: 8.7, 12: 3.2
    },
    
    # 模拟月平均气温 (Tmean ≈ (Tmax + Tmin)/2)
    "monthly_avg_temp": {
        1: 4.6, 2: 6.4, 3: 10.3, 4: 16.0,
        5: 21.1, 6: 24.6, 7: 28.8, 8: 28.1,
        9: 23.8, 10: 18.5, 11: 12.5, 12: 6.8
    },

    # 年度统计
    "annual_stats": {
        "avg_precipitation": 1440.8,  # 年总降水量 mm
        "avg_temperature": 17.2,  # 年平均气温 (°C)
        "avg_tmax": 21.8,  # 年平均最高温
        "avg_tmin": 13.1,  # 年平均最低温
        "rainy_days": 155,  # 年降水日数 (日降水≥0.1mm)
        "snow_days": 7.4,  # 年积雪日数
        "frost_days": 35,  # 年霜冻日数
        "hot_days": 38,  # 年高温日数 (Tmax≥35°C)
        "sunshine_hours": 1765,  # 年日照时数
        "avg_wind_speed": 2.1,  # 年平均风速 (m/s)
        "dominant_wind_direction": "E",  # 主导风向
    },

    # 极端气候值
    "extremes": {
        "max_temp_record": 41.6,  # 极端最高气温 (°C)
        "min_temp_record": -8.6,  # 极端最低气温
        "max_daily_precip": 246.4,  # 最大日降水量 (mm)
        "max_snow_depth": 31,  # 最大积雪深度 (cm)
        "max_wind_speed": 33.0,  # 最大风速 (m/s)
    }
}


def get_monthly_climate(month):
    """获取指定月份的气候态数据"""
    return {
        "precipitation": HANGZHOU_8110_CLIMATOLOGY["monthly_precipitation"][month],
        "tmax": HANGZHOU_8110_CLIMATOLOGY["monthly_tmax"][month],
        "tmin": HANGZHOU_8110_CLIMATOLOGY["monthly_tmin"][month]
    }


def get_annual_climate():
    """获取年度气候态数据"""
    return HANGZHOU_8110_CLIMATOLOGY["annual_stats"]


if __name__ == "__main__":
    # 测试输出
    print("杭州萧山站 1981-2010 气候态数据")
    print(f"年平均温度: {get_annual_climate()['avg_temperature']}°C")
    print(f"年总降水量: {get_annual_climate()['avg_precipitation']}mm")