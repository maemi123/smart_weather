"""
RP5气象数据解析器 - 最终修正版
"""
import pandas as pd
import numpy as np
from datetime import datetime
import re
import os


class RP5ParserFinal:
    def __init__(self, filepath):
        self.filepath = filepath
        self.raw_data = None
        self.parsed_data = None
        self.daily_data = None

    def parse_file(self):
        """解析RP5文件 - 直接使用pandas的CSV读取"""
        print(f"正在解析文件: {self.filepath}")

        # 1. 使用pandas直接读取CSV，注意格式
        # 分隔符是分号，引号字符是双引号
        self.raw_data = pd.read_csv(
            self.filepath,
            sep=';',
            quotechar='"',
            encoding='utf-8',
            on_bad_lines='skip',
            low_memory=False,
            skip_blank_lines=True
        )

        print(f"原始数据形状: {self.raw_data.shape}")
        print(f"列名: {self.raw_data.columns.tolist()}")

        # 2. 第一列是日期时间，列名可能是 '当地时间 杭州市(机场)'
        # 重命名第一列为 'datetime_str'
        first_col = self.raw_data.columns[0]
        self.raw_data = self.raw_data.rename(columns={first_col: 'datetime_str'})

        # 3. 解析日期时间
        print("正在解析日期时间...")
        self.raw_data['datetime'] = self.raw_data['datetime_str'].apply(self._parse_datetime)

        # 4. 移除无法解析的日期
        valid_dates = self.raw_data['datetime'].notna()
        self.raw_data = self.raw_data[valid_dates].copy()
        print(f"有效数据记录: {len(self.raw_data)}")

        # 5. 按时间排序
        self.raw_data = self.raw_data.sort_values('datetime')
        self.raw_data = self.raw_data.reset_index(drop=True)

        # 6. 提取数值数据
        self._extract_numeric_data()

        # 7. 生成日统计数据
        self._generate_daily_stats()

        print("解析完成！")
        return self.parsed_data

    def _parse_datetime(self, dt_str):
        """解析日期时间字符串（格式：DD.MM.YYYY HH:MM）"""
        if pd.isna(dt_str):
            return pd.NaT

        try:
            # 清理字符串
            dt_str = str(dt_str).strip()

            # 格式: "29.12.2025 23:00"
            # 注意：这是欧洲日期格式 DD.MM.YYYY
            return datetime.strptime(dt_str, "%d.%m.%Y %H:%M")
        except Exception as e:
            # 尝试其他格式
            try:
                return pd.to_datetime(dt_str, dayfirst=True)  # 指定日在前
            except:
                # print(f"日期解析失败: {dt_str} - {e}")
                return pd.NaT

    def _extract_numeric_data(self):
        """提取和转换数值数据"""
        print("正在提取数值数据...")

        self.parsed_data = pd.DataFrame()
        self.parsed_data['datetime'] = self.raw_data['datetime']

        # 关键字段映射
        field_mapping = {
            'T': 'temperature',  # 气温 (°C)
            'Tx': 'temp_max',  # 最高温 (°C)
            'Tn': 'temp_min',  # 最低温 (°C)
            'U': 'humidity',  # 相对湿度 (%)
            'Ff': 'wind_speed',  # 风速 (m/s)
            'RRR': 'precipitation',  # 降水量 (mm)
            'sss': 'snow_depth',  # 积雪深度 (cm) - 重点关注！
            'VV': 'visibility',  # 能见度 (km)
            'Td': 'dew_point',  # 露点温度 (°C)
        }

        # 提取每个字段
        for rp5_field, new_name in field_mapping.items():
            if rp5_field in self.raw_data.columns:
                self.parsed_data[new_name] = self.raw_data[rp5_field].apply(self._convert_to_float)
                non_na = self.parsed_data[new_name].notna().sum()
                print(f"  {new_name}: {non_na} 条有效记录")
            else:
                self.parsed_data[new_name] = np.nan
                print(f"  {new_name}: 列不存在")

        # 提取文本字段
        if 'DD' in self.raw_data.columns:
            self.parsed_data['wind_direction'] = self.raw_data['DD'].apply(self._parse_wind_direction)

        if 'WW' in self.raw_data.columns:
            self.parsed_data['weather'] = self.raw_data['WW'].apply(self._parse_weather)

        # 添加日期信息
        self.parsed_data['date'] = self.parsed_data['datetime'].dt.date
        self.parsed_data['year'] = self.parsed_data['datetime'].dt.year
        self.parsed_data['month'] = self.parsed_data['datetime'].dt.month
        self.parsed_data['day'] = self.parsed_data['datetime'].dt.day
        self.parsed_data['hour'] = self.parsed_data['datetime'].dt.hour

        # 添加标记
        self.parsed_data['has_snow'] = self.parsed_data['snow_depth'] > 0
        self.parsed_data['is_rainy'] = self.parsed_data['precipitation'] > 0.1

        # 添加季节
        self.parsed_data['season'] = self.parsed_data['month'].apply(
            lambda m: 'winter' if m in [12, 1, 2] else
            'spring' if m in [3, 4, 5] else
            'summer' if m in [6, 7, 8] else 'autumn'
        )

    def _convert_to_float(self, value):
        """安全转换为浮点数"""
        if pd.isna(value):
            return np.nan

        try:
            str_val = str(value).strip()

            # 处理空字符串
            if str_val == '':
                return np.nan

            # 处理特殊文本
            if '无降水' in str_val:
                return 0.0
            if '或更高' in str_val or '或无' in str_val:
                return np.nan
            if '无' in str_val and len(str_val) < 5:  # 简单的"无"
                return 0.0

            # 尝试直接转换
            return float(str_val)
        except:
            # 尝试提取数字
            nums = re.findall(r"[-+]?\d*\.\d+|\d+", str(value))
            if nums:
                return float(nums[0])
            return np.nan

    def _parse_wind_direction(self, value):
        """解析风向文本为缩写"""
        if pd.isna(value):
            return np.nan

        value_str = str(value).strip()

        # 风向映射
        dir_map = {
            '北': 'N', '东北': 'NE', '东': 'E', '东南': 'SE',
            '南': 'S', '西南': 'SW', '西': 'W', '西北': 'NW',
            '从北方吹来的风': 'N', '从南方吹来的风': 'S',
            '从东方吹来的风': 'E', '从西方吹来的风': 'W',
            '从西北偏北方向吹来的风': 'NNW',
            '从东北偏北方向吹来的风': 'NNE',
            '从东南偏东方向吹来的风': 'ESE',
            '从西南偏南方向吹来的风': 'SSW',
        }

        for chinese, abbrev in dir_map.items():
            if chinese in value_str:
                return abbrev

        return np.nan

    def _parse_weather(self, value):
        """简化天气现象分类"""
        if pd.isna(value):
            return 'unknown'

        value_str = str(value).strip()

        if '晴' in value_str:
            return 'clear'
        elif '霾' in value_str:
            return 'haze'
        elif '云' in value_str:
            return 'cloudy'
        elif '雨' in value_str:
            if '小雨' in value_str:
                return 'light_rain'
            elif '大雨' in value_str or '暴雨' in value_str:
                return 'heavy_rain'
            else:
                return 'rain'
        elif '雪' in value_str:
            if '小雪' in value_str:
                return 'light_snow'
            elif '大雪' in value_str or '暴雪' in value_str:
                return 'heavy_snow'
            else:
                return 'snow'
        elif '雾' in value_str:
            return 'fog'
        else:
            return 'unknown'

    def _generate_daily_stats(self):
        """生成日统计数据"""
        print("正在生成日统计数据...")

        if self.parsed_data is None or len(self.parsed_data) == 0:
            print("没有解析数据，无法生成日统计")
            return

        # 按日期分组
        daily_groups = self.parsed_data.groupby('date')

        daily_stats = []

        for date, group in daily_groups:
            # 基本统计
            day_stats = {
                'date': date,
                'year': group['year'].iloc[0],
                'month': group['month'].iloc[0],
                'day': group['day'].iloc[0],

                # 温度统计
                'temp_avg': group['temperature'].mean(),
                'temp_max': group['temperature'].max(),
                'temp_min': group['temperature'].min(),

                # 降水统计
                'precip_total': group['precipitation'].sum(),
                'rainy_hours': (group['precipitation'] > 0).sum(),

                # 积雪统计
                'snow_depth_max': group['snow_depth'].max(),
                'has_snow': (group['snow_depth'] > 0).any(),

                # 其他
                'humidity_avg': group['humidity'].mean(),
                'wind_speed_avg': group['wind_speed'].mean(),
                'visibility_avg': group['visibility'].mean(),
            }

            # 风向（最常见的方向）
            if 'wind_direction' in group.columns:
                wind_dirs = group['wind_direction'].dropna()
                if len(wind_dirs) > 0:
                    day_stats['wind_dir_common'] = wind_dirs.mode().iloc[0] if not wind_dirs.mode().empty else np.nan
                else:
                    day_stats['wind_dir_common'] = np.nan

            daily_stats.append(day_stats)

        self.daily_data = pd.DataFrame(daily_stats)

        # 处理NaN值
        numeric_cols = ['temp_avg', 'temp_max', 'temp_min', 'precip_total',
                        'snow_depth_max', 'humidity_avg', 'wind_speed_avg', 'visibility_avg']

        for col in numeric_cols:
            if col in self.daily_data.columns:
                self.daily_data[col] = self.daily_data[col].fillna(0)

        print(f"生成 {len(self.daily_data)} 天的日统计数据")

    def get_data_summary(self):
        """获取数据摘要"""
        if self.parsed_data is None:
            return None

        summary = {
            'period': {
                'start': self.parsed_data['datetime'].min(),
                'end': self.parsed_data['datetime'].max(),
                'days': self.daily_data['date'].nunique() if self.daily_data is not None else 0,
                'years': self.parsed_data['year'].nunique(),
            },
            'temperature': {
                'avg': self.parsed_data['temperature'].mean(),
                'max': self.parsed_data['temperature'].max(),
                'min': self.parsed_data['temperature'].min(),
            },
            'precipitation': {
                'total': self.parsed_data['precipitation'].sum(),
                'rainy_days': (self.daily_data['precip_total'] > 0).sum() if self.daily_data is not None else 0,
            },
            'snow': {
                'snow_days': self.parsed_data['has_snow'].sum(),
                'max_depth': self.parsed_data['snow_depth'].max(),
                'years_with_snow': self.parsed_data[self.parsed_data['has_snow']]['year'].nunique(),
            },
            'records_count': len(self.parsed_data),
            'data_quality': {
                'temperature_notna': self.parsed_data['temperature'].notna().mean() * 100,
                'precipitation_notna': self.parsed_data['precipitation'].notna().mean() * 100,
                'snow_depth_notna': self.parsed_data['snow_depth'].notna().mean() * 100,
            }
        }

        return summary

    def get_yearly_stats(self):
        """生成年统计数据"""
        if self.daily_data is None:
            self._generate_daily_stats()

        yearly_stats = self.daily_data.groupby('year').agg({
            'temp_avg': 'mean',
            'temp_max': 'mean',
            'temp_min': 'mean',
            'precip_total': 'sum',
            'snow_depth_max': lambda x: (x > 0).sum(),  # 积雪日数
            'has_snow': 'sum',
            'rainy_hours': 'sum',
            'humidity_avg': 'mean',
            'wind_speed_avg': 'mean',
        }).reset_index()

        yearly_stats.columns = [
            'year', 'temp_avg', 'temp_max_avg', 'temp_min_avg',
            'precip_total', 'snow_days', 'snow_days_bool', 'rainy_hours',
            'humidity_avg', 'wind_speed_avg'
        ]

        # 计算高温日数（需要小时数据）
        if self.parsed_data is not None:
            yearly_hot_days = self.parsed_data[self.parsed_data['temperature'] >= 35].groupby('year').size()
            yearly_stats = yearly_stats.merge(
                yearly_hot_days.rename('hot_days'),
                left_on='year',
                right_index=True,
                how='left'
            ).fillna(0)

        return yearly_stats

    def export_clean_data(self, output_dir="data"):
        """导出清洗后的数据"""
        os.makedirs(output_dir, exist_ok=True)

        # 导出详细数据
        detail_path = os.path.join(output_dir, "hangzhou_hourly.csv")
        if self.parsed_data is not None:
            self.parsed_data.to_csv(detail_path, index=False, encoding='utf-8')
            print(f"详细数据已导出到: {detail_path}")

        # 导出日统计数据
        daily_path = os.path.join(output_dir, "hangzhou_daily.csv")
        if self.daily_data is not None:
            self.daily_data.to_csv(daily_path, index=False, encoding='utf-8')
            print(f"日统计数据已导出到: {daily_path}")

        # 导出年统计数据
        yearly_path = os.path.join(output_dir, "hangzhou_yearly.csv")
        yearly_stats = self.get_yearly_stats()
        yearly_stats.to_csv(yearly_path, index=False, encoding='utf-8')
        print(f"年统计数据已导出到: {yearly_path}")


