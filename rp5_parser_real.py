"""
RP5气象数据解析器 - 针对真实数据格式修正版
"""
import pandas as pd
import numpy as np
from datetime import datetime
import re
import os


class RP5ParserReal:
    def __init__(self, filepath):
        self.filepath = filepath
        self.raw_data = None
        self.parsed_data = None
        self.daily_summary = None
        self.yearly_summary = None

    def parse_file(self):
        """解析RP5 CSV文件 - 修正版"""
        print(f"正在解析文件: {self.filepath}")

        try:
            # 方法1：直接使用pandas读取，指定分号分隔符
            self.raw_data = pd.read_csv(
                self.filepath,
                sep=';',
                encoding='utf-8',
                quotechar='"',
                on_bad_lines='skip',
                low_memory=False,
                skip_blank_lines=True
            )

            print(f"成功读取原始数据，形状: {self.raw_data.shape}")
            print(f"列数: {len(self.raw_data.columns)}")

            # 显示列名（通常第一列是datetime）
            print(f"前5个列名: {self.raw_data.columns[:5].tolist()}")

            # 重命名第一列为datetime
            first_col = self.raw_data.columns[0]
            if '当地时间' in first_col or '时间' in first_col:
                self.raw_data = self.raw_data.rename(columns={first_col: 'datetime_raw'})
                print(f"已将第一列重命名为: datetime_raw")

            # 解析数据
            self._parse_and_process()

            return self.parsed_data

        except Exception as e:
            print(f"标准读取失败: {e}")
            # 尝试备用方法
            return self._parse_alternative()

    def _parse_and_process(self):
        """解析和处理数据"""
        print("\n开始解析数据字段...")

        # 1. 解析日期时间
        self._parse_datetime()

        # 2. 解析数值字段
        self._parse_numeric_fields()

        # 3. 解析文本字段
        self._parse_text_fields()

        # 4. 添加派生字段
        self._add_derived_fields()

        # 5. 数据清洗
        self._clean_data()

        print(f"解析完成！有效记录: {len(self.parsed_data)}")

        # 6. 生成汇总数据
        self._generate_summaries()

    def _parse_datetime(self):
        """解析日期时间列"""
        print("解析日期时间...")

        if 'datetime_raw' in self.raw_data.columns:
            # 解析格式: "29.12.2025 23:00"
            self.parsed_data = pd.DataFrame()
            self.parsed_data['datetime'] = pd.to_datetime(
                self.raw_data['datetime_raw'],
                format='%d.%m.%Y %H:%M',
                errors='coerce'
            )

            # 检查解析结果
            valid_count = self.parsed_data['datetime'].notna().sum()
            print(f"成功解析 {valid_count}/{len(self.raw_data)} 条日期记录")

            # 移除无效日期
            self.parsed_data = self.parsed_data[self.parsed_data['datetime'].notna()].copy()

        else:
            raise ValueError("找不到日期时间列")

    def _parse_numeric_fields(self):
        """解析数值字段"""
        print("解析数值字段...")

        # 字段映射：RP5字段名 -> 新字段名
        field_mapping = {
            'T': 'temperature',  # 气温
            '"T"': 'temperature',  # 带引号的字段名
            'Tn': 'temp_min',  # 最低温
            '"Tn"': 'temp_min',
            'Tx': 'temp_max',  # 最高温
            '"Tx"': 'temp_max',
            'U': 'humidity',  # 湿度
            '"U"': 'humidity',
            'Ff': 'wind_speed',  # 风速
            '"Ff"': 'wind_speed',
            'RRR': 'precipitation',  # 降水量
            '"RRR"': 'precipitation',
            'sss': 'snow_depth',  # 积雪深度
            '"sss"': 'snow_depth',
            'VV': 'visibility',  # 能见度
            '"VV"': 'visibility',
            'Td': 'dew_point',  # 露点温度
            '"Td"': 'dew_point',
        }

        for rp5_field, new_field in field_mapping.items():
            if rp5_field in self.raw_data.columns:
                print(f"  解析 {rp5_field} -> {new_field}")
                self.parsed_data[new_field] = self.raw_data[rp5_field].apply(self._convert_to_float)
            else:
                # 如果找不到，可能列名有空格等问题
                for col in self.raw_data.columns:
                    if rp5_field.strip('"') in col:
                        self.parsed_data[new_field] = self.raw_data[col].apply(self._convert_to_float)
                        print(f"  找到近似列 {col} -> {new_field}")
                        break

        # 确保必要的字段存在
        required_fields = ['temperature', 'precipitation', 'snow_depth']
        for field in required_fields:
            if field not in self.parsed_data.columns:
                print(f"警告: 缺少必要字段 {field}，用NaN填充")
                self.parsed_data[field] = np.nan

    def _convert_to_float(self, value):
        """安全转换为浮点数"""
        if pd.isna(value):
            return np.nan

        try:
            # 处理字符串
            if isinstance(value, str):
                value = value.strip().strip('"')

                # 处理空值
                if value == '' or value.lower() in ['nan', 'na', 'null']:
                    return np.nan

                # 处理特殊文本
                if '无降水' in value:
                    return 0.0
                if '或更高' in value or '或无' in value:
                    return np.nan
                if '霾' in value:  # 天气描述，不是数值
                    return np.nan

                # 尝试转换为浮点数
                return float(value)

            # 已经是数字
            return float(value)

        except Exception as e:
            # 尝试提取数字
            str_value = str(value)
            numbers = re.findall(r"[-+]?\d*\.\d+|\d+", str_value)
            if numbers:
                return float(numbers[0])
            return np.nan

    def _parse_text_fields(self):
        """解析文本字段"""
        print("解析文本字段...")

        # 风向
        if 'DD' in self.raw_data.columns or '"DD"' in self.raw_data.columns:
            wind_col = 'DD' if 'DD' in self.raw_data.columns else '"DD"'
            self.parsed_data['wind_direction_raw'] = self.raw_data[wind_col]
            self.parsed_data['wind_direction'] = self.raw_data[wind_col].apply(self._parse_wind_direction)

        # 天气现象
        if 'WW' in self.raw_data.columns or '"WW"' in self.raw_data.columns:
            weather_col = 'WW' if 'WW' in self.raw_data.columns else '"WW"'
            self.parsed_data['weather_raw'] = self.raw_data[weather_col]
            self.parsed_data['weather'] = self.raw_data[weather_col].apply(self._parse_weather)

    def _parse_wind_direction(self, value):
        """解析风向文本"""
        if pd.isna(value):
            return np.nan

        value_str = str(value).strip('"')

        # 风向映射
        direction_map = {
            '北': 'N', '东北': 'NE', '东': 'E', '东南': 'SE',
            '南': 'S', '西南': 'SW', '西': 'W', '西北': 'NW',
            '从北方吹来的风': 'N',
            '从南方吹来的风': 'S',
            '从东方吹来的风': 'E',
            '从西方吹来的风': 'W',
            '从西北偏北方向吹来的风': 'NNW',
            '从东北偏北方向吹来的风': 'NNE',
            '从东南偏东方向吹来的风': 'ESE',
            '从西南偏南方向吹来的风': 'SSW',
        }

        for chinese, english in direction_map.items():
            if chinese in value_str:
                return english

        # 尝试提取主要方向
        for direction in ['北', '东', '南', '西']:
            if direction in value_str:
                return direction

        return np.nan

    def _parse_weather(self, value):
        """解析天气现象"""
        if pd.isna(value):
            return 'unknown'

        value_str = str(value).strip('"')

        # 天气分类
        if '晴' in value_str:
            return 'sunny'
        elif '云' in value_str and '无云' not in value_str:
            return 'cloudy'
        elif '雨' in value_str:
            return 'rainy'
        elif '雪' in value_str:
            return 'snowy'
        elif '霾' in value_str:
            return 'haze'
        elif '雾' in value_str:
            return 'fog'
        elif '无降水' in value_str:
            return 'no_precip'
        elif '无观测' in value_str or '未进行观测' in value_str:
            return 'no_obs'
        else:
            return 'other'

    def _add_derived_fields(self):
        """添加派生字段"""
        print("添加派生字段...")

        # 日期相关
        self.parsed_data['date'] = self.parsed_data['datetime'].dt.date
        self.parsed_data['year'] = self.parsed_data['datetime'].dt.year
        self.parsed_data['month'] = self.parsed_data['datetime'].dt.month
        self.parsed_data['day'] = self.parsed_data['datetime'].dt.day
        self.parsed_data['hour'] = self.parsed_data['datetime'].dt.hour

        # 标记字段
        self.parsed_data['has_snow'] = self.parsed_data['snow_depth'] > 0
        self.parsed_data['is_rainy'] = self.parsed_data['precipitation'] > 0.1

        # 季节
        def get_season(month):
            if month in [12, 1, 2]:
                return 'winter'
            elif month in [3, 4, 5]:
                return 'spring'
            elif month in [6, 7, 8]:
                return 'summer'
            else:
                return 'autumn'

        self.parsed_data['season'] = self.parsed_data['month'].apply(get_season)

        print(f"  添加了 {len(self.parsed_data.columns)} 个字段")

    def _clean_data(self):
        """数据清洗"""
        print("数据清洗...")

        original_count = len(self.parsed_data)

        # 1. 移除完全空白的行
        essential_cols = ['temperature', 'precipitation', 'humidity']
        has_data = self.parsed_data[essential_cols].notna().any(axis=1)
        self.parsed_data = self.parsed_data[has_data].copy()

        # 2. 修正明显错误值
        # 温度范围检查（杭州合理范围：-15°C 到 45°C）
        if 'temperature' in self.parsed_data.columns:
            temp_mask = (self.parsed_data['temperature'] >= -15) & (self.parsed_data['temperature'] <= 45)
            self.parsed_data.loc[~temp_mask, 'temperature'] = np.nan

        # 积雪深度范围（杭州合理范围：0-50cm）
        if 'snow_depth' in self.parsed_data.columns:
            snow_mask = (self.parsed_data['snow_depth'] >= 0) & (self.parsed_data['snow_depth'] <= 50)
            self.parsed_data.loc[~snow_mask, 'snow_depth'] = np.nan
            self.parsed_data.loc[self.parsed_data['snow_depth'] < 0, 'snow_depth'] = 0

        # 3. 按时间排序
        self.parsed_data = self.parsed_data.sort_values('datetime').reset_index(drop=True)

        cleaned_count = len(self.parsed_data)
        print(f"  清洗后保留 {cleaned_count}/{original_count} 条记录 ({cleaned_count / original_count * 100:.1f}%)")

    def _generate_summaries(self):
        """生成汇总数据"""
        print("\n生成汇总数据...")

        # 1. 日统计数据
        self._generate_daily_summary()

        # 2. 年统计数据
        self._generate_yearly_summary()

        # 3. 打印统计信息
        self._print_statistics()

    def _generate_daily_summary(self):
        """生成日统计数据"""
        if len(self.parsed_data) == 0:
            return

        # 按日期分组
        daily_groups = self.parsed_data.groupby('date')

        daily_data = []
        for date, group in daily_groups:
            # 计算日统计
            daily_stats = {
                'date': date,
                'temp_avg': group['temperature'].mean(),
                'temp_max': group['temperature'].max(),
                'temp_min': group['temperature'].min(),
                'precip_total': group['precipitation'].sum(),
                'snow_depth_max': group['snow_depth'].max(),
                'has_snow': (group['snow_depth'] > 0).any(),
                'humidity_avg': group['humidity'].mean(),
                'wind_speed_avg': group['wind_speed'].mean(),
                'record_count': len(group)
            }

            # 风向模式
            if 'wind_direction' in group.columns:
                wind_dirs = group['wind_direction'].dropna()
                if len(wind_dirs) > 0:
                    daily_stats['wind_dir_common'] = wind_dirs.mode()[0] if not wind_dirs.mode().empty else np.nan

            daily_data.append(daily_stats)

        self.daily_summary = pd.DataFrame(daily_data)

        # 填充NaN值
        numeric_cols = ['temp_avg', 'temp_max', 'temp_min', 'precip_total',
                        'snow_depth_max', 'humidity_avg', 'wind_speed_avg']
        for col in numeric_cols:
            if col in self.daily_summary.columns:
                self.daily_summary[col] = self.daily_summary[col].fillna(0)

        print(f"  生成了 {len(self.daily_summary)} 天的日统计数据")

    def _generate_yearly_summary(self):
        """生成年统计数据"""
        if self.daily_summary is None or len(self.daily_summary) == 0:
            return

        # 确保有年份列
        self.daily_summary['date'] = pd.to_datetime(self.daily_summary['date'])
        self.daily_summary['year'] = self.daily_summary['date'].dt.year

        # 按年分组
        yearly_groups = self.daily_summary.groupby('year')

        yearly_data = []
        for year, group in yearly_groups:
            # 计算年统计
            yearly_stats = {
                'year': year,
                'temp_avg': group['temp_avg'].mean(),
                'temp_max_avg': group['temp_max'].mean(),
                'temp_min_avg': group['temp_min'].mean(),
                'precip_total': group['precip_total'].sum(),
                'snow_days': group['has_snow'].sum(),
                'max_snow_depth': group['snow_depth_max'].max(),
                'humidity_avg': group['humidity_avg'].mean(),
                'wind_speed_avg': group['wind_speed_avg'].mean(),
                'days_count': len(group)
            }

            yearly_data.append(yearly_stats)

        self.yearly_summary = pd.DataFrame(yearly_data)

        print(f"  生成了 {len(self.yearly_summary)} 年的统计数据")

    def _print_statistics(self):
        """打印统计信息"""
        print("\n" + "=" * 60)
        print("数据统计摘要")
        print("=" * 60)

        if self.parsed_data is not None and len(self.parsed_data) > 0:
            print(f"详细数据记录数: {len(self.parsed_data)}")
            print(f"时间范围: {self.parsed_data['datetime'].min()} 到 {self.parsed_data['datetime'].max()}")
            print(f"覆盖年份: {sorted(self.parsed_data['year'].unique())}")

            # 积雪统计
            if 'snow_depth' in self.parsed_data.columns:
                snow_days = self.parsed_data[self.parsed_data['snow_depth'] > 0]
                print(f"\n积雪统计:")
                print(f"  积雪记录数: {len(snow_days)}")
                if len(snow_days) > 0:
                    print(f"  最大积雪深度: {snow_days['snow_depth'].max()} cm")
                    print(f"  平均积雪深度: {snow_days['snow_depth'].mean():.1f} cm")

            # 温度统计
            if 'temperature' in self.parsed_data.columns:
                print(f"\n温度统计:")
                print(f"  平均温度: {self.parsed_data['temperature'].mean():.1f}°C")
                print(f"  最高温度: {self.parsed_data['temperature'].max():.1f}°C")
                print(f"  最低温度: {self.parsed_data['temperature'].min():.1f}°C")

        if self.daily_summary is not None:
            print(f"\n日统计天数: {len(self.daily_summary)}")

        if self.yearly_summary is not None:
            print(f"\n年统计年份数: {len(self.yearly_summary)}")
            print("\n各年份统计:")
            print(self.yearly_summary.to_string())

        print("=" * 60)

    def _parse_alternative(self):
        """备用解析方法"""
        print("尝试备用解析方法...")

        try:
            # 手动逐行解析
            data_lines = []

            with open(self.filepath, 'r', encoding='utf-8') as f:
                # 跳过可能的表头
                header = f.readline()
                print(f"表头行: {header[:100]}...")

                line_count = 0
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        # 分割字段
                        parts = line.split(';')
                        if len(parts) >= 5:  # 至少要有基本字段
                            data_lines.append(parts)
                            line_count += 1

                    # 只读取前1000行测试
                    if line_count >= 1000:
                        break

            if data_lines:
                print(f"成功读取 {len(data_lines)} 行数据")

                # 创建DataFrame
                self.raw_data = pd.DataFrame(data_lines)
                print(f"创建的DataFrame形状: {self.raw_data.shape}")

                # 继续解析
                self._parse_and_process()

                return self.parsed_data

        except Exception as e:
            print(f"备用方法也失败: {e}")

        return None

    def save_clean_data(self, output_dir="data/cleaned"):
        """保存清洗后的数据"""
        os.makedirs(output_dir, exist_ok=True)

        if self.parsed_data is not None:
            detailed_path = os.path.join(output_dir, "hangzhou_detailed.csv")
            self.parsed_data.to_csv(detailed_path, index=False, encoding='utf-8')
            print(f"详细数据已保存: {detailed_path}")

        if self.daily_summary is not None:
            daily_path = os.path.join(output_dir, "hangzhou_daily.csv")
            self.daily_summary.to_csv(daily_path, index=False, encoding='utf-8')
            print(f"日统计数据已保存: {daily_path}")

        if self.yearly_summary is not None:
            yearly_path = os.path.join(output_dir, "hangzhou_yearly.csv")
            self.yearly_summary.to_csv(yearly_path, index=False, encoding='utf-8')
            print(f"年统计数据已保存: {yearly_path}")


