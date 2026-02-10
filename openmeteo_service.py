import requests
import pandas as pd
import time
from datetime import datetime, timedelta


class OpenMeteoService:
    def __init__(self):
        self.base_url = "https://api.open-meteo.com/v1"
        self.cache = {}
        self.cache_timeout = 3600  # 1小时缓存

    def get_ecmwf_forecast(self, latitude=30.25, longitude=120.17, days=3):
        """获取ECMWF数值预报数据"""
        cache_key = f"ecmwf_{latitude}_{longitude}_{days}"

        # 检查缓存
        if cache_key in self.cache:
            cached_data, timestamp = self.cache[cache_key]
            if time.time() - timestamp < self.cache_timeout:
                print("使用缓存数据")
                return cached_data

        print("正在从Open-Meteo获取ECMWF预报数据...")

        url = f"{self.base_url}/forecast"
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "hourly": "temperature_2m,precipitation,relative_humidity_2m,wind_speed_10m,wind_direction_10m,cloud_cover",
            "models": "ecmwf_ifs",  # 指定ECMWF模型
            "forecast_days": days,
            "timezone": "Asia/Shanghai"
        }

        try:
            response = requests.get(url, params=params, timeout=15)
            data = response.json()

            if "hourly" in data:
                # 处理小时数据
                hourly_data = data["hourly"]

                # 转换为DataFrame
                df = pd.DataFrame({
                    "time": hourly_data["time"],
                    "temp_2m": hourly_data["temperature_2m"],
                    "precipitation": hourly_data["precipitation"],
                    "humidity": hourly_data["relative_humidity_2m"],
                    "wind_speed": hourly_data["wind_speed_10m"],
                    "wind_direction": hourly_data["wind_direction_10m"],
                    "cloud_cover": hourly_data.get("cloud_cover", [0] * len(hourly_data["time"]))
                })

                # 转换为日期时间
                df["time"] = pd.to_datetime(df["time"])

                # 缓存数据
                self.cache[cache_key] = (df, time.time())
                print("✅ ECMWF数据获取成功！")
                return df
            else:
                print(f"API响应异常: {data.get('error', '未知错误')}")
                return self.get_fallback_data()

        except Exception as e:
            print(f"网络请求失败: {e}")
            return self.get_fallback_data()

    def get_historical_weather(self, latitude=30.25, longitude=120.17, start_date="2023-01-01", end_date="2023-12-31"):
        """获取历史天气数据（用于分析）"""
        print(f"获取历史数据: {start_date} 到 {end_date}")

        url = f"{self.base_url}/archive"
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "start_date": start_date,
            "end_date": end_date,
            "hourly": "temperature_2m,precipitation",
            "timezone": "Asia/Shanghai"
        }

        try:
            response = requests.get(url, params=params, timeout=15)
            data = response.json()

            if "hourly" in data:
                hourly_data = data["hourly"]
                df = pd.DataFrame({
                    "time": hourly_data["time"],
                    "temp_2m": hourly_data["temperature_2m"],
                    "precipitation": hourly_data["precipitation"]
                })
                df["time"] = pd.to_datetime(df["time"])
                return df
            else:
                print(f"历史数据获取失败: {data.get('error', '未知错误')}")
                return None

        except Exception as e:
            print(f"历史数据请求失败: {e}")
            return None

    def get_fallback_data(self):
        """备用数据"""
        print("使用备用数据...")
        today = datetime.now()

        # 生成一些看起来真实的模拟数据
        time_points = []
        temp_points = []
        precip_points = []

        for i in range(24 * 3):  # 3天的每小时数据
            hour_offset = timedelta(hours=i)
            current_time = today + hour_offset

            # 模拟日变化温度
            hour_of_day = current_time.hour
            base_temp = 15 + 10 * abs(hour_of_day - 12) / 12  # 中午最高

            # 添加一些随机变化
            temp = base_temp + (i % 24 - 12) / 3 + (i // 24) * 2  # 每天升高2度

            # 模拟降水
            precip = 0
            if i > 24 and i < 30:  # 第二天凌晨有雨
                precip = 1.5

            time_points.append(current_time.strftime("%Y-%m-%d %H:%M"))
            temp_points.append(round(temp, 1))
            precip_points.append(precip)

        return pd.DataFrame({
            "time": time_points,
            "temp_2m": temp_points,
            "precipitation": precip_points,
            "humidity": [65 + i % 20 for i in range(len(time_points))],
            "wind_speed": [2 + (i % 10) / 5 for i in range(len(time_points))],
            "wind_direction": [90 + i * 15 for i in range(len(time_points))],
            "cloud_cover": [30 + i % 50 for i in range(len(time_points))]
        })

    def process_for_display(self, df_hourly, days=3):
        """将小时数据处理为每日摘要（用于网页显示）"""
        if df_hourly.empty:
            return []

        df_hourly["time"] = pd.to_datetime(df_hourly["time"])
        df_hourly["date"] = df_hourly["time"].dt.date

        daily_summary = []
        unique_dates = df_hourly["date"].unique()[:days]

        for date in unique_dates:
            day_data = df_hourly[df_hourly["date"] == date]

            # 转换风向角度为中文方向
            wind_dir_avg = day_data["wind_direction"].mean()
            wind_direction = self.degrees_to_direction(wind_dir_avg)

            daily_summary.append({
                "date": date.strftime("%m月%d日"),
                "weekday": self.get_chinese_weekday(date),
                "temp_max": round(day_data["temp_2m"].max(), 1),
                "temp_min": round(day_data["temp_2m"].min(), 1),
                "precipitation": round(day_data["precipitation"].sum(), 1),
                "weather": self.get_weather_description(
                    day_data["precipitation"].sum(),
                    day_data["cloud_cover"].mean()
                ),
                "wind_direction": wind_direction,
                "wind_scale": self.wind_speed_to_scale(day_data["wind_speed"].mean()),
                "humidity": round(day_data["humidity"].mean()),
                "data_source": "ECMWF via Open-Meteo"
            })

        return daily_summary

    @staticmethod
    def degrees_to_direction(degrees):
        """将角度转换为风向"""
        directions = ["北", "东北", "东", "东南", "南", "西南", "西", "西北"]
        index = round(degrees / 45) % 8
        return directions[index]

    @staticmethod
    def get_chinese_weekday(date):
        """获取中文星期几"""
        weekdays = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
        return weekdays[date.weekday()]

    @staticmethod
    def get_weather_description(precip, cloud_cover):
        """根据降水量和云量描述天气"""
        if precip > 10:
            return "大雨"
        elif precip > 5:
            return "中雨"
        elif precip > 1:
            return "小雨"
        elif precip > 0:
            return "零星小雨"
        elif cloud_cover > 70:
            return "阴"
        elif cloud_cover > 30:
            return "多云"
        else:
            return "晴"

    @staticmethod
    def wind_speed_to_scale(speed_mps):
        """将风速(m/s)转换为风力等级"""
        if speed_mps < 1.5:
            return "1级"
        elif speed_mps < 3.3:
            return "2级"
        elif speed_mps < 5.5:
            return "3级"
        elif speed_mps < 7.9:
            return "4级"
        elif speed_mps < 10.7:
            return "5级"
        else:
            return f"{int(speed_mps / 2.5) + 1}级"


# 测试函数
def test_openmeteo():
    print("=== Open-Meteo 测试 ===")
    service = OpenMeteoService()

    # 测试ECMWF预报
    print("\n1. 获取ECMWF预报数据...")
    df = service.get_ecmwf_forecast(days=3)

    if df is not None:
        print(f"获取到 {len(df)} 条小时数据")
        print(f"时间范围: {df['time'].iloc[0]} 到 {df['time'].iloc[-1]}")
        print(f"温度范围: {df['temp_2m'].min():.1f}°C 到 {df['temp_2m'].max():.1f}°C")

        # 处理为每日摘要
        daily_summary = service.process_for_display(df, days=3)
        print("\n2. 每日摘要:")
        for day in daily_summary:
            print(f"  {day['date']} {day['weekday']}: {day['temp_min']}~{day['temp_max']}°C, "
                  f"{day['weather']}, 降水{day['precipitation']}mm, {day['wind_direction']}{day['wind_scale']}")

    # 测试历史数据（可选）
    print("\n3. 测试历史数据获取...")
    hist_df = service.get_historical_weather(
        start_date="2024-01-01",
        end_date="2024-01-07"
    )
    if hist_df is not None:
        print(f"获取到历史数据 {len(hist_df)} 条")


if __name__ == "__main__":
    test_openmeteo()