# 使用示例
def test_parser():
    """测试解析器"""
    filepath = "data/hangzhou_weather.csv"

    if not os.path.exists(filepath):
        print(f"文件不存在: {filepath}")
        print("请将RP5数据文件放在 data/hangzhou_weather.csv")
        return

    print("=" * 70)
    print("RP5数据解析器测试")
    print("=" * 70)

    parser = RP5ParserFinal(filepath)

    try:
        # 解析文件
        data = parser.parse_file()

        if data is None or len(data) == 0:
            print("解析失败：没有数据")
            return

        # 获取摘要
        summary = parser.get_data_summary()

        print("\n" + "=" * 70)
        print("数据摘要")
        print("=" * 70)
        print(f"时间范围: {summary['period']['start']} 到 {summary['period']['end']}")
        print(f"总天数: {summary['period']['days']} 天")
        print(f"覆盖年份: {summary['period']['years']} 年")
        print(f"总记录数: {summary['records_count']:,} 条（小时数据）")

        print(f"\n温度统计:")
        print(f"  平均温度: {summary['temperature']['avg']:.1f}°C")
        print(f"  最高温度: {summary['temperature']['max']:.1f}°C")
        print(f"  最低温度: {summary['temperature']['min']:.1f}°C")

        print(f"\n降水统计:")
        print(f"  总降水量: {summary['precipitation']['total']:.1f} mm")
        print(f"  降水日数: {summary['precipitation']['rainy_days']} 天")

        print(f"\n积雪统计:")
        print(f"  积雪日数: {summary['snow']['snow_days']} 天")
        print(f"  最大积雪深度: {summary['snow']['max_depth']} cm")
        print(f"  有积雪的年份: {summary['snow']['years_with_snow']} 年")

        print(f"\n数据质量:")
        print(f"  温度数据完整度: {summary['data_quality']['temperature_notna']:.1f}%")
        print(f"  降水数据完整度: {summary['data_quality']['precipitation_notna']:.1f}%")
        print(f"  积雪数据完整度: {summary['data_quality']['snow_depth_notna']:.1f}%")

        # 查看积雪数据详情
        if 'snow_depth' in data.columns:
            snow_data = data[data['snow_depth'] > 0]
            if len(snow_data) > 0:
                print(f"\n积雪数据详情:")
                print(f"  有积雪的记录数: {len(snow_data)}")
                print(f"  积雪深度统计:")
                print(f"    最大值: {snow_data['snow_depth'].max()} cm")
                print(f"    平均值: {snow_data['snow_depth'].mean():.1f} cm")
                print(f"    最小值: {snow_data['snow_depth'].min()} cm")

                # 按年份统计
                yearly_snow = snow_data.groupby('year').agg({
                    'snow_depth': ['max', 'mean', 'count']
                })
                print(f"\n按年份积雪统计:")
                for year in yearly_snow.index:
                    max_depth = yearly_snow.loc[year, ('snow_depth', 'max')]
                    avg_depth = yearly_snow.loc[year, ('snow_depth', 'mean')]
                    count = yearly_snow.loc[year, ('snow_depth', 'count')]
                    print(f"  {year}年: {count}小时有积雪，最大{max_depth}cm，平均{avg_depth:.1f}cm")

        # 导出数据
        print(f"\n" + "=" * 70)
        print("导出数据文件...")
        parser.export_clean_data()

        # 显示前几行数据
        print(f"\n前3天日统计数据:")
        if parser.daily_data is not None:
            print(parser.daily_data[['date', 'temp_avg', 'temp_max', 'temp_min',
                                     'precip_total', 'snow_depth_max']].head(3))

        print(f"\n前3小时详细数据:")
        print(data[['datetime', 'temperature', 'precipitation', 'snow_depth',
                    'humidity', 'wind_speed']].head(3))

        print("\n✓ 解析成功！")

    except Exception as e:
        print(f"\n✗ 解析失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    test_parser()