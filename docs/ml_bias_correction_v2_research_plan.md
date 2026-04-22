# Smart Weather ML 误差校正 V2 方案

## 0. 文档定位

这份文档采用接近 `idea-discovery` + `research-pipeline` 的工作流风格来组织：

1. 先界定当前问题与升级目标
2. 再基于代码仓库现状和外部数据源做证据审计
3. 然后形成候选方案对比
4. 最后给出一条不覆盖现版模型的 V2 落地路线

本方案只做设计，不覆盖当前线上/当前仓库已存在的模型产物。

---

## 1. Problem Framing

### 1.1 当前问题

`smart_weather` 当前的机器学习误差校正已经完成了一版重要收敛：

- 训练样本已切到 `data/hangzhou_openmeteo`
- 训练与推理都开始统一到杭州国家站/馒头山坐标 `30.2444, 120.1528`
- `issue_time` 的推断和训练切分比旧版真实得多
- 运行时已经只对 `ECMWF/Open-Meteo` 这条链路启用校正

但当前版本仍有一个核心短板没有真正解决：

- **真值源仍然是 `Meteostat 58457`，而不是项目可验证的中国气象局杭州国家站原始/官方实况。**

这会带来三个直接风险：

1. 训练目标口径不完全可控  
   当前仓库 `models/config_*.json` 和 `models/training_manifest.json` 都明确把观测源写成了 `Meteostat 58457`，并标注为 `fallback`。

2. 业务可解释性受限  
   即使指标提升，也很难严格证明模型是在“杭州国家站官方实况”上提升，而不是在第三方聚合或重处理数据上提升。

3. 模型天花板受限  
   如果真值本身存在站点映射偏差、时间戳偏差、降水规则差异或缺测填补痕迹，模型学到的会是“预报误差 + 真值误差”的混合残差。

### 1.2 V2 目标

V2 不是简单“换个算法再训一遍”，而是要同时解决三件事：

1. **真值口径升级**
   尽量从 `Meteostat fallback` 升级到“杭州国家站官方实况”。

2. **建模能力升级**
   让模型结构比当前随机森林方案更适合中短期数值预报后处理。

3. **工程链路升级**
   让训练、评估、上线和回退形成双轨制，不覆盖当前稳定版。

---

## 2. Repository Evidence

### 2.1 当前训练链路

从仓库代码可确认：

- 训练脚本：`train_bias_correction.py`
- 运行时校正：`ml_correction.py`
- 运行时入口：`/apply-ml-correction`
- 预报输入：`advanced_forecast_service.py`
- 时次规则：`forecast_issue_time.py`

### 2.2 当前已落地的有效改进

从 `train_bias_correction.py` 和 `models/training_manifest.json` 可确认：

- 训练集目录：`data/hangzhou_openmeteo`
- 文件总数：`100`
- 有效加载：`97`
- 剔除异常文件：`3`
- 采集主簇：
  - `04:15` 左右 -> 映射到前一日 `20:00` 本地 issue_time -> `12Z`
  - `16:15` 左右 -> 映射到当日 `08:00` 本地 issue_time -> `00Z`
- 站点配置：
  - `station_id = 58457`
  - `lat = 30.2444`
  - `lon = 120.1528`

### 2.3 当前模型形态

当前模型是传统树模型方案：

- 温度：随机森林回归
- 湿度：随机森林回归
- 风速：随机森林回归
- 降水：二阶段
  - 降水分类随机森林
  - 降水回归随机森林

### 2.4 当前主要局限

从 `ml_correction.py` 和训练逻辑看，当前仍存在这些局限：

1. **特征仍偏浅层**
   主要是 forecast value + hour/month/day_of_week + issue/lead 派生，尚未引入更强的 cycle、season regime、rolling consistency 或多模式辅助特征。

2. **模型类型偏保守**
   随机森林鲁棒，但在数值后处理这类“连续值偏差订正”问题上，通常不是最强的表格模型。

3. **未显式建 uncertainty**
   当前只有点预测，没有分位数、不确定性或置信区间。

4. **未分层建模**
   现在虽然用了 `lead_hours` 和 `lead_category`，但没有把不同季节、昼夜、时效段的误差结构真正拆开。

5. **真值质量控制仍然较弱**
   目前只做了基础时间对齐与缺测容忍，没有形成“站点真值 QA pipeline”。

---

## 3. External Research Findings

