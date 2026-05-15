# 智慧天气

基于 `Flask` 的综合气象信息服务系统，围绕“预报分析能力构建”这一主线，集成多模式数值预报、探空诊断、历史气候分析、机器学习误差校正和农业气象服务，面向杭州地区提供较完整的天气分析与应用支撑能力。

## 项目概览

当前系统主要包含以下页面与模块：

- `/`
  - 首页导航页，提供实时天气概览、露点与干湿感、智能提醒和各模块统一入口
- `/advanced-forecast`
  - 多模式预报分析，支持 `ECMWF / GFS / ICON` 对比、72 小时精细化预报和 ECMWF 机器学习校正
- `/upperair`
  - 探空分析，支持 `Skew-T / T-lnP` 图、稳定度参数、风险提示与异常值处理
- `/history/yearly`、`/history/trend`
  - 历史气候年度分析与趋势分析，支持原始极值和 `EW` 指数代表事件识别
- `/agro-dashboard`、`/crop/<crop_id>`
  - 农业气象服务，支持作物适宜度、积温进度、风险提醒和农事建议
- 首页右下角 **智慧天气 Agent** 聊天窗口
  - 基于 DeepSeek Function Calling 的智能天气助手，支持自然语言查询天气、预报对比、探空分析、历史气候、农业建议等

## 当前亮点

### 首页不只是入口页

首页承担“统一入口 + 实时概览 + 模块分发”的平台级作用。顶部实时天气除了温度、体感、湿度、风速外，还展示露点和干湿感，更适合快速判断当前体感干湿程度。

### 多模式预报分析

系统基于 `Open-Meteo` 组织 `ECMWF`、`GFS`、`ICON` 等模式结果，支持：

- 72 小时逐小时精细化预报
- 7 天多模式对比
- ECMWF 机器学习误差校正
- 统一站点口径与 issue time 识别

### 探空分析更强调业务可用性

探空模块基于怀俄明大学资料，支持：

- `Skew-T`、`T-lnP`、风矢图等专业图形
- `CAPE`、`CIN`、`K 指数`、`Lifted Index` 等关键参数
- 北京时间输入自动换算到标准 UTC 探空时次
- 指标异常值按 `N/A` 展示，避免误导

### 历史气候代表事件识别

历史气候模块除了保留原始极值榜单外，还新增了 `EW` 指数模式：

- 依据历史同月同日经验百分位衡量相对异常程度
- 低温使用反向百分位
- 加入同季门槛和过程去重
- 采用四季分组展示代表性事件

### ECMWF 机器学习误差校正重训

当前模型基于新版 `data/hangzhou_openmeteo` 样本重训，并统一到杭州国家站 / 馒头山口径：

- 训练样本目录：`data/hangzhou_openmeteo`
- 审计文件数：`100`
- 有效加载文件数：`97`
- 统一坐标：`30.2444, 120.1528`
- 观测真值：当前使用 `Meteostat 58457` 作为最佳可用统一源

最终留出测试集结果：

| 变量 | 原始 MAE | 校正 MAE | 改进幅度 |
|------|----------|----------|----------|
| 温度 | 2.355°C | 1.832°C | 22.2% |
| 湿度 | 9.851% | 9.085% | 7.8% |
| 风速 | 4.413 m/s | 2.613 m/s | 40.8% |

降水结果：

- 分类准确率：`0.754 -> 0.743`
- Precision：`0.675 -> 0.677`
- Recall：`0.496 -> 0.426`
- F1：`0.572 -> 0.523`
- 雨样本 MAE：`1.024 mm -> 0.586 mm`
- 全样本 MAE：`0.414 mm -> 0.251 mm`

说明：降水分类指标并非全面优于原始预报，但雨量级误差改善明显，当前模型更偏向减少误报降水，适合灌溉、水库调度、排涝准备等更关注降水量级的场景。

### 农业气象服务

农业模块围绕浙江典型作物组织，包括：

- 作物知识库
- 适宜度评分
- 气象风险提醒
- 历史积温与未来积温增量估算
- AI 农事建议与规则回退

其中历史积温主要基于 `ERA5-Land`，未来 7 天增量主要基于 `ECMWF` 预报链路。

### 智慧天气 Agent

首页右下角集成了基于 `DeepSeek API` 的智能天气助手，支持**双模式**运行：

**Code Interpreter 模式（默认）** — LLM 通过 `run_code` 工具调用项目高层函数（8 个），一次代码执行完成取数据+分析+画图，典型查询仅需 2-3 次 API 调用，token 消耗较低。

**Function Calling 模式（自动降级）** — 11 个工具函数自动调用各模块，CI 模式回复质量不佳时自动切换，保证回答可靠性。

支持能力：

