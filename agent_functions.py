"""
智慧天气 Agent - 基于 DeepSeek Function Calling 的智能天气助手 v2
支持：多模式预报、探空分析、历史气候、农业气象、ML校正、动态图表生成
"""
import os
import json
import base64
import io
import sys
import traceback
import requests
import threading
from datetime import datetime, timedelta
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from dotenv import load_dotenv

import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm

# ── 中文字体 ──
_CJK_FONT = None
for _fname in fm.findSystemFonts():
    try:
        _fp = fm.FontProperties(fname=_fname)
        _fn = _fp.get_name()
        if any(k in _fn.lower() for k in ['microsoft yahei', 'simhei', 'simsun', 'noto sans cjk', 'wenquanyi']):
            _CJK_FONT = _fp
            break
    except Exception:
        continue
if _CJK_FONT:
    plt.rcParams['font.family'] = _CJK_FONT.get_name()
    plt.rcParams['font.sans-serif'] = [_CJK_FONT.get_name()]
plt.rcParams['axes.unicode_minus'] = False

load_dotenv()
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"

HANGZHOU_LAT = 30.25
HANGZHOU_LON = 120.17

WMO_CODES = {
    0: "晴", 1: "基本晴", 2: "局部多云", 3: "多云",
    45: "雾", 48: "冻雾",
    51: "小雨", 53: "中雨", 55: "强降雨",
    56: "冻雨（轻）", 57: "冻雨（强）",
    61: "小雨", 63: "中雨", 65: "强降雨",
    66: "冻雨（轻）", 67: "冻雨（强）",
    71: "小雪", 73: "中雪", 75: "强降雪", 77: "雪粒",
    80: "小阵雨", 81: "中阵雨", 82: "强阵雨",
    85: "小阵雪", 86: "强阵雪",
    95: "雷暴", 96: "雷暴伴小冰雹", 99: "雷暴伴强冰雹",
}

MODEL_ALIASES = {
    "ec": "ecmwf_ifs", "ecmwf": "ecmwf_ifs",
    "gfs": "gfs_seamless",
    "icon": "icon_global",
    "gem": "gem_global",
    "best": "best_match", "auto": "best_match",
    "ensemble": "ensemble", "eps": "ensemble",
}
MODEL_NAMES = {
    "best_match": "最佳匹配", "ecmwf_ifs": "ECMWF", "gfs_seamless": "GFS",
    "gem_global": "GEM", "icon_global": "ICON", "ensemble": "集合预报",
}

# ═══════════════════════════════════════════════════════════════
# Code Interpreter 模式
# ═══════════════════════════════════════════════════════════════

SYSTEM_PROMPT_CI = """你是"智慧天气"系统的AI助手，为杭州地区用户提供专业天气服务。
通过调用高层函数获取数据，用print()输出结果，用plt画图。

【高层函数 — 每个一行调用，不要自己写底层代码】

1. 实时天气: w = get_current_weather()
   # -> {temp, feels_like, humidity, dew_point, wind_speed, weather_desc, pressure, update_time}

2. 预报: fc = get_forecast_summary(days=3, model='ecmwf_ifs')
   # model可选: ecmwf_ifs(默认), gfs_seamless, icon_global, gem_global, best_match, ensemble
   # -> {summary, daily: [{date, weekday, temp_min, temp_max, precip_total, main_weather, sw_radiation_mean}]}
   # sw_radiation_mean = 日均短波辐射(W/m²)，可用于光伏发电效率分析

3. 探空: snd = get_sounding_analysis(date_str='2026-05-16')
   # 不填date_str取最近时次
   # -> {parameters: {cape_jkg, k_index, lifted_index, shear_0_6km_ms, ...},
   #     risk_assessment: {level, description, hazards}}

4. 历史: hist = get_historical_stats(2024)
   # -> {stats: {avg_temp, total_precip, hot_days, ...}, ew_extremes_top3}

5. 日气候: clim = get_daily_climatology(5, 16)
   # -> {avg_temp, avg_high, avg_low, record_high, record_low, rain_probability}

6. 积温: gdd = calc_crop_gdd('citrus')
   # 水稻=rice, 龙井=tea, 柑橘=citrus, 杨梅=bayberry, 小白菜=bokchoy
   # 小白菜需播种日: calc_crop_gdd('bokchoy', sowing_date='2026-05-01')
   # -> "柑橘 | 积温: 320/1800°C (18%) | 当前阶段: 生理落果期 | 基温: 12°C"

7. 作物信息: info = get_crop_info('tea')
   # -> {name, gdd_base, gdd_total, current_stage: {name, temp_min, temp_opt, temp_max}}

8. 洗车建议: adv = get_washing_advice()
   # -> {verdict, score, reasons}

【代码规范】
- 只调用上面的高层函数，不要自己import模块手写数据访问
- 用print()输出结果，用plt画图（不调savefig）
- 一次run_code完成取数据+分析+画图
- 回答简洁，不dump原始数据"""

TOOLS_CI = [
    {
        "type": "function",
        "function": {
            "name": "run_code",
            "description": "执行Python代码获取数据、分析、绘图。可访问项目所有模块（预报/探空/历史/农业/Open-Meteo）。用print输出文字结果，用plt画图（不调savefig）。一次代码可完成取数据+分析+画图全流程",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "Python代码。不用import matplotlib.use或调plt.savefig，它们由环境自动处理"}
                },
                "required": ["code"]
            }
        }
    }
]


