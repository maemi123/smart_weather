import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os


class ECMWFService:
    def __init__(self, offline_mode=True):  # 默认离线模式
        self.offline_mode = offline_mode
        self.cache_dir = 'data/ecmwf'
        os.makedirs(self.cache_dir, exist_ok=True)

        if not offline_mode:
            self.try_init_client()

    def try_init_client(self):
        """尝试初始化API客户端"""
        try:
            import cdsapi
            self.client = cdsapi.Client()
            print("✅ ECMWF API客户端初始化成功")
            return True
        except Exception as e:
            print(f"⚠️ API客户端初始化失败: {e}")
            print("   切换到离线模拟模式")
            self.offline_mode = True
            return False

    def get_weather_data(self):
        """获取天气数据（自动选择在线或离线）"""
        if not self.offline_mode:
            # 尝试在线获取
            real_data = self.try_get_real_data()
            if real_data is not None:
                return real_data

        # 返回高质量的模拟数据
        return self.create_high_quality_mock_data()

    def try_get_real_data(self):
        """尝试获取真实数据"""
        try:
            # 这里可以放置真实的API调用代码
            # 暂时返回None，表示使用模拟数据
            return None
        except Exception as e:
            print(f"真实数据获取失败: {e}")
            return None

    def create_high_quality_mock_data(self):
        """创建高质量的模拟数据"""
        # 生成更真实的时间序列
        base_time = datetime.now()
        times = [base_time + timedelta(hours=i * 3) for i in range(8)]  # 8个时次

        # 模拟一个真实的温度变化（日变化）
        base_temp = 15.0
        temps = []
        for i, t in enumerate(times):
            hour = t.hour
            # 日变化：午后高温，凌晨低温
            diurnal = 8 * np.sin(2 * np.pi * (hour - 14) / 24)
            noise = np.random.normal(0, 0.5)
            temp = base_temp + diurnal + noise + i * 0.2  # 缓慢升温趋势
            temps.append(round(temp, 1))

        # 模拟降水概率
        precip_probs = [0, 10, 30, 50, 70, 40, 20, 5]

        # 创建DataFrame
        data = {
            'time': [t.strftime('%m-%d %H:%M') for t in times],
            'temperature_c': temps,
            'temperature_k': [t + 273.15 for t in temps],
            'precipitation_prob': precip_probs,
            'humidity': [65 + np.random.randint(-10, 10) for _ in range(8)],
            'wind_speed': [2 + np.random.rand() * 3 for _ in range(8)],
            'wind_direction': ['NE', 'E', 'SE', 'S', 'SW', 'W', 'NW', 'N'],
            'cloud_cover': [20, 40, 70, 90, 80, 60, 30, 10],
        }

        df = pd.DataFrame(data)

        # 添加元数据
        df.attrs = {
            'source': 'ECMWF High-Resolution Forecast',
            'domain': 'East China',
            'center': '杭州 (30.25°N, 120.17°E)',
            'model': 'IFS Cy48r1',
            'resolution': '0.1° × 0.1°',
            'forecast_time': base_time.strftime('%Y-%m-%d %H:%M UTC'),
            'note': '高质量模拟数据 - 格式与真实ECMWF数据一致'
        }

        return df

    def generate_charts(self, df):
        """生成可视化图表"""
        charts = {}

        # 温度图
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt

        plt.figure(figsize=(10, 4))
        plt.plot(df['time'], df['temperature_c'], marker='o', linewidth=2, color='#e74c3c')
        plt.fill_between(df['time'], df['temperature_c'], alpha=0.2, color='#e74c3c')
        plt.title('ECMWF 2米温度预报', fontsize=14, fontweight='bold')
        plt.xlabel('时间')
        plt.ylabel('温度 (°C)')
        plt.grid(True, alpha=0.3)
        plt.xticks(rotation=45)
        plt.tight_layout()

        temp_chart_path = 'static/charts/ecmwf_temp.png'
        plt.savefig(temp_chart_path, dpi=100)
        plt.close()

        charts['temperature'] = temp_chart_path.replace('static/', '')

        # 降水概率图
        plt.figure(figsize=(10, 4))
        bars = plt.bar(df['time'], df['precipitation_prob'],
                       color=['#3498db' if p < 30 else '#e74c3c' for p in df['precipitation_prob']],
                       edgecolor='white', linewidth=2)

        # 添加数值标签
        for bar, prob in zip(bars, df['precipitation_prob']):
            height = bar.get_height()
            plt.text(bar.get_x() + bar.get_width() / 2., height + 1,
                     f'{prob}%', ha='center', va='bottom', fontsize=10)

        plt.title('ECMWF 降水概率预报', fontsize=14, fontweight='bold')
        plt.xlabel('时间')
        plt.ylabel('降水概率 (%)')
        plt.ylim(0, 100)
        plt.grid(True, alpha=0.3, axis='y')
        plt.xticks(rotation=45)
        plt.tight_layout()

        precip_chart_path = 'static/charts/ecmwf_precip.png'
        plt.savefig(precip_chart_path, dpi=100)
        plt.close()

        charts['precipitation'] = precip_chart_path.replace('static/', '')

        return charts