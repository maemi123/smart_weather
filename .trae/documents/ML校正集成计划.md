# 集成机器学习误差校正模型到 /advanced-forecast 页面

## 目标
将训练好的随机森林误差校正模型集成到多模式预报页面，提供机器学习后处理功能。

## 已有模型文件
- `models/rf_temp.pkl` - 温度校正
- `models/rf_rhum.pkl` - 湿度校正
- `models/rf_wspd.pkl` - 风速校正
- `models/rf_precip_clf.pkl` - 降水分类
- `models/rf_precip_reg.pkl` - 降水回归

## 实施步骤

### 步骤1: 创建 ml_correction.py 模块

**功能**:
- 加载所有5个模型
- 封装预测函数
- 特征工程逻辑（复用训练脚本）

**关键代码**:
```python
FEATURE_COLUMNS = [
    'forecast_temp', 'forecast_rhum', 'forecast_wspd', 'forecast_pres',
    'hour', 'month', 'day_of_week', 'is_day', 'is_weekend',
    'lead_hours', 'lead_category', 'hour_sin', 'hour_cos'
]

class MLCorrector:
    def __init__(self, models_dir='models'):
        # 加载所有模型
        pass
    
    def create_features(self, forecast_data, issue_time):
        # 创建特征（复用训练脚本逻辑）
        pass
    
    def correct(self, forecast_data, issue_time):
        # 对预报数据进行校正
        # 返回校正后的数据
        pass
```

### 步骤2: 修改 app.py 添加新路由

**新路由**: `/apply-ml-correction`

```python
@app.route('/apply-ml-correction', methods=['POST'])
def apply_ml_correction():
    """
    应用机器学习误差校正
    接收: {"data": 预报数据列表, "issue_time": 起报时间}
    返回: {"success": True, "corrected_data": 校正后数据}
    """
    pass
```

### 步骤3: 修改 advanced_forecast.html

#### 3.1 72小时精细化页面
在图表上方添加开关：
```html
<div class="ml-correction-toggle">
    <label>
        <input type="checkbox" id="ml_correction" onchange="toggleMLCorrection()">
        机器学习误差校正
    </label>
</div>
```

修改 `updateDetailedChart()` 函数：
- 当开关打开时，调用 `/apply-ml-correction` API
- 用返回的校正数据重新绘制图表

#### 3.2 多模式对比页面
在模型选择器中添加新模型：
```html
<div class="model-checkbox">
    <input type="checkbox" id="model_ecmwf_ml" onchange="updateModelComparison()">
    <div class="color-indicator" style="background: #e67e22;"></div>
    <label for="model_ecmwf_ml">ECMWF (ML后处理)</label>
</div>
```

### 步骤4: 特征工程复用

需要复用 `train_bias_correction.py` 中的特征工程逻辑：
- `hour`: 小时 (0-23)
- `month`: 月份
- `day_of_week`: 星期几
- `is_day`: 是否白天
- `is_weekend`: 是否周末
- `lead_hours`: 预报时效
- `lead_category`: 时效分类
- `hour_sin/cos`: 小时周期性编码

### 步骤5: 错误处理

- 模型加载失败时返回原始数据
- 添加日志记录
- 前端显示校正状态

## 文件修改清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `ml_correction.py` | 新建 | ML校正模块 |
| `app.py` | 修改 | 添加 `/apply-ml-correction` 路由 |
| `templates/advanced_forecast.html` | 修改 | 添加开关和JS逻辑 |

## 注意事项

1. **特征一致性**: 预测时的特征必须与训练时完全一致
2. **起报时间推断**: 需要正确推断起报时间用于计算 lead_hours
3. **数据格式**: 确保前后端数据格式一致
4. **性能**: 考虑缓存模型对象，避免每次请求都加载