def run_code(code=None):
    """Code Interpreter 沙箱：执行Python代码，返回stdout文本 + matplotlib图表"""
    if not code:
        return {"success": False, "stdout": "", "image_base64": None,
                "error": "code参数为空，请提供Python代码"}
    import re

    # 清理代码
    code = re.sub(r'^import matplotlib\s*\n\s*matplotlib\.use\(.*?\)\s*\n', '', code, flags=re.MULTILINE)
    code = re.sub(r'\n\s*plt\.savefig\(.*?\)\s*\n', '\n', code)
    code = re.sub(r'\n\s*plt\.close\(.*?\)\s*\n', '\n', code)

    stdout_buf = io.StringIO()
    img_buf = io.BytesIO()

    safe_builtins = {
        'print': lambda *a, **k: print(*a, **k, file=stdout_buf),
        'len': len, 'range': range, 'list': list, 'dict': dict, 'set': set, 'tuple': tuple,
        'str': str, 'int': int, 'float': float, 'bool': bool, 'type': type,
        'min': min, 'max': max, 'sum': sum, 'abs': abs, 'round': round,
        'zip': zip, 'enumerate': enumerate, 'sorted': sorted, 'reversed': reversed,
        'True': True, 'False': False, 'None': None,
        'isinstance': isinstance, 'any': any, 'all': all,
        'hasattr': hasattr, 'getattr': getattr,
        'Exception': Exception, 'ValueError': ValueError, 'KeyError': KeyError,
        'IndexError': IndexError, 'TypeError': TypeError,
        'json': json,
    }

    namespace = {
        '__builtins__': {**safe_builtins, '__import__': __import__},
        'plt': plt,
        'np': __import__('numpy'),
        'pd': pd,
        'datetime': datetime,
        'timedelta': timedelta,
        'requests': requests,
        'json': json,
    }

    # 预导入项目模块
    for mod_name in ['advanced_forecast_service', 'history_analyzer',
                       'sounding_parser', 'sounding_analyzer', 'sounding_plotter',
                       'crop_database', 'agro_calculator', 'agro_alert_engine',
                       'ml_correction', 'ml_correction_v2', 'chart_generator']:
        try:
            namespace[mod_name] = __import__(mod_name)
        except Exception:
            pass

    # 暴露高层函数（CI模式核心：LLM直接调用，不造轮子）
    namespace['get_current_weather'] = get_current_weather
    namespace['get_forecast_summary'] = get_forecast
    namespace['get_washing_advice'] = get_washing_advice
    namespace['get_sounding_analysis'] = get_upper_air_data
    namespace['get_historical_stats'] = get_historical_stats
    namespace['get_daily_climatology'] = get_daily_climatology
    namespace['get_crop_info'] = get_crop_info
    # calc_crop_gdd 通过下面注入

    # 积温辅助函数（基于ERA5-Land + ECMWF预报）
    def _calc_crop_gdd(crop_id, sowing_date=None):
        from crop_database import crop_db
        info = crop_db.get_crop_info(crop_id)
        if not info:
            return f"未找到作物: {crop_id}"
        base = info.get('gdd_base', 10)
        total = info.get('gdd_total', 0)
        if total == 0:
            return f"{info['name']}无积温配置"

        today = datetime.now()
        # 确定起始日
        if sowing_date:
            try:
                start = datetime.strptime(sowing_date, '%Y-%m-%d')
            except Exception:
                return f"日期格式错误: {sowing_date}，请用YYYY-MM-DD"
        else:
            gs = info.get('gdd_start', '01-01')
            if gs == 'user':
                return f"{info['name']}需要指定播种日期，请提供sowing_date参数"
            start = datetime(today.year, *map(int, gs.split('-')))

        svc = _get_forecast_svc()
        # 历史积温：用 forecast API + past_days（archive API 无2026年数据）
        hist_gdd = 0
        try:
            days_since_start = (today - start).days
            past_days = min(max(days_since_start, 7), 92)
            hist = requests.get("https://api.open-meteo.com/v1/forecast", params={
                "latitude": 30.25, "longitude": 120.17,
                "past_days": past_days,
                "daily": "temperature_2m_mean",
                "timezone": "Asia/Shanghai"
            }, timeout=15).json()
            daily_data = hist.get('daily', {}) if isinstance(hist, dict) else {}
            times = daily_data.get('time', [])
            temps = daily_data.get('temperature_2m_mean', [])
            for i, t in enumerate(temps):
                if i < len(times) and t is not None and times[i] >= start.strftime('%Y-%m-%d'):
                    hist_gdd += max(0, float(t) - base)
        except Exception:
            hist_gdd = 0

        # 预报积温(ECMWF)
        try:
            fc = svc.fetch_multi_model_forecast(7).get('ecmwf_ifs', {})
            fc_inner = fc.get('data', {}).get('data', {})
            fc_temps = fc_inner.get('temperature_2m', [])
            fc_timestamps = fc.get('data', {}).get('timestamps', [])
            daily_temps = {}
            for i, ts_str in enumerate(fc_timestamps):
                try:
                    dt = datetime.strptime(ts_str, '%Y-%m-%d %H:%M')
                    dk = dt.strftime('%Y-%m-%d')
                    if dk not in daily_temps:
                        daily_temps[dk] = {'tmin': 99, 'tmax': -99}
                    if i < len(fc_temps) and fc_temps[i] is not None:
                        t = fc_temps[i]
                        daily_temps[dk]['tmin'] = min(daily_temps[dk]['tmin'], t)
                        daily_temps[dk]['tmax'] = max(daily_temps[dk]['tmax'], t)
                except Exception:
                    pass
            fc_gdd = sum(max(0, (v['tmax']+v['tmin'])/2 - base) for v in daily_temps.values() if v['tmin'] != 99)
        except Exception:
            fc_gdd = 0

        curr = hist_gdd + fc_gdd
        pct = min(curr / total * 100, 100)
        stage = crop_db.get_current_stage(crop_id)
        return f"{info['name']} | 积温: {curr:.0f}/{total}°C ({pct:.0f}%) | 当前阶段: {stage['name'] if stage else '未知'} | 基温: {base}°C | 起算: {start.strftime('%Y-%m-%d')}"
    namespace['calc_crop_gdd'] = _calc_crop_gdd

    wrapped = f"""
{code}
__fig = plt.gcf()
if __fig.get_axes():
    plt.savefig(_img_buf, format='png', dpi=120, bbox_inches='tight', facecolor='#F5F7FA')
plt.close('all')
"""

    def target(_ns, _wrapped, _img, _stdout):
        _ns['_img_buf'] = _img
        exec(_wrapped, _ns)

    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(target, namespace, wrapped, img_buf, stdout_buf)
            future.result(timeout=15)
    except FutureTimeoutError:
        plt.close('all')
        return {"success": False, "stdout": "", "image_base64": None,
                "error": "代码执行超时(>15秒)，请简化"}
    except SyntaxError as e:
        plt.close('all')
        return {"success": False, "stdout": stdout_buf.getvalue(),
                "image_base64": None, "error": f"第{e.lineno}行语法错误: {e.msg}，请修正缩进"}
    except Exception as e:
        plt.close('all')
        return {"success": False, "stdout": stdout_buf.getvalue(),
                "image_base64": None, "error": f"{type(e).__name__}: {e}，请修正代码重试"}

    img_buf.seek(0)
    img_data = img_buf.read()
    img_b64 = base64.b64encode(img_data).decode('utf-8') if len(img_data) > 100 else None

    stdout_text = stdout_buf.getvalue()
    if len(stdout_text) > 3000:
        stdout_text = stdout_text[:3000] + "\n...(输出已截断)"

    return {"success": True, "stdout": stdout_text, "image_base64": img_b64, "error": None}


# ═══════════════════════════════════════════════════════════════
# Function Calling 模式（保留）
# ═══════════════════════════════════════════════════════════════

