# test_data_clean.py
import sys
import os
sys.path.append(os.path.dirname(__file__))

from weather_service import WeatherService

# 测试数据清洗
test_data = [
    {"humidity": "75", "temp_max": "22", "temp_min": "15", "precipitation": "0.5"},
    {"humidity": "invalid", "temp_max": "19", "temp_min": "12", "precipitation": "3.2"},
    {"humidity": "", "temp_max": "21", "temp_min": "13", "precipitation": "0"}
]

import pandas as pd
df = pd.DataFrame(test_data)

service = WeatherService("test_key")
df_clean = service.clean_weather_data(df)

print("原始数据:")
print(df)
print("\n清洗后数据:")
print(df_clean)
print("\n数据类型:")
print(df_clean.dtypes)