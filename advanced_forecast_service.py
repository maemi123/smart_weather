import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
from typing import Dict, List, Optional, Tuple
import time


class AdvancedForecastService:
    """高级预报数据服务 - 修复版"""

    HANGZHOU_LAT = 30.25
    HANGZHOU_LON = 120.17

    # Open-Meteo支持的模型
    MODELS = {
        "best_match": "最佳匹配（自动）",
        "ecmwf_ifs": "ECMWF",
        "gfs_seamless": "GFS",
        "gem_global": "GEM",
        "icon_global": "ICON",
    }

    # 天气代码到中文和emoji的映射
    WEATHER_CODES = {
        0: {"name": "晴", "emoji": "☀️"},
        1: {"name": "基本晴", "emoji": "🌤️"},
        2: {"name": "局部多云", "emoji": "⛅"},
        3: {"name": "多云", "emoji": "☁️"},
        45: {"name": "雾", "emoji": "🌫️"},
        48: {"name": "冻雾", "emoji": "🌫️❄️"},
        51: {"name": "小雨", "emoji": "🌦️"},
        53: {"name": "中雨", "emoji": "🌧️"},
        55: {"name": "强降雨", "emoji": "🌧️💦"},
        56: {"name": "冻雨（轻）", "emoji": "🌧️❄️"},
        57: {"name": "冻雨（强）", "emoji": "🌧️❄️💦"},
        61: {"name": "小雨", "emoji": "🌦️"},
        63: {"name": "中雨", "emoji": "🌧️"},
        65: {"name": "强降雨", "emoji": "🌧️💦"},
        66: {"name": "冻雨（轻）", "emoji": "🌧️❄️"},
        67: {"name": "冻雨（强）", "emoji": "🌧️❄️💦"},
        71: {"name": "小雪", "emoji": "🌨️"},
        73: {"name": "中雪", "emoji": "❄️"},
        75: {"name": "强降雪", "emoji": "❄️💨"},
        77: {"name": "雪粒", "emoji": "🌨️"},
        80: {"name": "小阵雨", "emoji": "🌦️"},
        81: {"name": "中阵雨", "emoji": "🌧️"},
        82: {"name": "强阵雨", "emoji": "⛈️"},
        85: {"name": "小阵雪", "emoji": "🌨️"},
        86: {"name": "强阵雪", "emoji": "❄️💨"},
        95: {"name": "雷暴", "emoji": "⛈️"},
        96: {"name": "雷暴伴小冰雹", "emoji": "⛈️🧊"},
        99: {"name": "雷暴伴强冰雹", "emoji": "⛈️🧊💥"}
    }

    def __init__(self):
        self.base_url = "https://api.open-meteo.com/v1/forecast"

    def fetch_multi_model_forecast(self, forecast_days: int = 7) -> Dict:
        """获取多模式预报数据 - 确保获取足够天数"""
        print(f"🔄 开始获取多模式预报数据（请求{forecast_days}天）...")

        results = {}

        # 尝试获取更多天数的模型
        target_models = ["best_match", "ecmwf_ifs", "gfs_seamless", "icon_global"]

        for model_name in target_models:
            model_display = self.MODELS.get(model_name, model_name)
            print(f"  正在获取 {model_display} 数据（{forecast_days}天）...")

            try:
                params = {
                    "latitude": self.HANGZHOU_LAT,
                    "longitude": self.HANGZHOU_LON,
                    "hourly": ("temperature_2m,precipitation,relative_humidity_2m,"
                               "wind_speed_10m,pressure_msl,weather_code,"
                               "et0_fao_evapotranspiration,shortwave_radiation,"
                               "soil_moisture_0_to_7cm,soil_temperature_0_to_7cm"),
                    "forecast_days": min(forecast_days, 7),  # 获取7天
                    "models": model_name,
                    "timezone": "Asia/Shanghai"
                }

                response = requests.get(self.base_url, params=params, timeout=25)

                if response.status_code == 200:
                    data = response.json()
                    processed = self._process_hourly_data(data, detailed=True)
                    if processed and processed.get("data"):
                        results[model_name] = {
                            "name": model_display,
                            "data": processed,
                            "color": self._get_model_color(model_name)
                        }
                        print(f"    ✅ {model_display} 获取成功，{len(processed.get('timestamps', []))} 个时间点")
                    else:
                        print(f"    ⚠️  {model_display} 数据处理失败")
                else:
                    print(f"    ❌ {model_display} 获取失败: {response.status_code}")

            except Exception as e:
                print(f"    ❌ {model_display} 获取异常: {str(e)}")

        # 生成集合预报
        if len(results) >= 2:
            results["ensemble"] = self._generate_ensemble_forecast(results)
            print(f"    ✅ 集合预报生成成功")

        print(f"✅ 多模式数据获取完成，成功获取 {len(results)} 个模型")
        return results

    def fetch_historical_data(self, start_date: str, end_date: str) -> Dict:
        """获取历史气象数据 (Open-Meteo ERA5-Land)"""
        print(f"🔄 获取历史数据: {start_date} 至 {end_date}...")
        url = "https://archive-api.open-meteo.com/v1/archive"
        params = {
            "latitude": self.HANGZHOU_LAT,
            "longitude": self.HANGZHOU_LON,
            "start_date": start_date,
            "end_date": end_date,
            "daily": "temperature_2m_max,temperature_2m_min,temperature_2m_mean",
            "timezone": "Asia/Shanghai"
        }
        try:
            response = requests.get(url, params=params, timeout=25)
            if response.status_code == 200:
                print("✅ 历史数据获取成功")
                return response.json()
            print(f"❌ 历史数据获取失败: {response.status_code}")
            return {}
        except Exception as e:
            print(f"❌ 历史数据获取异常: {str(e)}")
            return {}

    def fetch_detailed_72h_forecast(self) -> Dict:
        """获取72小时精细化预报（从当前时间开始）"""
        print("🔄 获取72小时精细化预报...")

        current_time = datetime.now()
        current_hour = current_time.hour

        params = {
            "latitude": self.HANGZHOU_LAT,
            "longitude": self.HANGZHOU_LON,
            "hourly": ("temperature_2m,precipitation,relative_humidity_2m,"
                       "wind_speed_10m,wind_direction_10m,pressure_msl,"
                       "cloud_cover,weather_code,visibility,uv_index"),
            "forecast_days": 4,  # 获取4天确保有72小时数据
            "models": "best_match",
            "timezone": "Asia/Shanghai"
        }

        try:
            response = requests.get(self.base_url, params=params, timeout=20)

            if response.status_code == 200:
                data = response.json()
                processed = self._process_hourly_data(data, detailed=True, current_hour=current_hour)
                print(f"✅ 72小时精细化预报获取成功，数据点: {len(processed.get('timestamps', []))}")
                return processed
            else:
                print(f"❌ 72小时预报获取失败: {response.status_code}")
                return {}

        except Exception as e:
            print(f"❌ 72小时预报获取异常: {str(e)}")
            return {}

    # 只修改有问题的函数，保持其他不变

    def _process_hourly_data(self, raw_data: Dict, detailed: bool = False,
                             current_hour: int = None) -> Dict:
        """处理原始小时数据 - 修复时间轴问题"""
        if "hourly" not in raw_data:
            return {"timestamps": [], "full_labels": [], "dates": [], "hours": [], "data": {}}

        hourly = raw_data["hourly"]
        times = hourly["time"]

        if not times:
            return {"timestamps": [], "full_labels": [], "dates": [], "hours": [], "data": {}}

        # 修复：API返回的已经是当地时间（北京时间），不需要+8
        bj_times = []
        full_labels = []
        date_labels = []
        hour_labels = []
        day_labels = []

        for i, t in enumerate(times):
            try:
                # 直接使用API返回的时间（已经是北京时间）
                dt = datetime.fromisoformat(t.replace('Z', '+00:00'))

                # 修复：不进行+8转换
                # dt = dt + timedelta(hours=8)  # 删除这行

                # 如果是详细模式且指定了current_hour
                if current_hour is not None and detailed:
                    # 只跳过明显过去的时间（比如超过3小时前）
                    if dt.hour < current_hour - 3 and dt.date() == datetime.now().date():
                        continue

                bj_times.append(dt.strftime("%Y-%m-%d %H:%M"))
                full_labels.append(dt.strftime("%m/%d %H:%M"))
                date_labels.append(dt.strftime("%m/%d"))
                hour_labels.append(f"{dt.hour:02d}:00")
                day_labels.append(dt.strftime("%m月%d日"))
            except Exception as e:
                print(f"时间解析错误: {t}, 错误: {e}")
                continue

        # 修复：如果是详细模式，确保获取完整的72小时
        if detailed and bj_times:
            # 从第一个时间点开始，取最多72小时
            start_index = 0
            end_index = min(168, len(bj_times))

            bj_times = bj_times[start_index:end_index]
            full_labels = full_labels[start_index:end_index]
            date_labels = date_labels[start_index:end_index]
            hour_labels = hour_labels[start_index:end_index]
            day_labels = day_labels[start_index:end_index]

        result = {
            "timestamps": bj_times,
            "full_labels": full_labels,
            "dates": date_labels,
            "hours": hour_labels,
            "day_labels": day_labels,
            "data": {}
        }

        # 提取各参数数据
        for key, values in hourly.items():
            if key != "time":
                if detailed and bj_times:
                    # 确保数据长度匹配
                    if len(values) >= len(bj_times):
                        result["data"][key] = values[:len(bj_times)]
                    else:
                        result["data"][key] = values + [None] * (len(bj_times) - len(values))
                else:
                    result["data"][key] = values

        # 关键：确保添加天气描述和图标
        if "weather_code" in result["data"]:
            weather_codes = result["data"]["weather_code"]
            weather_names = []
            weather_emojis = []

            for code in weather_codes:
                if code is None:
                    weather_info = {"name": "未知", "emoji": "❓"}
                else:
                    weather_info = self.WEATHER_CODES.get(int(code),
                                                          {"name": "未知", "emoji": "❓"})
                weather_names.append(weather_info["name"])
                weather_emojis.append(weather_info["emoji"])

            result["data"]["weather_name"] = weather_names
            result["data"]["weather_emoji"] = weather_emojis

        # 添加风力方向箭头符号
        if "wind_direction_10m" in result["data"]:
            wind_directions = result["data"]["wind_direction_10m"]
            result["data"]["wind_arrows"] = [
                self._degrees_to_arrow(d) for d in wind_directions
            ]

        print(
            f"数据处理完成: {len(bj_times)} 个数据点，时间范围: {bj_times[0] if bj_times else '无'} 到 {bj_times[-1] if bj_times else '无'}")
        print(f"包含天气数据: {'weather_emoji' in result['data']}")
        return result

    def _degrees_to_arrow(self, degrees: float) -> str:
        """将风向角度转换为箭头符号"""
        if degrees is None:
            return "↓"

        # 简化的风向箭头对应
        arrows = {
            (0, 22.5): "↓",  # 北
            (22.5, 67.5): "↙",  # 东北
            (67.5, 112.5): "←",  # 东
            (112.5, 157.5): "↖",  # 东南
            (157.5, 202.5): "↑",  # 南
            (202.5, 247.5): "↗",  # 西南
            (247.5, 292.5): "→",  # 西
            (292.5, 337.5): "↘",  # 西北
            (337.5, 360): "↓"  # 北
        }

        for (start, end), arrow in arrows.items():
            if start <= degrees < end:
                return arrow
        return "↓"

    def _generate_ensemble_forecast(self, models_data: Dict) -> Dict:
        """生成集合预报统计 - 使用75%分位作为置信区间"""
        print("  正在生成集合预报（75%分位置信区间）...")

        # 找出所有模型共有的时间点（使用best_match的时间轴）
        base_model = models_data.get("best_match",
                                     models_data.get("ecmwf_ifs",
                                                     list(models_data.values())[0] if models_data else None))

        if not base_model:
            return {}

        base_data = base_model["data"]

        ensemble_data = {
            "name": "集合预报（75%置信区间）",
            "color": "#9b59b6",
            "data": {
                "timestamps": base_data["timestamps"],
                "full_labels": base_data["full_labels"],
                "dates": base_data["dates"],
                "hours": base_data["hours"],
                "day_labels": base_data.get("day_labels", base_data["dates"]),
                "data": {},
                "statistics": {}
            }
        }

        # 对每个参数计算集合统计
        parameters = ["temperature_2m", "precipitation", "wind_speed_10m", "relative_humidity_2m"]

        for param in parameters:
            # 收集所有模型该参数的数据
            all_values = []
            valid_models = []

            for model_key, model_info in models_data.items():
                if model_key != "ensemble":
                    data = model_info["data"]["data"]
                    if param in data and data[param]:
                        all_values.append(data[param])
                        valid_models.append(model_key)

            if all_values and len(all_values) >= 2:
                # 转换为numpy数组
                try:
                    values_array = np.array(all_values)

                    # 计算统计量
                    ensemble_data["data"]["data"][param] = np.mean(values_array, axis=0).tolist()

                    # 计算75%置信区间（使用百分位数）
                    q25 = np.percentile(values_array, 25, axis=0).tolist()
                    q75 = np.percentile(values_array, 75, axis=0).tolist()
                    median = np.median(values_array, axis=0).tolist()

                    ensemble_data["data"]["statistics"][param] = {
                        "mean": np.mean(values_array, axis=0).tolist(),
                        "median": median,
                        "q25": q25,
                        "q75": q75,
                        "std": np.std(values_array, axis=0).tolist(),
                        "min": np.min(values_array, axis=0).tolist(),
                        "max": np.max(values_array, axis=0).tolist(),
                        "model_count": len(valid_models),
                        "models": valid_models
                    }

                    print(f"    {param}: 基于{len(valid_models)}个模型，置信区间[{q25[0]:.1f}, {q75[0]:.1f}]")

                except Exception as e:
                    print(f"    计算{param}统计量时出错: {e}")

        return ensemble_data

    def _get_model_color(self, model_name: str) -> str:
        """获取各模型的显示颜色"""
        colors = {
            "best_match": "#2c3e50",
            "ecmwf_ifs": "#e74c3c",
            "gfs_seamless": "#3498db",
            "gem_global": "#2ecc71",
            "icon_global": "#f39c12",
            "ensemble": "#9b59b6"
        }
        return colors.get(model_name, "#95a5a6")

    def generate_10day_summary(self, models_data: Dict) -> List[Dict]:
        """生成10天预报摘要 - 完全重写，确保获取10天数据"""

        print(f"\n🔍 开始生成10天摘要，传入模型数量: {len(models_data)}")

        if not models_data:
            print("⚠️ 没有模型数据")
            return []

        # 详细检查每个模型的数据
        for model_key, model_info in models_data.items():
            data = model_info["data"]
            timestamps = data.get("timestamps", [])
            temps = data["data"].get("temperature_2m", [])

            print(f"📊 模型 '{model_key}' 数据检查:")
            print(f"   时间点数量: {len(timestamps)}")
            print(f"   温度值数量: {len(temps)}")

            if timestamps:
                print(f"   时间范围: {timestamps[0]} 到 {timestamps[-1]}")

                # 计算覆盖天数
                if len(timestamps) >= 2:
                    try:
                        first = datetime.fromisoformat(timestamps[0].replace('Z', '+00:00'))
                        last = datetime.fromisoformat(timestamps[-1].replace('Z', '+00:00'))
                        days = (last - first).days + 1
                        print(f"   覆盖天数: {days} 天")
                    except:
                        pass

        # 优先使用集合预报，其次ECMWF，最后best_match
        base_model = None
        for model_key in ["ensemble", "ecmwf_ifs", "best_match"]:
            if model_key in models_data:
                base_model = models_data[model_key]
                print(f"使用模型: {model_key} 生成摘要")
                break

        if not base_model:
            print("⚠️ 没有找到可用的基础模型")
            return []

        data = base_model["data"]

        # 调试信息
        print(f"基础模型数据: timestamps={len(data.get('timestamps', []))}, "
              f"temperature_2m={len(data.get('data', {}).get('temperature_2m', []))}")

        # 获取温度和降水数据
        temps = data["data"].get("temperature_2m", [])
        precips = data["data"].get("precipitation", [])
        weather_codes = data["data"].get("weather_code", [])
        timestamps = data.get("timestamps", [])

        if not temps or not timestamps:
            print(f"⚠️ 温度数据为空: temps={len(temps)}, timestamps={len(timestamps)}")
            return []

        print(f"原始数据: {len(timestamps)} 个时间点，{len(temps)} 个温度值")

        model_daily_precip = {}
        for model_key, model_info in models_data.items():
            if model_key == "ensemble":
                continue
            try:
                md = model_info.get("data") or {}
                mts = md.get("timestamps") or []
                mp = (md.get("data") or {}).get("precipitation") or []
                daily = {}
                n = min(len(mts), len(mp))
                for j in range(n):
                    ts = mts[j]
                    if not ts:
                        continue
                    date_str = ts.split(" ")[0] if " " in ts else ts[:10]
                    daily[date_str] = daily.get(date_str, 0.0) + (mp[j] or 0.0)
                model_daily_precip[model_key] = daily
            except Exception:
                model_daily_precip[model_key] = {}

        # 按日期聚合数据
        daily_data = {}
        for i, ts in enumerate(timestamps):
            try:
                # 解析时间戳
                if ' ' in ts:
                    date_str = ts.split(' ')[0]  # 格式: "2026-01-12 01:00"
                else:
                    # 如果没有空格，尝试其他格式
                    date_str = ts[:10] if len(ts) >= 10 else ts

                if date_str not in daily_data:
                    daily_data[date_str] = {
                        "temps": [],
                        "precips": [],
                        "weather_codes": [],
                        "timestamps": []
                    }

                if i < len(temps):
                    daily_data[date_str]["temps"].append(temps[i])

                if i < len(precips):
                    daily_data[date_str]["precips"].append(precips[i])
                
                if i < len(weather_codes):
                    daily_data[date_str]["weather_codes"].append(weather_codes[i])

                daily_data[date_str]["timestamps"].append(ts)

            except Exception as e:
                print(f"处理时间戳 {ts} 时出错: {e}")
                continue

        print(f"聚合后的天数: {len(daily_data)}")

        # 生成摘要（最多10天）
        summary = []
        today = datetime.now().date()

        # 按日期排序
        sorted_dates = sorted(daily_data.keys())

        for i, date_str in enumerate(sorted_dates):
            if i >= 7:  # 最多7天
                break

            values = daily_data[date_str]
            if not values["temps"]:
                continue

            try:
                # 解析日期
                dt = datetime.strptime(date_str, "%Y-%m-%d").date()

                # 计算与今天的天数差（用于可信度评估）
                days_diff = (dt - today).days

                # 无论days_diff是多少，都显示（因为API数据已经是未来的）
                weekday = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][dt.weekday()]

                # 计算日统计
                temp_values = [t for t in values["temps"] if t is not None]
                if not temp_values:
                    continue

                temp_min = min(temp_values)
                temp_max = max(temp_values)
                temp_avg = sum(temp_values) / len(temp_values)

                # 计算降水
                precip_values = [p for p in values["precips"] if p is not None]
                precip_total = sum(precip_values) if precip_values else 0

                precip_model_vals = []
                for mk, mp_map in model_daily_precip.items():
                    if date_str in (mp_map or {}):
                        precip_model_vals.append(mp_map[date_str])
                if precip_model_vals:
                    if len(precip_model_vals) >= 2:
                        precip_lower = float(np.percentile(np.array(precip_model_vals), 25))
                        precip_upper = float(np.percentile(np.array(precip_model_vals), 75))
                    else:
                        precip_lower = float(precip_model_vals[0])
                        precip_upper = float(precip_model_vals[0])
                else:
                    precip_lower = None
                    precip_upper = None

                # 计算降水概率（有降水的小时数比例）
                precip_hours = sum(1 for p in precip_values if p > 0.1)
                precip_prob = min(100, precip_hours / max(1, len(precip_values)) * 100)
                
                # 获取主要天气代码 (众数)
                day_weather_codes = [c for c in values["weather_codes"] if c is not None]
                main_weather_code = 0
                if day_weather_codes:
                    # 如果有降水，优先看降水时的天气代码
                    precip_codes = [c for j, c in enumerate(day_weather_codes) 
                                   if j < len(precip_values) and precip_values[j] > 0.1]
                    if precip_codes:
                        main_weather_code = max(set(precip_codes), key=precip_codes.count)
                    else:
                        main_weather_code = max(set(day_weather_codes), key=day_weather_codes.count)

                # 天气描述
                weather_desc = self._generate_weather_desc(precip_total, temp_avg, main_weather_code, temp_min)

                # 可信度评估和置信区间
                if days_diff <= 2:
                    confidence = "高"
                    conf_emoji = "🟢"
                    temp_range = round((temp_max - temp_min) * 0.15, 1)
                elif days_diff <= 5:
                    confidence = "中"
                    conf_emoji = "🟡"
                    temp_range = round((temp_max - temp_min) * 0.2, 1)
                else:
                    confidence = "低"
                    conf_emoji = "🔴"
                    temp_range = round((temp_max - temp_min) * 0.3, 1)

                # 如果有集合预报统计信息，使用更精确的置信区间
                if "ensemble" in models_data and models_data["ensemble"]["data"].get("statistics", {}).get(
                        "temperature_2m"):
                    stats = models_data["ensemble"]["data"]["statistics"]["temperature_2m"]
                    # 找到对应时间段的统计
                    ensemble_temps = models_data["ensemble"]["data"]["data"].get("temperature_2m", [])
                    ensemble_timestamps = models_data["ensemble"]["data"].get("timestamps", [])

                    # 找到日期匹配的数据点
                    date_temps = []
                    for j, ts in enumerate(ensemble_timestamps):
                        if ts.startswith(date_str) and j < len(ensemble_temps):
                            date_temps.append(ensemble_temps[j])

                    if date_temps:
                        temp_avg = sum(date_temps) / len(date_temps)
                        # 使用集合预报的标准差作为置信区间
                        temp_range = round(np.std(date_temps) * 1.5, 1) if len(date_temps) > 1 else temp_range

                summary.append({
                    "date": dt.strftime("%m/%d"),
                    "weekday": weekday,
                    "weather": weather_desc,
                    "temp_min": round(temp_min, 1),
                    "temp_max": round(temp_max, 1),
                    "temp_avg": round(temp_avg, 1),
                    "temp_range": temp_range,
                    "temp_lower": round(temp_avg - temp_range, 1),  # 置信区间下界
                    "temp_upper": round(temp_avg + temp_range, 1),  # 置信区间上界
                    "precip_total": round(precip_total, 1),
                    "precip_prob": round(precip_prob, 0),
                    "precip_lower": round(precip_lower, 1) if precip_lower is not None else None,
                    "precip_upper": round(precip_upper, 1) if precip_upper is not None else None,
                    "confidence": confidence,
                    "conf_emoji": conf_emoji,
                    "days_ahead": days_diff
                })

                print(f"  第{i + 1}天: {date_str} {weekday} {weather_desc} "
                      f"{temp_min:.1f}~{temp_max:.1f}°C 平均{temp_avg:.1f}±{temp_range:.1f}°C")

            except Exception as e:
                print(f"生成{date_str}摘要时出错: {e}")
                continue

        print(f"✅ 生成 {len(summary)} 天的预报摘要")
        print(
            f"最终生成 {len(summary)} 天摘要，包含置信区间: {any('temp_lower' in d and 'temp_upper' in d for d in summary)}")
        for i, day in enumerate(summary):
            print(f"  第{i + 1}天: {day['date']} 平均{day['temp_avg']}±{day['temp_range']}°C "
                  f"置信区间[{day.get('temp_lower', 'N/A')}, {day.get('temp_upper', 'N/A')}]")
        return summary

    def _generate_weather_desc(self, precip_total: float, temp_mean: float, weather_code: int = None, temp_min: float = None) -> str:
        """根据降水、温度和天气代码生成天气描述"""
        # 1. 优先处理降水天气
        if precip_total > 0.1:
            # 确定降水强度前缀
            if precip_total >= 50:
                intensity = "暴"
            elif precip_total >= 25:
                intensity = "大"
            elif precip_total >= 10:
                intensity = "中"
            else:
                intensity = "小"

            # 确定降水类型后缀
            suffix = "雨"
            
            # 固态降水代码 (雪: 71,73,75,77,85,86)
            snow_codes = [71, 73, 75, 77, 85, 86]
            # 冻雨代码 (56,57,66,67)
            freezing_codes = [56, 57, 66, 67]
            # 雷暴代码
            thunder_codes = [95, 96, 99]

            # 关键修正：即使没有明确的雪代码，如果温度够低，也强制判定为雪或雨夹雪
            is_snow_code = weather_code in snow_codes
            
            # 智能判定逻辑
            if is_snow_code:
                if temp_min is not None and temp_min > 0:
                    suffix = "雨夹雪"
                else:
                    suffix = "雪"
            elif weather_code in freezing_codes:
                suffix = "冻雨"
            elif temp_min is not None and temp_min <= 0:
                # 即使代码不是雪，但温度<=0度且有降水，大概率是雪
                suffix = "雪"
            elif temp_min is not None and temp_min <= 2:
                # 温度在0-2度之间，大概率是雨夹雪
                suffix = "雨夹雪"
            elif weather_code in thunder_codes:
                # 雷暴特殊处理
                if precip_total >= 25:
                    return "雷暴伴强降水"
                else:
                    return "雷阵雨"
            
            return f"{intensity}{suffix}"

        # 2. 无降水时的天气描述 (基于天气代码)
        if weather_code is not None:
            weather_info = self.WEATHER_CODES.get(int(weather_code))
            if weather_info:
                return weather_info["name"]

        # 3. 兜底逻辑 (仅基于温度)
        if temp_mean > 30:
            return "晴热"
        elif temp_mean > 25:
            return "晴朗"
        elif temp_mean > 20:
            return "多云转晴"
        elif temp_mean > 15:
            return "多云"
        else:
            return "阴天"