SYSTEM_PROMPT_FC = """你是"智慧天气"系统的AI助手，为杭州地区用户提供专业天气服务。

【数据模块】
1. 实时天气 → get_current_weather
2. 多模式预报 → get_forecast（支持ECMWF/GFS/ICON/GEM/ensemble）
3. 探空分析 → get_upper_air_data / get_upper_air_plot（CAPE/K指数/风切变/强对流风险）
4. 历史气候 → get_historical_stats / get_climate_trend / get_daily_climatology（年度统计/趋势/某月某日历史均值极值）
5. 农业气象 → get_crop_info / get_crop_gdd（作物知识库/积温计算）
6. 动态图表 → generate_chart（根据需求编写matplotlib代码生成任意图表）

【数据源选择规则 - 重要】
- 问实时天气 → get_current_weather
- 问未来几天天气 → get_forecast，用户未指定模型时默认使用model="ecmwf_ifs"
- 问今天的强对流/雷暴风险 → 优先get_upper_air_data（探空实测数据最准确）
- 问未来的强对流风险 → get_forecast(model="ecmwf_ifs")获取CAPE/K指数等参数
- 问降水概率/确定性 → 使用model="ensemble"查看集合预报成员离散度
- 问历史气候/极端事件 → get_historical_stats / get_climate_trend
- 问"历史上的今天"某月某日气候 → get_daily_climatology(month, day)，默认用当前日期
- 问降水性质/强对流 → 结合get_forecast(查看降水时段和强度)和get_upper_air_data(查看CAPE和切变)
- 问作物/农业 → get_crop_info先查作物知识库，再用get_crop_gdd算积温
- 问多模式对比（如EC vs GFS）→ 分别调用get_forecast不同model，再用generate_chart画对比图
- 每轮最多调用3个工具，不要一次调用4个以上（会超载）

【图表生成规则】
- 不要只用一个模板，根据用户问题选择合适的可视化类型
- 对比类（EC vs GFS）→ 分组柱状图
- 趋势类 → 折线图
- 剖面/垂直分布 → 折线图（高度为y轴）
- 分布/离散度 → 箱线图或带误差棒的图
- 图表标题、轴标签、图例用中文，风格简洁专业
- generate_chart的code参数写完整可执行的matplotlib代码，data_json传入需要的数据

【数据边界规则】
- 工具返回空结果/None/error时，明确告知用户"XX数据暂不可用，原因：..."
- GEM模型(Open-Meteo gem_global)可能不稳定，失败时告知用户
- 探空数据来自怀俄明大学，每天00Z和12Z各一次，其它时次可能没有
- 历史数据覆盖2014-2025年，超出范围告知用户

【回复格式 - 严格执行】
- 禁止使用markdown格式（不要用 **bold**、|表格|、---、#标题、`代码块`）
- 用自然段落表达，可用emoji但不要过度
- 语言简洁，控制在150字以内
- 只回答用户问的内容：问"会不会下雨"只讲降水，不提气温/湿度；问"天气怎么样"才概括多要素

【图表生成 - 严格执行】
- get_forecast返回的daily数据只是文字摘要，不包含图表
- 需要图表时必须调用generate_chart工具，自己写matplotlib代码
- 不要使用任何预设模板，根据用户问题类型自定义图表
- 对比类（EC vs GFS）用分组柱状图，趋势类用折线图

【逐小时降水查询】
- 用户问"几点会下雨"→用get_forecast(days=1)获取的hourly_precip数据直接回答
- hourly_precip包含每小时的降水mm和天气描述，可直接判断降雨时段"""

# ── FC 工具定义 ──