### 3.1 是否能找到真正的杭州国家站实况观测数据源？

可以找到**官方候选源**，但目前没有看到匿名可直接调用的公开 API。

### 3.2 已确认的官方来源

#### 来源 A：国家气象信息中心 / 中国气象数据网

我检索到国家气象信息中心官方数据门户存在以下数据资源：

- **中国地面基本气象观测数据**
  - 官方页面显示为“中国国家地面气象站”
  - 数据描述为“逐三小时数据”
  - 包括气温、气压、湿度、风、降水
  - 滞后约 `2` 天
  - 共享级别为“个人实名、单位实名注册用户访问”

- **中国地面气象观测数据**
  - 空间范围为“中国国际交换地面气象站”
  - 同样为国家气象信息中心官方资料
  - 滞后约 `1-2` 天

- 平台首页特色资源中还出现了
  - **中国地面气象站逐小时观测资料**

但这一条“逐小时观测资料”的详情页我在匿名状态下没法稳定打开，因此**我只能合理推断它存在，但无法在当前条件下确认匿名接口细节、下载格式和授权门槛。**

#### 来源 B：杭州国家基准气候站官方站点背景

中国气象局官方报道可以确认：

- 杭州国家基准气候站确实位于馒头山一带
- 1971 年迁至凤山门馒头山现址
- 1993 年扩建为国家基准气候站
- 后续持续进行自动化观测升级

这说明当前项目把训练目标对齐到“杭州国家站/馒头山口径”的方向是正确的。

### 3.3 对 Meteostat 的判断

结论不是“不能用”，而是：

- **可以继续作为 fallback truth source 使用**
- **不适合继续作为 V2 的最高可信训练真值**

这是我的综合判断，依据包括：

1. 项目自身已经把它标成了 `fallback`
2. 它不是当前项目内可验证的 CMA 直接原始源
3. 对降水、风速、时次、站点元数据等业务敏感要素，第三方聚合源通常难以保证完全与国家站业务口径一致

换句话说：

- **做原型可以**
- **做论文可交代版本可以**
- **要追求更可信、更可持续的业务版 V2，不应继续把它当最终真值**

---

## 4. Opportunity Map

### 4.1 误差校正 V2 的最大提升点不在算法本身

如果只换模型、不换真值源，提升会有，但上限有限。

V2 更大的价值来自：

1. 真值口径升级
2. 真值质量控制
3. 分层建模
4. 更适合表格后处理的模型
5. 更真实的验证设计

### 4.2 V2 的核心假设

#### 假设 H1：官方国家站实况会优于 Meteostat fallback

这条最重要。  
一旦成立，哪怕算法暂时不变，结果可信度都会提升。

#### 假设 H2：分变量、分时效、分季节的轻分层模型会优于当前单套 RF

江南地区 ECMWF 常见的偏暖、偏湿误差具有明显季节性和时效性，统一一套模型会吃掉很多结构信息。

#### 假设 H3：降水应继续单独处理，甚至比当前更独立

降水的零值占比高、尾部重、随机性强，不宜和温湿风的连续订正思路完全混用。

---

## 5. Candidate Designs

### 5.1 方案 A：保守增强版

#### 数据

- 继续使用现有 `data/hangzhou_openmeteo`
- 真值优先改为 CMA 官方站点资料
- 实在拿不到时，再回落到 Meteostat

#### 模型

- 温度/湿度/风速：`LightGBM` 或 `CatBoost` 回归
- 降水：
  - 阶段 1：是否降水分类
  - 阶段 2：正降水样本回归

#### 优点

- 改造成本低
- 与当前运行时接口容易兼容

#### 缺点

- 不确定性输出仍弱
- 降水极端样本的稳定性仍可能一般

### 5.2 方案 B：业务优先推荐版

这是我最推荐的方案。

#### 数据层

- 构建 `observations_v2/` 数据层
- 按 source priority 组织：
  1. `cma_station_official`
  2. `provincial_cma_feed`（若后续有）
  3. `meteostat_fallback`
- 每小时样本都携带：
  - `obs_source`
  - `obs_quality_flag`
  - `station_id`
  - `station_distance_km`
  - `time_alignment_flag`

#### 模型层

按变量拆分：

- 温度：分位数回归 + 点估计回归
- 湿度：有界回归或变换后回归
- 风速：对数/平方根变换后回归
- 降水：零膨胀两阶段模型

