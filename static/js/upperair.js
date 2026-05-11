document.addEventListener('DOMContentLoaded', function() {
    // 状态变量
    let currentPlotType = 't_lnp';
    let currentDate = null;
    
    // DOM元素
    const plotImage = document.getElementById('plotImage');
    const plotPlaceholder = document.getElementById('plotPlaceholder');
    const plotLoading = document.getElementById('plotLoading');
    const refreshBtn = document.getElementById('refreshBtn');
    
    // 图表类型说明
    const plotDescriptions = {
        't_lnp': 'T-lnP图是气象专业标准探空图，展示了大气温度、露点随高度（气压）的变化，用于分析大气层结稳定性。',
        'skewt': 'Skew-T（斜温图）将温度坐标倾斜45度，使得等温线与干绝热线夹角接近90度，便于直观判断能量面积（CAPE）。',
        'wind': '高空风矢图展示了不同高度的风向和风速变化，左侧为风速廓线，右侧为风向随高度的变化趋势。',
        'simple': '卡通直观图通过直观的图标和颜色，向非专业人士展示当前大气的稳定状态和适宜活动。'
    };

    // 1. 图表类型切换
    document.getElementById('plotTypeGroup').addEventListener('click', function(e) {
        if (e.target.closest('.list-group-item')) {
            const btn = e.target.closest('.list-group-item');
            
            // 更新UI激活状态
            document.querySelectorAll('#plotTypeGroup .list-group-item').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            
            // 更新状态
            currentPlotType = btn.dataset.type;
            
            // 更新标题和说明
            document.getElementById('plotTitle').textContent = btn.textContent.trim();
            document.getElementById('plotDesc').textContent = plotDescriptions[currentPlotType];
            
            // 重新加载图表
            loadPlot();
        }
    });

    // 2. 时间选择切换
    document.querySelectorAll('input[name="timeOption"]').forEach(radio => {
        radio.addEventListener('change', function(e) {
            const historyGroup = document.getElementById('historyDateGroup');
            if (e.target.value === 'history') {
                historyGroup.classList.remove('d-none');
            } else {
                historyGroup.classList.add('d-none');
                currentDate = null;
            }
        });
    });

    // 历史时间变更
    document.getElementById('historyDate').addEventListener('change', function(e) {
        currentDate = e.target.value.replace('T', ' ');
    });

    // 3. 刷新按钮点击
    refreshBtn.addEventListener('click', function() {
        refreshAllData();
    });

    // 查看原始数据按钮
    document.getElementById('viewRawBtn').addEventListener('click', function() {
        // 显示加载中
        document.getElementById('rawDataContent').value = "正在加载原始数据...";
        const rawModal = new bootstrap.Modal(document.getElementById('rawDataModal'));
        rawModal.show();
        
        // 构建请求URL
        let url = '/upperair/data';
        if (currentDate) {
            url += `?date=${encodeURIComponent(currentDate)}`;
        }
        
        // 这里需要后端API支持返回原始CSV内容
        // 目前 /upperair/data 返回的是解析后的JSON
        // 我们可以在JSON里带上原始数据的下载链接，或者直接请求CSV文件
        // 为了简单，我们先用JSON里的数据手动格式化一下，或者请求一个新接口
        // 鉴于时间关系，我们从JSON重构CSV展示
        
        fetch(url)
            .then(response => response.json())
            .then(result => {
                if (result.success && result.data.raw_levels) {
                    // 使用后端返回的 raw_levels 构造完整 CSV 数据
                    let text = "PRES(hPa),HGHT(m),TEMP(C),DWPT(C),RELH(%),MIXR(g/kg),DRCT(deg),SPED(m/s),THTA(K),THTE(K),THTV(K)\n";
                    
                    const levels = result.data.raw_levels;
                    if (Array.isArray(levels)) {
                        levels.forEach(row => {
                            // 确保顺序一致，处理可能缺失的字段
                            const fields = [
                                row.PRES, row.HGHT, row.TEMP, row.DWPT, 
                                row.RELH, row.MIXR, row.DRCT, row.SPED, 
                                row.THTA, row.THTE, row.THTV
                            ];
                            text += fields.map(v => v !== undefined ? v : '').join(',') + "\n";
                        });
                    }
                    
                    document.getElementById('rawDataContent').value = text;
                } else if (result.success && result.data.layer_data) {
                    // 降级方案：如果 raw_levels 不存在，显示摘要
                    let text = "--- 关键层级数据摘要 (完整数据未加载) ---\n\n";
                    // ... (原有摘要逻辑)
                    const layers = result.data.layer_data;
                    for (const [level, info] of Object.entries(layers)) {
                        text += `[${level}]\n`;
                        if (typeof info === 'object') {
                            for (const [k, v] of Object.entries(info)) {
                                text += `  ${k}: ${v}\n`;
                            }
                        } else {
                            text += `  ${info}\n`;
                        }
                        text += "\n";
                    }
                    document.getElementById('rawDataContent').value = text;
                } else {
                    document.getElementById('rawDataContent').value = "获取数据失败";
                }
            });
    });
    
    // 一键复制功能
    document.getElementById('copyRawBtn').addEventListener('click', function() {
        const textarea = document.getElementById('rawDataContent');
        textarea.select();
        document.execCommand('copy');
        
        const originalText = this.innerHTML;
        this.innerHTML = '<i class="fas fa-check me-2"></i>已复制';
        setTimeout(() => {
            this.innerHTML = originalText;
        }, 2000);
    });

    // 初始化Tooltips
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'))
    var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl)
    })

    // 4. 加载图表函数
    function loadPlot() {
        showLoading(true);
        
        let url = `/upperair/plot/${currentPlotType}`;
        if (currentDate) {
            url += `?date=${encodeURIComponent(currentDate)}`;
        }
        
        fetch(url)
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    plotImage.src = data.url + '?t=' + new Date().getTime(); // 防止缓存
                    plotImage.classList.remove('d-none');
                    plotPlaceholder.classList.add('d-none');
                } else {
                    alert('获取图表失败: ' + data.error);
                }
            })
            .catch(error => console.error('Error:', error))
            .finally(() => showLoading(false));
    }

    // 5. 加载数据和分析
    function loadDataAndAnalysis() {
        // 更新UI显示正在加载
        document.getElementById('aiAnalysisContent').innerHTML = `
            <div class="d-flex align-items-center">
                <div class="spinner-grow text-primary me-2" role="status"></div>
                <span>正在获取最新数据并生成分析...</span>
            </div>
        `;
        
        let url = '/upperair/data';
        if (currentDate) {
            url += `?date=${encodeURIComponent(currentDate)}`;
        }
        
        fetch(url)
            .then(response => response.json())
            .then(result => {
                if (result.success) {
                    updateUI(result.data);
                } else {
                    document.getElementById('aiAnalysisContent').innerHTML = `
                        <div class="alert alert-danger">
                            获取数据失败: ${result.error}
                        </div>
                    `;
                }
            })
            .catch(error => {
                console.error('Error:', error);
                document.getElementById('aiAnalysisContent').innerHTML = `
                    <div class="alert alert-danger">网络请求异常</div>
                `;
            });
    }

    // 6. 更新UI界面
    function updateUI(data) {
        // 更新元数据
        if (data.metadata) {
            const time = data.metadata.time_utc || '未知时间';
            const station = data.metadata.station_id || '58457';
            document.getElementById('stationInfo').textContent = `杭州 (${station}) ${time}`;
            const requestedLocal = data.metadata.requested_time_local || '最新可用时次';
            const resolvedUtc = data.metadata.resolved_time_utc || '未知 UTC 时次';
            const fallbackText = data.metadata.fallback_used ? '，已自动回退到上一标准时次。' : '';
            document.getElementById('resolvedTimeInfo').textContent =
                `按北京时间请求：${requestedLocal}；实际分析时次：${resolvedUtc}${fallbackText}`;
        }

        // 更新指数列表
        const p = data.parameters;
        updateBadge('val_cape', p.cape, 1000, 2500);
        updateBadge('val_cin', p.cin, null, null); // CIN通常越小越好，暂不设色
        updateBadge('val_k', p.k_index, 30, 35);
        updateBadge('val_li', p.lifted_index, 0, -3, true); // LI越小越不稳定
        updateBadge('val_shear', p.shear_06km, 12, 20);
        updateBadge('val_pw', p.precip_water, 30, 50);

        // 更新风险评估
        const risk = data.risk_assessment;
        const riskAlert = document.getElementById('riskAlert');
        riskAlert.className = `alert alert-${getRiskAlertClass(risk.color)}`;
        document.getElementById('riskLevel').textContent = `风险等级：${risk.level}`;
        document.getElementById('riskDesc').textContent = risk.description;
        document.getElementById('riskHazards').textContent = risk.hazards.length > 0 ? risk.hazards.join('、') : '无';
        
        // 更新风险进度条
        updateProgressBar('capeBar', p.cape, 3000, 'J/kg');
        updateProgressBar('shearBar', p.shear_06km, 30, 'm/s');

        // 更新AI分析报告
        const ai = data.ai_analysis;
        const impacts = ai.impacts || {};
        
        let html = `
            <div class="mb-3">
                <h5 class="text-dark">📊 专业解读</h5>
                <p class="text-secondary">${ai.professional}</p>
            </div>
            
            <div class="mb-3 p-3 bg-white rounded border-start border-4 border-warning">
                <h5 class="text-warning"><i class="fas fa-lightbulb me-2"></i>通俗比喻</h5>
                <p class="mb-0 fw-bold">"${ai.simple}"</p>
            </div>
            
            <div class="row g-2">
                <div class="col-md-4">
                    <div class="card h-100 border-0 bg-light">
                        <div class="card-body p-2 text-center">
                            <i class="fas fa-plane text-primary mb-1"></i>
                            <h6 class="card-title text-muted small">航空影响</h6>
                            <small>${impacts.aviation || '无特殊影响'}</small>
                        </div>
                    </div>
                </div>
                <div class="col-md-4">
                    <div class="card h-100 border-0 bg-light">
                        <div class="card-body p-2 text-center">
                            <i class="fas fa-seedling text-success mb-1"></i>
                            <h6 class="card-title text-muted small">农业影响</h6>
                            <small>${impacts.agriculture || '无特殊影响'}</small>
                        </div>
                    </div>
                </div>
                <div class="col-md-4">
                    <div class="card h-100 border-0 bg-light">
                        <div class="card-body p-2 text-center">
                            <i class="fas fa-walking text-info mb-1"></i>
                            <h6 class="card-title text-muted small">生活影响</h6>
                            <small>${impacts.daily || '无特殊影响'}</small>
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        document.getElementById('aiAnalysisContent').innerHTML = html;
    }

    // 辅助函数：更新徽章
    function updateBadge(id, value, warnThresh, dangerThresh, reverse=false) {
        const el = document.getElementById(id);
        const isMissing = value === null || value === undefined || value === 'N/A';
        el.textContent = isMissing ? 'N/A' : value;
        
        el.className = 'badge rounded-pill';
        
        if (isMissing) {
            el.classList.add('bg-secondary');
            return;
        }
        
        let isDanger = false;
        let isWarn = false;
        
        if (reverse) {
            if (value < dangerThresh) isDanger = true;
            else if (value < warnThresh) isWarn = true;
        } else {
            if (value > dangerThresh) isDanger = true;
            else if (value > warnThresh) isWarn = true;
        }
        
        if (isDanger) el.classList.add('bg-danger');
        else if (isWarn) el.classList.add('bg-warning', 'text-dark');
        else el.classList.add('bg-success');
    }
    
    // 辅助函数：获取风险颜色类
    function getRiskAlertClass(color) {
        const map = {
            'success': 'success',
            'info': 'info',
            'warning': 'warning',
            'danger': 'danger'
        };
        return map[color] || 'secondary';
    }
    
    // 辅助函数：更新进度条
    function updateProgressBar(id, value, max, unit) {
        const bar = document.getElementById(id);
        const text = document.getElementById(id.replace('Bar', 'Text'));

        if (value === null || value === undefined || value === 'N/A') {
            bar.style.width = '0%';
            text.textContent = 'N/A';
            return;
        }

        const val = parseFloat(value);
        if (Number.isNaN(val)) {
            bar.style.width = '0%';
            text.textContent = 'N/A';
            return;
        }
        const percent = Math.min(100, Math.max(0, (val / max) * 100));
        
        bar.style.width = `${percent}%`;
        text.textContent = `${val} ${unit}`;
    }

    function showLoading(show) {
        if (show) {
            plotLoading.style.display = 'flex';
        } else {
            plotLoading.style.display = 'none';
        }
    }

    function refreshAllData() {
        // 先加载图表，再加载分析，并行进行
        loadPlot();
        loadDataAndAnalysis();
    }

    // 初始化：自动加载最新数据
    refreshAllData();
    function formatUpperairError(prefix, message) {
        const text = message || '未知错误';
        return `${prefix}：${text}`;
    }

    loadPlot = function() {
        showLoading(true);

        let url = `/upperair/plot/${currentPlotType}`;
        if (currentDate) {
            url += `?date=${encodeURIComponent(currentDate)}`;
        }

        fetch(url)
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    plotImage.src = data.url + '?t=' + new Date().getTime();
                    plotImage.classList.remove('d-none');
                    plotPlaceholder.classList.add('d-none');
                } else {
                    alert(formatUpperairError('获取图表失败', data.error));
                }
            })
            .catch(error => {
                console.error('Error:', error);
                alert(formatUpperairError('获取图表失败', '网络请求异常，请检查网络连接后重试。'));
            })
            .finally(() => showLoading(false));
    };

    loadDataAndAnalysis = function() {
        document.getElementById('aiAnalysisContent').innerHTML = `
            <div class="d-flex align-items-center">
                <div class="spinner-grow text-primary me-2" role="status"></div>
                <span>正在获取最新数据并生成分析...</span>
            </div>
        `;

        let url = '/upperair/data';
        if (currentDate) {
            url += `?date=${encodeURIComponent(currentDate)}`;
        }

        fetch(url)
            .then(response => response.json())
            .then(result => {
                if (result.success) {
                    updateUI(result.data);
                } else {
                    document.getElementById('aiAnalysisContent').innerHTML = `
                        <div class="alert alert-danger">
                            ${formatUpperairError('获取数据失败', result.error)}
                        </div>
                    `;
                }
            })
            .catch(error => {
                console.error('Error:', error);
                document.getElementById('aiAnalysisContent').innerHTML = `
                    <div class="alert alert-danger">${formatUpperairError('获取数据失败', '网络请求异常，请检查网络连接后重试。')}</div>
                `;
            });
    };
});
