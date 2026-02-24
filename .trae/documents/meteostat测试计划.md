# Meteostat 数据获取测试计划

## 目标
测试 meteostat 库获取杭州萧山机场 (58457) 昨日和今日逐小时观测数据的能力

## 测试内容
1. **站点**: 杭州萧山机场 (58457)
2. **时间范围**: 
   - 昨天 00:00 到 23:00（逐小时）
   - 今天可用数据
3. **要素**: 全部能获取到的（温度、降水、湿度、风速、风向、气压、云量等）

## 输出要求
1. 打印所有字段名称
2. 打印昨日第一条数据（展示有哪些字段）
3. 统计哪些字段有完整数据（非空比例）
4. 说明数据更新的最晚时次（延迟情况）

## 实施步骤

### 步骤1: 检查/安装 meteostat
- 检查 requirements.txt 是否包含 meteostat
- 如未安装，需要 `pip install meteostat`

### 步骤2: 创建测试脚本
创建 `test_meteostat.py` 测试脚本，包含：
- 导入 meteostat 库
- 设置站点 ID (58457)
- 获取昨日和今日逐小时数据
- 输出所需统计信息

### 步骤3: 运行测试并分析结果
- 执行测试脚本
- 分析数据完整性和更新延迟

## 预期代码结构

```python
from meteostat import Hourly, Stations
from datetime import datetime, timedelta
import pandas as pd

# 设置时间范围
yesterday = datetime.now() - timedelta(days=1)
start = yesterday.replace(hour=0, minute=0, second=0, microsecond=0)
end = start + timedelta(days=1)  # 昨日全天

# 获取站点数据
station_id = '58457'  # 杭州萧山机场
data = Hourly(station_id, start, end)
df = data.fetch()

# 输出分析结果
```

## 注意事项
- Meteostat 数据可能有延迟，实时数据可能不完整
- 需要检查网络连接
- 站点 ID 格式可能需要验证