按误差结构轻分层：

- `00Z` / `12Z` 分开
- `0-24h`、`24-72h`、`72-168h` 分 bucket
- warm season / cool season 分 bucket

#### 训练特征

保留当前特征，再新增：

- `issue_cycle`
- `season`
- `forecast_temp_change_3h`
- `forecast_rhum_change_3h`
- `forecast_wspd_change_3h`
- `target_hour_bucket`
- `lead_bucket × season` 交互特征
- 可选：
  - 同次起报相邻时效的 forecast trend
  - 多模式 spread 特征（若后续要把 GFS/ICON 作为辅助，不作为主校正对象）

#### 产出

- 点预测
- 分位数区间（如 `P10/P50/P90`）
- source-aware manifest

#### 优点

- 比现版更有业务解释力
- 比纯随机森林更适合后处理
- 能自然扩展到区间预报

#### 缺点

- 工程复杂度中等
- 需要额外依赖和训练治理

### 5.3 方案 C：研究增强版

在方案 B 基础上继续做：

- 残差序列建模
- regime clustering
- 多模型 stacking
- conformal calibration

这个方向更强，但当前项目阶段不建议作为第一落点。

---

## 6. Recommended V2 Architecture

## 6.1 总体判断

推荐采用 **方案 B：业务优先推荐版**。

原因：

1. 它比现版明显更强，但仍可控
2. 它把最大风险点放在“真值源治理”而不是盲目调参
3. 它可以保留现版模型并新增 V2，不会破坏当前线上链路

## 6.2 数据架构

### Truth Source Priority

```text
Tier 1: CMA / NMIC 官方国家站观测
Tier 2: 省级气象数据共享或授权接口
Tier 3: Meteostat 58457 fallback
```

### Observation Store

建议新增：

```text
data/observations_v2/
  manifest.json
  cma_hourly_hangzhou_YYYYMM.csv
  meteostat_hourly_hangzhou_YYYYMM.csv
  aligned_truth_YYYYMM.parquet
```

### 关键原则

- 预报样本和真值样本都按 `target_time` 小时整点对齐
- 一个样本键唯一为：
  - `issue_time + target_time + station_id + obs_source`
- 任何 fallback 都必须显式记录来源和质量等级

## 6.3 模型架构

### 连续变量

- 温度：`CatBoostRegressor` 或 `LightGBMRegressor`
- 湿度：`CatBoostRegressor`，输出后 clip 到 `0-100`
- 风速：对 `wspd` 做 `log1p` 后回归，再逆变换

### 降水

- 模型 1：`is_precip >= 0.1mm` 分类
- 模型 2：仅对 rain cases 做 amount regression
- 模型 3（可选）：极端降水 tail model

### 为什么不优先继续随机森林

- 模型文件很大
- 外推和分段偏差订正能力一般
- 对时效/季节结构的表达不如 boosting 系树模型自然

## 6.4 训练与验证

保持当前按 `issue_time` 切分的原则，不做随机打乱。

建议升级为：

- rolling origin CV
- final holdout by issue cycle
- 单独统计：
  - `00Z`
  - `12Z`
  - `0-24h / 24-72h / 72-168h`
  - warm season / cool season

### 指标

连续变量：

- `MAE`
- `RMSE`
- `Bias`
- `P90 absolute error`
- lead bucket MAE

降水：

- `Accuracy`
- `Precision`
- `Recall`
- `F1`
- `CSI`
- `Brier score`（如输出概率）
- `rainy-sample MAE`
- `overall MAE`

---

## 7. Official Observation Source Strategy

## 7.1 最优路线

### Route A：直接接入国家气象信息中心官方站点资料

目标源：

- 中国地面基本气象观测数据
- 中国地面气象观测数据
- 若可申请到，则优先“逐小时观测资料”

### 现实判断

这条路线**最可信**，但大概率需要：

- 实名注册
- 手工申请
- 下载权限
- 可能无公开匿名 API

因此它更适合作为 **V2 正式版真值源**。

## 7.2 次优路线

### Route B：省级气象数据共享/业务接口

如果你后续能拿到浙江省或杭州本地业务共享接口，这条路线甚至可能比国家数据门户更适合工程接入，因为：

- 更新频率更高
- 接口更贴近日常业务
- 更容易形成自动化采集

但当前这条路我没有查到公开可匿名验证的稳定官方入口。

