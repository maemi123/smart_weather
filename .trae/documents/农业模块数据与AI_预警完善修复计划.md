# 农业模块“有日历但无预警/AI/详情数据”修复计划

## 问题结论（为什么现在看起来没数据）
- **预警为空**：当前预警引擎触发条件偏严（机会提示要求 `wind < 3`），且不少风险阈值只会在极端天气触发；另外预警阶段匹配逻辑缺少括号，后续扩展也容易出错。代码点：[agro_alert_engine.py](file:///D:/pythonProject/smart_weather/agro_alert_engine.py)；阈值不一致点：[agro_dashboard.html](file:///D:/pythonProject/smart_weather/templates/agro_dashboard.html) vs [agro_alert_engine.py](file:///D:/pythonProject/smart_weather/agro_alert_engine.py)
- **AI建议没有**：前端请求体是写死的 mock 天气/空 alerts；后端 DeepSeek Key 默认从环境变量读不到就直接失败。代码点：[agro_dashboard.js](file:///D:/pythonProject/smart_weather/static/js/agro_dashboard.js)、[farming_ai_adviser.py](file:///D:/pythonProject/smart_weather/farming_ai_adviser.py)
- **作物详情页显示“5月默认数据”**：Chart.js 数据硬编码。代码点：[crop_detail.html](file:///D:/pythonProject/smart_weather/templates/crop_detail.html)
- **水稻 0 分**：当前 2 月属于非生育期，水稻阶段返回 `None`，评分函数按“数据缺失”返回 0。代码点：[crop_database.py](file:///D:/pythonProject/smart_weather/crop_database.py)、[agro_calculator.py](file:///D:/pythonProject/smart_weather/agro_calculator.py)

## 目标
- 首页至少稳定显示：
  - 未来7天日历（已有）
  - **3–6条可解释的预警/机会/提醒**（即使极端天气没发生也能有“作业窗口/注意事项”）
- 作物详情页：
  - 图表使用**真实未来7天数据**（不再是5月演示）
  - AI建议可用（DeepSeek 正常时用模型；失败时**规则引擎降级**仍可生成结构化建议）

## 实施方案

### 1) 统一农业模块的“未来7天农业用预报”数据源（后端）
- 在 [app.py](file:///D:/pythonProject/smart_weather/app.py) 抽一个内部 helper（或小函数）
  - 输入：multi_model（或模型优先级）
  - 输出：`forecast_list`（天粒度，含 temp_min/temp_max/temp_avg/precip/wind/humidity）
- `/agro-dashboard` 和 `/crop/<crop_id>` **复用同一套预报构造逻辑**，避免首页有数据、详情页没数据。

### 2) 修复并增强预警引擎（让它“经常有可用提示”）
修改 [agro_alert_engine.py](file:///D:/pythonProject/smart_weather/agro_alert_engine.py)：
- **机会提示阈值与页面一致**：把机会提示从 `wind < 3` 放宽到 `wind < 4`（与总览表一致）。
- **修复 stage 匹配条件括号优先级**：统一写成 `if risk_cfg and (stage_name in stages or 'all' in stages):`，避免隐患。
- **补齐已建模但未实现的风险类型**：至少加入
  - `wind`（大风落果/倒伏）
  - `high_humidity`（高湿烂果/病害）
- **跨年阶段提醒修正**：像“越冬期 11-01~02-15”，在 1/2 月时 stage_start_year 应该取去年，避免提醒永远不触发。

### 3) 让水稻在非生育期也有“阶段”，避免0分
修改 [crop_database.py](file:///D:/pythonProject/smart_weather/crop_database.py)：
- 给 `rice` 增加一个跨年的阶段，例如 `越冬休闲/整地期`（11-16~05-14），并给合理的 temp/water_need。
- 这样 2 月水稻不再是 None，
  - 评分不会变成 0
  - 也能产生“冻害/低温管理/整地窗口”类提示（符合主动智能）。

### 4) AI建议链路打通 + 优雅降级
同时改两处：
- 前端 [agro_dashboard.js](file:///D:/pythonProject/smart_weather/static/js/agro_dashboard.js)
  - 移除 mock `weather` 字段
  - 从页面注入的真实 `forecast/alerts` 生成 `weather_summary` 再调用 `/api/agro/advice`
- 后端 [farming_ai_adviser.py](file:///D:/pythonProject/smart_weather/farming_ai_adviser.py)
  - 如果 `DEEPSEEK_API_KEY` 未配置或调用失败：返回 **success=True** 的“规则化 JSON 建议”（基于阶段+未来天气+alerts），保证页面可用。

### 5) 作物详情页不再显示5月演示数据
- 修改 [app.py](file:///D:/pythonProject/smart_weather/app.py) 的 `crop_detail(crop_id)`
  - 传入 `forecast_list`（未来7天）
  - 传入 `crop_alerts`（筛选该作物相关的 alerts）
- 修改 [crop_detail.html](file:///D:/pythonProject/smart_weather/templates/crop_detail.html)
  - Chart.js 的 labels/data 改为使用后端传入的 `forecast_list`
  - AI 请求时把 `weather_summary` 和 `crop_alerts` 一起 POST 给 `/api/agro/advice`

## 验证方式
- 访问 `/agro-dashboard`
  - 中部日历有7行
  - 右侧列表与顶部滚动条至少出现 3 条提示（无极端天气也应有“窗口机会/注意事项”）
- 访问 `/crop/rice`、`/crop/tea` 等
  - 图表日期与当周一致（不是5月）
  - 点击“生成新建议”能返回内容（DeepSeek 或降级建议）

我将按以上 1→5 顺序落地修改，并在本地运行后确认 `/agro-dashboard` 与 `/crop/<id>` 页面数据完整显示。