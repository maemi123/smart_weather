# ====== 第一步：先设置matplotlib后端，避免警告 ======
import matplotlib
matplotlib.use('Agg')  # 必须在导入pyplot之前设置

# ====== 第二步：忽略所有警告（临时解决方案） ======
import warnings
warnings.filterwarnings("ignore", category=UserWarning)

# ====== 第三步：现在导入其他库 ======
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
import platform

# ====== 第四步：设置中文字体（简化版，避免问题） ======
# 不尝试加载特定字体，直接使用系统默认
try:
    # 只设置字体族，不指定具体字体文件
    plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'DejaVu Sans']
    plt.rcParams['axes.unicode_minus'] = False
    print("[INFO] Font configuration applied")
except Exception as e:
    print("[INFO] Using default font: " + str(e))

# ====== 第五步：导入其他需要的库 ======
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import os
import numpy as np  # 添加这行

matplotlib.use('Agg')  # 重要：在Flask中使用必须设置此项

# === 新增：解决中文显示问题 ===
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
import platform

# 根据操作系统设置中文字体
system = platform.system()
if system == 'Windows':
    # Windows系统使用微软雅黑
    font_path = 'C:/Windows/Fonts/msyh.ttc'  # 微软雅黑
elif system == 'Darwin':  # macOS
    font_path = '/System/Library/Fonts/PingFang.ttc'  # 苹方
else:  # Linux
    font_path = '/usr/share/fonts/truetype/wqy/wqy-microhei.ttc'  # 文泉驿

try:
    # 设置全局字体
    matplotlib.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'DejaVu Sans']
    matplotlib.rcParams['axes.unicode_minus'] = False  # 解决负号显示问题

    # 创建字体属性对象
    chinese_font = FontProperties(fname=font_path)
    # 使用纯ASCII字符的输出，避免编码问题
    print("[INFO] Chinese font loaded successfully: " + font_path)
except Exception as e:
    # 使用纯英文错误信息
    print("[WARNING] Font loading failed, using default: " + str(e))
    chinese_font = FontProperties()


# === 字体配置结束 ===


