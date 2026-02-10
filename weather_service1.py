import requests
import pandas as pd
from datetime import datetime, timedelta


class WeatherService1:
    def __init__(self, api_key):
        self.api_key = api_key
        self.base_url = "https://api.qweather.com/v7"

    '''def get_daily_forecast(self, location="101210101"):  # 杭州的城市ID,和风
        """获取3天天气预报"""
        url = f"{self.base_url}/weather/3d"
        params = {
            "key": self.api_key,
            "location": location,
            "lang": "zh"
        }

        print(f"正在请求URL: {url}")  # 调试信息
        print(f"参数: {params}")  # 调试信息

        try:
            response = requests.get(url, params=params, timeout=10)
            print(f"响应状态码: {response.status_code}")  # 调试信息
            print(f"响应内容: {response.text[:200]}")  # 调试信息

            data = response.json()

            if data["code"] == "200":
                daily_data = data["daily"]

                # 转换为DataFrame
                weather_list = []
                for day in daily_data:
                    weather_list.append({
                        "date": day["fxDate"],
                        "temp_max": int(day["tempMax"]),
                        "temp_min": int(day["tempMin"]),
                        "precipitation": float(day["precip"]),  # 降水量
                        "weather": day["textDay"],  # 白天天气
                        "wind_dir": day["windDirDay"],  # 风向
                        "wind_scale": day["windScaleDay"],  # 风力等级
                        "humidity": day["humidity"],  # 湿度
                    })

                return pd.DataFrame(weather_list)
            else:
                print(f"API返回异常: {data}")  # 看具体错误信息
                return self.get_fallback_data()

        except Exception as e:
            print(f"网络请求失败: {e}")
            return self.get_fallback_data()'''

    def get_daily_forecast(self, location="101210101"):  # 改回原来的方法名
        """使用高德地图天气API"""
        try:
            # 你的高德Key - 先用这个测试Key
            gaode_key = "f196bdbacff93e06e22fb3aadff299b7"  # 公开测试Key

            url = "https://restapi.amap.com/v3/weather/weatherInfo"
            params = {
                "key": gaode_key,
                "city": "330100",  # 杭州城市编码
                "extensions": "all",
                "output": "JSON"
            }

            print(f"正在调用高德天气API...")
            response = requests.get(url, params=params, timeout=10)
            data = response.json()

            print(f"API响应: {data}")  # 先打印看看返回什么

            if data.get("status") == "1" and data.get("forecasts"):
                forecast_data = data["forecasts"][0]["casts"]

                weather_list = []
                for day in forecast_data:
                    weather_list.append({
                        "date": day["date"],
                        "temp_max": int(day["daytemp"]),
                        "temp_min": int(day["nighttemp"]),
                        "precipitation": float(day.get("dayprecip", 0)),
                        "weather": day["dayweather"],
                        "wind_dir": day["daywind"],
                        "wind_scale": day["daypower"],
                        "humidity": 60,  # 默认值
                    })

                df = pd.DataFrame(weather_list)
                print(f"[成功] 高德API成功！获取到 {len(df)} 天预报")
                return df
            else:
                print(f"[错误] 高德API返回错误: {data}")
                return self.get_fallback_data()

        except Exception as e:
            print(f"[错误] 高德API异常: {e}")
            import traceback
            traceback.print_exc()  # 打印详细错误
            return self.get_fallback_data()



    def get_fallback_data(self):
        """备用数据：当API失败时返回模拟数据"""
        print("使用备用数据...")
        return pd.read_csv('weather_data.csv')

    def get_current_weather(self, location="101210101"):
        """获取实时天气"""
        url = f"{self.base_url}/weather/now"
        params = {
            "key": self.api_key,
            "location": location
        }

        response = requests.get(url, params=params)
        return response.json()


# 全局服务实例（稍后在app.py中初始化）
weather_service = None