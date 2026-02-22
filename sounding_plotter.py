import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import metpy.calc as mpcalc
from metpy.plots import SkewT, Hodograph
from metpy.units import units
import io
import os

class SoundingPlotter:
    """探空图表生成器"""

    def __init__(self, data_path="data/upperair"):
        self.data_path = data_path
        # 设置中文字体
        # 优先使用微软雅黑，然后是 Emoji 字体，最后是通用字体
        plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'Segoe UI Emoji', 'SimHei', 'Arial']
        plt.rcParams['axes.unicode_minus'] = False

    def plot(self, plot_type: str, data: pd.DataFrame, station_info: dict, cape: float = 0) -> str:
        """生成指定类型的图表"""
        if plot_type == "t_lnp":
            return self._plot_skewt(data, station_info, plot_type="t_lnp")
        elif plot_type == "skewt":
            return self._plot_skewt(data, station_info, plot_type="skewt")
        elif plot_type == "wind":
            return self._plot_wind_profile(data, station_info)
        elif plot_type == "simple":
            return self._plot_simple(data, station_info, cape)
        else:
            raise ValueError(f"Unknown plot type: {plot_type}")

    def _prepare_data(self, data: pd.DataFrame):
        """准备MetPy所需的数据格式"""
        # 清理数据
        df = data.dropna(subset=['PRES', 'TEMP', 'DWPT']).copy()
        
        # 转换单位
        p = df['PRES'].values * units.hPa
        T = df['TEMP'].values * units.degC
        Td = df['DWPT'].values * units.degC
        
        # 风数据可能不完整，单独处理
        if 'DRCT' in df.columns and 'SPED' in df.columns:
            # 填充缺失的风数据
            df_wind = data.dropna(subset=['PRES', 'DRCT', 'SPED']).copy()
            p_wind = df_wind['PRES'].values * units.hPa
            # 转换风速 m/s -> knots (MetPy绘图通常用knots)
            wind_speed = (df_wind['SPED'].values * units('m/s')).to('knots')
            wind_dir = df_wind['DRCT'].values * units.degrees
            u, v = mpcalc.wind_components(wind_speed, wind_dir)
            return p, T, Td, p_wind, u, v
        else:
            return p, T, Td, None, None, None

    def _plot_skewt(self, data: pd.DataFrame, station_info: dict, plot_type="t_lnp") -> str:
        """绘制T-lnP图或Skew-T图"""
        p, T, Td, p_wind, u, v = self._prepare_data(data)
        
        fig = plt.figure(figsize=(9, 9))
        skew = SkewT(fig, rotation=45 if plot_type == "skewt" else 0)

        # 绘制温度和露点
        skew.plot(p, T, 'r', linewidth=2, label='温度')
        skew.plot(p, Td, 'g', linewidth=2, label='露点')

        # 绘制风羽
        if p_wind is not None:
            # 稀疏化风场数据，避免过密
            interval = max(1, len(p_wind) // 30)
            skew.plot_barbs(p_wind[::interval], u[::interval], v[::interval])

        # 添加辅助线
        skew.ax.set_ylim(1000, 100)
        skew.ax.set_xlim(-40, 40)

        # 干绝热线
        skew.plot_dry_adiabats(t0=np.arange(-40, 100, 10) * units.degC, alpha=0.25, color='orange')
        # 湿绝热线
        skew.plot_moist_adiabats(t0=np.arange(-40, 100, 10) * units.degC, alpha=0.25, color='green')
        # 混合比线
        skew.plot_mixing_lines(pressure=np.arange(1000, 99, -20) * units.hPa, linestyle='dotted', color='blue')

        # 标题
        title = f"{station_info.get('station_name', 'Unknown')} ({station_info.get('station_id', '')}) " \
                f"{station_info.get('time_utc', '')}"
        plt.title(title, fontsize=12)
        plt.xlabel("温度 (°C)")
        plt.ylabel("气压 (hPa)")
        plt.legend(loc='upper right')

        # 保存图片
        return self._save_fig(fig, f"{plot_type}_{station_info.get('time_utc', 'unknown').replace(' ', '_')}")

    def _plot_wind_profile(self, data: pd.DataFrame, station_info: dict) -> str:
        """绘制高空风廓线图"""
        # 清理风数据
        df = data.dropna(subset=['HGHT', 'DRCT', 'SPED']).copy()
        h = df['HGHT'].values
        ws = df['SPED'].values
        wd = df['DRCT'].values
        
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 8), sharey=True)
        
        # 风速廓线
        ax1.plot(ws, h, 'b-', linewidth=2)
        ax1.set_xlabel('风速 (m/s)')
        ax1.set_ylabel('高度 (m)')
        ax1.grid(True)
        ax1.set_title('风速随高度变化')
        
        # 风向散点图
        ax2.scatter(wd, h, c=ws, cmap='viridis', s=20)
        ax2.set_xlabel('风向 (度)')
        ax2.set_xlim(0, 360)
        ax2.set_xticks([0, 90, 180, 270, 360])
        ax2.set_xticklabels(['N', 'E', 'S', 'W', 'N'])
        ax2.grid(True)
        ax2.set_title('风向随高度变化')
        
        plt.suptitle(f"高空风场分析 - {station_info.get('station_name', '')}", fontsize=14)
        
        return self._save_fig(fig, f"wind_profile_{station_info.get('time_utc', '').replace(' ', '_')}")

    def _plot_simple(self, data: pd.DataFrame, station_info: dict, cape: float = 0) -> str:
        """绘制卡通直观图 (Atmospheric Health Report)"""
        fig = plt.figure(figsize=(10, 12))
        ax = fig.add_subplot(111)
        ax.set_facecolor('#f8f9fa')
        
        # 数据准备
        df = data.copy()
        
        # 1. 提取关键层数据
        # 高空 (约200hPa / 12km)
        high_level = df.iloc[(df['PRES'] - 200).abs().argsort()[:1]]
        high_wind = high_level['SPED'].values[0] if not high_level.empty else 0
        
        # 中层 (500hPa / 5.5km)
        mid_level = df.iloc[(df['PRES'] - 500).abs().argsort()[:1]]
        mid_rh = mid_level['RELH'].values[0] if not mid_level.empty else 50
        mid_temp = mid_level['TEMP'].values[0] if not mid_level.empty else -10
        mid_dwpt = mid_level['DWPT'].values[0] if not mid_level.empty else -20
        mid_depression = mid_temp - mid_dwpt
        
        # 0度层高度
        freezing_level = df.iloc[(df['TEMP'] - 0).abs().argsort()[:1]]
        freezing_hght = freezing_level['HGHT'].values[0] if not freezing_level.empty else 0
        
        # 低层 (地面)
        sfc = df.iloc[0]
        sfc_rh = sfc['RELH']
        sfc_wind = sfc['SPED']
        sfc_hght = sfc['HGHT']
        
        # 逆温层检测 (1.5km以下)
        low_levels = df[df['HGHT'] < (sfc_hght + 1500)]
        has_inversion = False
        inversion_hght = 0
        if len(low_levels) > 2:
            # 简单检测：是否有温度随高度升高的情况
            temps = low_levels['TEMP'].values
            hghts = low_levels['HGHT'].values
            for i in range(len(temps)-1):
                if temps[i+1] > temps[i]:
                    has_inversion = True
                    inversion_hght = hghts[i]
                    break

        # 2. 绘制布局
        # 格式化标题时间为中文
        time_str = station_info.get('time_utc', '')
        try:
            from datetime import datetime, timedelta
            dt = datetime.strptime(time_str, "%HZ %d %b %Y")
            dt_cst = dt + timedelta(hours=8)
            title_time = dt_cst.strftime("%Y年%m月%d日 %H时")
        except:
            title_time = time_str
            
        ax.text(0.5, 0.96, f"大气体检报告 (杭州 {title_time})", 
                ha='center', fontsize=16, fontweight='bold', color='#2c3e50')
        ax.plot([0.1, 0.9], [0.93, 0.93], color='#34495e', lw=2)
        
        # 垂直轴线
        ax.arrow(0.2, 0.15, 0, 0.7, head_width=0.02, head_length=0.02, fc='#7f8c8d', ec='#7f8c8d')
        ax.text(0.15, 0.85, "高\n度", ha='center', va='center', fontsize=12, color='#7f8c8d')
        
        # --- 云层与降水可视化 (右侧) ---
        ax.text(0.9, 0.85, "云/水", ha='center', va='center', fontsize=12, color='#7f8c8d')
        
        # 统一高度映射参数
        # 假设地面到12000米映射到Y轴 0.2~0.9
        max_hght = 12000
        min_hght = sfc_hght # 使用实际地面高度作为基准
        plot_min_y = 0.2
        plot_max_y = 0.9
        plot_range = plot_max_y - plot_min_y
        
        def h_to_y(h):
            """高度转Y坐标"""
            norm = (h - min_hght) / (max_hght - min_hght)
            return plot_min_y + norm * plot_range

        # 随机种子
        np.random.seed(42)
        
        # 筛选有效层级
        valid_levels = df.dropna(subset=['HGHT', 'RELH', 'TEMP', 'SPED'])
        
        # 按高度步长采样，避免图标过密
        for h in range(int(min_hght), max_hght, 500):
            # 找到最接近该高度的层
            layer = valid_levels.iloc[(valid_levels['HGHT'] - h).abs().argsort()[:1]]
            if layer.empty: continue
            
            rh = layer['RELH'].values[0]
            temp = layer['TEMP'].values[0]
            actual_h = layer['HGHT'].values[0]
            wind_spd = layer['SPED'].values[0]
            
            y_pos = h_to_y(actual_h)
            if y_pos > plot_max_y or y_pos < plot_min_y: continue

            # --- 1. 湿度可视化 (多列散布) ---
            if rh > 85:
                icon = "💧" if temp > 0 else "❄️"
                color = "#3498db" if temp > 0 else "#bdc3c7"
                
                # 在每一层随机生成 3-6 个图标
                num_icons = np.random.randint(3, 7)
                for _ in range(num_icons):
                    # 在 X 轴 0.65 ~ 0.95 范围内随机散布
                    x_pos = np.random.uniform(0.65, 0.95)
                    # Y 轴加一点微小扰动
                    y_jit = np.random.uniform(-0.01, 0.01)
                    
                    ax.text(x_pos, y_pos + y_jit, icon, fontsize=12, color=color, 
                            ha='center', va='center', alpha=0.7, fontname='Segoe UI Emoji')

            # --- 2. 大风可视化 (流线型符号) ---
            if wind_spd > 25: # 提高阈值到 25m/s (约10级风)
                # 风速越大，符号越密集/颜色越深
                # alpha = min(1.0, (wind_spd - 25) / 30 + 0.3)
                alpha = 0.6 # 固定透明度，避免太浅看不清
                
                # 使用 ASCII 字符代替 Unicode 图标，确保 100% 兼容性
                # > 40m/s: >>> (红色)
                # > 25m/s: >>  (橙色)
                wind_marker = ">>>" if wind_spd > 40 else ">>"
                wind_color = "#e74c3c" if wind_spd > 40 else "#f39c12"
                
                # 在中间区域绘制，使用默认字体加粗
                ax.text(0.55, y_pos, wind_marker, 
                        fontsize=16, color=wind_color, ha='center', va='center', 
                        alpha=alpha, fontweight='bold')

        # --- 各层分析 (按真实高度比例显示) ---
        
        # 辅助函数：绘制图文分离的文本
        def draw_icon_text(x, y, icon, text, color, fontsize=12):
            ax.text(x, y, icon, color=color, fontsize=fontsize, fontweight='bold', fontname='Segoe UI Emoji')
            ax.text(x + 0.03, y, text, color=color, fontsize=fontsize, fontweight='bold')

        # A. 高空 (10km+) - 按真实高度
        y_high_real = h_to_y(10000)
        y_high = min(0.88, max(0.75, y_high_real))  # 限制在合理范围避免超出
        status_color = 'red' if high_wind > 40 else 'orange' if high_wind > 20 else 'green'
        status_icon = "🏃‍♂️" if high_wind > 40 else "🚶"
        status_text = "心率过快" if high_wind > 40 else "正常"
        
        ax.text(0.25, y_high, "高空 (10km+)", fontweight='bold', fontsize=12)
        draw_icon_text(0.45, y_high, status_icon, status_text, status_color)
        
        ax.text(0.25, y_high-0.03, f"风速: {high_wind:.1f} m/s ({'强急流' if high_wind>30 else '弱风'})", fontsize=10)
        
        flight_icon = "✈️"
        flight_text = "飞机可能颠簸" if high_wind > 20 else "飞行平稳"
        ax.text(0.25, y_high-0.06, "→ 对您意味着:", fontsize=10, color='#e67e22', style='italic')
        draw_icon_text(0.38, y_high-0.06, flight_icon, flight_text, '#e67e22', fontsize=10)
        
        self._draw_status_bar(ax, 0.85, y_high-0.03, high_wind/60, status_color)

        # B. 中层 (5km) - 按真实高度
        y_mid_real = h_to_y(5500)  # 500hPa约5.5km
        y_mid = min(0.72, max(0.45, y_mid_real))  # 限制在合理范围
        # 中层湿度判断（三级）
        if mid_depression > 15:
            status_color = 'red'
            status_icon = "🤧"
            status_text = "严重干燥"
        elif mid_depression > 8:
            status_color = 'orange'
            status_icon = "🌤️"
            status_text = "湿度适中"
        else:
            status_color = 'green'
            status_icon = "💧"
            status_text = "湿润"
        
        ax.text(0.25, y_mid, "中层 (5km)", fontweight='bold', fontsize=12)
        draw_icon_text(0.45, y_mid, status_icon, status_text, status_color)

        ax.text(0.25, y_mid-0.03, f"湿度: {mid_rh:.0f}% (温露差 {mid_depression:.1f}°C)", fontsize=10)
        
        # 风险提示（三级）
        is_mid_dry = (mid_depression > 12) or (mid_rh < 35)
        if is_mid_dry and cape > 1500:
            risk_icon = "⚡"
            risk_text = "对流能量充足且温露差大，雷暴大风风险增高"
        elif is_mid_dry:
            risk_icon = "☀️"
            risk_text = "空气干燥，云层较少"
        elif mid_depression > 8:
            risk_icon = "⛅"
            risk_text = "湿度适中，天气稳定"
        else:
            risk_icon = "☁️"
            risk_text = "湿度较高，云层可能发展"
        ax.text(0.25, y_mid-0.06, "→ 潜在风险:", fontsize=10, color='#e67e22', style='italic')
        draw_icon_text(0.35, y_mid-0.06, risk_icon, risk_text, '#e67e22', fontsize=10)
        
        self._draw_status_bar(ax, 0.85, y_mid-0.03, 1 - mid_rh/100, status_color)

        # 动态调整 0度层 和 逆温层 的位置
        # 计算真实高度对应的 Y 坐标
        y_freeze_real = h_to_y(freezing_hght)
        y_inv_real = h_to_y(inversion_hght) if has_inversion else 0.35
        
        # 定义干燥状态（用于底部诊断）
        is_dry = mid_depression > 15
        
        # 计算中层文字的最低位置
        y_mid_bottom = y_mid - 0.09
        
        # 动态计算0度层标签位置，取中层和逆温层之间的中间位置
        y_freeze_label = max(0.30, min(0.55, y_freeze_real))
        if y_freeze_real > y_mid:
            # 0度层真实高度高于中层，标签放在中层上方
            y_freeze_label = min(y_freeze_label, y_mid - 0.12)
        else:
            # 0度层标签在中层文字下方和逆温层上方之间取中间值，稍微偏上
            y_freeze_label = (y_mid_bottom + 0.35) / 2 + 0.02
        
        y_inv_label = 0.35
        
        # 当逆温层在0度层上面时，交换标签位置避免重叠
        if has_inversion and inversion_hght > freezing_hght:
            y_freeze_label, y_inv_label = y_inv_label, y_freeze_label
            y_freeze_label = max(0.24, y_freeze_label - 0.06)
            if (y_inv_label - y_freeze_label) < 0.09:
                y_freeze_label = max(0.24, y_inv_label - 0.09)
            
        # C. 0度层
        # 画线要在真实高度
        if min_hght < freezing_hght < max_hght:
            ax.plot([0.18, 0.8], [y_freeze_real, y_freeze_real], ls='--', color='#3498db', lw=1)
            # 标签放在固定位置，但加箭头指向
            ax.annotate(f"0℃层 ({freezing_hght:.0f}m)", 
                        xy=(0.6, y_freeze_real), xytext=(0.25, y_freeze_label),
                        arrowprops=dict(arrowstyle="->", color='#3498db'),
                        color='#2980b9', fontsize=11, fontweight='bold')
            draw_icon_text(0.45, y_freeze_label, "🎯", "关键分界线", '#2980b9', fontsize=11)
            ax.text(0.25, y_freeze_label-0.03, f"→ 降水形态: 此高度以下为雨，以上可能为雪/冰", fontsize=10, color='#7f8c8d')

        # D. 逆温层 (如果有且在显示范围内)
        if has_inversion and min_hght < inversion_hght < max_hght:
            ax.plot([0.18, 0.8], [y_inv_real, y_inv_real], ls=':', color='#d35400', lw=2)
            ax.annotate(f"逆温层 (~{inversion_hght:.0f}m)",
                        xy=(0.6, y_inv_real), xytext=(0.25, y_inv_label),
                        arrowprops=dict(arrowstyle="->", color='#d35400'),
                        fontweight='bold', fontsize=12, color='#d35400')
            draw_icon_text(0.48, y_inv_label, "🚧", "交通堵塞", '#d35400')
            ax.text(0.25, y_inv_label-0.03, "特性: 温度随高度上升 (反常现象)", fontsize=10)
            ax.text(0.25, y_inv_label-0.06, "→ 对您意味着:", fontsize=10, color='#e67e22', style='italic')
            draw_icon_text(0.38, y_inv_label-0.06, "😷", "污染物堆积，雾霾难散", '#e67e22', fontsize=10)
            self._draw_status_bar(ax, 0.85, y_inv_label-0.03, 0.8, 'orange')

        # E. 地面 - 按真实高度
        y_sfc_real = h_to_y(sfc_hght)
        y_sfc = max(0.22, min(0.35, y_sfc_real))  # 限制在合理范围
        is_very_humid = sfc_rh >= 90
        is_humid = sfc_rh >= 70
        is_comfortable = 40 < sfc_rh < 70
        status_color = 'blue' if is_humid else 'green'
        status_icon = "😷" if is_very_humid else "🙂" if is_humid else "😊" if is_comfortable else "🌵"
        status_text = "极度潮湿" if is_very_humid else "偏湿" if is_humid else "舒适" if is_comfortable else "干燥"
        
        ax.text(0.25, y_sfc, "低层 (地面)", fontweight='bold', fontsize=12)
        draw_icon_text(0.45, y_sfc, status_icon, status_text, status_color)

        ax.text(0.25, y_sfc-0.03, f"湿度: {sfc_rh:.0f}%", fontsize=10)
        
        life_icon = "🌫️" if is_very_humid else "🚗"
        life_text = "有雾，出行注意安全" if is_very_humid else "能见度良好"
        ax.text(0.25, y_sfc-0.06, "→ 生活提示:", fontsize=10, color='#e67e22', style='italic')
        draw_icon_text(0.35, y_sfc-0.06, life_icon, life_text, '#e67e22', fontsize=10)
        
        self._draw_status_bar(ax, 0.85, y_sfc-0.03, sfc_rh/100, status_color)

        # 3. 底部诊断总结
        ax.plot([0.1, 0.9], [0.1, 0.1], color='#34495e', lw=2)
        
        diagnosis_y = 0.05
        health_score = "良好"
        if has_inversion or high_wind > 40 or is_dry:
            health_score = "亚健康"
        
        ax.text(0.15, diagnosis_y, "【今日诊断】", fontsize=12, fontweight='bold', color='#2c3e50')
        ax.text(0.3, diagnosis_y, f"大气状态: {health_score}", fontsize=12, color='green' if health_score=="良好" else 'orange')
        
        tips = "天气平稳，适宜活动。"
        if has_inversion: tips = "空气扩散条件差，敏感人群减少外出。"
        elif high_wind > 30: tips = "高空风强，航空出行留意航班动态。"
        
        draw_icon_text(0.55, diagnosis_y, "💊", tips, '#2c3e50', fontsize=10)

        # 右下角卡通图案
        if health_score == "良好":
            face_color = '#f1c40f'
            mouth_y = 0.04
            mouth_char = "‿"
        else:
            face_color = '#95a5a6'
            mouth_y = 0.03
            mouth_char = "—"
            
        circle = plt.Circle((0.9, 0.06), 0.04, color=face_color, transform=ax.transAxes, zorder=10)
        ax.add_patch(circle)
        ax.text(0.885, 0.07, "•", fontsize=20, transform=ax.transAxes, zorder=11)
        ax.text(0.905, 0.07, "•", fontsize=20, transform=ax.transAxes, zorder=11)
        ax.text(0.9, mouth_y, mouth_char, fontsize=20, ha='center', transform=ax.transAxes, zorder=11, fontname='Segoe UI Emoji')

        # 去除坐标轴
        ax.set_xticks([])
        ax.set_yticks([])
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['bottom'].set_visible(False)
        ax.spines['left'].set_visible(False)
        
        return self._save_fig(fig, f"simple_{station_info.get('time_utc', '').replace(' ', '_')}")

    def _draw_status_bar(self, ax, x, y, percent, color):
        """绘制简单的状态色条"""
        # 背景条
        ax.add_patch(plt.Rectangle((x, y), 0.1, 0.015, color='#ecf0f1', transform=ax.transAxes))
        # 进度条
        width = 0.1 * min(1.0, max(0.0, percent))
        ax.add_patch(plt.Rectangle((x, y), width, 0.015, color=color, transform=ax.transAxes))

    def _save_fig(self, fig, name):
        """保存图表并返回相对路径"""
        filename = f"{name}.png"
        save_path = os.path.join("static/charts/upperair", filename)
        
        # 确保目录存在
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        
        fig.savefig(save_path, bbox_inches='tight', dpi=100)
        plt.close(fig)
        
        return f"charts/upperair/{filename}"
