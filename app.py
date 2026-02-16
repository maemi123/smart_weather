import numpy as np
from flask import Flask, render_template, request, jsonify, redirect, url_for
import pandas as pd
import requests
from weather_service import WeatherService
import json
import math
from datetime import datetime, timedelta
from chart_generator import ChartGenerator

import os
import sys
import io
import time

from ecmwf_service import ECMWFService
# 添加导入
from advanced_forecast_service import AdvancedForecastService
from typing import Dict, List

from history_analyzer import analyzer
from datetime import datetime

# 初始化服务
forecast_service = AdvancedForecastService()

# 初始化服务
ecmwf_service = ECMWFService()

# 修复Windows控制台编码问题
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

app = Flask(__name__)

# 初始化天气服务（替换YOUR_QWEATHER_KEY）
QWEATHER_KEY = "REMOVED_KEY_2"
weather_service = WeatherService(QWEATHER_KEY)

_DASH_CACHE = {}

def _cache_get(key: str, max_age_seconds: int):
    item = _DASH_CACHE.get(key)
    if not item:
        return None
    ts = item.get("ts", 0)
    if time.time() - ts > max_age_seconds:
        return None
    return item.get("value")

def _cache_set(key: str, value):
    _DASH_CACHE[key] = {"ts": time.time(), "value": value}


# 1. 读取模拟数据
def get_weather_data():
    df = pd.read_csv('weather_data.csv')
    # 将数据转换为字典列表，方便前端展示
    weather_list = df.to_dict('records')
    return weather_list


# 2. 调用DeepSeek API进行AI分析
def get_ai_analysis(weather_text):
    # TODO: 替换为你的真实API Key（下一步会获取）
    api_key = "REMOVED_KEY_5"
    url = "https://api.deepseek.com/v1/chat/completions"

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }

    prompt = f"""
    你是一个天气分析师。请根据以下未来几天的天气预报数据，生成一段简洁易懂的天气分析报告：

    {weather_text}

    请包括：
    1. 整体天气趋势
    2. 温度变化特点
    3. 给市民的出行建议
    请用亲切的口语化语言回答。
    """

    data = {
        "model": "deepseek-chat",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7
    }

    try:
        response = requests.post(url, headers=headers, json=data)
        result = response.json()
        analysis = result['choices'][0]['message']['content']
        return analysis
    except Exception as e:
        return f"AI分析暂时不可用。错误信息：{str(e)}"


@app.route('/')
def index():
    return render_template('index.html', city="杭州")


@app.route('/api/current-weather')
def api_current_weather():
    try:
        latitude = 30.25
        longitude = 120.17
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "current_weather": "true",
            "hourly": "relative_humidity_2m,pressure_msl,precipitation,apparent_temperature",
            "timezone": "Asia/Shanghai",
            "windspeed_unit": "ms",
        }
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json() or {}

        current = data.get("current_weather") or {}
        hourly = data.get("hourly") or {}
        times = hourly.get("time") or []
        current_time = current.get("time")

        idx = None
        if current_time and times:
            try:
                idx = times.index(current_time)
            except ValueError:
                idx = len(times) - 1

        def pick(key, default=None):
            arr = hourly.get(key) or []
            if idx is None or not arr:
                return default
            try:
                return arr[idx]
            except Exception:
                return default

        temp = current.get("temperature")
        feels_like = pick("apparent_temperature", temp)
        humidity = pick("relative_humidity_2m")
        pressure = pick("pressure_msl")
        precipitation = pick("precipitation", 0.0)
        wind_speed = current.get("windspeed")
        weather_code = current.get("weathercode")
        update_time = current_time or datetime.now().strftime("%Y-%m-%d %H:%M")

        return jsonify({
            "temp": float(temp) if temp is not None else None,
            "feels_like": float(feels_like) if feels_like is not None else None,
            "humidity": int(humidity) if humidity is not None else None,
            "wind_speed": float(wind_speed) if wind_speed is not None else None,
            "pressure": float(pressure) if pressure is not None else None,
            "precipitation": float(precipitation) if precipitation is not None else None,
            "weather_code": int(weather_code) if weather_code is not None else None,
            "update_time": str(update_time),
        })
    except Exception as e:
        return jsonify({"error": "current-weather fetch failed", "detail": str(e)}), 502


