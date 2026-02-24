# Meteostat 实况数据收集脚本计划

## 目标
创建一个 Python 脚本，从 Meteostat 获取杭州萧山机场 (58457) 从 2026-01-11 到 2026-02-21 的逐小时观测数据，用于机器学习误差校正模型的训练。

## 数据需求分析

### 预报数据字段（Open-Meteo/ECMWF）
| 字段 | 说明 | 对应实况字段 |
|------|------|--------------|
| temperature_2m | 温度(°C) | temp |
| relative_humidity_2m | 相对湿度(%) | rhum |
| precipitation | 降水量(mm) | prcp |
| pressure_msl | 海平面气压(hPa) | pres |
| cloud_cover | 云量(%) | cldc |
| wind_speed_10m | 风速(km/h) | wspd |
| wind_direction_10m | 风向(°) | wdir |
| weather_code | 天气代码 | coco |

### 实况数据输出格式
```
datetime: 北京时间 (YYYY-MM-DD HH:MM)
temp: 温度(°C)
rhum: 湿度(%)
prcp: 降水量(mm)
wdir: 风向(°)
wspd: 风速(km/h)
pres: 气压(hPa)
cldc: 云量(%)
coco: 天气代码
```

## 实施步骤

### 步骤1: 创建数据收集脚本 `fetch_meteostat_observed.py`

**核心功能**:
1. 时间范围: 2026-01-11 00:00 到 2026-02-21 23:00
2. 站点: 58457 (杭州萧山机场)
3. 分批请求: 按月分批获取，避免请求超时
4. 重试机制: 失败后最多重试3次
5. 进度显示: 使用 tqdm 显示进度条

**脚本结构**:
```python
# 1. 导入依赖
import meteostat
from datetime import datetime, timedelta
import pandas as pd
from tqdm import tqdm
import time
import os
import shutil

# 2. 配置参数
STATION_ID = '58457'
START_DATE = datetime(2026, 1, 11)
END_DATE = datetime(2026, 2, 21, 23, 59, 59)
OUTPUT_PATH = 'data/hangzhou_observed_20260111_20260221.csv'

# 3. 分批获取函数
def fetch_data_in_batches(station_id, start, end, batch_days=30):
    """分批获取数据，每批30天"""
    pass

# 4. 重试机制
def fetch_with_retry(station_id, start, end, max_retries=3):
    """带重试的数据获取"""
    pass

# 5. 数据处理
def process_data(df):
    """处理字段名、时区、缺失值"""
    pass

# 6. 统计输出
def print_statistics(df):
    """打印数据统计信息"""
    pass

# 7. 主函数
def main():
    pass
```

### 步骤2: 数据处理细节

1. **时区处理**: Meteostat 返回 UTC 时间，需转换为北京时间 (UTC+8)
2. **字段重命名**: 将 meteostat 字段映射为标准字段名
3. **缺失值处理**: 缺失的小时用 NaN 填充，不插值
4. **数据对齐**: 确保每小时都有记录

### 步骤3: 统计输出内容

1. 总天数、总小时数
2. 各字段缺失情况（非空比例）
3. 每日数据条数（检查缺失日期）
4. 完全缺失的日期列表

### 步骤4: 输出文件

- 路径: `data/hangzhou_observed_20260111_20260221.csv`
- 编码: UTF-8
- 时间格式: YYYY-MM-DD HH:MM

## 注意事项

1. **缓存清理**: 每次运行前清理 `~/.meteostat/cache` 避免兼容性问题
2. **请求间隔**: 每批请求间隔 1 秒，避免被限流
3. **错误处理**: 记录失败的日期批次，最后汇总报告
4. **日志输出**: 打印详细的获取进度和状态

## 预期输出示例

```
============================================================
Meteostat 实况数据收集
============================================================
站点: 58457 (杭州萧山机场)
时间范围: 2026-01-11 00:00 ~ 2026-02-21 23:00
总天数: 42天
总小时数: 1008小时

[进度] 获取数据中...
  批次1 (2026-01-11 ~ 2026-02-10): 100%|████████| 30天/30天
  批次2 (2026-02-11 ~ 2026-02-21): 100%|████████| 12天/12天

[统计信息]
总记录数: 1008
字段完整性:
  temp:  100.0% (1008/1008)
  rhum:  100.0% (1008/1008)
  prcp:  100.0% (1008/1008)
  wdir:  100.0% (1008/1008)
  wspd:  100.0% (1008/1008)
  pres:  100.0% (1008/1008)
  cldc:   95.0% (958/1008)
  coco:   95.0% (958/1008)

每日数据条数:
  2026-01-11: 24条
  2026-01-12: 24条
  ...

[保存] data/hangzhou_observed_20260111_20260221.csv
完成！
============================================================
```
