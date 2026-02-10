import requests
import pandas as pd
import time
from datetime import datetime, timedelta


class WeatherService:
    def __init__(self, api_key):
        self.api_key = api_key
        self.base_url = "https://api.seniverse.com/v3"
        self.cache = {}
        self.cache_timeout = 300  # 5分钟缓存

    def get_daily_forecast(self, location="hangzhou"):  # 使用城市拼音
        """获取3天天气预报 - 心知天气版本"""
        cache_key = f"forecast_{location}"

        # 检查缓存
        if cache_key in self.cache:
            cached_data, timestamp = self.cache[cache_key]
            if time.time() - timestamp < self.cache_timeout:
                print("使用缓存数据")
                return cached_data

        url = f"{self.base_url}/weather/daily.json"
        params = {
            "key": self.api_key,
            "location": location,
            "language": "zh-Hans",
            "unit": "c",
            "start": 0,
            "days": 3  # 获取3天预报
        }

        print(f"正在请求心知天气API...")

        try:
            response = requests.get(url, params=params, timeout=10)
            data = response.json()

            if "results" in data:
                daily_data = data["results"][0]["daily"]

                # 转换为DataFrame
                weather_list = []
                for day in daily_data:
                    # 心知天气的日期格式是 "2024-12-27"
                    date_str = day["date"]
                    # 转换为更友好的格式，如 "12月27日 周五"
                    try:
                        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
                        friendly_date = date_obj.strftime("%m月%d日 %a").replace("Mon", "周一").replace("Tue",
                                                                                                        "周二").replace(
                            "Wed", "周三").replace("Thu", "周四").replace("Fri", "周五").replace("Sat", "周六").replace(
                            "Sun", "周日")
                    except:
                        friendly_date = date_str

                    weather_list.append({
                        "date": friendly_date,  # 友好日期格式
                        "temp_max": int(day["high"]),
                        "temp_min": int(day["low"]),
                        "precipitation": float(day["precip"]),  # 降水量
                        "weather": day["text_day"],  # 白天天气
                        "wind_dir": day["wind_direction"],  # 风向
                        "wind_scale": day["wind_scale"],  # 风力等级
                        # 修复：确保湿度是数字类型
                        "humidity": int(float(day["humidity"])) if day["humidity"] and day["humidity"] != "" else 50,
                        "raw_date": date_str  # 保留原始日期用于排序
                    })

                df = pd.DataFrame(weather_list)
                # 按日期排序
                df = df.sort_values("raw_date")
                df = df.drop(columns=["raw_date"])

                # 新增：数据清洗
                df = self.clean_weather_data(df)

                # 更新缓存
                self.cache[cache_key] = (df, time.time())
                print("心知天气API请求成功！")
                return df
            else:
                print(f"API响应异常: {data}")
                return self.get_fallback_data()

        except Exception as e:
            print(f"网络请求失败: {e}")
            return self.get_fallback_data()

    def get_fallback_data(self):
        """备用数据：当API失败时返回模拟数据"""
        print("API请求失败，使用备用数据...")
        # 创建一些看起来像真实数据的模拟数据
        today = datetime.now()
        dates = [(today + timedelta(days=i)).strftime("%m月%d日") for i in range(3)]

        import random
        mock_data = []
        for i, date in enumerate(dates):
            base_temp = 15 + i * 2
            mock_data.append({
                "date": f"{date} 周{'一二三'[i]}",
                "temp_max": base_temp + random.randint(2, 5),
                "temp_min": base_temp - random.randint(2, 5),
                "precipitation": random.choice([0, 0, 0.5, 1.2, 3.5]),
                "weather": random.choice(["晴", "多云", "阴", "小雨", "多云转晴"]),
                "wind_dir": random.choice(["东北", "东南", "西北", "南"]),
                "wind_scale": random.choice(["1-2", "2-3", "3-4"]),
                "humidity": random.randint(50, 85)
            })

        return pd.DataFrame(mock_data)

    def clean_weather_data(self, df):
        """清洗天气数据，确保数值类型正确（修复inplace警告）"""
        # 创建副本
        df_clean = df.copy()

        # 确保数值列是数字类型
        numeric_columns = ['temp_max', 'temp_min', 'precipitation', 'humidity']

        for col in numeric_columns:
            if col in df_clean.columns:
                # 转换为数字
                df_clean[col] = pd.to_numeric(df_clean[col].astype(str).str.replace('°C', ''),
                                              errors='coerce')

                # 修复：不使用inplace，直接赋值
                if col == 'humidity':
                    df_clean[col] = df_clean[col].fillna(50)  # 默认湿度50%
                elif col in ['temp_max', 'temp_min']:
                    df_clean[col] = df_clean[col].fillna(20)  # 默认温度20度
                elif col == 'precipitation':
                    df_clean[col] = df_clean[col].fillna(0)  # 默认降水0mm

        # 确保数值在合理范围内
        if 'humidity' in df_clean.columns:
            df_clean['humidity'] = df_clean['humidity'].clip(0, 100)

        if 'temp_max' in df_clean.columns:
            df_clean['temp_max'] = df_clean['temp_max'].clip(-50, 50)

        if 'temp_min' in df_clean.columns:
            df_clean['temp_min'] = df_clean['temp_min'].clip(-50, 50)

        return df_clean