# 继续UI美化计划 - 剩余页面

## 当前进度
- ✅ 公共CSS文件已创建 (static/css/common.css)
- ✅ 首页已美化 (index.html)
- ⏳ 多模式预报页 (advanced_forecast.html) - 待美化
- ⏳ 历史气候页 (history_yearly.html) - 待美化
- ⏳ 探空分析页 (upperair.html) - 待美化
- ⏳ 农业气象页 (agro_dashboard.html) - 待美化

## 实施策略

对于每个页面，我将执行以下标准化改造：

### 1. 引入公共CSS
在 `<head>` 中添加：
```html
<link href="{{ url_for('static', filename='css/common.css') }}" rel="stylesheet">
```

### 2. 替换导航栏
将原有导航栏替换为统一风格：
```html
<nav class="navbar navbar-expand-lg navbar-custom">
    <div class="container">
        <a class="navbar-brand" href="/">
            <i class="fas fa-cloud-sun"></i>智慧天气
        </a>
        <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#navbarNav">
            <span class="navbar-toggler-icon"></span>
        </button>
        <div class="collapse navbar-collapse" id="navbarNav">
            <ul class="navbar-nav ms-auto">
                <li class="nav-item"><a class="nav-link" href="/">首页</a></li>
                <li class="nav-item"><a class="nav-link active" href="/advanced-forecast">多模式预报</a></li>
                <li class="nav-item"><a class="nav-link" href="/upperair">探空分析</a></li>
                <li class="nav-item"><a class="nav-link" href="/agro-dashboard">农业气象</a></li>
                <li class="nav-item"><a class="nav-link" href="/history/yearly">历史气候</a></li>
            </ul>
        </div>
    </div>
</nav>
```

### 3. 更新页面标题
统一格式：`智慧天气丨模块名称`

### 4. 使用CSS变量替换硬编码颜色
- `#3498db` → `var(--primary-color)` 或 `var(--forecast-theme)`
- `#f5f7fa` → `var(--bg-color)`
- `#2c3e50` → `var(--text-primary)`
- `#7f8c8d` → `var(--text-secondary)`
- 卡片阴影统一使用 `var(--card-shadow)`
- 圆角统一使用 `var(--card-radius)`

### 5. 各页面特定调整

#### 多模式预报页 (advanced_forecast.html)
- 主题色：浅蓝色 `#42A5F5`
- 标签页按钮使用 `.tab-btn-custom` 样式
- 图表容器使用 `.chart-container` 样式
- 数据卡片使用 `.metric-card` 样式

#### 历史气候页 (history_yearly.html)
- 主题色：橙黄色 `#FF8F00`
- 概览卡片添加主题色边框
- 控制面板美化

#### 探空分析页 (upperair.html)
- 主题色：深紫色 `#5E35B1`
- 控制面板卡片化
- 图表区域添加卡片容器

#### 农业气象页 (agro_dashboard.html)
- 主题色：绿色 `#43A047`
- 保留绿色主题但统一风格
- 预警区域美化

## 实施顺序
1. 多模式预报页 (advanced_forecast.html)
2. 历史气候页 (history_yearly.html)
3. 探空分析页 (upperair.html)
4. 农业气象页 (agro_dashboard.html)
5. 验证测试
