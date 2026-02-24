# UI修复完善计划

## 问题清单

### 1. 历史气候模块问题

#### history_yearly.html
- [ ] 应用橙黄色主题 (#FF8F00) - 当前只是加深了蓝色
- [ ] 修复 "基于RP5高质量历史观测数据 | 对比基准：1981-2010气候态" 文字颜色，确保清晰可见
- [ ] 移除底部的 "© 2026 智能天气分析系统 | Powered by Flask & Plotly"
- [ ] 添加"趋势分析"导航跳转链接

#### history_trend.html
- [ ] 同样应用橙黄色主题
- [ ] 修复文字颜色问题
- [ ] 移除底部版权信息
- [ ] 添加"年度分析"导航跳转链接（与趋势分析对应）

### 2. 农业气象模块问题

#### agro_dashboard.html
- [ ] 导航链接应该靠右对齐（目前是me-auto靠左）
- [ ] 统一导航栏样式

#### 作物详情页面 (crop_detail.html)
- [ ] 应用绿色主题
- [ ] 引入公共CSS
- [ ] 替换为统一导航栏
- [ ] 更新页面标题

### 3. 其他需要检查的页面
- [ ] forecast.html - 是否需要优化
- [ ] ecmwf.html - 是否需要优化
- [ ] error.html - 是否需要优化

## 具体修复内容

### 历史气候模块主题色应用
```css
/* 需要添加的样式 */
.theme-history .page-header {
    background: linear-gradient(135deg, rgba(255, 143, 0, 0.15), rgba(255,255,255,1));
    border-bottom: 3px solid var(--history-theme);
}

.theme-history .section-title::before {
    background: var(--history-theme);
}

.theme-history .overview-card {
    border-top: 3px solid var(--history-theme);
}
```

### 导航链接修复
在历史气候页面添加子导航：
```html
<div class="sub-nav">
    <a href="/history/yearly" class="{% if request.path == '/history/yearly' %}active{% endif %}">年度分析</a>
    <a href="/history/trend" class="{% if request.path == '/history/trend' %}active{% endif %}">趋势分析</a>
</div>
```

### 农业气象导航修复
```html
<!-- 将 me-auto 改为 ms-auto -->
<ul class="navbar-nav ms-auto">
```

## 文件清单
1. templates/history_yearly.html - 修复主题色、文字颜色、底部版权、导航
2. templates/history_trend.html - 修复主题色、文字颜色、底部版权、导航
3. templates/agro_dashboard.html - 修复导航对齐
4. templates/crop_detail.html - 完整优化
5. 检查其他页面
