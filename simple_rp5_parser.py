"""
简化版RP5解析器 - 一次性解决问题
"""
import pandas as pd
import numpy as np
from datetime import datetime
import re
import os


def parse_rp5_simple(filepath):
    """最简单的RP5解析器"""
    print(f"正在解析: {filepath}")

    # 1. 读取数据
    df = pd.read_csv(filepath, sep=';', encoding='utf-8', quotechar='"')
    print(f"原始数据: {df.shape}")

    # 2. 重命名第一列
    first_col = df.columns[0]
    df = df.rename(columns={first_col: 'datetime_str'})

    # 3. 解析日期时间
    print("解析日期时间...")
    df['datetime'] = pd.to_datetime(df['datetime_str'], format='%d.%m.%Y %H:%M', errors='coerce')

    # 移除无效日期
    valid_mask = df['datetime'].notna()
    df = df[valid_mask].copy()
    print(f"有效记录: {len(df)}")

    # 4. 提取关键字段
    result = pd.DataFrame()
    result['datetime'] = df['datetime']

    # 温度
    for col, new_name in [('T', 'temperature'), ('Tx', 'temp_max'), ('Tn', 'temp_min')]:
        if col in df.columns:
            result[new_name] = pd.to_numeric(df[col], errors='coerce')

    # 降水
    if 'RRR' in df.columns:
        result['precipitation'] = pd.to_numeric(df['RRR'], errors='coerce').fillna(0)

    # 积雪 - 重点关注！
    if 'sss' in df.columns:
        result['snow_depth'] = pd.to_numeric(df['sss'], errors='coerce').fillna(0)

    # 其他
    for col, new_name in [('U', 'humidity'), ('Ff', 'wind_speed'), ('VV', 'visibility'), ('Td', 'dew_point')]:
        if col in df.columns:
            result[new_name] = pd.to_numeric(df[col], errors='coerce')

    # 风向
    if 'DD' in df.columns:
        result['wind_direction'] = df['DD'].apply(lambda x: parse_wind_simple(str(x)))

    # 添加日期信息
    result['date'] = result['datetime'].dt.date
    result['year'] = result['datetime'].dt.year
    result['month'] = result['datetime'].dt.month
    result['hour'] = result['datetime'].dt.hour

    # 标记
    result['has_snow'] = result['snow_depth'] > 0
    result['is_rainy'] = result['precipitation'] > 0.1

    print(f"✅ 解析完成: {len(result)} 条记录")
    print(f"时间范围: {result['datetime'].min()} 到 {result['datetime'].max()}")

    # 积雪统计
    snow_days = result[result['has_snow']]
    if len(snow_days) > 0:
        print(f"积雪统计: {len(snow_days)} 条记录有积雪")
        print(f"最大积雪深度: {snow_days['snow_depth'].max()} cm")

    return result


def parse_wind_simple(wind_str):
    """简化风向解析"""
    wind_str = str(wind_str).strip('"')

    if '北' in wind_str and '东' in wind_str:
        return 'NE'
    elif '北' in wind_str and '西' in wind_str:
        return 'NW'
    elif '南' in wind_str and '东' in wind_str:
        return 'SE'
    elif '南' in wind_str and '西' in wind_str:
        return 'SW'
    elif '北' in wind_str:
        return 'N'
    elif '东' in wind_str:
        return 'E'
    elif '南' in wind_str:
        return 'S'
    elif '西' in wind_str:
        return 'W'
    else:
        return np.nan


def generate_daily_stats(hourly_data):
    """从小时数据生成日统计"""
    print("生成日统计数据...")

    # 按日期分组
    daily = hourly_data.groupby('date').agg({
        'temperature': ['mean', 'max', 'min'],
        'precipitation': 'sum',
        'snow_depth': 'max',
        'humidity': 'mean',
        'wind_speed': 'mean',
    }).reset_index()

    # 重命名列
    daily.columns = ['date', 'temp_avg', 'temp_max', 'temp_min',
                     'precip_total', 'snow_depth_max', 'humidity_avg', 'wind_speed_avg']

    # 添加年月日
    daily['date'] = pd.to_datetime(daily['date'])
    daily['year'] = daily['date'].dt.year
    daily['month'] = daily['date'].dt.month
    daily['day'] = daily['date'].dt.day

    print(f"生成 {len(daily)} 天数据")
    return daily


# 使用示例
if __name__ == "__main__":
    hourly_data = parse_rp5_simple("data/hangzhou_weather.csv")

    if len(hourly_data) > 0:
        print(f"\n前3行数据:")
        print(hourly_data[['datetime', 'temperature', 'precipitation', 'snow_depth']].head(3))

        # 生成日统计
        daily_data = generate_daily_stats(hourly_data)

        print(f"\n前3天统计:")
        print(daily_data[['date', 'temp_avg', 'temp_max', 'temp_min',
                          'precip_total', 'snow_depth_max']].head(3))

        # 保存
        hourly_data.to_csv("data/hangzhou_hourly_simple.csv", index=False)
        daily_data.to_csv("data/hangzhou_daily_simple.csv", index=False)
        print("\n✅ 数据已保存")