@app.route('/api/preview-charts')
def api_preview_charts():
    cached = _cache_get("preview_charts", 10 * 60)
    if cached:
        return jsonify(cached)

    try:
        today = datetime.now().date()

        latitude = 30.25
        longitude = 120.17
        forecast_url = "https://api.open-meteo.com/v1/forecast"

        forecast_7d = None
        try:
            forecast_params = {
                "latitude": latitude,
                "longitude": longitude,
                "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum",
                "forecast_days": 7,
                "models": "ecmwf_ifs",
                "timezone": "Asia/Shanghai",
            }
            fr = requests.get(forecast_url, params=forecast_params, timeout=15)
            fr.raise_for_status()
            fdata = fr.json() or {}
            daily = fdata.get("daily") or {}
            forecast_7d = {
                "dates": daily.get("time") or [],
                "tmax": daily.get("temperature_2m_max") or [],
                "tmin": daily.get("temperature_2m_min") or [],
                "precip": daily.get("precipitation_sum") or [],
            }
        except Exception:
            forecast_7d = None

        def daily_from_hourly(model: dict, days: int = 7):
            if not model:
                return {"dates": [], "tmax": [], "tmin": [], "precip": []}
            md = model.get("data") or {}
            ts = md.get("timestamps") or []
            d = (md.get("data") or {})
            temps = d.get("temperature_2m") or []
            precips = d.get("precipitation") or []

            daily = {}
            n = min(len(ts), len(temps), len(precips))
            for i in range(n):
                date_str = (ts[i] or "").split(" ")[0]
                if not date_str:
                    continue
                entry = daily.get(date_str)
                if entry is None:
                    entry = {"tmax": None, "tmin": None, "precip": 0.0}
                    daily[date_str] = entry
                t = temps[i]
                if t is not None:
                    tv = float(t)
                    entry["tmax"] = tv if entry["tmax"] is None else max(entry["tmax"], tv)
                    entry["tmin"] = tv if entry["tmin"] is None else min(entry["tmin"], tv)
                p = precips[i]
                if p is not None:
                    entry["precip"] += float(p)

            out_dates = []
            out_tmax = []
            out_tmin = []
            out_precip = []
            for i in range(days):
                d0 = today + timedelta(days=i)
                k = d0.strftime("%Y-%m-%d")
                entry = daily.get(k) or {}
                out_dates.append(k)
                out_tmax.append(None if entry.get("tmax") is None else round(float(entry.get("tmax")), 1))
                out_tmin.append(None if entry.get("tmin") is None else round(float(entry.get("tmin")), 1))
                out_precip.append(round(float(entry.get("precip") or 0.0), 1))

            return {"dates": out_dates, "tmax": out_tmax, "tmin": out_tmin, "precip": out_precip}

        if not forecast_7d or not (forecast_7d.get("dates") and forecast_7d.get("precip")):
            multi = forecast_service.fetch_multi_model_forecast(forecast_days=7)
            chosen_model = None
            for k in ["ecmwf_ifs", "ensemble", "best_match"]:
                if k in (multi or {}):
                    chosen_model = multi.get(k)
                    break
            forecast_7d = daily_from_hourly(chosen_model, 7)

        end_date = today - timedelta(days=1)
        start_date = end_date - timedelta(days=29)

        archive_url = "https://archive-api.open-meteo.com/v1/archive"
        archive_params = {
            "latitude": latitude,
            "longitude": longitude,
            "start_date": start_date.strftime("%Y-%m-%d"),
            "end_date": end_date.strftime("%Y-%m-%d"),
            "daily": "precipitation_sum,temperature_2m_max,temperature_2m_min",
            "timezone": "Asia/Shanghai",
        }
        ar = requests.get(archive_url, params=archive_params, timeout=20)
        ar.raise_for_status()
        adata = ar.json() or {}
        adaily = adata.get("daily") or {}
        p_dates = adaily.get("time") or []
        p_vals = adaily.get("precipitation_sum") or []
        p_tmax = adaily.get("temperature_2m_max") or []
        p_tmin = adaily.get("temperature_2m_min") or []
        p_tmean = []
        n = min(len(p_tmax), len(p_tmin))
        for i in range(n):
            a = p_tmax[i]
            b = p_tmin[i]
            if a is None or b is None:
                p_tmean.append(None)
            else:
                p_tmean.append((a + b) / 2)

        payload = {
            "forecast_7d": forecast_7d,
            "history_30d": {"dates": p_dates, "precip": p_vals, "tmean": p_tmean, "tmax": p_tmax, "tmin": p_tmin},
        }
        _cache_set("preview_charts", payload)
        return jsonify(payload)
    except Exception as e:
        today = datetime.now().date()
        f_dates = [(today + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7)]
        f_tmax = []
        f_tmin = []
        f_precip = []
        for i in range(7):
            base = 14.0 + 3.0 * math.sin((i / 6.0) * math.pi * 2.0)
            tmax = base + 4.0 + (0.8 if i % 3 == 0 else 0.0)
            tmin = base - 3.0 - (0.6 if i % 4 == 0 else 0.0)
            f_tmax.append(round(tmax, 1))
            f_tmin.append(round(tmin, 1))
            f_precip.append(round(0.0 if i % 3 != 0 else 12.0 + (i % 2) * 8.0, 1))

        h_end = today
        h_start = h_end - timedelta(days=29)
        h_dates = [(h_start + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(30)]
        h_tmax = []
        h_tmin = []
        h_tmean = []
        h_precip = []
        for i in range(30):
            base = 13.0 + 4.0 * math.sin((i / 29.0) * math.pi * 2.0)
            tmax = base + 4.5 + (0.5 if i % 7 == 0 else 0.0)
            tmin = base - 3.5 - (0.4 if i % 9 == 0 else 0.0)
            h_tmax.append(round(tmax, 1))
            h_tmin.append(round(tmin, 1))
            h_tmean.append(round((tmax + tmin) / 2.0, 1))
            h_precip.append(round(0.0 if i % 5 != 0 else 5.0 + (i % 3) * 1.5, 1))

        payload = {
            "forecast_7d": {"dates": f_dates, "tmax": f_tmax, "tmin": f_tmin, "precip": f_precip},
            "history_30d": {"dates": h_dates, "precip": h_precip, "tmean": h_tmean, "tmax": h_tmax, "tmin": h_tmin},
            "note": f"preview-charts fallback: {str(e)}",
        }
        _cache_set("preview_charts", payload)
        return jsonify(payload)


@app.route('/api/smart-tips')
def api_smart_tips():
    cached = _cache_get("smart_tips", 5 * 60)
    if cached:
        return jsonify(cached)

    tips = []
    try:
        multi_model = forecast_service.fetch_multi_model_forecast(forecast_days=7)

        forecast_list = build_agro_forecast_list(multi_model, forecast_days=7)
        alerts = agro_alert_engine.generate_alerts(forecast_list)

        if alerts:
            level_rank = {"high": 1, "medium": 2, "info": 3}
            sorted_alerts = sorted(alerts, key=lambda a: (level_rank.get(a.get("level"), 9), a.get("date", "")))
            picked = []
            seen_crop_ids = set()
            seen_titles = set()
            for a in sorted_alerts:
                cid = a.get("crop_id")
                title = (a.get("title") or "").strip()
                if title and title in seen_titles:
                    continue
                if cid and cid in seen_crop_ids:
                    continue
                if cid:
                    seen_crop_ids.add(cid)
                if title:
                    seen_titles.add(title)
                picked.append(a)
                if len(picked) >= 5:
                    break

            for a in picked:
                level = a.get("level")
                icon = "🌾"
                if level == "high":
                    icon = "🚨"
                elif level == "medium":
                    icon = "⚠️"
                tips.append({
                    "type": "农业",
                    "icon": icon,
                    "content": f"{a.get('crop_name','作物')}：{a.get('title','')}",
                    "action": "查看详情",
                    "link": f"/crop/{a.get('crop_id')}" if a.get("crop_id") else "/agro-dashboard",
                    "priority": 1 if level == "high" else 2 if level == "medium" else 3,
                    "crop_id": a.get("crop_id")
                })
        else:
            net_eff = sum((d.get("precip_eff", 0) or 0) for d in (forecast_list or [])[:7])
            if net_eff <= -10:
                tips.append({
                    "type": "农业",
                    "icon": "🌾",
                    "content": f"未来7天净有效降水{net_eff:.1f}mm，田间水分偏紧，建议关注灌溉与保墒。",
                    "action": "看农业",
                    "link": "/agro-dashboard",
                    "priority": 3
                })

        crops = crop_db.get_all_crops()
        best = None
        note_candidate = None
        for c in crops:
            cid = c.get("id")
            info = crop_db.get_crop_info(cid) if cid else None
            if not info:
                continue
            gdd_info = get_historical_gdd(cid, info, sowing_date_str=None)
            if not gdd_info.get("is_active"):
                if not note_candidate and gdd_info.get("note") and (info.get("gdd_total") or 0):
                    note_candidate = {
                        "crop_id": cid,
                        "crop_name": info.get("name"),
                        "icon": info.get("icon") or "🌱",
                        "note": gdd_info.get("note")
                    }
                continue
            total = float(info.get("gdd_total") or 0)
            if total <= 0:
                continue
            current = float(gdd_info.get("current") or 0)
            gdd_base = float(info.get("gdd_base") or 10)
            forecast_gdd = 0.0
            for day in (forecast_list or [])[:7]:
                avg = day.get("temp_avg")
                if avg is None:
                    continue
                forecast_gdd += max(0.0, float(avg) - gdd_base)
            predicted = current + forecast_gdd
            predicted_percent = predicted / total if total > 0 else 0
            if best is None or predicted_percent > best.get("predicted_percent", 0):
                best = {
                    "crop_id": cid,
                    "crop_name": info.get("name"),
                    "icon": info.get("icon") or "🌱",
                    "current": current,
                    "total": total,
                    "forecast_gdd": forecast_gdd,
                    "predicted_percent": predicted_percent,
                }

        if best:
            remaining = best["total"] - best["current"]
            days_to_reach = None
            if remaining > 0 and best.get("forecast_gdd", 0) > 0:
                days_to_reach = remaining / (best["forecast_gdd"] / 7.0)
            pct = min(100.0, max(0.0, best["current"] / best["total"] * 100.0)) if best["total"] > 0 else 0.0
            near = best["current"] < best["total"] and best.get("predicted_percent", 0) >= 0.95
            extra = f"，预计约{int(round(days_to_reach))}天接近阈值" if days_to_reach and days_to_reach < 30 else ""
            tips.append({
                "type": "作物进度",
                "icon": best["icon"],
                "content": f"{best['crop_name']}积温{best['current']:.0f}/{best['total']:.0f}℃（{pct:.0f}%）{extra}",
                "action": "查看作物",
                "link": f"/crop/{best['crop_id']}",
                "priority": 2,
                "crop_id": best["crop_id"]
            })
        elif note_candidate:
            tips.append({
                "type": "作物进度",
                "icon": note_candidate["icon"],
                "content": f"{note_candidate['crop_name']}积温：{note_candidate['note']}",
                "action": "查看作物",
                "link": f"/crop/{note_candidate['crop_id']}",
                "priority": 3,
                "crop_id": note_candidate["crop_id"]
            })

        if "ecmwf_ifs" in multi_model and "gfs_seamless" in multi_model:
            def sum_precip_first_days(model_key: str, days: int = 3):
                mi = multi_model.get(model_key) or {}
                d = (mi.get("data") or {}).get("data") or {}
                ts = (mi.get("data") or {}).get("timestamps") or []
                p = d.get("precipitation") or []
                daily_sum = {}
                n = min(len(ts), len(p))
                for i in range(n):
                    date_str = (ts[i] or "").split(" ")[0]
                    if not date_str:
                        continue
                    daily_sum[date_str] = daily_sum.get(date_str, 0.0) + (p[i] or 0.0)
                keys = sorted(daily_sum.keys())[:days]
                return sum(daily_sum[k] for k in keys)

            e_sum = sum_precip_first_days("ecmwf_ifs", 3)
            g_sum = sum_precip_first_days("gfs_seamless", 3)
            diff = abs(e_sum - g_sum)
            if diff >= 8:
                tips.append({
                    "type": "预报对比",
                    "icon": "📊",
                    "content": f"未来3天降水预报分歧较大：ECMWF约{e_sum:.1f}mm，GFS约{g_sum:.1f}mm。",
                    "action": "去对比",
                    "link": "/advanced-forecast",
                    "priority": 3
                })

    except Exception:
        pass

    try:
        cached_upper = _cache_get("upperair_tip", 30 * 60)
        if cached_upper:
            tips.append(cached_upper)
        else:
            result = sounding_parser.fetch_sounding_data("58457", None)
            if result.get("success"):
                parsed = sounding_parser.parse_sounding_data(result.get("raw_data"))
                analysis = sounding_analyzer.analyze(pd.DataFrame(parsed.get("levels", [])), parsed.get("indices", {}))
                risk = analysis.get("risk_assessment") or {}
                level = (risk.get("level") or "").strip()
                color = risk.get("color")
                if level and level != "低风险":
                    icon = "⚡" if color in ("warning", "danger") else "🎈"
                    tip = {
                        "type": "强对流",
                        "icon": icon,
                        "content": f"{level}：{risk.get('description','')}",
                        "action": "查看探空",
                        "link": "/upperair",
                        "priority": 2 if color == "warning" else 1 if color == "danger" else 3
                    }
                    _cache_set("upperair_tip", tip)
                    tips.append(tip)
    except Exception:
        pass

    tips = sorted(tips, key=lambda x: x.get("priority", 9))[:5]
    _cache_set("smart_tips", tips)
    return jsonify(tips)


@app.route('/api/module-status')
def api_module_status():
    cached = _cache_get("module_status", 2 * 60)
    if cached:
        return jsonify(cached)

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    modules = {}

    def model_run_label(model_key: str, now_utc: datetime) -> str:
        def latest_cycle(cycle_hours: list[int], latency_hours: int) -> str:
            candidates = []
            for d in [now_utc.date(), (now_utc - timedelta(days=1)).date()]:
                for h in cycle_hours:
                    cycle_dt = datetime(d.year, d.month, d.day, h, 0, 0)
                    if cycle_dt + timedelta(hours=latency_hours) <= now_utc:
                        candidates.append(cycle_dt)

            if candidates:
                best = max(candidates)
                return f"{best.hour:02d}z"

            fallback = []
            for d in [now_utc.date(), (now_utc - timedelta(days=1)).date()]:
                for h in cycle_hours:
                    fallback.append(datetime(d.year, d.month, d.day, h, 0, 0))
            best = max([c for c in fallback if c <= now_utc], default=max(fallback))
            return f"{best.hour:02d}z"

        if model_key == "ecmwf_ifs":
            return latest_cycle([0, 12], latency_hours=7)

        if model_key == "gfs_seamless":
            return latest_cycle([0, 6, 12, 18], latency_hours=5)

        return "--"

    try:
        multi_model = forecast_service.fetch_multi_model_forecast(forecast_days=7)
        ok = bool(multi_model and any(k in multi_model for k in ("ecmwf_ifs", "gfs_seamless", "best_match")))
        now_utc = datetime.utcnow()
        ec = model_run_label("ecmwf_ifs", now_utc) if (multi_model or {}).get("ecmwf_ifs") else "--"
        gfs = model_run_label("gfs_seamless", now_utc) if (multi_model or {}).get("gfs_seamless") else "--"
        detail = f"ecmwf：{ec} gfs：{gfs}"
        modules["forecast"] = {"status": "ok" if ok else "error", "detail": detail if ok else "预报数据不可用"}
    except Exception as e:
        modules["forecast"] = {"status": "error", "detail": str(e)}

    try:
        result = sounding_parser.fetch_sounding_data("58457", None)
        if result.get("success"):
            t = result.get("time")
            if isinstance(t, datetime):
                detail = f"已获取（最近时次）：{t.strftime('%Y-%m-%d')} {t.strftime('%H')}z"
            else:
                detail = "已获取（最近时次）"
            modules["sounding"] = {"status": "ok", "detail": detail}
        else:
            modules["sounding"] = {"status": "warn", "detail": result.get("error", "获取失败")}
    except Exception as e:
        modules["sounding"] = {"status": "warn", "detail": str(e)}

    try:
        crops = crop_db.get_all_crops()
        multi_model = forecast_service.fetch_multi_model_forecast(forecast_days=7)
        forecast_list = build_agro_forecast_list(multi_model, forecast_days=7)
        alerts = agro_alert_engine.generate_alerts(forecast_list)
        modules["agriculture"] = {"status": "track", "detail": f"{len(crops)}种作物，{len(alerts)}条预警"}
    except Exception as e:
        modules["agriculture"] = {"status": "warn", "detail": str(e)}

    try:
        years = analyzer.get_available_years()
        if years:
            modules["climate"] = {"status": "ok", "detail": f"{years[-1]}年数据可对比"}
        else:
            modules["climate"] = {"status": "warn", "detail": "暂无可用历史数据"}
    except Exception as e:
        modules["climate"] = {"status": "warn", "detail": str(e)}

    payload = {"last_update": now_str, "modules": modules}
    _cache_set("module_status", payload)
    return jsonify(payload)


@app.route('/ecmwf')
def ecmwf_demo():
    """ECMWF数据演示页面"""

    # 初始化服务（离线模式）
    ecmwf_service = ECMWFService(offline_mode=True)

    # 获取数据
    df = ecmwf_service.get_weather_data()

    # 转换为展示格式
    df_data = []
    for i, row in df.iterrows():
        df_data.append({
            'forecast_hour': f'T+{i * 3}h',
            'time': row['time'],
            'temperature': f"{row['temperature_c']:.1f}",
            'precip_prob': f"{row['precipitation_prob']}%",
            'humidity': f"{row['humidity']}%",
            'wind': f"{row['wind_direction']} {row['wind_speed']:.1f}m/s",
            'data_source': '🌍 ECMWF模拟预报'
        })

    # 生成图表
    charts = ecmwf_service.generate_charts(df)

    # 获取元数据
    metadata = df.attrs if hasattr(df, 'attrs') else {}

    return render_template('ecmwf.html',
                           ecmwf_data=df_data,
                           charts=charts,
                           metadata=metadata,
                           now=datetime.now().strftime("%Y-%m-%d %H:%M"))


@app.route('/ecmwf/real')
def ecmwf_real_data():
    """展示真实的ECMWF数据 - 修复版"""
    import xarray as xr
    import numpy as np

    real_file = 'data/ecmwf/real_data.grib'

    if not os.path.exists(real_file):
        return render_template('error.html',
                               message="❌ 真实数据文件不存在",
                               details="请先运行下载脚本获取真实ECMWF数据"), 404

    try:
        # 读取真实数据 - 使用更安全的方式
        print(f"正在读取GRIB文件: {real_file}")

        # 方法1: 尝试标准方式
        try:
            ds = xr.open_dataset(real_file, engine='cfgrib')
            print(f"✅ 使用cfgrib成功打开")
        except Exception as e1:
            print(f"cfgrib失败: {e1}")
            # 方法2: 尝试open_datasets
            import cfgrib
            datasets = cfgrib.open_datasets(real_file)
            if datasets:
                ds = datasets[0]  # 取第一个数据集
                print(f"✅ 使用open_datasets成功打开，找到{len(datasets)}个数据集")
            else:
                raise Exception("无法用任何方式打开GRIB文件")

        # 提取基本信息（更安全的方式）
        data_info = {
            'file_size': f"{os.path.getsize(real_file):,} bytes",
            'variables': list(ds.data_vars),
            'data_time': '未知',
            'latitude_info': 'N/A',
            'longitude_info': 'N/A',
        }

        # 尝试获取时间
        if hasattr(ds, 'time') and ds.time is not None:
            try:
                if hasattr(ds.time, 'values'):
                    data_info['data_time'] = str(ds.time.values)
                elif hasattr(ds.time, 'item'):
                    data_info['data_time'] = str(ds.time.item())
            except:
                pass

        # 尝试获取经纬度信息
        lat_info = []
        lon_info = []

        # 检查所有坐标
        for coord_name in ds.coords:
            coord = ds[coord_name]
            print(
                f"坐标 {coord_name}: shape={coord.shape}, values={coord.values[:3] if hasattr(coord.values, '__len__') else coord.values}")

            # 判断是否是纬度
            if 'lat' in coord_name.lower() or coord_name.lower() == 'latitude':
                lat_info.append(f"{coord_name}: {coord.values}")

            # 判断是否是经度
            if 'lon' in coord_name.lower() or coord_name.lower() == 'longitude':
                lon_info.append(f"{coord_name}: {coord.values}")

        if lat_info:
            data_info['latitude_info'] = " | ".join(lat_info)
        if lon_info:
            data_info['longitude_info'] = " | ".join(lon_info)

        # 提取温度数据
        temperature_data = []
        if 't2m' in ds.data_vars:
            temp_var = ds['t2m']
            print(f"温度变量形状: {temp_var.shape}")
            print(f"温度变量维度: {temp_var.dims}")

            # 安全地提取数据
            try:
                # 对于小文件，可能没有空间维度
                if temp_var.ndim == 0:  # 标量
                    temp_k = float(temp_var.values)
                    temp_c = temp_k - 273.15
                    temperature_data.append({
                        'grid_point': "单点数据",
                        'temperature_k': f"{temp_k:.2f}",
                        'temperature_c': f"{temp_c:.2f}",
                        'latitude': "N/A",
                        'longitude': "N/A",
                    })

                elif temp_var.ndim == 1:  # 一维数据（可能是时间序列）
                    for i in range(min(3, len(temp_var))):  # 只显示前3个
                        temp_k = float(temp_var[i].values)
                        temp_c = temp_k - 273.15
                        temperature_data.append({
                            'grid_point': f"时间点 {i}",
                            'temperature_k': f"{temp_k:.2f}",
                            'temperature_c': f"{temp_c:.2f}",
                            'latitude': "N/A",
                            'longitude': "N/A",
                        })

                elif temp_var.ndim >= 2:  # 二维或更高维
                    # 尝试获取前几个格点
                    indices = []
                    if 'latitude' in temp_var.dims and 'longitude' in temp_var.dims:
                        # 获取索引
                        lat_idx = list(range(min(2, temp_var.shape[temp_var.dims.index('latitude')])))
                        lon_idx = list(range(min(2, temp_var.shape[temp_var.dims.index('longitude')])))

                        # 创建索引组合
                        for i in lat_idx:
                            for j in lon_idx:
                                indices.append((i, j))
                    else:
                        # 如果找不到经纬度维度，取前几个元素
                        indices = [(i,) for i in range(min(4, temp_var.size))]

                    for idx in indices:
                        try:
                            temp_k = float(temp_var[idx].values)
                            temp_c = temp_k - 273.15

                            # 尝试获取对应的经纬度
                            lat_val = "N/A"
                            lon_val = "N/A"

                            if 'latitude' in ds.coords and len(idx) > 0:
                                try:
                                    lat_coord = ds['latitude']
                                    if hasattr(lat_coord, '__getitem__'):
                                        lat_val = float(lat_coord[idx[0]].values)
                                except:
                                    pass

                            if 'longitude' in ds.coords and len(idx) > 1:
                                try:
                                    lon_coord = ds['longitude']
                                    if hasattr(lon_coord, '__getitem__'):
                                        lon_val = float(lon_coord[idx[1]].values)
                                except:
                                    pass

                            temperature_data.append({
                                'grid_point': f"格点{idx}",
                                'temperature_k': f"{temp_k:.2f}",
                                'temperature_c': f"{temp_c:.2f}",
                                'latitude': lat_val if lat_val != "N/A" else "N/A",
                                'longitude': lon_val if lon_val != "N/A" else "N/A",
                            })
                        except:
                            continue
            except Exception as e:
                print(f"温度数据提取失败: {e}")
                temperature_data.append({
                    'grid_point': "数据提取错误",
                    'temperature_k': "N/A",
                    'temperature_c': "N/A",
                    'latitude': "N/A",
                    'longitude': "N/A",
                })

        # 获取变量属性
        variable_info = {}
        for var_name in ds.data_vars:
            var = ds[var_name]
            variable_info[var_name] = {
                'long_name': var.attrs.get('long_name', var_name),
                'units': var.attrs.get('units', 'unknown'),
                'shape': var.shape,
                'dims': str(var.dims),
            }

        ds.close()

        # 渲染模板
        return render_template('ecmwf_real_fixed.html',
                               data_info=data_info,
                               temperature_data=temperature_data,
                               variable_info=variable_info,
                               file_path=real_file,
                               download_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"❌ 数据读取错误: {e}")
        print(f"错误详情:\n{error_details}")

        return render_template('error.html',
                               message=f"❌ 数据读取错误: {str(e)[:100]}...",
                               details=error_details[:500]), 500


@app.route('/ecmwf/simple')
def ecmwf_simple_real():
    """最简单的真实数据展示"""
    import xarray as xr

    real_file = 'data/ecmwf/real_data.grib'

    if not os.path.exists(real_file):
        return "❌ 文件不存在", 404

    try:
        # 最简单直接的读取
        ds = xr.open_dataset(real_file, engine='cfgrib')

        # 提取温度数据
        temp_data = []
        if 't2m' in ds:
            temp_var = ds['t2m']

            # 这是一个2x2的网格
            for i in range(2):  # 纬度索引
                for j in range(2):  # 经度索引
                    lat = float(ds.latitude[i].values)
                    lon = float(ds.longitude[j].values)
                    temp_k = float(temp_var[i, j].values)
                    temp_c = temp_k - 273.15

                    temp_data.append({
                        'lat': f"{lat:.2f}",
                        'lon': f"{lon:.2f}",
                        'temp_k': f"{temp_k:.2f}",
                        'temp_c': f"{temp_c:.2f}",
                        'location': f"({lat:.2f}°N, {lon:.2f}°E)"
                    })

        # 提取基本信息
        info = {
            'file_size': os.path.getsize(real_file),
            'data_time': str(ds.time.values),
            'variables': list(ds.data_vars),
            'grid_size': f"{temp_var.shape[0]}x{temp_var.shape[1]}",
            'lat_range': f"{float(ds.latitude.min()):.2f}°N - {float(ds.latitude.max()):.2f}°N",
            'lon_range': f"{float(ds.longitude.min()):.2f}°E - {float(ds.longitude.max()):.2f}°E",
            'institution': ds.attrs.get('institution', 'Unknown'),
            'model': 'ERA5 reanalysis',
        }

        ds.close()

        return render_template('ecmwf_simple.html',
                               temp_data=temp_data,
                               info=info,
                               now=datetime.now().strftime("%Y-%m-%d %H:%M"))

    except Exception as e:
        return f"读取错误: {str(e)}", 500


@app.route('/forecast')
def weather_forecast():
    """天气预报主页面 - 修复版"""
    try:
        from forecast_visualizer import ForecastVisualizer

        visualizer = ForecastVisualizer()

        # 加载预报数据
        df = visualizer.load_forecast_data(use_real_data=True)
        data_source = df.attrs.get('source', 'ECMWF预报数据')

        print(f"数据加载成功，共{len(df)}条记录")
        print(f"时间范围: {df['time'].min()} 到 {df['time'].max()}")
        print(f"温度范围: {df['temperature'].min():.1f}°C 到 {df['temperature'].max():.1f}°C")

        # 生成图表
        temp_chart = visualizer.create_temperature_forecast_chart(df)
        precip_chart = visualizer.create_precipitation_probability_chart(df)

        # 生成天气摘要
        summary = visualizer.create_weather_summary_card(df)

        # AI分析 - 使用安全的文本
        forecast_text = f"杭州天气预报："
        for day in summary:
            forecast_text += f"{day['date']}{day['weather']}，温度{day['temp_range']}；"

        # 调用AI分析，如果失败使用备用文本
        try:
            ai_analysis = get_ai_analysis(forecast_text)
        except Exception as ai_error:
            print(f"AI分析失败: {ai_error}")
            ai_analysis = "AI分析：基于ECMWF预报数据，未来三天杭州天气以变化为主，建议关注最新预报更新。温度适中，降水概率存在不确定性，请携带雨具以防万一。"

        return render_template('forecast.html',
                               summary=summary,
                               temp_chart=temp_chart,
                               precip_chart=precip_chart,
                               ai_analysis=ai_analysis,
                               data_source=data_source,
                               now=datetime.now().strftime("%Y-%m-%d %H:%M"))

    except Exception as e:
        print(f"预报页面错误: {e}")
        import traceback
        traceback.print_exc()

        # 提供备用的简单数据
        backup_summary = [
            {
                'date': datetime.now().strftime('%m月%d日'),
                'weekday': ['周一', '周二', '周三', '周四', '周五', '周六', '周日'][datetime.now().weekday()],
                'weather': '多云 ⛅',
                'weather_color': '#bdc3c7',
                'temp_range': '15~22°C',
                'avg_temp': '18.5',
                'precip_prob': '20%',
                'humidity': '65%',
                'wind': '3.2 m/s',
                'comfort': '舒适',
            }
        ]

        return render_template('forecast.html',
                               summary=backup_summary,
                               temp_chart='charts/temperature_forecast.png' if os.path.exists(
                                   'static/charts/temperature_forecast.png') else '',
                               precip_chart='charts/precipitation_forecast.png' if os.path.exists(
                                   'static/charts/precipitation_forecast.png') else '',
                               ai_analysis='基于ECMWF数值预报，未来三天杭州地区天气总体平稳，温度适中，有零星降水可能。',
                               data_source='系统维护中（使用示例数据）',
                               now=datetime.now().strftime("%Y-%m-%d %H:%M"))


@app.route('/advanced-forecast')
def advanced_forecast():
    """专业预报展示页面"""
    try:
        print(f"\n{'=' * 60}")
        print(f"📡 开始获取专业预报数据 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        # 1. 获取72小时精细化预报
        print("1. 获取72小时精细化预报...")
        detailed_72h = forecast_service.fetch_detailed_72h_forecast()
        print(f"   结果: {'成功' if detailed_72h else '失败'}")

        # 2. 获取多模式7天预报（关键修改：改为7天）
        print("2. 获取多模式预报（7天）...")
        multi_model = forecast_service.fetch_multi_model_forecast(forecast_days=7)  # 改为7
        print(f"   获取到 {len(multi_model)} 个模型: {list(multi_model.keys())}")

        # 调试：查看获取了哪些模型
        for model_key, model_info in multi_model.items():
            if 'data' in model_info and 'timestamps' in model_info['data']:
                timestamps = model_info['data']['timestamps']
                print(f"   {model_key}: {len(timestamps)} 个时间点")
                if timestamps:
                    print(f"     时间范围: {timestamps[0]} 到 {timestamps[-1]}")

        # 3. 生成7天摘要（关键修改：改为7天）
        print("3. 生成7天摘要...")
        summary_10day = forecast_service.generate_10day_summary(multi_model)
        print(f"   生成 {len(summary_10day)} 天的摘要")

        # 4. 准备AI分析
        ai_analysis_text = prepare_ai_analysis_text(detailed_72h, summary_10day, multi_model)

        print(f"✅ 数据准备完成")
        print(f"{'=' * 60}\n")
        # 在return语句前添加：
        print(f"DEBUG - 传给模板的数据:")
        print(f"  summary_10day 长度: {len(summary_10day)}")
        for i, day in enumerate(summary_10day):
            print(f"  第{i}天: {day.get('date')} {day.get('weekday')}")

        return render_template('advanced_forecast.html',
                               detailed_72h=detailed_72h,
                               multi_model=multi_model,
                               summary_10day=summary_10day,
                               ai_analysis_text=ai_analysis_text,
                               now=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    except Exception as e:
        print(f"❌ 准备预报数据时出错: {str(e)}")
        import traceback
        traceback.print_exc()

        return render_template('advanced_forecast.html',
                               detailed_72h={},
                               multi_model={},
                               summary_10day=[],
                               ai_analysis_text="数据加载失败",
                               now=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))


def prepare_ai_analysis_text(detailed_72h: Dict, summary_10day: List[Dict], multi_model: Dict) -> str:
    """准备给AI分析的文本"""
    text_parts = []

    # 72小时精细化数据摘要
    if detailed_72h and "data" in detailed_72h:
        temps = detailed_72h["data"].get("temperature_2m", [])
        precips = detailed_72h["data"].get("precipitation", [])
        hours = detailed_72h.get("hours", [])

        if temps and len(temps) >= 24:
            text_parts.append("【未来24小时精细化预报】")
            for i in range(min(24, len(hours))):
                if i % 6 == 0:  # 每6小时一个点
                    text_parts.append(f"{hours[i]}: {temps[i]}°C, 降水{precips[i]}mm")

    # 10天摘要
    if summary_10day:
        text_parts.append("\n【未来10天趋势预报】")
        for i, day in enumerate(summary_10day[:7]):  # 前7天
            conf_symbol = "🔴" if day["confidence"] == "低" else "🟡" if day["confidence"] == "中" else "🟢"
            text_parts.append(
                f"{day['date']}({day['weekday']}): {day['weather']} "
                f"{day['temp_min']}~{day['temp_max']}°C "
                f"(降水概率{day['precip_prob']}%) {conf_symbol}"
            )

    # 多模式对比摘要
    if multi_model and len(multi_model) > 1:
        text_parts.append("\n【多模式预报对比】")
        for model_key, model_data in multi_model.items():
            if model_key != "ensemble":
                text_parts.append(f"- {model_data['name']}: 已获取数据")
        if "ensemble" in multi_model:
            text_parts.append("- 集合预报: 已生成多模式统计")

    return "\n".join(text_parts)


@app.route('/generate-ai-analysis', methods=['POST'])
def generate_ai_analysis():
    """生成AI分析报告 - 增加超时和重试"""
    try:
        data = request.json
        analysis_text = data.get('analysis_text', '')

        if not analysis_text:
            return jsonify({"success": False, "error": "缺少分析文本"})

        # 简化分析文本，避免太长
        if len(analysis_text) > 2000:
            analysis_text = analysis_text[:2000] + "... [数据过长已截断]"

        # 尝试调用DeepSeek API（带重试）
        max_retries = 2
        timeout_seconds = 45  # 增加超时时间

        for attempt in range(max_retries):
            try:
                api_key = "REMOVED_KEY_5"  # 替换为你的API Key
                url = "https://api.deepseek.com/v1/chat/completions"

                prompt = f"""
                你是一名资深气象预报员。请基于以下杭州天气预报数据，生成一份简洁实用的分析报告：

                {analysis_text}

                请包含：
                1. 未来3天关键天气
                2. 重要气象风险
                3. 给市民的实用建议
                4. 预报可信度说明

                要求：专业但易懂，重点突出，不超过300字。
                """

                headers = {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}"
                }

                payload = {
                    "model": "deepseek-chat",
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.7,
                    "max_tokens": 500  # 限制输出长度
                }

                print(f"尝试第{attempt + 1}次调用DeepSeek API...")
                response = requests.post(url, headers=headers, json=payload, timeout=timeout_seconds)

                if response.status_code == 200:
                    result = response.json()
                    ai_report = result['choices'][0]['message']['content']
                    print("✅ AI分析生成成功")

                    return jsonify({
                        "success": True,
                        "analysis": ai_report
                    })
                else:
                    print(f"⚠️  API调用失败 (尝试{attempt + 1}): {response.status_code}")
                    print(f"响应: {response.text[:200]}")

            except requests.exceptions.Timeout:
                print(f"⚠️  请求超时 (尝试{attempt + 1})")
                if attempt < max_retries - 1:
                    time.sleep(1)  # 重试前等待1秒
                continue

            except Exception as e:
                print(f"⚠️  请求异常 (尝试{attempt + 1}): {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(1)
                continue

        # 所有重试都失败，返回备用分析
        print("❌ 所有API调用尝试都失败，返回备用分析")

        # 智能生成备用分析
        backup_analysis = generate_backup_analysis(analysis_text)

        return jsonify({
            "success": True,
            "analysis": backup_analysis,
            "note": "⚠️ 由于网络问题，本次使用智能备用分析"
        })

    except Exception as e:
        print(f"❌ 生成AI分析时出错: {str(e)}")

        return jsonify({
            "success": False,
            "error": str(e),
            "analysis": "抱歉，AI分析服务暂时不可用。请检查网络连接或稍后重试。"
        })


def generate_backup_analysis(analysis_text: str) -> str:
    """智能生成备用分析"""
    try:
        # 从文本中提取关键信息
        lines = analysis_text.split('\n')

        # 提取温度信息
        temps = []
        for line in lines:
            if '°C' in line or '温度' in line:
                temps.append(line)

        # 提取降水信息
        precips = []
        for line in lines:
            if 'mm' in line or '降水' in line or '雨' in line:
                precips.append(line)

        # 生成分析
        analysis = "**杭州天气智能分析（备用版本）**\n\n"

        if temps:
            analysis += "**温度趋势：**"
            analysis += "未来三天温度总体" + ("偏高" if any('25' in t for t in temps[:3]) else "适中") + "。"
            analysis += "\n\n"

        if precips:
            analysis += "**降水情况：**"
            if any('雨' in p for p in precips[:3]):
                analysis += "明后两天可能有降雨过程，建议携带雨具。"
            else:
                analysis += "未来三天无明显降水，适宜户外活动。"
            analysis += "\n\n"

        analysis += "**生活建议：**"
        analysis += "1. 关注最新天气预报更新\n"
        analysis += "2. 适时增减衣物\n"
        analysis += "3. 雨天注意交通安全\n\n"

        analysis += "*注：由于网络限制，本次为简化分析。*"

        return analysis

    except:
        # 最后的备用方案
        return """**杭州天气分析报告**

**整体趋势：** 未来72小时天气总体平稳，温度适中。

**关键天气：** 当前预报显示无明显强降水过程。

**生活建议：** 适宜户外活动，建议关注最新预报更新。

*注：本次分析为简化版本，详细分析请稍后重试。*"""


# 在现有路由后添加新路由
@app.route('/history')
def history_home():
    """历史分析主页 - 重定向到年度分析"""
    return redirect(url_for('history_yearly', year=datetime.now().year - 1))


@app.route('/history/yearly')
def history_yearly_index():
    """年度历史分析首页 - 默认跳转到最近一年"""
    available_years = analyzer.get_available_years()
    if available_years:
        return redirect(url_for('history_yearly', year=available_years[-1]))
    else:
        return render_template('error.html', message="无可用历史数据", details="请检查数据文件是否正确加载")


@app.route('/history/yearly/<int:year>')
def history_yearly(year):
    """年度详细分析页面"""
    try:
        available_years = analyzer.get_available_years()
        if year not in available_years:
            return render_template('error.html', message=f"找不到 {year} 年的数据", details=f"可用年份: {available_years}"), 404
            
        # 获取请求参数中的气候态
        climatology_period = request.args.get('climatology', '8110')

        # 1. 获取年度分析数据
        result = analyzer.analyze_year(year, climatology_period=climatology_period)
        
        # 2. 生成图表
        chart_gen = ChartGenerator()
        charts = {}
        
        # 2.1 月度对比图 (传入年份)
        charts['monthly_comparison'] = chart_gen.create_monthly_comparison_chart(
            result['monthly_data'], 
            analyzer.climatology,
            year=year
        )
        
        # 2.2 温度分布图 (需要获取当年原始数据)
        year_data = analyzer.data[analyzer.data['year'] == year]
        charts['temp_distribution'] = chart_gen.create_daily_temp_distribution(year_data)
        
        # 2.3 风玫瑰图 (默认全年)
        charts['wind_rose'] = chart_gen.create_wind_rose_chart(year_data)

        # 3. AI分析报告 (构造Prompt - 历史气候分析版)
        stats = result['stats']
        comparison = result['comparison']
        
        # 安全获取 comfort 数据 (提前获取以供 AI 分析使用)
        comfort_data = result.get('comfort', {
            "counts": {"comfortable": 0, "hot": 0, "cold": 0},
            "total_days": 1
        })
        
        # 提取显著极端事件
        extreme_summary = ""
        if result['extremes']:
            top_events = result['extremes'][:3]
            extreme_summary = "、".join([f"{e['date']}{e['type']}({e['value']})" for e in top_events])
        else:
            extreme_summary = "本年度无显著极端天气事件"

        ai_prompt = f"""
        请扮演一位资深气候分析师，为《杭州{year}年气候公报》撰写一段年度气候综述。
        
        【核心数据】：
        1. 气温特征：年均温{stats['avg_temp']}°C，较常年{comparison['avg_temp']['trend']}{comparison['avg_temp']['diff']}°C。
        2. 降水特征：年降水{stats['total_precip']}mm，较常年{comparison['total_precip']['trend']}{comparison['total_precip']['percent']}%。
        3. 极端天气：{extreme_summary}。
        4. 舒适度：全年舒适天数{comfort_data['counts']['comfortable']}天，炎热天数{comfort_data['counts']['hot']}天，寒冷天数{comfort_data['counts']['cold']}天。

        【撰写要求】：
        1. **气候背景评价**：首先定性评价该年是偏暖/偏冷、偏湿/偏干年份。
        2. **极端事件回顾**：重点回顾上述提到的极端事件，分析其出现的季节特征（如夏季高温热浪、梅雨期强降水等）。
        3. **综合影响分析**：基于数据分析该年气候对城市运行（如供电压力、防汛抗旱）和市民生活的具体影响。
        4. **风格**：专业、客观、数据驱动，避免使用“建议出门带伞”等天气预报类语言。
        5. **格式**：输出HTML格式，重点数据或结论使用<b>标签加粗。字数控制在300字左右。
        """
        
        # 调用AI接口 (如果失败则使用备用文本)
        try:
            ai_report = get_ai_analysis(ai_prompt)
        except:
            trend_desc = "偏暖" if comparison['avg_temp']['diff'] > 0 else "偏冷"
            precip_desc = "偏多" if comparison['total_precip']['diff'] > 0 else "偏少"
            ai_report = f"""
            <p><b>总体评价：</b>{year}年杭州气候特征表现为<b>{trend_desc}{precip_desc}</b>。
            年平均气温为{stats['avg_temp']}°C，较常年{comparison['avg_temp']['trend']}{abs(comparison['avg_temp']['diff'])}°C；
            年降水量{stats['total_precip']}mm，较常年{comparison['total_precip']['trend']}{abs(comparison['total_precip']['percent'])}%。</p>
            <p><b>影响评估：</b>本年度极端天气事件频发，需重点关注夏季高温和汛期强降水对城市运行的影响。建议市民根据季节变化及时调整生活起居，政府部门加强极端天气预警响应机制。</p>
            """
            
        # 修正图表路径 (移除 static/ 前缀以适配 url_for)
        for key, path in charts.items():
            if path:
                charts[key] = path.replace('static/', '')

        return render_template('history_yearly.html',
                               year=year,
                               available_years=available_years,
                               climatology_period=climatology_period,
                               stats=result['stats'],
                               comparison=result['comparison'],
                               extremes=result['extremes'],
                               comfort=comfort_data,
                               charts=charts,
                               ai_report=ai_report)

    except Exception as e:
        print(f"Error in history_yearly: {e}")
        import traceback
        traceback.print_exc()
        return render_template('error.html', message="分析生成失败", details=str(e)), 500


@app.route('/api/wind_rose')
def api_wind_rose():
    """动态获取风玫瑰图API"""
    year = request.args.get('year', type=int)
    month = request.args.get('month', type=int)
    
    if not year:
        return jsonify({"error": "Missing year"}), 400
        
    try:
        # 获取当年数据
        if analyzer.data is None:
            analyzer.load_data()
            
        year_data = analyzer.data[analyzer.data['year'] == year]
        
        chart_gen = ChartGenerator()
        chart_path = chart_gen.create_wind_rose_chart(year_data, month)
        
        if chart_path:
            return jsonify({"url": url_for('static', filename=chart_path.replace('static/', ''))})
        else:
            return jsonify({"error": "No data for chart"}), 404
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500


from sounding_parser import SoundingDataParser
from sounding_plotter import SoundingPlotter
from sounding_analyzer import SoundingAnalyzer
# 导入农业模块
from crop_database import crop_db
from agro_calculator import agro_calculator
from agro_alert_engine import agro_alert_engine
from farming_ai_adviser import ai_adviser

# 初始化探空服务
sounding_parser = SoundingDataParser()
sounding_plotter = SoundingPlotter()
sounding_analyzer = SoundingAnalyzer()

@app.route('/upperair')
def upperair_home():
    """探空数据分析主页"""
    return render_template('upperair.html', 
                         now=datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"))

@app.route('/upperair/data')
def get_upperair_data():
    """获取探空数据API"""
    date_str = request.args.get('date') # 格式: YYYY-MM-DD HH:MM
    station_id = request.args.get('station', '58457') # 默认杭州
    
    target_time = None
    if date_str:
        try:
            raw_time = datetime.strptime(date_str, "%Y-%m-%d %H:%M")
            # 将时间规整到最近的 00Z 或 12Z
            # 逻辑：如果小时 < 6，归为 00Z；如果在 6-18 之间，归为 12Z；如果 > 18，归为次日 00Z
            if raw_time.hour < 6:
                target_time = raw_time.replace(hour=0, minute=0, second=0, microsecond=0)
            elif raw_time.hour < 18:
                target_time = raw_time.replace(hour=12, minute=0, second=0, microsecond=0)
            else:
                target_time = (raw_time + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
                
            print(f"🕒 请求时间: {date_str} -> 调整为标准探空时次: {target_time.strftime('%Y-%m-%d %H:%M')}")
        except ValueError:
            pass
            
    # 获取数据
    result = sounding_parser.fetch_sounding_data(station_id, target_time)
    
    if result['success']:
        # 解析数据
        parsed_data = sounding_parser.parse_sounding_data(result['raw_data'])
        
        # 保存数据
        sounding_parser.save_to_csv(parsed_data, f"sounding_{station_id}_{parsed_data['header'].get('time_utc', 'unknown').replace(' ', '_')}.csv")
        
        # 分析数据
        analysis = sounding_analyzer.analyze(
            pd.DataFrame(parsed_data['levels']), 
            parsed_data['indices']
        )
        
        # 添加元数据
        analysis['metadata'] = parsed_data['header']
        
        # 添加完整层级数据（用于前端展示原始数据）
        analysis['raw_levels'] = parsed_data['levels']
        
        return jsonify({
            "success": True,
            "data": analysis
        })
    else:
        return jsonify({
            "success": False,
            "error": result.get('error', 'Unknown error')
        })

@app.route('/upperair/plot/<plot_type>')
def get_upperair_plot(plot_type):
    """获取探空图表API"""
    date_str = request.args.get('date')
    station_id = request.args.get('station', '58457')
    
    target_time = None
    if date_str:
        try:
            raw_time = datetime.strptime(date_str, "%Y-%m-%d %H:%M")
            # 同样应用时间规整逻辑
            if raw_time.hour < 6:
                target_time = raw_time.replace(hour=0, minute=0, second=0, microsecond=0)
            elif raw_time.hour < 18:
                target_time = raw_time.replace(hour=12, minute=0, second=0, microsecond=0)
            else:
                target_time = (raw_time + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        except ValueError:
            pass
            
    # 获取数据 (这里简化处理，实际应该缓存数据避免重复请求)
    result = sounding_parser.fetch_sounding_data(station_id, target_time)
    
    if result['success']:
        parsed_data = sounding_parser.parse_sounding_data(result['raw_data'])
        df = pd.DataFrame(parsed_data['levels'])
        
        try:
            # 生成图表
            plot_path = sounding_plotter.plot(plot_type, df, parsed_data['header'])
            return jsonify({
                "success": True,
                "url": url_for('static', filename=plot_path.replace('static/', ''))
            })
        except Exception as e:
            return jsonify({"success": False, "error": str(e)})
    else:
        return jsonify({"success": False, "error": "Failed to fetch data"})

@app.route('/history/trend')
def history_trend():
    """长期气候变化趋势页面"""
    try:
        # 获取趋势数据
        trend_result = analyzer.analyze_trend()
        
        # 准备图表数据
        series = trend_result['series']
        trends = trend_result['trends']
        
        # 提取年份列表
        years = [d['year'] for d in series]
        
        # 1. 气温趋势图数据
        temp_data = {
            'years': years,
            'values': [d['avg_temp'] for d in series],
            'trend_line': [(trends['temp']['slope'] * y + trends['temp']['intercept']) for y in years],
            'rate': trends['temp']['rate_per_decade']
        }
        
        # 2. 降水趋势图数据
        precip_data = {
            'years': years,
            'values': [d['total_precip'] for d in series],
            'rainy_days': [d['rainy_days'] for d in series],
            'rate': trends['precip']['rate_per_decade']
        }
        
        # 3. 极端天气图数据
        extreme_data = {
            'years': years,
            'hot_days': [d['hot_days'] for d in series],
            'cold_days': [d['cold_days'] for d in series],
            'snow_days': [d['snow_days'] for d in series],
            'heavy_rain_days': [d.get('heavy_rain_days', 0) for d in series],
            'thunder_days': [d.get('thunder_days', 0) for d in series]
        }
        
        return render_template('history_trend.html',
                             temp_data=temp_data,
                             precip_data=precip_data,
                             extreme_data=extreme_data,
                             start_year=years[0] if years else "N/A",
                             end_year=years[-1] if years else "N/A")
                             
    except Exception as e:
        print(f"Error in history_trend: {e}")
        import traceback
        traceback.print_exc()
        return render_template('error.html', message="趋势分析生成失败", details=str(e)), 500


# --- 农业气象服务模块路由 ---

def build_agro_forecast_list(multi_model: Dict, forecast_days: int = 7) -> List[Dict]:
    model_data = (multi_model.get('ecmwf_ifs', {}) or multi_model.get('best_match', {}))
    if not model_data:
        for k, v in multi_model.items():
            if k != 'ensemble' and isinstance(v, dict):
                model_data = v
                break

    processed = model_data.get('data', {}) if isinstance(model_data, dict) else {}

    forecast_list: List[Dict] = []
    if processed:
        timestamps = processed.get('timestamps', [])
        hourly_data = processed.get('data', {}) or {}
        temps = hourly_data.get('temperature_2m', [])
        precips = hourly_data.get('precipitation', [])
        humidities = hourly_data.get('relative_humidity_2m', [])
        winds = hourly_data.get('wind_speed_10m', [])

        et0s = hourly_data.get('et0_fao_evapotranspiration', [])
        soil_moistures = hourly_data.get('soil_moisture_0_to_7cm', [])
        radiations = hourly_data.get('shortwave_radiation', [])

        daily_map = {}
        min_len = min(len(timestamps), len(temps), len(precips))

        for i in range(min_len):
            ts = timestamps[i]
            date_str = ts.split(' ')[0]
            if date_str not in daily_map:
                daily_map[date_str] = {
                    'temps': [], 'precip': 0.0, 'humidity': [], 'wind': [], 
                    'et0': 0.0, 'soil_moisture': [], 'radiation': []
                }
            if temps[i] is not None:
                daily_map[date_str]['temps'].append(temps[i])
            if precips[i] is not None:
                daily_map[date_str]['precip'] += precips[i]
            if i < len(humidities) and humidities[i] is not None:
                daily_map[date_str]['humidity'].append(humidities[i])
            if i < len(winds) and winds[i] is not None:
                daily_map[date_str]['wind'].append(winds[i])
            if i < len(et0s) and et0s[i] is not None:
                daily_map[date_str]['et0'] += et0s[i]
            if i < len(soil_moistures) and soil_moistures[i] is not None:
                daily_map[date_str]['soil_moisture'].append(soil_moistures[i])
            if i < len(radiations) and radiations[i] is not None:
                daily_map[date_str]['radiation'].append(radiations[i])

        for date_str in sorted(daily_map.keys()):
            data = daily_map[date_str]
            if not data['temps']:
                continue
            humidity_avg = sum(data['humidity']) / len(data['humidity']) if data['humidity'] else 70
            wind_avg = sum(data['wind']) / len(data['wind']) if data['wind'] else 3
            soil_moisture_avg = sum(data['soil_moisture']) / len(data['soil_moisture']) if data['soil_moisture'] else 0
            radiation_avg = sum(data['radiation']) / len(data['radiation']) if data['radiation'] else 0
            
            # 计算有效降水 (降水 - ET0，可为负)
            precip = data['precip']
            et0 = data['et0'] or 0
            precip_eff = (precip - et0) if precip is not None else 0
            
            forecast_list.append({
                'date': date_str,
                'temp_min': round(min(data['temps']), 1),
                'temp_max': round(max(data['temps']), 1),
                'temp_avg': round(sum(data['temps']) / len(data['temps']), 1),
                'precip': round(precip, 1),
                'et0': round(et0, 1),
                'precip_eff': round(precip_eff, 1),
                'wind': round(wind_avg, 1),
                'wind_speed': round(wind_avg, 1),
                'humidity': round(humidity_avg, 0),
                'soil_moisture': round(soil_moisture_avg, 1),
                'radiation': round(radiation_avg, 1)
            })

    if not forecast_list:
        today = datetime.now().date()
        for i in range(forecast_days):
            d = today + timedelta(days=i)
            temp_min = 8 + i * 0.5
            temp_max = 16 + i * 0.6
            precip = 0.0 if i % 3 != 0 else 2.0
            wind = 3.0 + (i % 2) * 0.6
            humidity = 60 + (i % 3) * 8
            forecast_list.append({
                'date': d.strftime("%Y-%m-%d"),
                'temp_min': round(temp_min, 1),
                'temp_max': round(temp_max, 1),
                'temp_avg': round((temp_min + temp_max) / 2, 1),
                'precip': round(precip, 1),
                'precip_eff': round(precip - 2.0, 1),
                'wind': round(wind, 1),
                'wind_speed': round(wind, 1),
                'humidity': humidity,
                'soil_moisture': 0,
                'radiation': 0
            })

    return forecast_list

def get_historical_gdd(crop_id, crop_info, sowing_date_str=None):
    """获取作物本生长季的历史积温"""
    gdd_base = crop_info.get('gdd_base', 10)
    gdd_total = crop_info.get('gdd_total', 0)
    
    if gdd_total == 0:
        return {"current": 0, "total": 0, "is_active": False}

    today = datetime.now()
    current_year = today.year
    start_date = None
    gdd_start = crop_info.get('gdd_start')

    if gdd_start == "user" or crop_id == "bokchoy":
        if not sowing_date_str:
            return {"current": 0, "total": gdd_total, "is_active": False, "note": "请先设置播种日期"}
        try:
            start_date = datetime.strptime(sowing_date_str, "%Y-%m-%d")
        except:
            return {"current": 0, "total": gdd_total, "is_active": False, "note": "播种日期格式需为YYYY-MM-DD"}
    elif gdd_start:
        try:
            start_date = datetime.strptime(f"{current_year}-{gdd_start}", "%Y-%m-%d")
        except:
            start_date = None
    else:
        stages = crop_info.get('stages', [])
        if stages:
            first_stage = stages[0]
            start_md = first_stage.get('start', '01-01')
            try:
                start_date = datetime.strptime(f"{current_year}-{start_md}", "%Y-%m-%d")
            except:
                start_date = None

    if not start_date:
        return {"current": 0, "total": gdd_total, "is_active": False}

    if start_date > today:
        return {"current": 0, "total": gdd_total, "is_active": False}
        
    yesterday = today - timedelta(days=1)
    if yesterday < start_date:
        return {"current": 0, "total": gdd_total, "is_active": True, "start_date": start_date.strftime("%Y-%m-%d")}
    
    # 获取历史数据
    print(f"🔄 计算GDD: {crop_id}, 周期: {start_date.strftime('%Y-%m-%d')} 至 {yesterday.strftime('%Y-%m-%d')}")
    hist_data = forecast_service.fetch_historical_data(
        start_date.strftime("%Y-%m-%d"), 
        yesterday.strftime("%Y-%m-%d")
    )
    
    hist_gdd = 0
    if hist_data and 'daily' in hist_data:
        daily = hist_data['daily']
        t_max = daily.get('temperature_2m_max', [])
        t_min = daily.get('temperature_2m_min', [])
        
        for i in range(len(t_max)):
            if t_max[i] is not None and t_min[i] is not None:
                avg = (t_max[i] + t_min[i]) / 2
                gdd = max(0, avg - gdd_base)
                hist_gdd += gdd
    
    print(f"✅ GDD计算完成: {hist_gdd:.1f}")
    return {
        "current": round(hist_gdd, 1),
        "total": gdd_total,
        "is_active": True,
        "start_date": start_date.strftime("%Y-%m-%d")
    }

@app.route('/agro-dashboard')
def agro_dashboard():
    """农业气象总览页"""
    try:
        # 1. 获取所有作物基本信息
        crops = crop_db.get_all_crops()
        
        # 2. 获取未来7天预报
        multi_model = forecast_service.fetch_multi_model_forecast(forecast_days=7)
        forecast_list = build_agro_forecast_list(multi_model, forecast_days=7)
                
        # 3. 生成预警
        alerts = agro_alert_engine.generate_alerts(forecast_list)
        
        # 4. 计算每个作物的适宜度
        crop_status = []
        for crop in crops:
            crop_id = crop['id']
            stage = crop_db.get_current_stage(crop_id)
            today_weather = forecast_list[0] if forecast_list else {}
            score, deductions = agro_calculator.calculate_suitability_score(stage, today_weather)
            
            crop_status.append({
                'id': crop_id,
                'name': crop['name'],
                'icon': crop['icon'],
                'stage': stage['name'] if stage else '休眠',
                'score': int(score),
                'status': '适宜' if score > 80 else '一般' if score > 60 else '不适宜'
            })
        
        # 5. 生成AI全域研判
        ai_summary = ai_adviser.generate_dashboard_summary(alerts, forecast_list, crop_status)

        return render_template('agro_dashboard.html', 
                             crops=crop_status,
                             alerts=alerts,
                             forecast=forecast_list,
                             ai_summary=ai_summary,
                             now=datetime.now().strftime("%Y-%m-%d"))
                             
    except Exception as e:
        import traceback
        traceback.print_exc()
        return render_template('error.html', message="农业模块加载失败", details=str(e)), 500

@app.route('/crop/<crop_id>')
def crop_detail(crop_id):
    """作物详情页"""
    crop = crop_db.get_crop_info(crop_id)
    if not crop:
        return "作物不存在", 404
    
    # 确保ID存在于字典中，供模板判断
    crop['id'] = crop_id
        
    stage = crop_db.get_current_stage(crop_id)
    if not stage:
        stage = {"name": "休眠", "start": "", "end": "", "temp_opt": 0, "water_need": "low"}

    multi_model = forecast_service.fetch_multi_model_forecast(forecast_days=7)
    forecast_list = build_agro_forecast_list(multi_model, forecast_days=7)
    all_alerts = agro_alert_engine.generate_alerts(forecast_list)
    crop_alerts = [a for a in all_alerts if a.get('crop_id') == crop_id]
    
    # 计算GDD
    sowing_date = request.args.get('sowing_date')
    gdd_info = get_historical_gdd(crop_id, crop, sowing_date_str=sowing_date)
    
    # 预测未来7天GDD
    forecast_gdd = 0
    if gdd_info.get('is_active'):
        gdd_base = crop.get('gdd_base', 10)
        for day in forecast_list:
            avg = day.get('temp_avg', 0)
            forecast_gdd += max(0, avg - gdd_base)
    
    gdd_info['forecast'] = round(forecast_gdd, 1)
    
    # 计算百分比
    if gdd_info['total'] > 0 and gdd_info.get('is_active'):
        gdd_info['percent'] = min(100, round(gdd_info['current'] / gdd_info['total'] * 100, 1))
        gdd_info['forecast_percent'] = min(100 - gdd_info['percent'], round(forecast_gdd / gdd_info['total'] * 100, 1))
    else:
        gdd_info['percent'] = 0
        gdd_info['forecast_percent'] = 0
        
    # 获取适宜降水量
    water_need_val = crop_db.get_water_need_value(stage.get('water_need', 'none'))
    net_precip_eff = round(sum([d.get('precip_eff', 0) or 0 for d in forecast_list]), 1)
    
    return render_template('crop_detail.html',
                         crop=crop,
                         current_stage=stage,
                         forecast=forecast_list,
                         alerts=crop_alerts,
                         gdd=gdd_info,
                         water_opt=water_need_val,
                         net_precip_eff=net_precip_eff,
                         sowing_date=sowing_date or "",
                         now=datetime.now().strftime("%Y-%m-%d"))

@app.route('/api/agro/advice', methods=['POST'])
def get_agro_advice():
    """获取AI农事建议API"""
    data = request.json
    crop_name = data.get('crop_name')
    stage = data.get('stage')
    weather = data.get('weather')
    alerts = data.get('alerts', [])
    
    result = ai_adviser.get_advice(crop_name, stage, weather, alerts)
    return jsonify(result)



if __name__ == '__main__':
    app.run(debug=True)
