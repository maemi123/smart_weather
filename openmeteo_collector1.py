import requests
import pandas as pd
import json
from datetime import datetime, timedelta
import time
import os
from typing import Dict, List, Optional

import requests
import pandas as pd
import json
from datetime import datetime
import time
import os
from typing import Dict, Optional


class OpenMeteoCollector1:
    """专业气象数据采集器 - 修正时间处理版本"""

    # 萧山国际机场精确坐标
    HANGZHOU_LAT = 30.2295
    HANGZHOU_LON = 120.4343

    def __init__(self, save_dir: str = "data/openmeteo/vertical"):
        self.save_dir = save_dir
        os.makedirs(save_dir, exist_ok=True)
        self.base_url = "https://api.open-meteo.com/v1/forecast"

        # 核心气象参数（确保都能获取）
        self.required_params = [
            "temperature_2m",  # 温度 (°C)
            "relative_humidity_2m",  # 湿度 (%)
            "dew_point_2m",  # 露点温度 (°C)
            "apparent_temperature",  # 体感温度 (°C)
            "precipitation",  # 降水 (mm)
            "rain",  # 降雨 (mm)
            "snowfall",  # 降雪 (cm)
            "weather_code",  # 天气代码
            "pressure_msl",  # 海平面气压 (hPa)
            "surface_pressure",  # 地面气压 (hPa)
            "cloud_cover",  # 云量 (%)
            "wind_speed_10m",  # 风速 (km/h)
            "wind_direction_10m",  # 风向 (°)
            "wind_gusts_10m",  # 阵风 (km/h)
            "visibility",  # 能见度 (m)
            "is_day",  # 是否白天 (1/0)

            # ===== 新增：关键垂直层参数 =====
            # 温度垂直剖面（不同高度）
            "temperature_850hPa",  # 850hPa温度 (~1500米) - 关键层！
            "temperature_700hPa",  # 700hPa温度 (~3000米)
            "temperature_500hPa",  # 500hPa温度 (~5500米) - 中层

            # 湿度垂直剖面
            "relative_humidity_850hPa",  # 850hPa相对湿度
            "relative_humidity_700hPa",  # 700hPa相对湿度
            "relative_humidity_500hPa",  # 500hPa相对湿度

            # 风场垂直剖面
            "wind_speed_850hPa",  # 850hPa风速
            "wind_direction_850hPa",  # 850hPa风向
            "wind_speed_700hPa",
            "wind_direction_700hPa",
            "wind_speed_500hPa",
            "wind_direction_500hPa",

            # 位势高度（反映气压系统）
            "geopotential_height_850hPa",  # 850hPa位势高度
            "geopotential_height_500hPa",  # 500hPa位势高度

            # 大气稳定度指数（直接反映热力条件）
            "cape",  # 对流有效位能 - 关键！
            "cin",  # 对流抑制能量
            "lifted_index",  # 抬升指数
            "k_index",  # K指数

            # 垂直速度（反映上升运动）
            "vertical_velocity_700hPa",  # 700hPa垂直速度
        ]

    def fetch_forecast_data(self, forecast_days: int = 7) -> Optional[Dict]:
        """获取预报数据"""
        try:
            params = {
                "latitude": self.HANGZHOU_LAT,
                "longitude": self.HANGZHOU_LON,
                "hourly": ",".join(self.required_params),
                "forecast_days": forecast_days,
                "timezone": "Asia/Shanghai",  # 指定时区
                "models": "best_match",
            }

            print(f"📍 目标: 萧山国际机场 (杭州)")
            print(f"📅 预报天数: {forecast_days}天")
            print(f"🕐 时区: Asia/Shanghai")

            response = requests.get(self.base_url, params=params, timeout=30)

            if response.status_code != 200:
                print(f"❌ 请求失败: {response.status_code}")
                return None

            data = response.json()

            if "hourly" not in data:
                print("❌ 数据结构异常")
                return None

            times = data['hourly']['time']
            print(f"✅ 数据获取成功")
            print(f"📅 时间范围: {times[0]} 到 {times[-1]}")
            print(f"🔢 数据点数: {len(times)}小时")

            return data

        except Exception as e:
            print(f"❌ 错误: {str(e)}")
            return None

    def process_and_save_data(self, data: Dict) -> Optional[str]:
        """处理并保存数据"""
        try:
            times = data['hourly']['time']

            # ===== 关键修正：时间处理 =====
            # Open-Meteo返回的时间已经是北京时间，格式: "2026-01-11T00:00"
            parsed_times = []
            beijing_hours = []
            dates = []

            for time_str in times:
                # 解析ISO 8601格式的本地时间
                # 格式: "2026-01-11T23:00"
                dt = datetime.fromisoformat(time_str)

                # 验证：小时应该在0-23之间
                if not (0 <= dt.hour <= 23):
                    print(f"⚠️  异常小时数: {dt.hour}")

                parsed_times.append(dt.strftime("%Y-%m-%d %H:%M"))
                beijing_hours.append(dt.hour)
                dates.append(dt.strftime("%Y-%m-%d"))

            # ===== 创建DataFrame =====
            df_dict = {
                'datetime_beijing': parsed_times,  # 北京时间，格式: "2026-01-11 23:00"
                'date': dates,  # 日期，格式: "2026-01-11"
                'hour_beijing': beijing_hours,  # 小时 (0-23)
                'timestamp_original': times,  # 原始时间字符串
            }

            # 添加气象数据
            print(f"\n📊 气象参数:")
            for param in self.required_params:
                if param in data['hourly']:
                    df_dict[param] = data['hourly'][param]
                    values = data['hourly'][param]
                    # 显示统计信息
                    if values and isinstance(values[0], (int, float)):
                        valid_vals = [v for v in values if v is not None]
                        if valid_vals:
                            print(f"  ✓ {param}: [{min(valid_vals):.1f}, {max(valid_vals):.1f}]")
                else:
                    print(f"  ✗ {param}: 未返回")
                    df_dict[param] = [None] * len(times)

            df = pd.DataFrame(df_dict)

            # ===== 数据质量验证 =====
            print(f"\n🔍 数据质量验证:")

            # 1. 检查时间连续性
            time_diffs = []
            for i in range(1, min(10, len(parsed_times))):
                t1 = datetime.strptime(parsed_times[i - 1], "%Y-%m-%d %H:%M")
                t2 = datetime.strptime(parsed_times[i], "%Y-%m-%d %H:%M")
                diff = (t2 - t1).total_seconds() / 3600  # 小时差
                time_diffs.append(diff)

            if all(diff == 1 for diff in time_diffs):
                print(f"  ✅ 时间连续性正常 (每小时一个数据点)")
            else:
                print(f"  ⚠️  时间连续性异常: {time_diffs}")

            # 2. 温度日变化分析
            if 'temperature_2m' in df.columns:
                # 按小时分析温度
                hourly_stats = df.groupby('hour_beijing')['temperature_2m'].agg(['mean', 'min', 'max'])

                print(f"\n🌡️  温度日变化分析:")
                print(f"{'小时':>3} | {'平均':>6} | {'最低':>6} | {'最高':>6}")
                print("-" * 40)

                max_temp = -100
                max_temp_hour = -1
                min_temp = 100
                min_temp_hour = -1

                for hour in sorted(hourly_stats.index):
                    stats = hourly_stats.loc[hour]
                    mean_temp = stats['mean']
                    min_temp_val = stats['min']
                    max_temp_val = stats['max']

                    print(f"{hour:2d}时 | {mean_temp:6.1f}°C | {min_temp_val:6.1f}°C | {max_temp_val:6.1f}°C")

                    # 找出最高温和最低温
                    if max_temp_val > max_temp:
                        max_temp = max_temp_val
                        max_temp_hour = hour
                    if min_temp_val < min_temp:
                        min_temp = min_temp_val
                        min_temp_hour = hour

                print(f"\n📈 温度极值:")
                print(f"  最高温: {max_temp:.1f}°C (出现在 {max_temp_hour}时)")
                print(f"  最低温: {min_temp:.1f}°C (出现在 {min_temp_hour}时)")

                # 判断日变化合理性
                if 10 <= max_temp_hour <= 17:
                    print(f"  ✅ 最高温出现在合理时段 ({max_temp_hour}时)")
                else:
                    print(f"  ⚠️  最高温出现在非常规时段 ({max_temp_hour}时)")

                if 0 <= min_temp_hour <= 6:
                    print(f"  ✅ 最低温出现在合理时段 ({min_temp_hour}时)")
                else:
                    print(f"  ⚠️  最低温出现在非常规时段 ({min_temp_hour}时)")

            # 3. 天气代码映射
            weather_mapping = {
                0: "晴", 1: "基本晴", 2: "局部多云", 3: "多云",
                45: "雾", 48: "冻雾",
                51: "小雨", 53: "中雨", 55: "强降雨",
                61: "小雨", 63: "中雨", 65: "强降雨",
                71: "小雪", 73: "中雪", 75: "强降雪",
                80: "小阵雨", 81: "中阵雨", 82: "强阵雨",
                85: "小阵雪", 86: "强阵雪",
                95: "雷暴", 96: "雷暴伴小冰雹", 99: "雷暴伴强冰雹"
            }

            if 'weather_code' in df.columns:
                df['weather_description'] = df['weather_code'].map(
                    lambda x: weather_mapping.get(x, f"代码{x}")
                )

                # 统计天气状况
                weather_counts = df['weather_description'].value_counts()
                print(f"\n🌤️  天气状况统计:")
                for weather, count in weather_counts.head(5).items():
                    print(f"  {weather}: {count}小时")

            # ===== 保存文件 =====
            forecast_start = dates[0]
            collect_time = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"HGH_forecast_{forecast_start}_{collect_time}.csv"
            filepath = os.path.join(self.save_dir, filename)

            df.to_csv(filepath, index=False, encoding='utf-8-sig')

            print(f"\n" + "=" * 60)
            print(f"💾 数据保存详情")
            print("=" * 60)
            print(f"📁 文件名: {filename}")
            print(f"📂 路径: {filepath}")
            print(f"📏 大小: {os.path.getsize(filepath) / 1024:.1f} KB")
            print(f"📊 维度: {len(df)} 行 × {len(df.columns)} 列")

            # 显示数据预览
            print(f"\n👀 数据预览 (前6行):")
            preview_cols = ['datetime_beijing', 'temperature_2m', 'precipitation',
                            'relative_humidity_2m', 'weather_description']
            preview_cols = [col for col in preview_cols if col in df.columns]

            preview_df = df.head(6)[preview_cols]
            print(preview_df.to_string(index=False))

            return filepath

        except Exception as e:
            print(f"❌ 处理错误: {str(e)}")
            import traceback
            traceback.print_exc()
            return None

    def collect_forecast(self, forecast_days: int = 7) -> bool:
        """完整的采集流程"""
        print("=" * 60)
        print(f"🚀 气象数据采集任务开始")
        print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 60)

        data = self.fetch_forecast_data(forecast_days)
        if not data:
            print("❌ 数据获取失败")
            return False

        filepath = self.process_and_save_data(data)
        if not filepath:
            print("❌ 数据处理失败")
            return False

        print(f"\n✅ 采集任务完成!")
        print(f"📁 文件: {os.path.basename(filepath)}")
        return True

    def validate_vertical_data(self, data):
        """验证垂直数据是否获取成功"""
        print(f"\n🔬 垂直数据验证:")

        vertical_params = [
            ('temperature_850hPa', '850hPa温度'),
            ('relative_humidity_850hPa', '850hPa湿度'),
            ('wind_speed_850hPa', '850hPa风速'),
            ('cape', '对流有效位能'),
            ('geopotential_height_500hPa', '500hPa位势高度'),
        ]

        available = 0
        for param, desc in vertical_params:
            if param in data['hourly']:
                values = data['hourly'][param]
                if values and values[0] is not None:
                    print(f"  ✅ {desc}: [{min(values):.1f}, {max(values):.1f}]")
                    available += 1
                else:
                    print(f"  ⚠️  {desc}: 数据为空")
            else:
                print(f"  ❌ {desc}: 未返回")

        print(f"垂直参数获取率: {available}/{len(vertical_params)}")
        return available > 0


# 主程序
if __name__ == "__main__":
    collector = OpenMeteoCollector1()

    # 获取7天预报数据
    success = collector.collect_forecast(7)

    print("\n" + "=" * 60)
    if success:
        print("🎉 气象数据采集成功完成!")
        print("   数据已保存至 data/openmeteo/ 目录")
        print("   可用于机器学习训练和天气分析")
    else:
        print("❌ 数据采集失败，请检查网络或API状态")
    print("=" * 60)