#!/usr/bin/env python
# -*- coding: utf-8 -*-
# 测试图表生成，独立于Flask

import sys
import os

sys.path.append(os.path.dirname(__file__))

from chart_generator import ChartGenerator
import pandas as pd

# 创建测试数据
test_data = {
    'date': ['12月26日 周四', '12月27日 周五', '12月28日 周六'],
    'temp_max': [22, 19, 21],
    'temp_min': [15, 12, 13],
    'precipitation': [0.5, 3.2, 0],
    'weather': ['多云', '小雨', '阴转多云'],
    'wind_dir': ['东南', '东北', '西北'],
    'wind_scale': ['2-3', '3-4', '2-3'],
    'humidity': [75, 85, 68]
}

df = pd.DataFrame(test_data)

print("开始测试图表生成...")
try:
    chart_gen = ChartGenerator()

    # 测试温度图
    temp_path = chart_gen.create_temperature_chart(df)
    print(f"✓ 温度图生成成功: {temp_path}")

    # 测试降水量图
    precip_path = chart_gen.create_precipitation_chart(df)
    print(f"✓ 降水量图生成成功: {precip_path}")

    # 测试雷达图
    radar_path = chart_gen.create_weather_radar_chart(df)
    if radar_path:
        print(f"✓ 雷达图生成成功: {radar_path}")

    print("\n✅ 所有图表测试通过！")

except Exception as e:
    print(f"❌ 测试失败: {e}")
    import traceback

    traceback.print_exc()