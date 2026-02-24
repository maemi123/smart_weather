# 修复 ML 校正功能问题

## 问题分析

### 问题1: 72小时图表标题与图例重叠
- **原因**: `legend.y` 设置为 1.2，但 `margin.t` 只有 50px，空间不足
- **解决方案**: 
  - 增加 `margin.t` 到 80px
  - 调整 `legend.y` 到合适位置

### 问题2: 多模式对比页面 ML 后处理模型不显示
- **原因**: 当前实现只是把原始 ECMWF 数据重新显示，没有调用后端 API 进行校正
- **解决方案**:
  - 在 `updateModelComparison()` 中，当选中 ML 后处理模型时，需要异步调用 `/apply-ml-correction` API
  - 获取校正后的数据后再绘制图表

## 修改计划

### 修改文件
- `templates/advanced_forecast.html`

### 具体修改

#### 1. 修复72小时图表布局
```javascript
// 修改前
legend: {
    x: 0,
    y: 1.2,
    orientation: 'h',
    font: { size: 10 }
},
margin: { l: 50, r: 120, t: 50, b: 100 }

// 修改后
legend: {
    x: 0,
    y: -0.15,  // 移到图表下方
    orientation: 'h',
    font: { size: 10 }
},
margin: { l: 50, r: 120, t: 60, b: 80 }  // 调整边距
```

#### 2. 修复多模式对比 ML 后处理模型
- 将 `updateModelComparison()` 改为异步函数
- 当选中 ML 后处理模型时，调用 `/apply-ml-correction` API
- 使用校正后的数据绘制图表

## 实施步骤

1. 修改72小时图表的 legend 和 margin 设置
2. 修改 `updateModelComparison()` 函数，添加异步 ML 校正逻辑
