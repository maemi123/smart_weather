"""
Open-Meteo气候数据客户端 - 修复版
"""
import requests
import pandas as pd
from datetime import datetime
import os

class OpenMeteoClient:
    def __init__(self):
        self.base_url = "https://climate-api.open-meteo.com/v1/climate"

    def get_hangzhou_climatology(self):
        """获取杭州1991-2020气候态数据"""
        # 杭州经纬度
        latitude = 30.23
        longitude = 120.17

        params = {
            "latitude": latitude,
            "longitude": longitude,
            "start_date": "1991-01-01",
            "end_date": "2020-12-31",
            "models": "EC_Earth3P_HR",
            "daily": [
                "temperature_2m_mean",
                "temperature_2m_max",
                "temperature_2m_min",
                "precipitation_sum",
                "rain_sum",
                "snowfall_sum",
                "wind_speed_10m_mean",
                "wind_gusts_10m_max",
                "shortwave_radiation_sum",
            ],
            "timeformat": "unixtime"
        }

        print(f"正在从Open-Meteo获取杭州气候态数据(1991-2020)...")

        try:
            response = requests.get(self.base_url, params=params, timeout=30)
            data = response.json()

            if "daily" in data:
                print(f"成功获取气候态数据！")
                return self._process_climatology_data(data)
            else:
                print(f"API响应异常: {data.get('reason', '未知错误')}")
                return None

        except Exception as e:
            print(f"获取气候态数据失败: {e}")
            return None

    def _process_climatology_data(self, data):
        """处理气候态数据，计算月平均值"""
        daily_data = data["daily"]

        # 转换为DataFrame
        df = pd.DataFrame({
            "time": pd.to_datetime(daily_data["time"], unit="s"),
            "temp_mean": daily_data["temperature_2m_mean"],
            "temp_max": daily_data["temperature_2m_max"],
            "temp_min": daily_data["temperature_2m_min"],
            "precipitation": daily_data["precipitation_sum"],
            "rain": daily_data["rain_sum"],
            "snowfall": daily_data["snowfall_sum"],
            "wind_speed": daily_data["wind_speed_10m_mean"],
            "wind_gust": daily_data["wind_gusts_10m_max"],
            "solar_radiation": daily_data["shortwave_radiation_sum"],
        })

        # 添加月份列
        df["month"] = df["time"].dt.month
        df["year"] = df["time"].dt.year

        print(f"获取了 {len(df)} 天数据")
        print(f"时间范围: {df['time'].min().date()} 到 {df['time'].max().date()}")

        # 计算30年月平均气候态
        monthly_climatology = self._calculate_monthly_climatology(df)

        return {
            "raw_data": df,
            "monthly_climatology": monthly_climatology,
            "annual_climatology": self._calculate_annual_climatology(monthly_climatology)
        }

    def _calculate_monthly_climatology(self, df):
        """计算月平均气候态"""
        monthly_stats = {}

        for month in range(1, 13):
            month_data = df[df["month"] == month]

            if len(month_data) > 0:
                monthly_stats[month] = {
                    "temp_mean": month_data["temp_mean"].mean(),
                    "temp_max": month_data["temp_max"].mean(),
                    "temp_min": month_data["temp_min"].mean(),
                    "precipitation": month_data["precipitation"].mean(),
                    "rain_days": (month_data["precipitation"] >= 0.1).mean() * 30.4,
                    "snowfall": month_data["snowfall"].mean(),
                    "wind_speed": month_data["wind_speed"].mean(),
                    "solar_radiation": month_data["solar_radiation"].mean(),
                    "sample_years": month_data["year"].nunique()
                }

        return monthly_stats

    def _calculate_annual_climatology(self, monthly_climatology):
        """计算年度气候态统计"""
        if not monthly_climatology:
            return {}

        annual_stats = {
            "avg_temp": sum(m["temp_mean"] for m in monthly_climatology.values()) / 12,
            "total_precip": sum(m["precipitation"] for m in monthly_climatology.values()),
            "avg_temp_max": sum(m["temp_max"] for m in monthly_climatology.values()) / 12,
            "avg_temp_min": sum(m["temp_min"] for m in monthly_climatology.values()) / 12,
            "total_rain_days": sum(m["rain_days"] for m in monthly_climatology.values()),
            "total_snowfall": sum(m["snowfall"] for m in monthly_climatology.values()),
            "avg_wind_speed": sum(m["wind_speed"] for m in monthly_climatology.values()) / 12,
            "total_solar_radiation": sum(m["solar_radiation"] for m in monthly_climatology.values())
        }

        # 四舍五入
        for key in annual_stats:
            if isinstance(annual_stats[key], float):
                annual_stats[key] = round(annual_stats[key], 1)

        return annual_stats

    def save_climatology_to_file(self, climatology_data, filename=None):
        """保存气候态数据到Python文件"""
        if filename is None:
            filename = os.path.join("climate_data", "climatology_9120.py")

        print(f"\n保存气候态数据到 {filename}...")

        # 确保目录存在
        os.makedirs(os.path.dirname(filename), exist_ok=True)

        # 生成代码
        code = self._generate_climatology_code(climatology_data)

        with open(filename, "w", encoding="utf-8") as f:
            f.write(code)

        print(f"已保存到 {filename}")

        # 显示关键统计
        self._print_statistics(climatology_data)

    def _generate_climatology_code(self, climatology_data):
        """生成气候态数据Python代码"""
        annual = climatology_data["annual_climatology"]
        monthly = climatology_data["monthly_climatology"]

        # 构建月度数据字符串
        monthly_code = "{\n"
        for month in range(1, 13):
            if month in monthly:
                m = monthly[month]
                monthly_code += f'''        {month}: {{
            "temp_mean": {m["temp_mean"]:.1f},
            "temp_max": {m["temp_max"]:.1f},
            "temp_min": {m["temp_min"]:.1f},
            "precipitation": {m["precipitation"]:.1f},
            "rain_days": {m["rain_days"]:.1f},
            "snowfall": {m["snowfall"]:.1f},
            "wind_speed": {m["wind_speed"]:.1f},
            "solar_radiation": {m["solar_radiation"]:.1f}
        }},
'''
        monthly_code += "    }"

        code = f'''"""
杭州萧山站 1991-2020 气候态数据
数据来源：Open-Meteo Climate API (基于ERA5再分析数据)
获取时间：{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
数据点：{len(climatology_data['raw_data'])} 天
"""

HANGZHOU_9120_CLIMATOLOGY = {{
    "station_name": "杭州萧山",
    "period": "1991-2020",
    "data_source": "Open-Meteo Climate API (ERA5)",
    "latitude": 30.23,
    "longitude": 120.17,
    "elevation": 41.7,
    
    # 月度气候态数据
    "monthly_climatology": {monthly_code},
    
    # 年度气候态统计
    "annual_stats": {{
        "avg_temperature": {annual.get("avg_temp", 0):.1f},
        "avg_precipitation": {annual.get("total_precip", 0):.1f},
        "avg_temp_max": {annual.get("avg_temp_max", 0):.1f},
        "avg_temp_min": {annual.get("avg_temp_min", 0):.1f},
        "rainy_days": {annual.get("total_rain_days", 0):.1f},
        "snowfall": {annual.get("total_snowfall", 0):.1f},
        "avg_wind_speed": {annual.get("avg_wind_speed", 0):.1f},
        "solar_radiation": {annual.get("total_solar_radiation", 0):.1f}
    }}
}}

def get_monthly_climate(month):
    """获取指定月份的气候态数据"""
    return HANGZHOU_9120_CLIMATOLOGY["monthly_climatology"].get(month)

def get_annual_climate():
    """获取年度气候态数据"""
    return HANGZHOU_9120_CLIMATOLOGY["annual_stats"]

if __name__ == "__main__":
    print("杭州1991-2020气候态数据")
    print(f"年平均温度: {{get_annual_climate()['avg_temperature']}}°C")
    print(f"年总降水量: {{get_annual_climate()['avg_precipitation']}}mm")
    print(f"年降水日数: {{get_annual_climate()['rainy_days']:.0f}} 天")
'''

        return code

    def _print_statistics(self, climatology_data):
        """打印统计信息"""
        annual = climatology_data["annual_climatology"]
        monthly = climatology_data["monthly_climatology"]

        print(f"\n{'='*60}")
        print("杭州1991-2020气候态统计")
        print(f"{'='*60}")
        print(f"年平均温度: {annual['avg_temp']:.1f}°C")
        print(f"年总降水量: {annual['total_precip']:.1f}mm")
        print(f"年平均最高温: {annual['avg_temp_max']:.1f}°C")
        print(f"年平均最低温: {annual['avg_temp_min']:.1f}°C")
        print(f"年降水日数: {annual['total_rain_days']:.0f} 天")
        print(f"年平均风速: {annual['avg_wind_speed']:.1f}m/s")

        print(f"\n月度降水量分布:")
        for month in range(1, 13):
            if month in monthly:
                precip = monthly[month]["precipitation"]
                print(f"  {month:2}月: {precip:5.1f}mm")

        print(f"\n与81-10气候态对比（预估）:")
        # 81-10年平均温度约17.2°C，降水1440mm
        temp_change = annual['avg_temp'] - 17.2
        precip_change = annual['total_precip'] - 1440.8
        print(f"  温度变化: {temp_change:+.1f}°C ({temp_change/17.2*100:+.1f}%)")
        print(f"  降水变化: {precip_change:+.1f}mm ({precip_change/1440.8*100:+.1f}%)")

# 使用示例
if __name__ == "__main__":
    client = OpenMeteoClient()

    print("="*60)
    print("获取杭州1991-2020气候态数据")
    print("="*60)

    # 获取气候态数据
    climatology = client.get_hangzhou_climatology()

    if climatology:
        # 保存到文件
        client.save_climatology_to_file(climatology)
    else:
        print("获取气候态数据失败！")