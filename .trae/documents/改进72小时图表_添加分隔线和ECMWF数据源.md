# 改进72小时精细化图表

## 需求

1. 每到新的一天显示一条加粗的黑线作为分隔
2. 将图表数据来源从 `best_match` 改为 `ecmwf_ifs`

## 实现方案

### 1. 修改数据源（后端）

**文件**: [advanced\_forecast\_service.py](file:///d:/pythonProject/smart_weather/advanced_forecast_service.py#L151)

将第151行的模型参数从 `"best_match"` 改为 `"ecmwf_ifs"`：

```python
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
        "forecast_days": 4,
        "models": "ecmwf_ifs",  # ← 修改：从 best_match 改为 ecmwf_ifs
        "timezone": "Asia/Shanghai"
    }
    ...
```

### 2. 添加每天分隔线（前端）

**文件**: [advanced\_forecast.html](file:///d:/pythonProject/smart_weather/templates/advanced_forecast.html)

在 `updateDetailedChart` 函数中，找到处理数据的部分，添加识别每天分隔的逻辑，然后在 layout 中添加垂直线形状。

#### 步骤1：识别每天的分隔点

在 JavaScript 中找到数据处理的代码段（约第388行附近），添加识别每天第一个数据点的逻辑：

```javascript
const labels = data.timestamps ? data.timestamps.slice(0, maxPoints) : data.full_labels.slice(0, maxPoints);

// 创建显示标签（每24小时显示日期，其他显示时间）
const displayLabels = labels.map((label, index) => {
    if (index % 24 === 0) {
        return label;
    } else if (index % 6 === 0) {
        return label.split(' ')[1];
    }
    return '';
});

// 识别每天的分隔点（新的一天开始）
const dayBoundaries = [];
let currentDate = '';
labels.forEach((label, index) => {
    const date = label.split(' ')[0];  // 获取日期部分
    if (date !== currentDate && index > 0) {
        dayBoundaries.push(label);
        currentDate = date;
    } else if (index === 0) {
        currentDate = date;
    }
});
```

#### 步骤2：在 layout 中添加分隔线

在 layout 配置中添加 `shapes` 属性来绘制垂直分隔线：

```javascript
const layout = {
    title: '未来72小时精细化预报',
    xaxis: {
        title: '日期时间',
        tickangle: 45,
        gridcolor: '#f0f0f0',
        tickmode: 'array',
        tickvals: labels.filter((_, i) => i % 6 === 0),
        ticktext: displayLabels.filter((_, i) => i % 6 === 0)
    },
    yaxis: {
        title: '温度 (°C)',
        side: 'left',
        position: 0.05,
        gridcolor: '#f0f0f0'
    },
    ...
    // 添加每天分隔线
    shapes: dayBoundaries.map(dateLabel => ({
        type: 'line',
        x0: dateLabel,
        x1: dateLabel,
        y0: 0,
        y1: 1,
        yref: 'paper',  // 使用相对坐标，从图表底部到顶部
        line: {
            color: '#000000',
            width: 2,
            dash: 'solid'
        }
    })),
    ...
};
```

### 3. 可选：改进标签显示

为了让新的一天更加醒目，可以改进标签显示逻辑，在每天的第一个标签前添加日期标识：

```javascript
const displayLabels = labels.map((label, index) => {
    if (index % 24 === 0) {
        // 每24小时（新的一天）显示完整日期
        return '▎' + label;  // 添加分隔符标识
    } else if (index % 6 === 0) {
        return label.split(' ')[1];
    }
    return '';
});
```

## 实施步骤

1. **修改后端数据源**

   * 打开 `advanced_forecast_service.py`

   * 找到 `fetch_detailed_72h_forecast` 函数

   * 将 `"models": "best_match"` 改为 `"models": "ecmwf_ifs"`

2. **添加每天分隔线**

   * 打开 `advanced_forecast.html`

   * 找到 `updateDetailedChart` 函数

   * 在数据处理部分添加 `dayBoundaries` 识别逻辑

   * 在 `layout` 中添加 `shapes` 配置

3. **重启服务并验证**

   * 重启 Flask 服务

   * 访问 `/advanced-forecast` 页面

   * 验证：

     * 图表数据来自 ECMWF

     * 每天的分隔线正确显示

     * 温度峰值时间正确（14:00左右）

## 预期效果

1. **数据源**: 72小时精细化图表将显示 ECMWF 模型的数据
2. **分隔线**: 每到新的一天（00:00）会显示一条加粗的黑色垂直线
3. **视觉效果**: 图表按天清晰分隔，便于观察每日天气变化规律