TOOLS_FC = [
    {
        "type": "function",
        "function": {
            "name": "get_current_weather",
            "description": "获取杭州实时天气：温度、湿度、露点、风速、天气现象、体感温度、气压",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "城市名称，默认'杭州'"}
                },
                "required": ["city"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_forecast",
            "description": "获取未来天气预报，支持指定数值模型。可选model: ecmwf_ifs(ECMWF,默认), gfs_seamless(GFS), icon_global(ICON), gem_global(GEM), best_match(自动最佳), ensemble(集合预报)。返回逐小时数据+按天聚合摘要+图表",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "城市名称，默认'杭州'"},
                    "days": {"type": "integer", "description": "预报天数，默认3，最多7"},
                    "model": {"type": "string", "description": "数值模型：ecmwf_ifs/gfs_seamless/icon_global/gem_global/best_match/ensemble"}
                },
                "required": ["city"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_washing_advice",
            "description": "综合当前天气和未来预报判断是否适合洗车",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "城市名称，默认'杭州'"}
                },
                "required": ["city"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_upper_air_data",
            "description": "获取探空数据和分析结果：CAPE(对流有效位能)、CIN(对流抑制)、K指数、TT指数、LI(抬升指数)、0-6km风切变、可降水量、强对流风险评估。用于判断今天雷暴/强对流风险",
            "parameters": {
                "type": "object",
                "properties": {
                    "date_str": {"type": "string", "description": "日期，格式YYYY-MM-DD，如'2026-05-14'。不填则取最近可用时次"}
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_upper_air_plot",
            "description": "获取探空图：skewt(Skew-T对数压力图，显示温度/露点/风羽)、wind(风廓线图)、simple(大气健康诊断图)",
            "parameters": {
                "type": "object",
                "properties": {
                    "plot_type": {"type": "string", "description": "图表类型：skewt, wind, simple"},
                    "date_str": {"type": "string", "description": "日期，格式YYYY-MM-DD。不填则取最近可用时次"}
                },
                "required": ["plot_type"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_historical_stats",
            "description": "获取某一年杭州的气候统计：年均温、年降水、高温/低温天数、EW极端事件排名、与气候态对比",
            "parameters": {
                "type": "object",
                "properties": {
                    "year": {"type": "integer", "description": "年份，如2024。范围2014-2025"}
                },
                "required": ["year"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_climate_trend",
            "description": "获取杭州长期气候变化趋势：温度变化率(℃/10年)、降水变化率、逐年序列",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_daily_climatology",
            "description": "查询历史上某月某日（如5月15日）的多年气候统计：平均温度、平均最高/最低、历史极值及年份、降水概率。用于'历史上的今天'类问题",
            "parameters": {
                "type": "object",
                "properties": {
                    "month": {"type": "integer", "description": "月份，1-12，默认当前月"},
                    "day": {"type": "integer", "description": "日期，1-31，默认当前日"}
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_crop_info",
            "description": "查询作物知识库：生长阶段、温度阈值、水分需求、常见风险。支持：水稻(rice)、西湖龙井(tea)、杨梅(bayberry)、柑橘(citrus)、小白菜(bokchoy)",
            "parameters": {
                "type": "object",
                "properties": {
                    "crop_name": {"type": "string", "description": "作物名或ID，如'龙井'/'茶'/'tea'/'水稻'/'rice'/'杨梅'等"}
                },
                "required": ["crop_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_crop_gdd",
            "description": "计算作物从起始日期到现在的积温(GDD)进度，判断发育阶段是否正常",
            "parameters": {
                "type": "object",
                "properties": {
                    "crop_name": {"type": "string", "description": "作物名或ID，如'龙井'/'tea'/'水稻'/'rice'"}
                },
                "required": ["crop_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "generate_chart",
            "description": "执行matplotlib代码生成图表。重要规则：1)只写绘图逻辑，不要调用plt.savefig 2)不要import matplotlib或设置backend 3)注意Python缩进正确 4)用plt.subplots创建figure 5)可用变量:plt/np/pd/datetime/data",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "matplotlib绘图代码。只写纯粹的绘图逻辑（创建figure、画图、设置标签），不要调用savefig。可用变量：plt, np, pd, datetime, data"},
                    "data_json": {"type": "string", "description": "JSON数据，代码中通过data变量访问。如'{\"ec\": [...], \"gfs\": [...]}'"}
                },
                "required": ["code"]
            }
        }
    }
]

# ── 模型名称解析 ──

def _resolve_model(model_str):
    """将用户友好的模型名解析为内部key"""
    if not model_str:
        return "ecmwf_ifs"
    key = model_str.lower().strip()
    return MODEL_ALIASES.get(key, key)

# ── 工具实现 ──

def get_current_weather(city="杭州"):
    """获取实时天气（Open-Meteo）"""
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": HANGZHOU_LAT, "longitude": HANGZHOU_LON,
        "current_weather": "true",
        "hourly": "relative_humidity_2m,pressure_msl,apparent_temperature,dew_point_2m,precipitation",
        "timezone": "Asia/Shanghai", "windspeed_unit": "ms",
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
    humidity = pick("relative_humidity_2m")
    pressure = pick("pressure_msl")
    dew_point_raw = pick("dew_point_2m")
    wind_speed = current.get("windspeed")
    weather_code = current.get("weathercode")
    feels_like_raw = pick("apparent_temperature")
    update_time = current_time or datetime.now().strftime("%Y-%m-%d %H:%M")

    # 物理合理性校验：露点不能超过气温，体感温度不能偏离气温太多
    temp_f = float(temp) if temp is not None else None
    dp_f = float(dew_point_raw) if dew_point_raw is not None else None
    fl_f = float(feels_like_raw) if feels_like_raw is not None else None

    if dp_f is not None and temp_f is not None and dp_f > temp_f:
        dp_f = temp_f  # 露点不可能高于气温
    if fl_f is not None and temp_f is not None:
        if fl_f > temp_f + 15:
            fl_f = temp_f + 15
        if fl_f < temp_f - 10:
            fl_f = temp_f - 10

    weather_desc = WMO_CODES.get(weather_code, "未知")

    return {
        "city": city,
        "temp": round(temp_f, 1) if temp_f is not None else None,
        "feels_like": round(fl_f, 1) if fl_f is not None else None,
        "humidity": int(humidity) if humidity is not None else None,
        "pressure": round(float(pressure), 1) if pressure is not None else None,
        "dew_point": round(dp_f, 1) if dp_f is not None else None,
        "wind_speed": round(float(wind_speed), 1) if wind_speed is not None else None,
        "weather_desc": weather_desc,
        "weather_code": weather_code,
        "update_time": str(update_time),
    }


# 模块级单例，确保缓存共享
_FORECAST_SVC = None

def _get_forecast_svc():
    global _FORECAST_SVC
    if _FORECAST_SVC is None:
        from advanced_forecast_service import AdvancedForecastService
        _FORECAST_SVC = AdvancedForecastService()
    return _FORECAST_SVC


def _fetch_hourly_forecast(days=3, model="ecmwf_ifs"):
    """获取指定模型的逐小时预报，返回按天聚合 + 紧凑逐小时降水数据"""
    model_key = _resolve_model(model)
    svc = _get_forecast_svc()

    # 永远请求7天数据（命中缓存），然后切片
    try:
        raw = svc.fetch_multi_model_forecast(forecast_days=7)
    except Exception as e:
        return {"error": f"多模式预报获取失败: {e}"}

    model_data = raw.get(model_key)
    if not model_data:
        available = list(raw.keys())
        return {"error": f"模型'{MODEL_NAMES.get(model_key, model_key)}'数据不可用。可用模型: {available}"}

    inner = model_data.get("data", {})
    timestamps = inner.get("timestamps", [])
    measurements = inner.get("data", {})
    temps = measurements.get("temperature_2m", [])
    precip = measurements.get("precipitation", [])
    humidity_vals = measurements.get("relative_humidity_2m", [])
    wind_vals = measurements.get("wind_speed_10m", [])
    weather_names = measurements.get("weather_name", [])
    sw_vals = measurements.get("shortwave_radiation", [])

    # 紧凑逐小时降水数据，覆盖所有预报时次
    hourly_precip = []
    for i, ts_str in enumerate(timestamps):
        try:
            dt = datetime.strptime(ts_str, "%Y-%m-%d %H:%M")
            hour_str = dt.strftime("%m-%d %H:%M")
        except Exception:
            hour_str = ts_str
        p = round(precip[i], 2) if i < len(precip) and precip[i] is not None else 0
        w = weather_names[i] if i < len(weather_names) and weather_names[i] else ""
        hourly_precip.append({"t": hour_str, "p": p, "w": w})

    days_data = {}
    for i, ts_str in enumerate(timestamps):
        try:
            dt = datetime.strptime(ts_str, "%Y-%m-%d %H:%M")
        except Exception:
            continue
        date_key = dt.strftime("%Y-%m-%d")
        if date_key not in days_data:
            days_data[date_key] = {
                "date": date_key,
                "weekday": ["周一","周二","周三","周四","周五","周六","周日"][dt.weekday()],
                "temps": [], "precips": [], "humidities": [], "winds": [], "weather_names": [],
            }
        d = days_data[date_key]
        if i < len(temps) and temps[i] is not None:
            d["temps"].append(temps[i])
        if i < len(precip) and precip[i] is not None:
            d["precips"].append(precip[i])
        if i < len(humidity_vals) and humidity_vals[i] is not None:
            d["humidities"].append(humidity_vals[i])
        if i < len(wind_vals) and wind_vals[i] is not None:
            d["winds"].append(wind_vals[i])
        if i < len(weather_names) and weather_names[i]:
            d["weather_names"].append(weather_names[i])
        if i < len(sw_vals) and sw_vals[i] is not None:
            if "sw_rad" not in d: d["sw_rad"] = []
            d["sw_rad"].append(sw_vals[i])

    daily = []
    for date_key in sorted(days_data.keys())[:days]:
        d = days_data[date_key]
        temps_list = d["temps"]; precips_list = d["precips"]
        humidities_list = d["humidities"]; winds_list = d["winds"]
        names = d["weather_names"]

        temp_min = round(min(temps_list), 1) if temps_list else None
        temp_max = round(max(temps_list), 1) if temps_list else None
        precip_total = round(sum(p for p in precips_list if p), 1) if precips_list else 0
        humidity_avg = round(sum(humidities_list)/len(humidities_list), 1) if humidities_list else None
        wind_avg = round(sum(winds_list)/len(winds_list), 1) if winds_list else None
        main_weather = Counter(names).most_common(1)[0][0] if names else "未知"

        daily.append({
            "date": d["date"], "weekday": d["weekday"],
            "temp_min": temp_min, "temp_max": temp_max,
            "precip_total": precip_total,
            "humidity_avg": humidity_avg, "wind_avg": wind_avg,
            "main_weather": main_weather,
            "sw_radiation_mean": round(sum(d.get("sw_rad", [])) / len(d["sw_rad"]), 1) if d.get("sw_rad") else None,
        })

    return {
        "model": model_key,
        "model_name": MODEL_NAMES.get(model_key, model_key),
        "daily": daily,
        "hourly_precip": hourly_precip,
        "data_available": True,
    }


def get_forecast(city="杭州", days=3, model="ecmwf_ifs"):
    """获取未来几天预报（纯文字摘要，含逐小时降水数据）"""
    days = min(max(days, 1), 7)
    model_key = _resolve_model(model)
    forecast_data = _fetch_hourly_forecast(days, model_key)

    if "error" in forecast_data:
        return {"city": city, "model": model_key, "model_name": MODEL_NAMES.get(model_key, model_key),
                "summary": forecast_data["error"], "data_available": False}

    daily = forecast_data.get("daily", [])
    if not daily:
        return {"city": city, "model": model_key, "model_name": MODEL_NAMES.get(model_key, model_key),
                "summary": "暂无预报数据", "data_available": False}

    summary_parts = []
    for d in daily:
        t_range = f"{d['temp_min']}~{d['temp_max']}C" if d['temp_min'] is not None else "暂无温度"
        precip = f"降水{d['precip_total']}mm" if d['precip_total'] > 0 else "无降水"
        summary_parts.append(f"{d['weekday']}({d['date'][-5:]})：{d['main_weather']}，{t_range}，{precip}")

    model_label = MODEL_NAMES.get(model_key, model_key)
    summary = f"{city}未来{days}天预报（{model_label}）：\n" + "\n".join(summary_parts)

    return {
        "city": city, "model": model_key, "model_name": model_label,
        "summary": summary,
        "daily": daily,
        "hourly_precip": forecast_data.get("hourly_precip", []),
        "data_available": True,
    }


def get_washing_advice(city="杭州"):
    """洗车建议"""
    current = get_current_weather(city)
    fc = _fetch_hourly_forecast(3, "ecmwf_ifs")
    daily = fc.get("daily", []) if "daily" in fc else []

    reasons = []; score = 100
    weather_desc = current.get("weather_desc", "")
    wind = current.get("wind_speed") or 0

    if weather_desc and any(w in weather_desc for w in ["雨","雪","雷暴","阵雨"]):
        reasons.append(f"当前{weather_desc}，不适合洗车"); score -= 50
    if wind > 8:
        reasons.append(f"风速{wind}m/s较大，易沾灰"); score -= 20

    future_rain = False
    for d in daily:
        if d.get("precip_total", 0) > 1:
            future_rain = True
            reasons.append(f"{d['weekday']}预计降水{d['precip_total']}mm"); score -= 30
            break
    for d in daily:
        if d.get("wind_avg", 0) > 10:
            reasons.append(f"{d['weekday']}风力{d['wind_avg']}m/s较大"); score -= 15
            break

    if score >= 80:
        verdict = "适合洗车！未来几天天气不错。"
    elif score >= 50:
        verdict = "可以洗车，但建议关注天气变化。"
    else:
        verdict = "不太建议洗车，建议等天气好转。"

    return {
        "city": city, "verdict": verdict, "score": max(score,0),
        "reasons": reasons, "current_weather": weather_desc, "current_wind": wind,
    }


# ── 探空模块 ──

def get_upper_air_data(date_str=None):
    """获取探空稳定度指数和强对流风险评估"""
    from sounding_parser import SoundingDataParser
    from sounding_analyzer import SoundingAnalyzer
    import pandas as pd

    parser = SoundingDataParser()
    analyzer = SoundingAnalyzer()

    target_time = None
    if date_str:
        try:
            target_time = datetime.strptime(date_str, "%Y-%m-%d")
            target_time = target_time.replace(hour=12, minute=0, second=0)
        except ValueError:
            return {"error": f"日期格式错误: {date_str}，请使用YYYY-MM-DD格式"}

    try:
        result = parser.fetch_sounding_data(station_id="58457", target_time=target_time)
    except Exception as e:
        return {"error": f"探空数据获取失败: {e}，怀俄明大学可能暂不可用"}

    if not result.get("success"):
        return {"error": f"探空数据获取失败: {result.get('message', '未知错误')}，该时次可能无数据"}

    try:
        parsed = parser.parse_sounding_data(result["raw_data"])
    except Exception as e:
        return {"error": f"探空数据解析失败: {e}"}

    levels = parsed.get("levels", [])
    indices = parsed.get("indices", {})
    header = parsed.get("header", {})

    if not levels:
        return {"error": "探空数据为空，该时次可能无观测"}

    try:
        df = pd.DataFrame(levels)
        analysis = analyzer.analyze(df, indices)
    except Exception as e:
        return {"error": f"探空分析失败: {e}"}

    params = analysis.get("parameters", {})
    risk = analysis.get("risk_assessment", {})

    return {
        "data_available": True,
        "station": header.get("station_name", "杭州"),
        "time_utc": header.get("time_utc", ""),
        "parameters": {
            "cape_jkg": params.get("CAPE"),
            "cin_jkg": params.get("CIN"),
            "k_index": params.get("K_INDEX"),
            "total_totals": params.get("TOTAL_TOTALS"),
            "lifted_index": params.get("LIFTED_INDEX"),
            "showalter_index": params.get("SHOWALTER_INDEX"),
            "sweat_index": params.get("SWEAT_INDEX"),
            "precip_water_mm": params.get("PRECIP_WATER"),
            "shear_0_6km_ms": params.get("SHEAR_06KM") or params.get("BULK_SHEAR"),
            "lcl_height_m": params.get("LCL_HEIGHT"),
            "lfc_height_m": params.get("LFC_HEIGHT"),
        },
        "risk_assessment": {
            "level": risk.get("level"),
            "color": risk.get("color"),
            "description": risk.get("description"),
            "hazards": risk.get("hazards", []),
        },
        "layer_data": analysis.get("layer_data", {}),
    }


def get_upper_air_plot(plot_type="skewt", date_str=None):
    """获取探空图"""
    from sounding_parser import SoundingDataParser
    from sounding_plotter import SoundingPlotter
    import pandas as pd

    parser = SoundingDataParser()
    plotter = SoundingPlotter()

    target_time = None
    if date_str:
        try:
            target_time = datetime.strptime(date_str, "%Y-%m-%d")
            target_time = target_time.replace(hour=12, minute=0, second=0)
        except ValueError:
            return {"error": f"日期格式错误: {date_str}"}

    try:
        result = parser.fetch_sounding_data(station_id="58457", target_time=target_time)
    except Exception as e:
        return {"error": f"探空数据获取失败: {e}"}

    if not result.get("success"):
        return {"error": "探空数据不可用"}

    parsed = parser.parse_sounding_data(result["raw_data"])
    levels = parsed.get("levels", [])
    header = parsed.get("header", {})

    if not levels:
        return {"error": "探空数据为空"}

    df = pd.DataFrame(levels)

    valid_types = ["skewt", "t_lnp", "wind", "simple"]
    if plot_type not in valid_types:
        return {"error": f"不支持的图类型'{plot_type}'，可选: {valid_types}"}

    try:
        rel_path = plotter.plot(plot_type, df, header, cape=None)
    except Exception as e:
        return {"error": f"绘图失败: {e}"}

    full_path = os.path.join("static", rel_path)
    try:
        with open(full_path, "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode("utf-8")
        return {
            "data_available": True,
            "plot_type": plot_type,
            "image_base64": img_b64,
            "url": f"/static/{rel_path}",
        }
    except FileNotFoundError:
        return {"error": f"图表文件未找到: {rel_path}"}


# ── 历史气候模块 ──

def get_historical_stats(year):
    """获取年度气候统计"""
    from history_analyzer import analyzer as hist_analyzer

    try:
        year = int(year)
    except (TypeError, ValueError):
        return {"error": f"无效的年份: {year}"}

    available = hist_analyzer.get_available_years()
    if year not in available:
        return {"error": f"年份{year}不在可用范围。可用年份: {min(available)}-{max(available)}"}

    try:
        result = hist_analyzer.analyze_year(year)
    except Exception as e:
        return {"error": f"历史数据分析失败: {e}"}

    stats = result.get("stats", {})
    comparison = result.get("comparison", {})
    ew_summary = result.get("extremes_ew_summary", [])
    if isinstance(ew_summary, dict):
        ew_items = ew_summary.get("all_seasons", [])
    elif isinstance(ew_summary, list):
        ew_items = ew_summary
    else:
        ew_items = []

    return {
        "data_available": True,
        "year": year,
        "stats": {
            "avg_temp": stats.get("avg_temp"),
            "temp_max": stats.get("temp_max"),
            "temp_min": stats.get("temp_min"),
            "hot_days": stats.get("hot_days"),
            "cold_days": stats.get("cold_days"),
            "total_precip": stats.get("total_precip"),
            "rainy_days": stats.get("rainy_days"),
            "heavy_rain_days": stats.get("heavy_rain_days"),
            "max_daily_precip": stats.get("max_daily_precip"),
            "snow_days": stats.get("snow_days"),
            "thunder_days": stats.get("thunder_days"),
            "avg_wind_speed": stats.get("avg_wind_speed"),
        },
        "vs_climatology": {k: {"diff": v.get("diff"), "trend": v.get("trend")} for k, v in comparison.items()},
        "ew_extremes_top3": [
            {"type": e.get("type"), "date": e.get("peak_date"), "duration_days": e.get("duration_days"),
             "value": e.get("value"), "ew_score": e.get("ew_score"), "description": e.get("description")}
            for e in ew_items[:3]
        ],
    }


def get_climate_trend():
    """获取长期气候趋势"""
    from history_analyzer import analyzer as hist_analyzer

    try:
        result = hist_analyzer.analyze_trend()
    except Exception as e:
        return {"error": f"趋势分析失败: {e}"}

    trends = result.get("trends", {})
    series = result.get("series", [])

    return {
        "data_available": True,
        "trends": {
            "temp_rate_per_decade": trends.get("temp", {}).get("rate_per_decade"),
            "precip_rate_per_decade": trends.get("precip", {}).get("rate_per_decade"),
        },
        "recent_5yr": [
            {"year": s.get("year"), "avg_temp": s.get("avg_temp"),
             "total_precip": s.get("total_precip"), "hot_days": s.get("hot_days")}
            for s in series[-5:]
        ],
        "year_count": len(series),
    }


# ── 日气候工具 ──

def get_daily_climatology(month=None, day=None):
    """获取历史上某月某日的气候统计（多年平均温度、极值、降水概率）"""
    from history_analyzer import analyzer as hist_analyzer

    if month is None:
        month = datetime.now().month
    if day is None:
        day = datetime.now().day

    try:
        month = int(month)
        day = int(day)
    except (TypeError, ValueError):
        return {"error": f"无效的月日参数: {month}/{day}"}

    try:
        df = hist_analyzer.load_data()
    except Exception as e:
        return {"error": f"历史数据加载失败: {e}"}

    if df is None or df.empty:
        return {"error": "历史数据为空"}

    # 筛选该月日
    mask = (df.get('month') == month) & (df.get('day') == day)
    day_data = df[mask]

    if day_data.empty:
        return {"error": f"没有找到{month}月{day}日的历史数据"}

    temps = day_data.get('temperature', pd.Series(dtype=float)).dropna()
    highs = day_data.get('temp_max_24h', pd.Series(dtype=float)).dropna()
    lows = day_data.get('temp_min_24h', pd.Series(dtype=float)).dropna()
    precips = day_data.get('precipitation_corrected', pd.Series(dtype=float)).dropna()

    if temps.empty:
        return {"error": f"{month}月{day}日无有效温度数据"}

    years = day_data.get('year', pd.Series(dtype=int)).dropna()
    year_range = f"{int(years.min())}-{int(years.max())}" if not years.empty else "未知"

    # 找极端值对应的年份
    record_high_idx = highs.idxmax() if not highs.empty else None
    record_low_idx = lows.idxmin() if not lows.empty else None
    record_high_year = int(df.loc[record_high_idx, 'year']) if record_high_idx is not None and 'year' in df.columns else None
    record_low_year = int(df.loc[record_low_idx, 'year']) if record_low_idx is not None and 'year' in df.columns else None

    return {
        "data_available": True,
        "date": f"{month}月{day}日",
        "data_years": year_range,
        "avg_temp": round(float(temps.mean()), 1),
        "avg_high": round(float(highs.mean()), 1) if not highs.empty else None,
        "avg_low": round(float(lows.mean()), 1) if not lows.empty else None,
        "record_high": round(float(highs.max()), 1) if not highs.empty else None,
        "record_high_year": record_high_year,
        "record_low": round(float(lows.min()), 1) if not lows.empty else None,
        "record_low_year": record_low_year,
        "rain_probability": round(float((precips > 0.1).sum() / len(precips) * 100), 1) if not precips.empty else None,
        "avg_precip": round(float(precips.mean()), 1) if not precips.empty else None,
        "sample_count": len(temps),
    }


# ── 农业模块 ──

_CROP_ALIASES = {
    "龙井": "tea", "龙井茶": "tea", "西湖龙井": "tea", "茶": "tea",
    "水稻": "rice", "稻": "rice",
    "杨梅": "bayberry",
    "柑橘": "citrus", "橘子": "citrus",
    "小白菜": "bokchoy", "青菜": "bokchoy",
}

def _resolve_crop(crop_name):
    key = crop_name.lower().strip()
    return _CROP_ALIASES.get(key, key)


def get_crop_info(crop_name):
    """查询作物知识库"""
    from crop_database import crop_db

    crop_id = _resolve_crop(crop_name)
    info = crop_db.get_crop_info(crop_id)

    if not info:
        all_crops = crop_db.get_all_crops()
        names = [f"{c['name']}({c['id']})" for c in all_crops]
        return {"data_available": False, "error": f"未找到作物'{crop_name}'。已知作物: {', '.join(names)}"}

    stage = crop_db.get_current_stage(crop_id)

    return {
        "data_available": True,
        "crop_id": crop_id,
        "name": info.get("name"),
        "category": info.get("category"),
        "gdd_base": info.get("gdd_base"),
        "gdd_total": info.get("gdd_total"),
        "current_stage": {
            "name": stage.get("name"),
            "period": f"{stage.get('start')} ~ {stage.get('end')}",
            "temp_min": stage.get("temp_min"),
            "temp_opt": stage.get("temp_opt"),
            "temp_max": stage.get("temp_max"),
            "water_need": stage.get("water_need"),
        } if stage else None,
        "all_stages": [{"name": s.get("name"), "period": f"{s.get('start')}~{s.get('end')}"}
                       for s in info.get("stages", [])],
        "risks": [{"name": v.get("desc"), "threshold": v.get("threshold")}
                  for v in info.get("risks", {}).values()],
    }


def get_crop_gdd(crop_name):
    """计算积温进度"""
    from crop_database import crop_db
    from agro_calculator import agro_calculator

    crop_id = _resolve_crop(crop_name)
    info = crop_db.get_crop_info(crop_id)

    if not info:
        return {"error": f"未找到作物'{crop_name}'"}

    gdd_base = info.get("gdd_base", 10)
    gdd_total = info.get("gdd_total", 1000)
    gdd_start_str = info.get("gdd_start", "01-01")

    try:
        gdd_start = datetime(datetime.now().year, *map(int, gdd_start_str.split("-")))
    except Exception:
        gdd_start = datetime(datetime.now().year, 1, 1)

    fc = _fetch_hourly_forecast(7, "ecmwf_ifs")
    daily = fc.get("daily", []) if "daily" in fc else []

    if not daily:
        return {"error": "无法获取预报数据，积温计算失败"}

    daily_temps = []
    cumulative = 0
    for d in daily:
        if d["temp_min"] is not None and d["temp_max"] is not None:
            tavg = (d["temp_min"] + d["temp_max"]) / 2
            gdd_day = max(tavg - gdd_base, 0)
            cumulative += gdd_day
            daily_temps.append({
                "date": d["date"], "tavg": round(tavg, 1),
                "gdd_daily": round(gdd_day, 1), "gdd_cumulative": round(cumulative, 1),
            })

    progress_pct = round(cumulative / gdd_total * 100, 1) if gdd_total > 0 else 0

    return {
        "data_available": True,
        "crop_name": info.get("name"),
        "gdd_base": gdd_base,
        "gdd_total": gdd_total,
        "gdd_accumulated": round(cumulative, 1),
        "progress_pct": progress_pct,
        "daily_gdd": daily_temps[:7],
        "status": "积温充足，发育正常" if progress_pct >= 90 else
                  "积温偏少，发育可能延迟" if progress_pct < 60 else
                  "积温正常推进中",
    }


# ── 动态图表生成（代码沙箱） ──

_SAFE_BUILTINS = {
    'print': print, 'len': len, 'range': range, 'list': list, 'dict': dict,
    'str': str, 'int': int, 'float': float, 'bool': bool,
    'min': min, 'max': max, 'sum': sum, 'abs': abs, 'round': round,
    'zip': zip, 'enumerate': enumerate, 'sorted': sorted,
    'True': True, 'False': False, 'None': None,
    'isinstance': isinstance, 'type': type, 'reversed': reversed,
    'Exception': Exception, 'ValueError': ValueError, 'KeyError': KeyError,
    'json': json,
}


def _clean_chart_code(code):
    """清理LLM生成的代码：去掉冗余导入、plt.savefig调用、matplotlib.use等"""
    import re
    lines = code.split('\n')
    cleaned = []
    for line in lines:
        stripped = line.strip()
        # 跳过这些行
        if stripped.startswith('import matplotlib'):
            continue
        if stripped.startswith('matplotlib.use('):
            continue
        if 'plt.savefig(' in stripped:
            continue
        cleaned.append(line)
    return '\n'.join(cleaned)


def generate_chart(code=None, data_json=None):
    """执行自定义 matplotlib 代码生成图表（沙箱执行，10秒超时）"""
    if not code:
        return {"success": False, "image_base64": None, "error": "code参数为空，请提供matplotlib绘图代码"}
    data_context = {}
    if data_json:
        try:
            data_context = json.loads(data_json)
        except json.JSONDecodeError as e:
            return {"success": False, "image_base64": None, "error": f"data_json解析失败: {e}"}

    code = _clean_chart_code(code)

    buf = io.BytesIO()
    namespace = {
        '__builtins__': {**_SAFE_BUILTINS, '__import__': __import__},
        'plt': plt,
        'np': __import__('numpy'),
        'pd': __import__('pandas'),
        'datetime': datetime,
        'timedelta': timedelta,
        'data': data_context,
        '_buf': buf,
    }

    wrapped = f"""
{code}

plt.savefig(_buf, format='png', dpi=120, bbox_inches='tight', facecolor='#F5F7FA')
plt.close('all')
"""

    def target():
        exec(wrapped, namespace)

    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(target)
            future.result(timeout=10)
    except FutureTimeoutError:
        plt.close('all')
        return {"success": False, "image_base64": None, "error": "代码执行超时（>10秒），请简化图表"}
    except SyntaxError as e:
        plt.close('all')
        # 提取行号和上下文帮助LLM修正
        lineno = e.lineno if hasattr(e, 'lineno') else '?'
        lines = code.split('\n')
        ctx_start = max(0, (lineno if isinstance(lineno, int) else 1) - 2)
        ctx_end = min(len(lines), ctx_start + 5)
        ctx = '\n'.join(f'  {i+1}: {lines[i]}' for i in range(ctx_start, ctx_end))
        return {"success": False, "image_base64": None, "error": f"代码第{lineno}行语法错误: {e.msg}。附近代码:\n{ctx}\n请修正缩进后重试"}
    except Exception as e:
        plt.close('all')
        tb = traceback.format_exc()
        return {"success": False, "image_base64": None, "error": f"{type(e).__name__}: {e}"}

    buf.seek(0)
    img_data = buf.read()
    if len(img_data) < 100:
        return {"success": False, "image_base64": None, "error": "生成的图表为空，请检查代码逻辑"}
    return {"success": True, "image_base64": base64.b64encode(img_data).decode('utf-8'), "error": None}


# ── 默认预报图表 ──

# ── DeepSeek 调用 ──

def _call_deepseek(messages, tools=None, max_tokens=800):
    if not DEEPSEEK_API_KEY:
        return None

    payload = {
        "model": "deepseek-chat",
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": max_tokens,
    }
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = "auto"

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}"
    }

    try:
        resp = requests.post(DEEPSEEK_API_URL, headers=headers, json=payload, timeout=45)
        if resp.status_code == 200:
            return resp.json()
        print(f"DeepSeek API error: {resp.status_code} {resp.text[:200]}")
        return None
    except Exception as e:
        print(f"DeepSeek API call failed: {e}")
        return None


# ── 工具调度映射 ──

TOOL_MAP_FC = {
    "get_current_weather": get_current_weather,
    "get_forecast": get_forecast,
    "get_washing_advice": get_washing_advice,
    "get_upper_air_data": get_upper_air_data,
    "get_upper_air_plot": get_upper_air_plot,
    "get_historical_stats": get_historical_stats,
    "get_climate_trend": get_climate_trend,
    "get_daily_climatology": get_daily_climatology,
    "get_crop_info": get_crop_info,
    "get_crop_gdd": get_crop_gdd,
    "generate_chart": generate_chart,
}


# ── 主流程 ──

def _process_chat(user_message, mode="code_interpreter", history=None):
    """处理用户消息，支持双模式：code_interpreter / function_calling"""
    if mode == "code_interpreter":
        system = SYSTEM_PROMPT_CI
        tools = TOOLS_CI
        tool_map = {"run_code": run_code}
        max_rounds = 5
    else:
        system = SYSTEM_PROMPT_FC
        tools = TOOLS_FC
        tool_map = TOOL_MAP_FC
        max_rounds = 4

    messages = [{"role": "system", "content": system}]
    if history and isinstance(history, list):
        # 限制历史轮数（最近6条消息），避免上下文过长
        for h in history[-6:]:
            if isinstance(h, dict) and h.get("role") in ("user", "assistant"):
                messages.append({"role": h["role"], "content": h.get("content", "")})
    messages.append({"role": "user", "content": user_message})

    collected_images = []
    collected_stdout = ""
    error_log = []
    token_usage = {"prompt_tokens": 0, "completion_tokens": 0,
                   "cache_hit": 0, "cache_miss": 0, "api_calls": 0}

    for round_idx in range(max_rounds):
        response = _call_deepseek(messages, tools=tools)

        if not response:
            if collected_images:
                return {"reply": "AI服务暂时不可用，但已生成的图表如下。",
                        "image": collected_images[0], "usage": token_usage}
            if error_log:
                details = "; ".join(error_log[-3:])
                return {"reply": f"AI服务暂时不可用。已尝试: {details}",
                        "image": None, "usage": token_usage}
            return {"reply": "抱歉，AI服务暂时不可用，请稍后再试。",
                    "image": None, "usage": token_usage}

        # 统计token
        usage = response.get("usage", {})
        token_usage["api_calls"] += 1
        token_usage["prompt_tokens"] += usage.get("prompt_tokens", 0)
        token_usage["completion_tokens"] += usage.get("completion_tokens", 0)
        token_usage["cache_hit"] += usage.get("prompt_cache_hit_tokens", 0)
        token_usage["cache_miss"] += usage.get("prompt_cache_miss_tokens", 0)

        choice = response["choices"][0]
        msg = choice["message"]

        if msg.get("tool_calls"):
            tool_calls = msg["tool_calls"]
            if len(tool_calls) > 3:
                tool_calls = tool_calls[:3]

            tool_results = []
            for tool_call in tool_calls:
                func_name = tool_call["function"]["name"]
                try:
                    func_args = json.loads(tool_call["function"]["arguments"])
                except json.JSONDecodeError:
                    func_args = {}
                    error_log.append(f"{func_name}(参数解析失败)")

                func = tool_map.get(func_name)
                if func:
                    try:
                        result = func(**func_args)
                    except Exception as e:
                        result = {"error": f"工具执行异常: {e}"}
                        error_log.append(f"{func_name}执行异常")
                else:
                    result = {"error": f"未知功能: {func_name}"}
                    error_log.append(f"{func_name}未知")

                if isinstance(result, dict):
                    if result.get("error"):
                        error_log.append(f"{func_name}: {result['error'][:80]}")

                # 收集图片和stdout
                if isinstance(result, dict):
                    if result.get("image_base64"):
                        collected_images.append(result["image_base64"])
                    if result.get("stdout") and result.get("success"):
                        collected_stdout = result["stdout"]

                # 发给LLM：去base64 + 压缩hourly_precip
                llm_result = dict(result) if isinstance(result, dict) else result
                if isinstance(llm_result, dict):
                    llm_result.pop("image_base64", None)
                    hp = llm_result.get("hourly_precip")
                    if isinstance(hp, list) and len(hp) > 24:
                        llm_result["hourly_precip"] = [h for h in hp if h.get("p", 0) > 0]

                tool_results.append({
                    "tool_call_id": tool_call["id"],
                    "role": "tool",
                    "content": json.dumps(llm_result, ensure_ascii=False, default=str),
                })

            messages.append(msg)
            messages.extend(tool_results)
            continue

        reply = msg.get("content", "").strip()
        import re as _re
        reply = _re.sub(r'<\||\|?DSML\|?.*?tool_calls.*?>', '', reply, flags=_re.DOTALL)
        reply = reply.strip()
        # stdout降级：LLM回复太短时用代码输出（但拒绝对原始数据dump）
        if len(reply) < 25 and collected_stdout:
            lines = collected_stdout.strip().split('\n')
            # 拒绝数据dump: 超过30行 或 有时戳模式 或 含Python对象repr
            is_dump = (len(lines) > 30 or
                       any('°C 降水:' in l for l in lines[:5]) or
                       any(l.strip().startswith('{') and 'name' in l for l in lines[:5]))
            if not is_dump:
                filtered = '\n'.join(l for l in lines
                           if '__' not in l and '.py' not in l and '/static/' not in l)
                if filtered.strip():
                    reply = filtered.strip()
        image_b64 = collected_images[0] if collected_images else None
        return {"reply": reply, "image": image_b64, "usage": token_usage}

    problems = "; ".join(error_log[-3:]) if error_log else "多次尝试未能获取足够数据"
    fallback_reply = f"抱歉，{problems}。请尝试简化问题或换个方式提问。"
    if collected_stdout:
        lines = collected_stdout.strip().split('\n')
        is_dump = (len(lines) > 30 or
                   any('°C 降水:' in l for l in lines[:5]) or
                   any(l.strip().startswith('{') and 'name' in l for l in lines[:5]))
        if not is_dump:
            filtered = '\n'.join(l for l in lines
                       if '__' not in l and '.py' not in l and '/static/' not in l)
            if filtered.strip():
                fallback_reply = filtered.strip()
    return {"reply": fallback_reply,
            "image": collected_images[0] if collected_images else None, "usage": token_usage}


def process_chat(user_message, mode="code_interpreter", history=None):
    """CI模式，失败自动降级FC"""
    result = _process_chat(user_message, mode, history)
    reply = result.get("reply", "")

    # CI模式检测低质量回复 → 自动降级FC
    is_bad = (mode == "code_interpreter" and
              ("抱歉" in reply or len(reply) < 15 or
               (reply.strip().startswith('[') and 'get_' in reply) or
               reply.strip().startswith('{')))

    if is_bad:
        fc_result = _process_chat(user_message, "function_calling", history)
        fc_result["degraded"] = True
        return fc_result

    result["degraded"] = False
    return result