# 测试函数
def test_parser():
    """测试解析器"""
    filepath = "data/hangzhou_weather.csv"

    if not os.path.exists(filepath):
        print(f"文件不存在: {filepath}")
        return

    parser = RP5ParserReal(filepath)

    try:
        print("=" * 60)
        print("开始解析RP5数据文件")
        print("=" * 60)

        # 解析数据
        data = parser.parse_file()

        if data is not None and len(data) > 0:
            print("\n解析成功！")
            print(f"详细数据记录数: {len(data)}")
            print(f"时间范围: {data['datetime'].min()} 到 {data['datetime'].max()}")

            # 显示数据样本
            print("\n数据样本（前3行）:")
            sample_cols = ['datetime', 'temperature', 'precipitation', 'snow_depth', 'wind_direction', 'weather']
            available_cols = [col for col in sample_cols if col in data.columns]
            print(data[available_cols].head(3))

            # 保存清洗后的数据
            parser.save_clean_data()

            return parser
        else:
            print("解析失败：数据为空")

    except Exception as e:
        print(f"解析失败: {e}")
        import traceback
        traceback.print_exc()

    return None


if __name__ == "__main__":
    parser = test_parser()

    if parser is not None:
        # 使用解析器的数据更新历史分析器
        print("\n" + "=" * 60)
        print("准备历史分析数据")
        print("=" * 60)

        # 这里可以添加代码将数据传递给历史分析器