class ChartGenerator:
    @staticmethod
    def create_temperature_chart(weather_df):
        """创建温度趋势图（Matplotlib版本）"""
        # 确保目录存在
        os.makedirs('static/charts', exist_ok=True)

        plt.figure(figsize=(10, 5))

        # 准备数据 - 更安全的日期处理
        dates = []
        for i, date_str in enumerate(weather_df['date'].tolist()):
            try:
                # 尝试解析日期字符串
                if isinstance(date_str, str):
                    # 如果是 "12月26日 周四" 格式
                    if '月' in date_str and '日' in date_str:
                        date_part = date_str.split()[0]  # "12月26日"
                        month = date_part.split('月')[0]
                        day = date_part.split('月')[1].replace('日', '')
                        dates.append(f"{month}/{day}")
                    else:
                        dates.append(f"Day {i + 1}")
                else:
                    dates.append(f"Day {i + 1}")
            except:
                dates.append(f"Day {i + 1}")

        # 只取前3个数据点
        dates = dates[:3]
        max_temps = weather_df['temp_max'].tolist()[:3]
        min_temps = weather_df['temp_min'].tolist()[:3]

        # 绘制折线
        plt.plot(dates, max_temps, marker='o', linewidth=3, color='#ff6b6b', label='最高温')
        plt.plot(dates, min_temps, marker='s', linewidth=3, color='#4d96ff', label='最低温')

        # 填充区域
        plt.fill_between(dates, min_temps, max_temps, alpha=0.2, color='#95e1d3')

        # 添加数据标签
        for i, (date, max_t, min_t) in enumerate(zip(dates, max_temps, min_temps)):
            plt.text(date, max_t + 0.3, f'{max_t}°C', ha='center', va='bottom', fontsize=10)
            plt.text(date, min_t - 0.5, f'{min_t}°C', ha='center', va='top', fontsize=10)

        # 美化图表
        plt.title('未来三天温度趋势', fontsize=16, fontweight='bold', pad=20)
        plt.xlabel('日期', fontsize=12)
        plt.ylabel('温度 (°C)', fontsize=12)
        plt.grid(True, alpha=0.3, linestyle='--')
        plt.legend(loc='upper left')
        plt.xticks(rotation=15)

        # 保存为图片
        chart_path = 'static/charts/temperature_trend.png'
        plt.tight_layout()
        plt.savefig(chart_path, dpi=100, transparent=False)
        plt.close()

        return chart_path

    @staticmethod
    def create_weather_radar_chart(weather_df):
        """创建直观易懂的天气雷达图"""
        try:
            # 1. 计算真实、易懂的指标
            categories = ['平均高温', '平均低温', '总降水量', '平均湿度', '平均风力']

            # 使用真实数值，不归一化到0-1
            avg_high_temp = weather_df['temp_max'].mean()
            avg_low_temp = weather_df['temp_min'].mean()
            total_precip = weather_df['precipitation'].sum()
            avg_humidity = weather_df['humidity'].mean()

            # 风力处理：将"2-3级"这样的字符串转换为数字
            wind_levels = []
            for wind in weather_df['wind_scale']:
                if isinstance(wind, str):
                    # 提取数字，如"2-3" -> 取第一个数字2
                    if '-' in wind:
                        try:
                            level = float(wind.split('-')[0])
                            wind_levels.append(level)
                        except:
                            wind_levels.append(1.0)
                    else:
                        try:
                            wind_levels.append(float(wind))
                        except:
                            wind_levels.append(1.0)
                else:
                    wind_levels.append(1.0)

            avg_wind = sum(wind_levels) / len(wind_levels) if wind_levels else 1.0

            # 2. 为了雷达图展示，我们需要相对值（但保留真实数值标签）
            # 设置合理的最大值范围
            max_values = [35, 25, 30, 100, 6]  # 高温,低温,降水,湿度,风力的最大可能值

            # 计算雷达图需要的相对值（0-1范围）
            relative_values = [
                min(avg_high_temp / max_values[0], 1.0),
                min(avg_low_temp / max_values[1], 1.0),
                min(total_precip / max_values[2], 1.0),
                min(avg_humidity / max_values[3], 1.0),
                min(avg_wind / max_values[4], 1.0)
            ]

            # 3. 创建雷达图
            fig = go.Figure(data=go.Scatterpolar(
                r=relative_values + [relative_values[0]],  # 闭合图形
                theta=categories + [categories[0]],  # 闭合图形
                fill='toself',
                line=dict(color='#3498db', width=3),
                fillcolor='rgba(52, 152, 219, 0.3)',
                marker=dict(size=8, color='#2c3e50'),
                hoverinfo='text',
                # 添加悬停文本，显示真实数值
                text=[f'{cat}: {val:.1f}' for cat, val in zip(
                    categories,
                    [avg_high_temp, avg_low_temp, total_precip, avg_humidity, avg_wind]
                )]
            ))

            # 4. 美化图表
            fig.update_layout(
                polar=dict(
                    radialaxis=dict(
                        visible=True,
                        range=[0, 1],
                        tickvals=[0, 0.25, 0.5, 0.75, 1],
                        ticktext=['低', '较低', '中等', '较高', '高'],
                        tickfont=dict(size=11),
                        gridcolor='rgba(200, 200, 200, 0.5)',
                        linecolor='gray'
                    ),
                    angularaxis=dict(
                        tickfont=dict(size=12, color='#2c3e50'),
                        gridcolor='rgba(200, 200, 200, 0.3)',
                        linecolor='gray'
                    ),
                    bgcolor='rgba(248, 249, 250, 0.8)'
                ),
                showlegend=False,
                title=dict(
                    text='天气综合指数雷达图',
                    font=dict(size=16, color='#2c3e50'),
                    x=0.5,
                    y=0.95
                ),
                margin=dict(l=50, r=50, t=80, b=50),
                height=400,
                hoverlabel=dict(
                    bgcolor="white",
                    font_size=12,
                    font_family="Arial"
                )
            )

            # 5. 添加真实数值标注
            annotations = []
            angle_per_category = 360 / len(categories)

            for i, (cat, real_val, rel_val) in enumerate(zip(
                    categories,
                    [avg_high_temp, avg_low_temp, total_precip, avg_humidity, avg_wind],
                    relative_values
            )):
                # 计算角度（弧度）
                angle_rad = i * (2 * 3.14159 / len(categories))

                # 单位文本
                units = ['°C', '°C', 'mm', '%', '级']
                value_text = f'{real_val:.1f}{units[i]}'

                annotations.append(dict(
                    text=f'<b>{cat}</b><br>{value_text}',
                    x=0.5 + 0.6 * rel_val * np.cos(angle_rad - 3.14159 / 2),
                    y=0.5 + 0.6 * rel_val * np.sin(angle_rad - 3.14159 / 2),
                    xref="paper",
                    yref="paper",
                    showarrow=False,
                    font=dict(size=10, color='#2c3e50'),
                    align="center",
                    bgcolor="rgba(255, 255, 255, 0.8)",
                    bordercolor="#ddd",
                    borderwidth=1,
                    borderpad=3
                ))

            fig.update_layout(annotations=annotations)

            # 6. 保存图表
            os.makedirs('static/charts', exist_ok=True)
            chart_path = 'static/charts/weather_radar.html'
            fig.write_html(chart_path, include_plotlyjs='include')

            print("[INFO] Radar chart created successfully")
            return chart_path

        except Exception as e:
            print(f"[ERROR] Radar chart failed: {e}")
            # 返回一个简单的占位符图表
            return None

    @staticmethod
    def create_simple_radar_chart(weather_df):
        """创建简单但可靠的雷达图（备用方案）"""
        try:
            # 只使用最基本的指标
            categories = ['高温', '低温', '降水', '湿度']

            # 计算平均值
            values = [
                weather_df['temp_max'].mean(),
                weather_df['temp_min'].mean(),
                weather_df['precipitation'].sum(),
                weather_df['humidity'].mean()
            ]

            # 简单归一化（基于经验最大值）
            max_values = [35, 25, 30, 100]
            normalized = [v / max_v for v, max_v in zip(values, max_values)]

            fig = go.Figure(data=go.Scatterpolar(
                r=normalized + [normalized[0]],
                theta=categories + [categories[0]],
                fill='toself',
                fillcolor='rgba(135, 206, 235, 0.3)',
                line=dict(color='rgb(135, 206, 235)', width=2)
            ))

            fig.update_layout(
                polar=dict(
                    radialaxis=dict(
                        visible=True,
                        range=[0, 1],
                        ticktext=['', '', '', ''],
                        showticklabels=False
                    )
                ),
                showlegend=False,
                title=dict(
                    text='天气指数简图',
                    font=dict(size=14)
                ),
                margin=dict(l=40, r=40, t=60, b=40),
                height=300
            )

            chart_path = 'static/charts/simple_radar.html'
            os.makedirs('static/charts', exist_ok=True)
            fig.write_html(chart_path, include_plotlyjs='include')

            return chart_path

        except Exception as e:
            print(f"[INFO] Simple radar also failed: {e}")
            return None

    @staticmethod
    def create_precipitation_chart(weather_df):
        """创建降水量柱状图"""
        plt.figure(figsize=(8, 4))

        # 使用相同的日期处理逻辑
        dates = []
        for date_str in weather_df['date'].tolist():
            if isinstance(date_str, str):
                date_part = date_str.split()[0] if ' ' in date_str else date_str
                if '月' in date_part and '日' in date_part:
                    month = date_part.split('月')[0]
                    day = date_part.split('月')[1].replace('日', '')
                    if len(day) == 1:
                        day = '0' + day
                    dates.append(f"{month}/{day}")
                else:
                    dates.append(date_str[:5])
            else:
                dates.append(f"Day {len(dates) + 1}")

        dates = dates[:3]
        precipitations = weather_df['precipitation'].tolist()[:3]

        # 确保数据长度一致
        precipitations = precipitations[:len(dates)]



        colors = ['#3498db' if p < 5 else '#e74c3c' if p < 20 else '#9b59b6' for p in precipitations]

        bars = plt.bar(dates, precipitations, color=colors, edgecolor='white', linewidth=2)

        # 添加数值标签
        for bar, precip in zip(bars, precipitations):
            height = bar.get_height()
            plt.text(bar.get_x() + bar.get_width() / 2., height + 0.1,
                     f'{precip}mm', ha='center', va='bottom', fontsize=10)

        plt.title('未来三天降水量预报', fontsize=14, fontweight='bold', pad=15)
        plt.xlabel('日期', fontsize=11)
        plt.ylabel('降水量 (mm)', fontsize=11)
        plt.grid(True, alpha=0.2, axis='y')
        plt.xticks(rotation=15)

        # 使用英文标题
        plt.title('3-Day Precipitation Forecast', fontsize=14, fontweight='bold', pad=15)
        plt.xlabel('Date (Month/Day)', fontsize=11)
        plt.ylabel('Precipitation (mm)', fontsize=11)
        plt.grid(True, alpha=0.2, axis='y')
        plt.xticks(rotation=15)

        # 添加图例
        import matplotlib.patches as mpatches
        legend_elements = [
            mpatches.Patch(facecolor='#3498db', label='小雨 (<5mm)'),
            mpatches.Patch(facecolor='#e74c3c', label='中雨 (5-20mm)'),
            mpatches.Patch(facecolor='#9b59b6', label='大雨 (>20mm)')
        ]
        plt.legend(handles=legend_elements, loc='upper right')

        chart_path = 'static/charts/precipitation_chart.png'
        plt.tight_layout()
        plt.savefig(chart_path, dpi=100)
        plt.close()

        return chart_path

    @staticmethod
    def create_monthly_comparison_chart(year_data, climatology, year=None):
        """创建月度对比图表 (Bar + Line) - Plotly"""
        try:
            months = list(range(1, 13))
            
            # 准备当年数据
            year_temp = []
            year_precip = []
            for m in months:
                m_data = year_data.get(m, {})
                year_temp.append(m_data.get('avg_temp', None))
                year_precip.append(m_data.get('total_precip', 0))
            
            # 准备气候态数据
            # 优先使用平均温度
            if 'monthly_avg_temp' in climatology:
                clim_temp = [climatology['monthly_avg_temp'].get(m, None) for m in months]
            elif 'monthly_temperature' in climatology:
                clim_temp = [climatology['monthly_temperature'][m] for m in months]
            else:
                 # 回退到Tmax，但应该避免
                clim_temp = [climatology['monthly_tmax'][m] for m in months]
            
            clim_precip = [climatology['monthly_precipitation'][m] for m in months]

            fig = go.Figure()

            # 1. 降水柱状图 (当年)
            fig.add_trace(go.Bar(
                x=months,
                y=year_precip,
                name=f'{year}年降水' if year else '当年降水',
                marker_color='rgba(52, 152, 219, 0.7)',
                yaxis='y1'
            ))

            # 2. 降水柱状图 (气候态 - 虚线框或较浅颜色)
            fig.add_trace(go.Bar(
                x=months,
                y=clim_precip,
                name='气候态降水',
                marker_color='rgba(149, 165, 166, 0.3)',
                yaxis='y1'
            ))

            # 3. 温度折线图 (当年)
            fig.add_trace(go.Scatter(
                x=months,
                y=year_temp,
                name=f'{year}年温度' if year else '当年温度',
                mode='lines+markers',
                line=dict(color='#e74c3c', width=3),
                yaxis='y2'
            ))

            # 4. 温度折线图 (气候态)
            fig.add_trace(go.Scatter(
                x=months,
                y=clim_temp,
                name='气候态温度',
                mode='lines',
                line=dict(color='#95a5a6', width=2, dash='dash'),
                yaxis='y2'
            ))

            # 布局设置
            title_text = f'月度气候特征对比 ({year} vs 1981-2010)' if year else '月度气候特征对比'
            
            fig.update_layout(
                title=title_text,
                xaxis=dict(
                    title='月份',
                    tickmode='linear',
                    tick0=1,
                    dtick=1
                ),
                yaxis=dict(
                    title='降水量 (mm)',
                    side='left',
                    showgrid=False
                ),
                yaxis2=dict(
                    title='温度 (°C)',
                    side='right',
                    overlaying='y',
                    showgrid=True
                ),
                legend=dict(
                    x=0.01,
                    y=0.99,
                    bgcolor='rgba(255, 255, 255, 0.8)'
                ),
                margin=dict(l=50, r=50, t=50, b=50),
                height=400
            )

            chart_path = 'static/charts/monthly_comparison.html'
            os.makedirs('static/charts', exist_ok=True)
            fig.write_html(chart_path, include_plotlyjs='include', full_html=False)
            
            return chart_path

        except Exception as e:
            print(f"[ERROR] Monthly comparison chart failed: {e}")
            return None

    @staticmethod
    def create_daily_temp_distribution(year_df):
        """创建日温度分布图 (Boxplot)"""
        try:
            if 'month' not in year_df.columns:
                year_df['month'] = pd.to_datetime(year_df['date']).dt.month
            
            fig = go.Figure()

            fig.add_trace(go.Box(
                x=year_df['month'],
                y=year_df['temperature'],
                name='温度分布',
                marker_color='#e74c3c',
                boxpoints=False # 不显示所有点，只显示统计
            ))

            fig.update_layout(
                title='月度日平均气温分布',
                xaxis=dict(
                    title='月份',
                    tickmode='linear',
                    tick0=1,
                    dtick=1
                ),
                yaxis=dict(title='温度 (°C)'),
                margin=dict(l=50, r=50, t=50, b=50),
                height=350
            )

            chart_path = 'static/charts/temp_distribution.html'
            os.makedirs('static/charts', exist_ok=True)
            fig.write_html(chart_path, include_plotlyjs='include', full_html=False)
            return chart_path

        except Exception as e:
            print(f"[ERROR] Temp distribution chart failed: {e}")
            return None
    
    @staticmethod
    def create_wind_rose_chart(year_df, month=None):
        """创建风向玫瑰图，支持月份筛选"""
        try:
            # 确保有风向和风速数据
            if 'wind_direction' not in year_df.columns or 'wind_speed' not in year_df.columns:
                return None
            
            # 数据筛选
            if month is not None:
                 # 确保有month列
                 if 'month' not in year_df.columns:
                     year_df['month'] = pd.to_datetime(year_df['date']).dt.month
                 
                 # 筛选特定月份
                 df_to_plot = year_df[year_df['month'] == int(month)].copy()
                 title_text = f"{month}月风况玫瑰图"
            else:
                 df_to_plot = year_df.copy()
                 title_text = "年度风况玫瑰图"

            # 确保数据不为空
            if len(df_to_plot) == 0:
                return None

            # 简化：使用Plotly Express
            # 需要将风向(0-360)转换为方向(N, NE, E...)
            def wind_dir_to_cardinal(d):
                try:
                    d = float(d)
                    dirs = ['N', 'NNE', 'NE', 'ENE', 'E', 'ESE', 'SE', 'SSE', 'S', 'SSW', 'SW', 'WSW', 'W', 'WNW', 'NW', 'NNW']
                    ix = round(d / (360. / 16.))
                    return dirs[ix % 16]
                except:
                    return None
            
            # 取一部分样本避免过慢 (如果是按月，数据量通常不大，可以全取)
            if len(df_to_plot) > 5000:
                sample_df = df_to_plot.sample(n=5000).copy()
            else:
                sample_df = df_to_plot.copy()
                
            dirs = ['N', 'NNE', 'NE', 'ENE', 'E', 'ESE', 'SE', 'SSE', 'S', 'SSW', 'SW', 'WSW', 'W', 'WNW', 'NW', 'NNW']
            dir_set = set(dirs)

            def normalize_direction(v):
                if v is None:
                    return None
                if isinstance(v, (int, float, np.number)):
                    return wind_dir_to_cardinal(v)
                s = str(v).strip().upper()
                if not s:
                    return None
                cn_map = [
                    ("从西北偏北方向吹来的风", "NNW"),
                    ("从东北偏北方向吹来的风", "NNE"),
                    ("从东南偏东方向吹来的风", "ESE"),
                    ("从西南偏南方向吹来的风", "SSW"),
                    ("从北方吹来的风", "N"),
                    ("从南方吹来的风", "S"),
                    ("从东方吹来的风", "E"),
                    ("从西方吹来的风", "W"),
                    ("西北", "NW"),
                    ("东北", "NE"),
                    ("东南", "SE"),
                    ("西南", "SW"),
                    ("北", "N"),
                    ("东", "E"),
                    ("南", "S"),
                    ("西", "W"),
                ]
                for cn, abbr in cn_map:
                    if cn in s:
                        return abbr
                if s in dir_set:
                    return s
                if "VAR" in s or "VRB" in s or "VARIABLE" in s:
                    return None
                if "CALM" in s or "静" in s:
                    return None
                try:
                    return wind_dir_to_cardinal(float(s))
                except:
                    pass
                cleaned = s.replace("°", "").replace("DEG", "").replace("度", "")
                try:
                    return wind_dir_to_cardinal(float(cleaned))
                except:
                    return None

            sample_df['wind_speed'] = pd.to_numeric(sample_df['wind_speed'], errors='coerce')
            sample_df['direction'] = sample_df['wind_direction'].apply(normalize_direction)
            sample_df = sample_df.dropna(subset=['direction', 'wind_speed'])
            sample_df = sample_df[sample_df['wind_speed'] > 0]
            
            if len(sample_df) == 0:
                print(f"[WARNING] No valid wind data for rose chart (Year/Month)")
                return None

            # 统计频次和强度
            fig = px.bar_polar(sample_df, r="wind_speed", theta="direction",
                   color="wind_speed", template="plotly_white",
                   color_discrete_sequence=px.colors.sequential.Plasma_r,
                   title=title_text)
            
            # 改进布局
            fig.update_layout(
                title=dict(x=0.5),
                margin=dict(l=40, r=40, t=60, b=40),
                legend=dict(title="风速 (m/s)")
            )

            # 根据月份保存不同文件
            filename = f'wind_rose_{month}.html' if month else 'wind_rose_year.html'
            chart_path = f'static/charts/{filename}'
            
            os.makedirs('static/charts', exist_ok=True)
            fig.write_html(chart_path, include_plotlyjs='include', full_html=True)
            return chart_path

        except Exception as e:
            print(f"[ERROR] Wind rose chart failed: {e}")
            import traceback
            traceback.print_exc()
            return None
