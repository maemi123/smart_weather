#!/usr/bin/env python3
"""
检查图表生成
"""

import os
import sys

print("检查图表目录...")

# 检查static目录结构
static_dirs = ['static', 'static/charts']
for dir_path in static_dirs:
    if not os.path.exists(dir_path):
        print(f"创建目录: {dir_path}")
        os.makedirs(dir_path)

# 检查是否有图表文件
chart_files = ['temperature_forecast.png', 'precipitation_forecast.png']
for chart in chart_files:
    chart_path = f'static/charts/{chart}'
    if os.path.exists(chart_path):
        size = os.path.getsize(chart_path)
        print(f"✅ {chart}: 存在 ({size:,} bytes)")
    else:
        print(f"❌ {chart}: 不存在")

# 运行一个简单的测试生成图表
print("\n测试生成图表...")
try:
    from forecast_visualizer import ForecastVisualizer

    visualizer = ForecastVisualizer()
    df = visualizer.create_simulated_forecast()

    temp_chart = visualizer.create_temperature_forecast_chart(df)
    precip_chart = visualizer.create_precipitation_probability_chart(df)

    print(f"温度图表: {temp_chart}")
    print(f"降水图表: {precip_chart}")

except Exception as e:
    print(f"测试失败: {e}")