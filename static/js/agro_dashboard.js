// agro_dashboard.js
// 农业气象模块前端逻辑

document.addEventListener('DOMContentLoaded', function() {
    
    // 1. 初始化 Tooltips
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'))
    var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl)
    });

    // 2. 详情页 AI 建议刷新逻辑
    const refreshAiBtn = document.getElementById('refreshAiBtn');
    if (refreshAiBtn) {
        refreshAiBtn.addEventListener('click', fetchAiAdvice);
    }
});

/**
 * 获取 AI 农事建议
 */
function fetchAiAdvice() {
    const btn = document.getElementById('refreshAiBtn');
    const loading = document.getElementById('aiLoading');
    const content = document.getElementById('aiContent');
    
    const cropName = document.getElementById('cropName').value;
    const cropStage = document.getElementById('cropStage').value;
    
    // UI 状态切换
    btn.disabled = true;
    content.classList.add('d-none');
    loading.classList.remove('d-none');
    
    const agroContextEl = document.getElementById('agroContext');
    let forecast = [];
    let alerts = [];
    if (agroContextEl && agroContextEl.textContent) {
        try {
            const ctx = JSON.parse(agroContextEl.textContent);
            forecast = Array.isArray(ctx.forecast) ? ctx.forecast : [];
            alerts = Array.isArray(ctx.alerts) ? ctx.alerts : [];
        } catch (e) {
            forecast = [];
            alerts = [];
        }
    }

    const forecast3 = forecast.slice(0, 3);
    const weatherSummary = forecast3.length
        ? forecast3.map(d => `${d.date} ${d.temp_min}~${d.temp_max}℃ 降水${d.precip}mm 风${d.wind}m/s`).join('；')
        : "暂无未来天气数据";

    const cropAlerts = alerts.filter(a => (a.crop_name === cropName) || (a.crop_id && a.crop_id === cropName));

    const payload = {
        crop_name: cropName,
        stage: cropStage,
        weather: weatherSummary,
        alerts: cropAlerts.slice(0, 6)
    };
    
    fetch('/api/agro/advice', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(payload)
    })
    .then(response => response.json())
    .then(result => {
        loading.classList.add('d-none');
        content.classList.remove('d-none');
        btn.disabled = false;
        
        if (result.success && result.data) {
            renderAiAdvice(result.data);
        } else {
            // 显示错误或备用信息
            document.getElementById('aiSummary').textContent = "AI 服务暂时繁忙，请稍后再试。";
            if (result.error) console.error(result.error);
        }
    })
    .catch(error => {
        console.error('Error:', error);
        loading.classList.add('d-none');
        content.classList.remove('d-none');
        btn.disabled = false;
        document.getElementById('aiSummary').textContent = "网络请求失败。";
    });
}

/**
 * 渲染 AI 建议到页面
 */
function renderAiAdvice(data) {
    // 1. 总结
    if (data.summary) {
        document.getElementById('aiSummary').textContent = data.summary;
    }
    
    // 2. 操作建议
    const opsList = document.getElementById('aiOps');
    opsList.innerHTML = '';
    if (data.operations && data.operations.length > 0) {
        data.operations.forEach(op => {
            const li = document.createElement('li');
            li.className = 'list-group-item bg-transparent';
            li.innerHTML = `<span class="fw-bold text-dark">${op.action}</span>: <span class="text-muted small">${op.detail}</span>`;
            opsList.appendChild(li);
        });
    } else {
        opsList.innerHTML = '<li class="list-group-item bg-transparent text-muted">无特殊操作建议</li>';
    }
    
    // 3. 风险防范
    const risksList = document.getElementById('aiRisks');
    risksList.innerHTML = '';
    if (data.risks && data.risks.length > 0) {
        // 兼容字符串列表或对象列表
        data.risks.forEach(risk => {
            const li = document.createElement('li');
            li.className = 'list-group-item bg-transparent';
            // 如果是对象则取 risk 字段，否则直接显示
            const riskText = typeof risk === 'object' ? (risk.risk || risk.desc || JSON.stringify(risk)) : risk;
            li.innerHTML = `<i class="fas fa-dot-circle text-danger me-2 small"></i>${riskText}`;
            risksList.appendChild(li);
        });
    } else {
        risksList.innerHTML = '<li class="list-group-item bg-transparent text-muted">无明显气象风险</li>';
    }
    
    // 4. 叮嘱
    if (data.tips) {
        document.getElementById('aiTips').textContent = data.tips;
    }
}
