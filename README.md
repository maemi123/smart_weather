# 🌤️ 智慧天气 - 综合气象服务系统

基于 Flask 的智能天气分析平台，集成 ECMWF/GFS/ICON 数值预报、探空数据分析、农业气象服务和历史气候可视化功能，为用户提供全方位的气象信息服务。

---

## ✨ 核心功能模块

### 🏠 首页
项目概览与模块导航，展示系统运行状态和快速入口。

### 📊 多模式预报 (`/advanced-forecast`)
集成 ECMWF、GFS、ICON 等主流数值预报模型，提供：
- 72小时精细化预报（逐小时）
- 多模式对比分析（7天）
- 集合预报置信区间
- 7天预报趋势
- AI 分析
- 🤖 **机器学习误差校正**（随机森林模型）

### 🎈 探空分析 (`/upperair`)
基于怀俄明大学探空数据，提供：
- 斜温图（Skew-T）可视化
- 大气稳定度分析（CAPE/CIN）
- 逆温层、零度层识别
- 卡通直观图模式
- AI 分析

### 🌾 农业气象 (`/agro-dashboard`) - 核心模块
支持 5 种浙江典型作物的积温预测与农事建议：

| 作物 | 起算日期 | 目标积温 | 基点温度 | 应用场景 |
|------|----------|----------|----------|----------|
| 🌾 单季晚稻 | 4月15日 | 2200℃ | 10℃ | 预测成熟收获期 |
| 🍃 西湖龙井 | 1月1日 | 380℃ | 10℃ | 预测春茶开采期 |
| 🍒 杨梅 | 1月1日 | 950℃ | 10℃ | 预测果实成熟期 |
| 🍊 柑橘 | 1月1日 | 1800℃ | 12.5℃ | 预测成熟采摘期 |
| 🥬 小白菜 | 用户自选 | 400℃ | 5℃ | 预测采收日期 |

**特色功能**：
- 🤖 AI 农事顾问（DeepSeek API）
- 📈 积温进度可视化
- ⚠️ 气象灾害预警

### 📜 历史气候 (`/history`)
杭州历史气候数据可视化：
- 气温长期变化趋势
- 降水年际变化分析
- ERA5 再分析数据支持

---

## 🛠️ 技术栈

| 类别 | 技术 |
|------|------|
| **后端框架** | Python 3.8+ / Flask |
| **数据处理** | Pandas / NumPy / Xarray |
| **数据源** | Open-Meteo API / ERA5 / 怀俄明大学探空数据 / Meteostat API |
| **可视化** | Matplotlib / Plotly / ECharts |
| **机器学习** | Scikit-learn（随机森林回归/分类） |
| **AI 能力** | DeepSeek API |
| **API 请求** | requests / requests_cache / retry_requests / openmeteo_requests |
| **数据解析** | cfgrib（GRIB 文件解析） |
| **任务调度** | schedule |
| **其他** | tqdm（进度条） / cdsapi（ERA5 数据下载） |

---

## 🚀 快速开始

### 环境要求
- **Python 3.9 - 3.12**（暂不支持 3.13）
- pip 20.0+

### 安装步骤

> **⚠️ 注意**：本项目包含较多历史数据文件，仓库体积较大（约150MB）。建议先配置Git缓冲区，并使用浅克隆以加快下载速度。

```bash
# 配置Git缓冲区（防止大文件传输中断）
git config --global http.postBuffer 524288000
git config --global core.compression 0

# 浅克隆（只下载最近1个commit，速度更快）
git clone --depth 1 https://github.com/maemi123/smart_weather.git

# 或者完整克隆（如需完整历史记录）
# git clone https://github.com/maemi123/smart_weather.git

cd smart_weather

# 创建虚拟环境
python -m venv .venv

# 激活虚拟环境
# Windows:
.venv\Scripts\activate
# Mac/Linux:
source .venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 配置 API 密钥（可选，用于 AI 农事顾问）
echo "DEEPSEEK_API_KEY=你的密钥" > .env

# 运行（方式1：使用启动脚本）
run_flask.bat

# 或者（方式2：直接运行）
python app.py
```

访问 http://127.0.0.1:5000 即可使用。

> **💡 提示**：Windows 用户推荐使用 `run_flask.bat` 启动，它会自动检测虚拟环境并启动应用。

---

## 📁 项目结构

```
smart_weather/
├── app.py                      # Flask 主应用
├── advanced_forecast_service.py # 多模式预报服务
├── sounding_analyzer.py        # 探空数据分析
├── sounding_plotter.py         # 探空图绘制
├── agro_calculator.py          # 农业气象计算引擎
├── agro_alert_engine.py        # 农业预警引擎
├── crop_database.py            # 作物知识库
├── farming_ai_adviser.py       # AI 农事顾问
├── history_analyzer.py         # 历史气候分析
├── ml_correction.py            # 机器学习误差校正
├── train_bias_correction.py    # 模型训练脚本
├── templates/                  # HTML 模板
├── static/                     # 静态资源
├── models/                     # ML 模型文件
├── data/                       # 数据存储
└── climate_data/               # 气候数据模块
```

---

## 🔧 特色功能

### 1. 多模式预报并行加速
使用 `ThreadPoolExecutor` 并行请求多个预报模型，配合 5 分钟缓存机制，页面加载时间从 10-25 秒降至 3-5 秒。

### 2. 机器学习误差校正

基于随机森林的预报误差校正模型，对 ECMWF 预报数据进行后处理：

**训练数据**：
- 预报数据：Open-Meteo API 获取的 ECMWF 预报（2026-01-11 至 2026-02-21）
- 实况数据：Meteostat API 获取的杭州观测数据
- 数据划分：以 2026-02-10 为界，训练集 31 天，测试集 11 天

**特征工程**（13 个特征）：
- 预报特征：温度、湿度、风速、气压
- 时间特征：小时、月份、星期几、是否白天、是否周末
- 时效特征：预报时效、时效分类
- 周期编码：小时正弦/余弦变换

**模型效果**：
| 变量 | 原始 MAE | 校正 MAE | 改进幅度 |
|------|----------|----------|----------|
| 温度 | 1.78°C | 1.76°C | 1.1% |
| 湿度 | 9.65% | 8.14% | 15.6% |
| 风速 | 3.87 m/s | 2.79 m/s | 28.0% |
| 降水（分类准确率） | - | - | 92.1% |

### 3. AI 农事顾问
集成 DeepSeek API，根据作物生长阶段和天气预报，生成个性化农事建议。

---

## 📊 数据来源

| 数据类型 | 来源 | 更新频率 |
|----------|------|----------|
| 数值预报 | Open-Meteo (ECMWF/GFS/ICON) | 每日 2 次 |
| 探空数据 | 怀俄明大学 | 每日 2 次 (00Z/12Z) |
| 历史气候 | ERA5 / Meteostat | - |
| 实况数据 | Meteostat API | 每小时 |

---

## ⚠️ 项目说明

本项目因临时准备公开，仍存在以下不足，敬请谅解：

- 📌 **功能不完善**：部分功能可能存在小问题或 Bug 待修复
- 📁 **结构较杂乱**：项目中包含较多测试文件（`test_*.py`），未及时清理
- 🔧 **代码风格**：代码风格不够统一，部分代码缺少注释
- 📖 **文档缺失**：缺少详细的 API 文档和开发文档

欢迎提出 Issue 或 Pull Request 帮助改进！

---

## 📧 联系方式

如有问题或建议，欢迎联系：
- 作者：maemi123
- 邮箱：1021389463@qq.com

---