## 7.3 过渡路线

### Route C：继续使用 Meteostat，但显式降级为 fallback

如果短期内拿不到官方真值，就保留 Meteostat 作为兜底，但要加：

- source flag
- QC rules
- consistency audit
- 与官方样本交叉校验接口

---

## 8. Execution Roadmap

## Phase 0：不动现版

保留当前：

- `models/*.pkl`
- `models/config_*.json`
- `models/training_manifest.json`
- 当前 `/apply-ml-correction`

不覆盖，不替换。

## Phase 1：先做 V2 数据层

新增但不接线上：

- `train_bias_correction_v2.py`
- `ml_correction_v2.py`
- `data/observations_v2/`
- `models_v2/`

重点完成：

1. truth source adapter
2. source-aware alignment
3. observation QC
4. manifest v2

## Phase 2：先做 baseline V2

建议顺序：

1. 温度 V2
2. 风速 V2
3. 湿度 V2
4. 降水 V2

先让连续变量稳定优于现版，再处理降水。

## Phase 3：双轨评估

输出：

- `metrics_report_v2.json`
- `training_manifest_v2.json`
- `comparison_report_v1_vs_v2.md`

只比较，不上线替换。

## Phase 4：灰度接线

前端或接口增加：

- `ml_version = v1 | v2`

先只在开发/隐藏开关里启用 V2。

---

## 9. Concrete Recommendations for This Project

### 9.1 现在就该做的

1. 新增 V2 方案文档和双轨目录结构
2. 抽象真值源接口，不再把 Meteostat 写死在训练脚本里
3. 先做官方国家站数据接入调研脚本或手工下载流程
4. 建 observation QA 清单

### 9.2 不建议现在就做的

1. 不要直接覆盖现有 `models/`
2. 不要在还没换真值源时就大规模调参
3. 不要把 GFS/ICON 一起混入同一套订正模型

### 9.3 如果当前拿不到官方小时真值

推荐折中方案：

- 先以官方 `逐三小时` / `定时值` 站点观测替代一部分评估集
- 让 V2 至少先在“更可信评估集”上比较
- 训练集暂用 Meteostat + source flag
- 等官方逐小时或业务授权接口到位后再重训正式 V2

这样做的价值是：

- 先把“评估口径”拉正
- 再逐步把“训练口径”拉正

---

## 10. Final Recommendation

### 结论一句话

**V2 的正确方向不是“直接重训一个更复杂的模型”，而是“先把杭州国家站真值源升级到官方口径，再用更适合表格后处理的分层 boosting 模型替代当前随机森林”。**

### 当前最推荐的落点

- 保留现版模型不动
- 新建 `V2` 双轨链路
- 真值优先争取接入国家气象信息中心官方站点资料
- 如果暂时拿不到，则以 `Meteostat fallback + source-aware QC` 作为过渡
- 建模优先采用：
  - 温湿风：`CatBoost/LightGBM`
  - 降水：zero-inflated two-stage

---

## 11. Sources

以下是本轮调研中直接用到的来源：

- 中国气象局：中国气象数据网介绍  
  https://www.cma.gov.cn/2011xzt/2017zt/20171128/2017112808/201711/t20171129_457115.html

- 国家气象信息中心：气象科学专业知识服务系统 / 中国地面基本气象观测数据  
  https://k.data.cma.cn/mekb/?dataCode=A.0012.0001&r=data%2Fdetail

- 国家气象信息中心：气象科学专业知识服务系统 / 中国地面气象观测数据  
  https://k.data.cma.cn/mekb/?dataCode=A.0012.0001.S011&r=data%2Fdetail

- 国家气象信息中心：气象科学专业知识服务系统检索页（时间条件为世界时）  
  https://k.data.cma.cn/mekb/?datacode=A.0012.0001&r=dataService%2Fcdcindex

- 国家气象信息中心门户特色资源页（出现“中国地面气象站逐小时观测资料”）  
  https://k.data.cma.cn/dict/

- 中国气象局：浙江杭州国家基准气候站报道  
  https://www.cma.gov.cn/ztbd/2024zt/20240515/2024051409/202406/t20240619_6361123.html

### 说明

关于“杭州国家站逐小时官方真值是否存在公开匿名下载接口”，本轮没有在匿名状态下确认到稳定可直接调用的开放 API；这一点需要后续通过注册登录或业务授权继续核实。