- 实时天气、多模式预报对比（ECMWF / GFS / ICON / 集合预报）
- 逐小时降水时段分析、强对流风险评估（CAPE、K指数、风切变）
- 历史气候（年度统计、EW极端事件、长期趋势、"历史上的今天"）
- 农业气象（作物知识库、ERA5-Land+ECMWF积温进度、农事建议）
- 光伏发电效率分析（短波辐射趋势）、洗车建议
- 自定义 matplotlib 图表生成，支持悬浮放大查看
- 对话历史记忆 + localStorage 缓存（1h TTL）

Agent 核心逻辑定义在 `agent_functions.py`（~1500行），包含双模式调度、代码执行沙箱、积温计算管道、stdout 质量过滤等。

## 技术栈

| 类别 | 技术 |
|------|------|
| 后端框架 | `Flask` |
| 数据处理 | `Pandas` / `NumPy` / `Xarray` |
| 预报数据 | `Open-Meteo` |
| 探空数据 | 怀俄明大学探空资料 |
| 历史与观测 | `ERA5-Land` / `Meteostat` |
| 图形可视化 | `Plotly.js` / `Matplotlib` / `MetPy` / `Chart.js` |
| 机器学习 | `scikit-learn` |
| AI 能力 | `DeepSeek API` |

## 快速开始

### 环境要求

- Python `3.9 - 3.12`
- Windows 环境推荐使用 `run_flask.bat`

### 安装与运行

```bash
# 配置Git缓冲区（防止大文件传输中断）
git config --global http.postBuffer 524288000
git config --global core.compression 0

# 浅克隆（只下载最近1个commit，速度更快）
git clone --depth 1 https://github.com/maemi123/smart_weather.git

# 或者完整克隆（如需完整历史记录）
# git clone https://github.com/maemi123/smart_weather.git
cd smart_weather

python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
# source .venv/bin/activate

pip install -r requirements.txt

# 可选：配置 AI 能力
echo "DEEPSEEK_API_KEY=your_key" > .env

python app.py
```

启动后访问：

- [http://127.0.0.1:5000](http://127.0.0.1:5000)

## 项目结构

```text
smart_weather/
├── app.py                         # Flask 主应用
├── agent_functions.py             # 智慧天气 Agent（11工具+DeepSeek Function Calling）
├── advanced_forecast_service.py   # 多模式预报服务
├── history_analyzer.py            # 历史气候分析
├── sounding_parser.py             # 探空数据解析
├── sounding_analyzer.py           # 探空稳定度分析
├── sounding_plotter.py            # 探空图表绘制
├── ml_correction.py               # ML误差校正 V1（随机森林）
├── ml_correction_v2.py            # ML误差校正 V2（梯度提升）
├── train_bias_correction.py       # ML模型训练
├── crop_database.py               # 作物知识库
├── agro_calculator.py             # 农业气象计算
├── agro_alert_engine.py           # 农业预警引擎
├── farming_ai_adviser.py          # 农事AI顾问
├── chart_generator.py             # 图表生成
├── weather_service.py             # 天气服务
├── templates/                     # Jinja2 模板
├── static/                        # 静态资源
├── models/                        # ML模型文件
├── models_v2/                     # ML模型 V2
├── data/                          # 气象数据
└── docs/                          # 文档与论文素材
```

## 文档与论文素材

仓库中保留了部分项目文档与论文写作底稿：

- `USER_GUIDE.md`
  - 用户使用说明
- `INSTALL.md`
  - 安装说明
- `docs/thesis_*.md`
  - 论文初稿与模块细化稿
- `docs/diagrams/*.puml`
  - 论文图示 `PlantUML` 底稿

说明：

- 渲染后的论文图建议统一放入 `docs/diagrams/images/`
- 论文草稿、图示和相关素材已加入 `.gitignore`，默认不参与正式代码提交

## 测试与评估依据

项目内保留了若干关键测试与评估产物：

- `test_history_yearly_ew.py`
  - 验证 EW 指数、季节分组与页面渲染
- `test_forecast_issue_time.py`
  - 验证 ECMWF issue time 识别与运行时口径一致性
- `models/training_manifest.json`
  - 训练数据审计与站点、时次、样本范围说明
- `models/metrics_report.json`
  - 机器学习误差校正评估结果

## 当前说明

这是一个持续迭代中的毕业设计 / 综合项目仓库，当前已具备较完整的功能链路，但仍有一些现实限制：

- 对外部数据源稳定性仍有依赖
- 部分模块还在持续完善异常处理与细节体验
- 论文草稿和图示素材仍在同步整理

如果你只是想快速了解项目，建议优先查看首页、多模式预报、探空分析和历史气候模块。

## 联系方式

- GitHub: `maemi123`
- 邮箱: `1021389463@qq.com`
