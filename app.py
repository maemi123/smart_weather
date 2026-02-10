import numpy as np
from flask import Flask, render_template, request, jsonify, redirect, url_for
import pandas as pd
import requests
from weather_service import WeatherService
import json
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
    # 获取真实的天气数据
    df = weather_service.get_daily_forecast()
    weather_list = df.to_dict('records')

    # 生成图表
    chart_gen = ChartGenerator()
    temp_chart_path = chart_gen.create_temperature_chart(df)
    precip_chart_path = chart_gen.create_precipitation_chart(df)
    # 尝试生成雷达图，失败时使用备用方案
    radar_chart_path = chart_gen.create_weather_radar_chart(df)
    if radar_chart_path is None:
        radar_chart_path = chart_gen.create_simple_radar_chart(df)
        if radar_chart_path:
            print("[INFO] Using simple radar chart")

    # 将数据转换为文本，供AI分析
    weather_text = "\n".join([
        f"{item['date']}: 最高{item['temp_max']}°C, 最低{item['temp_min']}°C, "
        f"降水{item['precipitation']}mm, {item['weather']}, "
        f"湿度{item['humidity']}%, {item['wind_dir']}{item['wind_scale']}级"
        for item in weather_list
    ])

    # 获取AI分析
    ai_report = get_ai_analysis(weather_text)

    # 渲染到模板
    return render_template('index.html',
                           weather_data=weather_list,
                           ai_report=ai_report,
                           data_source="心知天气API",
                           now=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                           temp_chart=temp_chart_path.replace('static/', ''),
                           precip_chart=precip_chart_path.replace('static/', ''),
                           radar_chart=radar_chart_path.replace('static/', ''))


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
            'snow_days': [d['snow_days'] for d in series]
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

        daily_map = {}
        min_len = min(len(timestamps), len(temps), len(precips))

        for i in range(min_len):
            ts = timestamps[i]
            date_str = ts.split(' ')[0]
            if date_str not in daily_map:
                daily_map[date_str] = {'temps': [], 'precip': 0.0, 'humidity': [], 'wind': []}
            if temps[i] is not None:
                daily_map[date_str]['temps'].append(temps[i])
            if precips[i] is not None:
                daily_map[date_str]['precip'] += precips[i]
            if i < len(humidities) and humidities[i] is not None:
                daily_map[date_str]['humidity'].append(humidities[i])
            if i < len(winds) and winds[i] is not None:
                daily_map[date_str]['wind'].append(winds[i])

        for date_str in sorted(daily_map.keys()):
            data = daily_map[date_str]
            if not data['temps']:
                continue
            humidity_avg = sum(data['humidity']) / len(data['humidity']) if data['humidity'] else 70
            wind_avg = sum(data['wind']) / len(data['wind']) if data['wind'] else 3
            forecast_list.append({
                'date': date_str,
                'temp_min': round(min(data['temps']), 1),
                'temp_max': round(max(data['temps']), 1),
                'temp_avg': round(sum(data['temps']) / len(data['temps']), 1),
                'precip': round(data['precip'], 1),
                'wind': round(wind_avg, 1),
                'wind_speed': round(wind_avg, 1),
                'humidity': round(humidity_avg, 0)
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
                'wind': round(wind, 1),
                'wind_speed': round(wind, 1),
                'humidity': humidity
            })

    return forecast_list

@app.route('/agro-dashboard')
def agro_dashboard():
    """农业气象总览页"""
    try:
        # 1. 获取所有作物基本信息
        crops = crop_db.get_all_crops()
        
        # 2. 获取未来7天预报 (复用 forecast_service)
        # 注意：这里我们使用 Open-Meteo 数据，因为它包含更多农业参数
        forecast_7d = forecast_service.fetch_detailed_72h_forecast() # 这里实际需要长期的，暂时用这个代替或修改 fetch
        # 为了演示，我们先用 fetch_multi_model_forecast 获取 ECMWF 数据
        multi_model = forecast_service.fetch_multi_model_forecast(forecast_days=7)
        
        forecast_list = build_agro_forecast_list(multi_model, forecast_days=7)
                
        # 3. 生成预警
        alerts = agro_alert_engine.generate_alerts(forecast_list)
        
        # 4. 计算每个作物的适宜度 (Mock)
        crop_status = []
        for crop in crops:
            crop_id = crop['id']
            stage = crop_db.get_current_stage(crop_id)
            
            # 获取今天的天气
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
            
        return render_template('agro_dashboard.html', 
                             crops=crop_status,
                             alerts=alerts,
                             forecast=forecast_list,
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
        
    stage = crop_db.get_current_stage(crop_id)
    if not stage:
        stage = {"name": "休眠", "start": "", "end": "", "temp_opt": 0, "water_need": "low"}

    multi_model = forecast_service.fetch_multi_model_forecast(forecast_days=7)
    forecast_list = build_agro_forecast_list(multi_model, forecast_days=7)
    all_alerts = agro_alert_engine.generate_alerts(forecast_list)
    crop_alerts = [a for a in all_alerts if a.get('crop_id') == crop_id]
    
    return render_template('crop_detail.html',
                         crop=crop,
                         current_stage=stage,
                         forecast=forecast_list,
                         alerts=crop_alerts,
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
