# -*- coding: utf-8 -*-
"""
预报数据可视化模块 - 修复编码问题
"""

import matplotlib

matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os
import glob


class ForecastVisualizer:
    def __init__(self, data_dir='data/ecmwf'):
        self.data_dir = data_dir

    def load_forecast_data(self, use_real_data=True):
        """加载预报数据 - 修复版"""
        if use_real_data:
            # 查找最新的预报文件
            forecast_files = glob.glob(os.path.join(self.data_dir, 'hangzhou_forecast_*.grib'))

            if forecast_files:
                latest_file = max(forecast_files, key=os.path.getctime)
                print(f"加载真实预报数据: {latest_file}")

                real_data = self.load_real_forecast_data(latest_file)
                if real_data is not None:
                    return real_data

        # 使用模拟数据
        print("使用模拟预报数据")
        return self.create_simulated_forecast()

    def load_real_forecast_data(self, filepath):
        """加载真实的预报数据 - 简化版"""
        try:
            import xarray as xr

            # 尝试读取温度数据
            try:
                ds_temp = xr.open_dataset(filepath,
                                          engine='cfgrib',
                                          backend_kwargs={'filter_by_keys': {'shortName': '2t'}})
                print("温度数据读取成功")
            except Exception as e:
                print(f"筛选读取失败，尝试普通读取: {e}")
                # 尝试普通读取
                try:
                    ds_all = xr.open_dataset(filepath, engine='cfgrib')
                    if 't2m' in ds_all.data_vars:
                        ds_temp = ds_all[['t2m']]
                    else:
                        return None
                except Exception as e2:
                    print(f"普通读取也失败: {e2}")
                    return None

            # 转换为DataFrame
            df_temp = ds_temp.to_dataframe().reset_index()

            # 创建基础的DataFrame
            df = pd.DataFrame({
                'time': pd.to_datetime(df_temp['time']),
                'temperature': df_temp['t2m'] - 273.15,  # K转℃
                'latitude': df_temp['latitude'],
                'longitude': df_temp['longitude'],
            })

            # 添加模拟的其他变量
            np.random.seed(42)

            # 确保数据长度一致
            n_points = len(df)
            df['precipitation_prob'] = np.random.uniform(0, 70, n_points)
            df['humidity'] = np.random.uniform(50, 90, n_points)
            df['wind_speed'] = np.random.uniform(1, 5, n_points)

            # 风向
            directions = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW']
            df['wind_direction'] = [directions[i % 8] for i in range(n_points)]

            # 添加日期列用于分组
            df['date'] = df['time'].dt.date

            # 添加元数据
            df.attrs = {
                'source': 'ECMWF真实预报数据 + 模拟补充',
                'file': filepath,
                'real_variables': ['temperature'],
                'simulated_variables': ['precipitation_prob', 'humidity', 'wind'],
                'note': '温度数据为真实ECMWF数据，其他变量为模拟',
                'location': '杭州区域',
                'data_points': len(df),
            }

            return df

        except Exception as e:
            print(f"真实数据读取失败: {e}")
            import traceback
            traceback.print_exc()
            return None

    def create_simulated_forecast(self):
        """创建模拟预报数据"""
        # 生成未来3天，每6小时的数据
        base_time = datetime.now()
        times = [base_time + timedelta(hours=i * 6) for i in range(12)]

        np.random.seed(42)

        # 温度：日变化 + 趋势
        base_temp = 15.0
        temps = []
        for i, t in enumerate(times):
            hour = t.hour
            diurnal = 6 * np.sin(2 * np.pi * (hour - 14) / 24)
            trend = 0.2 * i
            error = np.random.normal(0, 1)
            temp = base_temp + diurnal + trend + error
            temps.append(temp)

        # 降水概率
        precip_probs = []
        for t in times:
            hour = t.hour
            if 13 <= hour <= 19:
                prob = 30 + np.random.randint(0, 40)
            else:
                prob = np.random.randint(0, 20)
            precip_probs.append(prob)

        df = pd.DataFrame({
            'time': times,
            'temperature': temps,
            'precipitation_prob': precip_probs,
            'humidity': np.random.uniform(50, 90, 12),
            'wind_speed': np.random.uniform(1, 5, 12),
            'wind_direction': ['NE', 'E', 'SE', 'S', 'SW', 'W', 'NW', 'N'] * 2,
            'date': [t.date() for t in times],
        })

        df.attrs = {
            'source': 'ECMWF模拟预报数据',
            'location': '杭州 (30.25N, 120.17E)',
            'forecast_period': '未来3天',
            'update_time': base_time.strftime('%Y-%m-%d %H:%M'),
        }

        return df

    def create_temperature_forecast_chart(self, df):
        """创建温度预报图"""
        plt.figure(figsize=(12, 6))

        # 确保时间列是datetime
        times = pd.to_datetime(df['time'])
        temps = df['temperature']

        # 主曲线
        plt.plot(times, temps, marker='o', linewidth=3, color='#e74c3c',
                 label='2米温度', markersize=8, markerfacecolor='white', markeredgewidth=2)

        # 填充区域表示预报不确定性
        uncertainty = 1.5
        plt.fill_between(times, temps - uncertainty, temps + uncertainty,
                         alpha=0.2, color='#e74c3c', label='预报不确定性')

        # 标注关键点
        if len(temps) > 0:
            max_idx = temps.idxmax()
            min_idx = temps.idxmin()

            plt.annotate(f'最高: {temps[max_idx]:.1f}C',
                         xy=(times[max_idx], temps[max_idx]),
                         xytext=(0, 15), textcoords='offset points',
                         ha='center', va='bottom', fontsize=11, fontweight='bold',
                         bbox=dict(boxstyle='round,pad=0.3', facecolor='white', alpha=0.8),
                         arrowprops=dict(arrowstyle='->', color='#e74c3c'))

            plt.annotate(f'最低: {temps[min_idx]:.1f}C',
                         xy=(times[min_idx], temps[min_idx]),
                         xytext=(0, -20), textcoords='offset points',
                         ha='center', va='top', fontsize=11, fontweight='bold',
                         bbox=dict(boxstyle='round,pad=0.3', facecolor='white', alpha=0.8),
                         arrowprops=dict(arrowstyle='->', color='#3498db'))

        # 美化
        plt.title('ECMWF 杭州温度预报（未来3天）', fontsize=18, fontweight='bold', pad=25)
        plt.xlabel('时间', fontsize=13)
        plt.ylabel('温度 (C)', fontsize=13)
        plt.grid(True, alpha=0.2, linestyle='--')
        plt.legend(loc='upper left', fontsize=11)

        # x轴格式
        plt.xticks(rotation=45, ha='right')
        plt.gca().xaxis.set_major_formatter(plt.matplotlib.dates.DateFormatter('%m/%d %H:%M'))

        plt.tight_layout()

        # 保存图表
        os.makedirs('static/charts', exist_ok=True)
        chart_path = 'static/charts/temperature_forecast.png'
        plt.savefig(chart_path, dpi=120, bbox_inches='tight')
        plt.close()

        print(f"温度图表已保存: {chart_path}")
        return 'charts/temperature_forecast.png'  # 返回相对路径

    def create_precipitation_probability_chart(self, df):
        """创建降水概率图"""
        plt.figure(figsize=(12, 5))

        times = pd.to_datetime(df['time'])
        probs = df['precipitation_prob']

        # 创建颜色渐变
        colors = []
        for prob in probs:
            if prob < 20:
                colors.append('#3498db')
            elif prob < 50:
                colors.append('#f39c12')
            else:
                colors.append('#e74c3c')

        # 条形图
        bars = plt.bar(times, probs, color=colors,
                       edgecolor='white', linewidth=2, width=0.03, alpha=0.9)

        # 添加概率标签
        for bar, prob in zip(bars, probs):
            height = bar.get_height()
            if prob > 10:
                plt.text(bar.get_x() + bar.get_width() / 2., height + 2,
                         f'{prob:.0f}%', ha='center', va='bottom',
                         fontsize=10, fontweight='bold')

        plt.title('ECMWF 杭州降水概率预报', fontsize=18, fontweight='bold', pad=25)
        plt.xlabel('时间', fontsize=13)
        plt.ylabel('降水概率 (%)', fontsize=13)
        plt.ylim(0, 105)
        plt.grid(True, alpha=0.2, axis='y')

        # x轴格式
        plt.xticks(rotation=45, ha='right')
        plt.gca().xaxis.set_major_formatter(plt.matplotlib.dates.DateFormatter('%m/%d %H:%M'))

        plt.tight_layout()

        chart_path = 'static/charts/precipitation_forecast.png'
        plt.savefig(chart_path, dpi=120, bbox_inches='tight')
        plt.close()

        print(f"降水图表已保存: {chart_path}")
        return 'charts/precipitation_forecast.png'

    def create_weather_summary_card(self, df):
        """创建天气摘要卡片"""
        summary = []

        if 'date' not in df.columns:
            df['date'] = pd.to_datetime(df['time']).dt.date

        # 按日期分组
        day_groups = df.groupby('date')

        for day, day_data in day_groups:
            if len(day_data) == 0:
                continue

            # 计算每日统计
            avg_temp = day_data['temperature'].mean()
            max_temp = day_data['temperature'].max()
            min_temp = day_data['temperature'].min()
            max_precip_prob = day_data['precipitation_prob'].max()
            avg_humidity = day_data['humidity'].mean()
            avg_wind = day_data['wind_speed'].mean()

            # 判断天气类型
            if max_precip_prob > 50:
                weather_type = '雨天'
                weather_color = '#3498db'
                weather_icon = '☔'
            elif max_precip_prob > 20:
                weather_type = '阴转雨'
                weather_color = '#95a5a6'
                weather_icon = '🌦️'
            else:
                if avg_temp > 22:
                    weather_type = '晴天'
                    weather_color = '#f39c12'
                    weather_icon = '☀️'
                elif avg_temp > 15:
                    weather_type = '多云'
                    weather_color = '#bdc3c7'
                    weather_icon = '⛅'
                else:
                    weather_type = '阴天'
                    weather_color = '#7f8c8d'
                    weather_icon = '☁️'

            # 判断舒适度
            comfort = "舒适"
            if avg_temp > 28 or avg_temp < 5:
                comfort = "不舒适"
            elif avg_humidity > 80:
                comfort = "闷热"

            # 星期几
            weekday_names = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
            try:
                weekday = weekday_names[pd.Timestamp(day).weekday()]
            except:
                weekday = ''

            summary.append({
                'date': day.strftime('%m月%d日') if hasattr(day, 'strftime') else str(day),
                'weekday': weekday,
                'weather': f"{weather_type} {weather_icon}",
                'weather_color': weather_color,
                'temp_range': f"{min_temp:.0f}~{max_temp:.0f}°C",
                'avg_temp': f"{avg_temp:.1f}",
                'precip_prob': f"{max_precip_prob:.0f}%",
                'humidity': f"{avg_humidity:.0f}%",
                'wind': f"{avg_wind:.1f} m/s",
                'comfort': comfort,
            })

        return summary