# 修复 ML 校正功能问题

## 问题分析

### 问题1: 图例位置错误
- **用户意图**: 图例应该在图表上方靠下一点向左对齐，- **当前问题**: 图例被移到了图表下方
- **正确做法**: 
  - `legend.y` 应该在 `1.0` 左右一点（比如 `0.98` 到 `1.10`）
  - `margin.t` 增加到 `70` 或 `80`

### 问题2: 多模式对比数据结构错误
- **当前代码**: `ecmwfData.data?.temperature_2m`
- **实际结构**: 从日志看应该是 `models.ecmwf.data.temperature_2m`（没有嵌套的 `data.data`）
- **正确做法**: `ecmwfData.data.temperature_2m` 或 `ecmwfData.temperature_2m`

## 修改计划

### 修改文件
- `templates/advanced_forecast.html`

### 具体修改

#### 1. 修复72小时图表图例位置
```javascript
// 修改前
legend: {
    x: 0,
    y: -0.18,    // 图表下方
    orientation: 'h',
    font: { size: 10 }
},
margin: { l: 50, r: 120, t: 60, b: 80 }

// 修改后
legend: {
    x: 0,
    y: 1.05,    // 图表上方靠下一点
    orientation: 'h',
    font: { size: 10 }
},
margin: { l: 50, r: 120, t: 70, b: 80 }
```

#### 2. 修复多模式对比数据结构
```javascript
// 修改前
const temps = ecmwfData.data?.temperature_2m || [];

// 修改后
const temps = ecmwfData.data?.temperature_2m || ecmwfData.temperature_2m || [];
