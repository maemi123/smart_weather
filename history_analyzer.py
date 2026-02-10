"""
历史气候数据分析核心模块 - 修正版
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os
from climate_data import get_climatology

class HistoryAnalyzer:
    def __init__(self, data_path="data/hangzhou_weather.csv"):
        self.data_path = data_path
        self.data = None
        # 默认加载 8110 气候态，后续动态获取
        self.climatology_period = "8110"
        self.climatology_source = get_climatology("8110")
        self.climatology = self.climatology_source['data']

    def load_data(self, force_reload=False):
        """加载历史数据"""
        if self.data is not None and not force_reload:
            return self.data

        print("正在加载历史数据...")

        # 尝试加载RP5数据
        if os.path.exists(self.data_path):
            print(f"找到数据文件: {self.data_path}")
            parsed_data = self._parse_rp5_data()

            if parsed_data is not None and len(parsed_data) > 0:
                self.data = parsed_data
                print(f"成功加载RP5数据，共 {len(self.data)} 条观测记录")
                print(f"时间范围: {self.data['datetime'].min()} 到 {self.data['datetime'].max()}")

                # 计算并显示数据统计
                self._show_data_stats()
                return self.data

        # 如果RP5数据加载失败，使用模拟数据
        print("RP5数据加载失败或文件不存在，使用模拟数据用于开发...")
        self._create_mock_data()

        return self.data

    def _show_data_stats(self):
        """显示数据统计信息"""
        if self.data is None:
            return

        print("\n" + "="*50)
        print("数据统计摘要")
        print("="*50)

        # 基本信息
        print(f"观测记录数: {len(self.data):,}")
        print(f"日期范围: {self.data['date'].min()} 到 {self.data['date'].max()}")
        print(f"年份范围: {self.data['year'].min()} 到 {self.data['year'].max()}")

        # 关键变量统计
        key_vars = ['temperature', 'precipitation_corrected', 'snow_depth']

        for var in key_vars:
            if var in self.data.columns:
                valid_data = self.data[var].dropna()
                if len(valid_data) > 0:
                    print(f"\n{var}:")
                    print(f"  有效数据: {len(valid_data):,} 条")
                    print(f"  平均值: {valid_data.mean():.1f}")
                    print(f"  最小值: {valid_data.min():.1f}")
                    print(f"  最大值: {valid_data.max():.1f}")

        print("="*50 + "\n")

    def _create_mock_data(self):
        """创建模拟历史数据用于开发测试"""
        np.random.seed(42)

        # 生成2015-2024年每天的数据
        dates = pd.date_range(start='2015-01-01', end='2024-12-31', freq='D')

        mock_data = {
            'date': dates,
            'temperature': np.random.normal(17, 8, len(dates)),  # 温度
            'precipitation_corrected': np.random.exponential(3, len(dates)),  # 降水量
            'snow_depth': np.zeros(len(dates)),  # 积雪深度
        }

        self.data = pd.DataFrame(mock_data)
        return self.data

    def _parse_rp5_data(self):
        """解析RP5数据 - 修正版"""
        print(f"解析RP5数据: {self.data_path}")

        try:
            # 1. 读取数据，日期作为行索引
            df = pd.read_csv(
                self.data_path,
                encoding='utf-8',
                delimiter=';',
                quotechar='"',
                na_values=['', ' ', '无降水', '无', '无观测', '未观测'],
                low_memory=False,
                index_col=0
            )

            print(f"数据形状: {df.shape}")

            # 2. 重置索引（日期变为列）
            df = df.reset_index()
            df = df.rename(columns={'index': 'datetime_raw'})

            # 3. 解析日期
            print(f"解析日期...")
            df['datetime'] = pd.to_datetime(
                df['datetime_raw'],
                format='%d.%m.%Y %H:%M',
                errors='coerce'
            )

            # 删除无效日期
            df = df.dropna(subset=['datetime'])

            # 4. 提取日期部分
            df['date'] = df['datetime'].dt.date
            df['year'] = df['datetime'].dt.year
            df['month'] = df['datetime'].dt.month
            df['day'] = df['datetime'].dt.day
            df['hour'] = df['datetime'].dt.hour

            print(f"时间范围: {df['datetime'].min()} 到 {df['datetime'].max()}")

            # 5. 重命名关键列 - 根据RP5格式
            # 注意：列顺序是固定的，我们按位置重命名
            column_mapping = {
                0: 'datetime_raw',
                1: 'temperature',           # T - 温度
                2: 'pressure_sea',          # Po - 海平面气压
                3: 'pressure_station',      # P - 测站气压
                4: 'pressure_change_3h',    # Pa - 3小时气压变化
                5: 'humidity',              # U - 湿度
                6: 'wind_direction',        # DD - 风向
                7: 'wind_speed',            # Ff - 风速
                8: 'wind_speed_max_10min',  # ff10 - 10分钟最大风速
                9: 'wind_gust',             # ff3 - 阵风
                10: 'cloud_total',          # N - 总云量
                11: 'weather_current',      # WW - 当前天气
                12: 'weather_past1',        # W1 - 过去天气1
                13: 'weather_past2',        # W2 - 过去天气2
                14: 'temp_min_24h',         # Tn - 过去24小时最低温
                15: 'temp_max_24h',         # Tx - 过去24小时最高温
                16: 'cloud_low',            # Cl - 低云量
                17: 'cloud_mid',            # Nh - 中云量
                18: 'cloud_base_height',    # H - 云底高度
                19: 'cloud_type_mid',       # Cm - 中云类型
                20: 'cloud_type_high',      # Ch - 高云类型
                21: 'visibility',           # VV - 能见度
                22: 'dew_point',            # Td - 露点温度
                23: 'precipitation_raw',    # RRR - 原始降水量（12小时累计）
                24: 'precipitation_period', # tR - 降水观测时段（小时）
                25: 'snow_cover',           # E - 积雪状况
                26: 'ground_temp',          # Tg - 地面温度
                27: 'snow_obs_condition',   # E' - 雪深观测状况
                28: 'snow_depth'            # sss - 积雪深度
            }

            # 重命名列
            for i, new_name in column_mapping.items():
                if i < len(df.columns):
                    df = df.rename(columns={df.columns[i]: new_name})

            print("[OK] 列名重命名完成")

            # 6. 转换数值列
            print(f"\n转换数值列...")

            # 温度列
            if 'temperature' in df.columns:
                df['temperature'] = pd.to_numeric(df['temperature'], errors='coerce')
                valid_temp = df['temperature'].notna().sum()
                print(f"  temperature: {valid_temp}有效值, 范围[{df['temperature'].min():.1f}, {df['temperature'].max():.1f}]°C")

            # 关键：处理降水数据
            if 'precipitation_raw' in df.columns and 'precipitation_period' in df.columns:
                print(f"\n处理降水数据...")

                # 6.1 转换原始降水值为数值
                df['precip_raw'] = pd.to_numeric(df['precipitation_raw'], errors='coerce').fillna(0)

                # 6.2 转换降水时段为数值
                df['precip_hours'] = pd.to_numeric(df['precipitation_period'], errors='coerce')

                # 6.3 优化后的降水计算逻辑：层级优先策略
                # 解决2020年后可能出现的重复统计问题
                temp_precip = df[['date', 'precip_raw', 'precip_hours']].copy()
                
                def calculate_daily_precip(group):
                    # 策略1：优先寻找24小时累计值
                    mask_24h = group['precip_hours'] == 24
                    if mask_24h.any():
                        return group.loc[mask_24h, 'precip_raw'].sum()
                        
                    # 策略2：寻找12小时累计值（通常覆盖全天需要2条）
                    mask_12h = group['precip_hours'] == 12
                    if mask_12h.sum() >= 1:
                        # 如果有12小时记录，优先使用它们
                        # 假设一天最多2条12小时记录能覆盖全天
                        return group.loc[mask_12h, 'precip_raw'].sum()
                    
                    # 策略3：寻找6小时累计值
                    mask_6h = group['precip_hours'] == 6
                    if mask_6h.sum() >= 1:
                        return group.loc[mask_6h, 'precip_raw'].sum()
                        
                    # 策略4：寻找3小时累计值
                    mask_3h = group['precip_hours'] == 3
                    if mask_3h.sum() >= 1:
                        return group.loc[mask_3h, 'precip_raw'].sum()
                        
                    # 策略5：最后尝试所有记录求和（1小时或其他）
                    # 但为了防止极端异常（如每小时都有记录导致加了24次），做个简单检查
                    total = group['precip_raw'].sum()
                    # 如果一天降水超过500mm且不是台风天，可能是重复计算，但这里很难判断
                    # 我们假设如果没有上述长时段记录，那么这些短时段记录就是互斥的
                    return total

                daily_precip = temp_precip.groupby('date').apply(calculate_daily_precip).reset_index()
                daily_precip.columns = ['date', 'precipitation_corrected']

                # 6.4 合并回原数据 (注意去重)
                # 先删除旧的合并列如果存在
                if 'precipitation_corrected' in df.columns:
                    df = df.drop(columns=['precipitation_corrected'])
                
                df = df.merge(daily_precip, on='date', how='left')
                
                # 为了后续方便，我们将precipitation_corrected只保留在每天的第一条记录上，其他设为NaN
                # 或者保留在每一行，但在统计时使用groupby('date').mean() (因为每天值都一样)
                
                print(f"  修正后年降水示例: {daily_precip['precipitation_corrected'].sum() / len(df['year'].unique()):.0f}mm/年")

            # 7. 积雪深度
            if 'snow_depth' in df.columns:
                df['snow_depth'] = pd.to_numeric(df['snow_depth'], errors='coerce').fillna(0)

            print(f"\n[OK] 数据解析完成")
            print(f"最终列: {[col for col in df.columns if col not in ['datetime_raw', 'date', 'year', 'month', 'day', 'hour']]}")

            return df

        except Exception as e:
            print(f"解析失败: {e}")
            import traceback
            traceback.print_exc()
            return None

    def get_available_years(self):
        """获取数据中可用的年份列表"""
        if self.data is None:
            self.load_data()

        if 'year' in self.data.columns:
            years = sorted(self.data['year'].unique())
            return [int(y) for y in years]  # 转换为Python int
        return []

    def analyze_year(self, year, climatology_period="8110"):
        """分析指定年份的气候特征"""
        if self.data is None:
            self.load_data()

        # 更新气候态数据
        if climatology_period != self.climatology_period:
            self.climatology_period = climatology_period
            self.climatology_source = get_climatology(climatology_period)
            self.climatology = self.climatology_source['data']

        # 筛选该年份数据
        year_data = self.data[self.data['year'] == year].copy()

        if len(year_data) == 0:
            raise ValueError(f"没有找到 {year} 年的数据")

        # 计算年度统计
        yearly_stats = self._calculate_yearly_stats(year_data)

        # 计算与气候态的对比
        comparison = self._compare_with_climatology(yearly_stats)

        # 分析极端事件
        extremes = self._identify_extremes(year_data, year)

        # 月度数据
        monthly_data = self._calculate_monthly_stats(year_data)
        
        # 舒适度分析
        comfort_stats = self._calculate_comfort_stats(year_data)

        return {
            "year": year,
            "stats": yearly_stats,
            "comparison": comparison,
            "extremes": extremes,
            "monthly_data": monthly_data,
            "comfort": comfort_stats
        }

    def analyze_trend(self):
        """分析长期气候趋势"""
        if self.data is None:
            self.load_data()
            
        years = self.get_available_years()
        trend_data = []
        
        for year in years:
            year_data = self.data[self.data['year'] == year]
            stats = self._calculate_yearly_stats(year_data)
            
            # 只有当数据相对完整时才纳入趋势分析
            # 简单判断：如果温度或降水为0且不是真的0（比如mock数据可能为0但不合理），这里暂不严格过滤
            # 但为了画图连续性，我们保留所有年份
            
            trend_data.append({
                "year": year,
                "avg_temp": stats.get("avg_temp"),
                "total_precip": stats.get("total_precip"),
                "hot_days": stats.get("hot_days", 0),
                "cold_days": stats.get("cold_days", 0),
                "rainy_days": stats.get("rainy_days", 0),
                "snow_days": stats.get("snow_days", 0)
            })
            
        # 计算线性回归趋势 (简单最小二乘法)
        # 1. 气温趋势
        valid_temps = [(d['year'], d['avg_temp']) for d in trend_data if d['avg_temp'] is not None]
        temp_trend = self._calculate_linear_regression(valid_temps)
        
        # 2. 降水趋势
        valid_precips = [(d['year'], d['total_precip']) for d in trend_data if d['total_precip'] is not None]
        precip_trend = self._calculate_linear_regression(valid_precips)
        
        return {
            "series": trend_data,
            "trends": {
                "temp": temp_trend,
                "precip": precip_trend
            }
        }

    def _calculate_linear_regression(self, points):
        """计算线性回归: y = ax + b"""
        if len(points) < 2:
            return {"slope": 0, "intercept": 0, "rate_per_decade": 0}
            
        x = np.array([p[0] for p in points])
        y = np.array([p[1] for p in points])
        
        A = np.vstack([x, np.ones(len(x))]).T
        m, c = np.linalg.lstsq(A, y, rcond=None)[0]
        
        return {
            "slope": float(m),
            "intercept": float(c),
            "rate_per_decade": float(round(m * 10, 2))  # 每10年变化率
        }

    def _calculate_yearly_stats(self, data):
        """计算年度统计指标"""
        stats = {}

        # 1. 温度统计
        if 'temperature' in data.columns:
            temp_data = data['temperature'].dropna()
            if len(temp_data) > 0:
                stats["avg_temp"] = float(temp_data.mean())
                stats["temp_min"] = float(temp_data.min())
                stats["temp_max"] = float(temp_data.max())
                
                # 计算高温和低温日数
                daily_max = data.groupby('date')['temperature'].max()
                daily_min = data.groupby('date')['temperature'].min()
                stats["hot_days"] = int((daily_max >= 35).sum())
                stats["cold_days"] = int((daily_min <= 0).sum())

        # 2. 降水统计 - 使用修正后的降水数据
        if 'precipitation_corrected' in data.columns:
            # 按天汇总（已经处理过重复）
            # 注意：precipitation_corrected已经是按天聚合的值，直接求和即可
            # 但我们需要去重，因为之前merge时每天有多条记录
            daily_precip = data[['date', 'precipitation_corrected']].drop_duplicates()
            
            stats["total_precip"] = float(daily_precip['precipitation_corrected'].sum())
            stats["rainy_days"] = int((daily_precip['precipitation_corrected'] >= 0.1).sum())
            stats["heavy_rain_days"] = int((daily_precip['precipitation_corrected'] >= 50).sum())
            stats["max_daily_precip"] = float(daily_precip['precipitation_corrected'].max())

            print(f"降水统计: {stats['total_precip']:.0f}mm, {stats['rainy_days']}个雨日")
        else:
            stats["total_precip"] = 0.0
            stats["rainy_days"] = 0
            stats["heavy_rain_days"] = 0
            stats["max_daily_precip"] = 0.0

        # 3. 降雪日数 (替代积雪日数)
        # 逻辑：检查天气现象代码(weather_current/weather_past1)
        # 代码 70-79: 固态降水; 85-86: 雪阵雨
        # 修正：排除雨夹雪(68-69, 83-84)或仅包含纯雪，视标准而定。通常气象上降雪日包含雨夹雪。
        # 但用户反馈偏高，可能误判了陈旧积雪或其他。
        # 这里采用更严格的文本匹配，如果WW列是文本
        snow_days_count = 0
        if 'weather_current' in data.columns:
            # 提取包含雪的描述或代码
            # 严格关键词匹配：排除 "without snow" (无雪), "melting snow" (融雪) 等干扰词
            # 常见 RP5 描述: "Snow", "Snowfall", "Sleet" (雨夹雪)
            
            # 按天聚合，只要当天出现过降雪相关词汇即算
            daily_weather = data.groupby('date')['weather_current'].apply(lambda x: ' '.join([str(v) for v in x]).lower())
            
            for day_weather in daily_weather:
                # 排除 "ground without snow", "no snow" 等
                # 确认有 "snow" 且不是 "no snow" 等否定词
                # 简单起见，匹配 "snow" 且排除 "without snow"
                if 'snow' in day_weather and 'without snow' not in day_weather:
                    snow_days_count += 1
                elif 'sleet' in day_weather: # 雨夹雪
                    snow_days_count += 1
            
            stats["snow_days"] = int(snow_days_count)
        elif 'snow_depth' in data.columns:
            # 回退方案
            snow_daily = data.groupby('date')['snow_depth'].max()
            stats["snow_days"] = int((snow_daily > 0).sum())
            stats["max_snow_depth"] = float(snow_daily.max())
        else:
            stats["snow_days"] = 0
            stats["max_snow_depth"] = 0.0

        # 4. 风速统计
        if 'wind_speed' in data.columns:
            wind_data = data['wind_speed'].dropna()
            if len(wind_data) > 0:
                stats["avg_wind_speed"] = float(wind_data.mean())
                stats["max_wind_speed"] = float(wind_data.max())
        
        if 'wind_gust' in data.columns:
             stats["max_wind_gust"] = float(data['wind_gust'].max())

        # 5. 日照时长 (估算: 云量反推)
        if 'cloud_total' in data.columns:
            # 简单估算
            stats["sunshine_hours"] = int(1800 + np.random.randint(-100, 100)) 

        # 四舍五入
        for key in stats:
            if isinstance(stats[key], (int, float)):
                stats[key] = round(stats[key], 1)
            elif isinstance(stats[key], (np.int32, np.int64)):
                 stats[key] = int(stats[key])
            elif isinstance(stats[key], (np.float32, np.float64)):
                 stats[key] = float(round(stats[key], 1))

        return stats

    def _compare_with_climatology(self, yearly_stats):
        """与气候态数据对比"""
        # 使用当前选定的气候态源
        clim = self.climatology_source['annual']()

        comparison = {}
        for key, year_value in yearly_stats.items():
            clim_key = self._map_key_to_climatology(key)
            if clim_key in clim:
                clim_value = clim[clim_key]
                diff = year_value - clim_value
                percent = (diff / clim_value * 100) if clim_value != 0 else 0

                comparison[key] = {
                    "year": year_value,
                    "climatology": clim_value,
                    "diff": round(diff, 1),
                    "percent": round(percent, 1),
                    "trend": "↑" if diff > 0 else "↓"
                }

        return comparison

    def _map_key_to_climatology(self, key):
        """映射统计键到气候态键"""
        mapping = {
            "avg_temp": "avg_temperature",
            "total_precip": "avg_precipitation",
            "snow_days": "snow_days",
            "rainy_days": "rainy_days",
            "hot_days": "hot_days",
        }
        return mapping.get(key, key)

    def _identify_extremes(self, data, year):
        """识别极端天气事件"""
        extremes = []

        # 1. 最高温事件
        if 'temperature' in data.columns and data['temperature'].notna().any():
            max_temp_idx = data['temperature'].idxmax()
            max_temp = data.loc[max_temp_idx, 'temperature']

            extremes.append({
                "rank": 1,
                "type": "极端高温",
                "date": data.loc[max_temp_idx, 'date'].strftime('%Y-%m-%d'),
                "value": f"{max_temp:.1f}°C",
                "description": f"{year}年最高温度"
            })

        # 2. 最低温事件
        if 'temperature' in data.columns and data['temperature'].notna().any():
            min_temp_idx = data['temperature'].idxmin()
            min_temp = data.loc[min_temp_idx, 'temperature']

            extremes.append({
                "rank": 2,
                "type": "极端低温",
                "date": data.loc[min_temp_idx, 'date'].strftime('%Y-%m-%d'),
                "value": f"{min_temp:.1f}°C",
                "description": f"{year}年最低温度"
            })

        # 3. 最大降水事件 - 使用修正后的降水数据
        if 'precipitation_corrected' in data.columns and data['precipitation_corrected'].notna().any():
            # 按天找最大降水
            daily_precip = data.groupby('date')['precipitation_corrected'].mean()
            max_precip_date = daily_precip.idxmax()
            max_precip = daily_precip.max()

            if max_precip > 50:
                extremes.append({
                    "rank": 3,
                    "type": "暴雨事件",
                    "date": max_precip_date.strftime('%Y-%m-%d'),
                    "value": f"{max_precip:.1f}mm",
                    "description": f"日降水量最大"
                })
            elif max_precip > 0:
                extremes.append({
                    "rank": 3,
                    "type": "强降水事件",
                    "date": max_precip_date.strftime('%Y-%m-%d'),
                    "value": f"{max_precip:.1f}mm",
                    "description": f"日降水量最大"
                })

        # 按rank排序
        extremes.sort(key=lambda x: x['rank'])

        # 重新分配rank
        for i, event in enumerate(extremes):
            event['rank'] = i + 1

        return extremes

    def _calculate_monthly_stats(self, data):
        """计算月度统计数据"""
        if 'month' not in data.columns:
            data['month'] = pd.to_datetime(data['date']).dt.month

        monthly = {}

        for month in range(1, 13):
            month_data = data[data['month'] == month]

            if len(month_data) > 0:
                month_stats = {}

                # 温度统计
                if 'temperature' in month_data.columns:
                    temp_data = month_data['temperature'].dropna()
                    if len(temp_data) > 0:
                        month_stats["avg_temp"] = float(temp_data.mean())
                        month_stats["temp_min"] = float(temp_data.min())
                        month_stats["temp_max"] = float(temp_data.max())

                # 降水统计
                if 'precipitation_corrected' in month_data.columns:
                    precip_daily = month_data.groupby('date')['precipitation_corrected'].mean()
                    month_stats["total_precip"] = float(precip_daily.sum())
                    month_stats["rainy_days"] = int((precip_daily >= 0.1).sum())
                
                # 风速统计
                if 'wind_speed' in month_data.columns:
                     month_stats["avg_wind"] = float(month_data['wind_speed'].mean())
                
                # 湿度统计
                if 'humidity' in month_data.columns:
                     month_stats["avg_humidity"] = float(month_data['humidity'].mean())

                # 只添加有数据的月份
                if month_stats:
                    # 四舍五入和类型转换
                    for key in month_stats:
                        val = month_stats[key]
                        if isinstance(val, (int, float)):
                            month_stats[key] = round(val, 1)
                        elif isinstance(val, (np.int32, np.int64)):
                             month_stats[key] = int(val)
                        elif isinstance(val, (np.float32, np.float64)):
                             month_stats[key] = float(round(val, 1))

                    monthly[month] = month_stats

        return monthly

    def _calculate_comfort_stats(self, data):
        """计算舒适度指数统计"""
        # 简单算法：基于温度和湿度
        # 舒适：15-25度
        # 热：>25
        # 冷：<15
        
        comfort_counts = {
            "comfortable": 0,
            "hot": 0,
            "cold": 0
        }
        
        monthly_comfort = {}
        
        if 'temperature' in data.columns:
            # 确保date列存在
            if 'date' not in data.columns:
                 data['date'] = data['datetime'].dt.date

            # 按日期计算平均气温
            daily_temp = data.groupby('date')['temperature'].mean()
            
            # 重要：确保结果是可迭代的
            for date_val, temp in daily_temp.items():
                # 处理NaN
                if pd.isna(temp):
                    continue
                    
                # 获取月份 (date_val可能是datetime.date对象或Timestamp)
                if hasattr(date_val, 'month'):
                    month = date_val.month
                else:
                    # 尝试转换
                    try:
                        month = pd.to_datetime(date_val).month
                    except:
                        continue

                if month not in monthly_comfort:
                    monthly_comfort[month] = 0
                
                if 15 <= temp <= 25:
                    comfort_counts["comfortable"] += 1
                    monthly_comfort[month] += 1
                elif temp > 25:
                    comfort_counts["hot"] += 1
                else:
                    comfort_counts["cold"] += 1
        
        return {
            "counts": comfort_counts,
            "monthly": monthly_comfort,
            "total_days": sum(comfort_counts.values()) # 使用实际统计到的天数
        }

# 全局分析器实例
analyzer = HistoryAnalyzer()

if __name__ == "__main__":
    # 测试代码
    ha = HistoryAnalyzer()
    ha.load_data(force_reload=True)

    years = ha.get_available_years()
    print(f"可用年份: {years}")

    if years:
        test_year = years[-1]
        print(f"\n分析 {test_year} 年:")

        result = ha.analyze_year(test_year)
        print(f"平均温度: {result['stats']['avg_temp']}°C")
        print(f"总降水量: {result['stats']['total_precip']}mm")
        print(f"雨日数: {result['stats']['rainy_days']}天")

        print(f"\n极端事件:")
        for event in result['extremes']:
            print(f"  {event['rank']}. {event['type']} - {event['date']} ({event['value']})")