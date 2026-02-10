"""
RP5气象数据解析器 - 增强版
"""
import pandas as pd
import numpy as np
from datetime import datetime
import re
import os
import chardet  # 需要安装：pip install chardet

class RP5Parser:
    def __init__(self, filepath):
        self.filepath = filepath
        self.raw_data = None
        self.parsed_data = None

    def inspect_file(self):
        """检查文件结构和编码"""
        print("=" * 60)
        print("文件检查报告")
        print("=" * 60)

        # 1. 检查文件大小
        file_size = os.path.getsize(self.filepath)
        print(f"文件大小: {file_size:,} bytes ({file_size/1024:.1f} KB)")

        # 2. 检测编码
        with open(self.filepath, 'rb') as f:
            raw_data = f.read(10000)  # 读取前10KB检测编码
            result = chardet.detect(raw_data)
            print(f"检测到编码: {result['encoding']} (置信度: {result['confidence']:.2f})")

        # 3. 查看前几行
        print("\n文件前5行内容:")
        print("-" * 40)
        try:
            with open(self.filepath, 'r', encoding='utf-8') as f:
                for i in range(5):
                    line = f.readline().strip()
                    print(f"第{i+1}行: {line[:100]}{'...' if len(line)>100 else ''}")
        except:
            try:
                with open(self.filepath, 'r', encoding='gbk') as f:
                    for i in range(5):
                        line = f.readline().strip()
                        print(f"第{i+1}行: {line[:100]}{'...' if len(line)>100 else ''}")
            except Exception as e:
                print(f"读取文件失败: {e}")

        print("=" * 60)

    def parse_file_smart(self):
        """智能解析文件，尝试多种方法"""
        self.inspect_file()

        # 方法1：尝试标准CSV读取
        print("\n尝试方法1: 标准CSV解析...")
        try:
            # 尝试检测分隔符
            with open(self.filepath, 'r', encoding='utf-8') as f:
                first_line = f.readline()

            # 判断分隔符
            if ';' in first_line:
                sep = ';'
                print(f"检测到分隔符: 分号 (;)")
            elif ',' in first_line:
                sep = ','
                print(f"检测到分隔符: 逗号 (,)")
            else:
                sep = '\t'
                print(f"检测到分隔符: 制表符 (\\t)")

            # 尝试读取
            self.raw_data = pd.read_csv(
                self.filepath,
                sep=sep,
                encoding='utf-8',
                on_bad_lines='skip',
                low_memory=False,
                skip_blank_lines=True
            )

            print(f"成功读取，形状: {self.raw_data.shape}")
            print(f"列名: {self.raw_data.columns.tolist()}")

        except Exception as e:
            print(f"方法1失败: {e}")
            self.raw_data = None

        # 如果方法1失败，尝试方法2：手动解析
        if self.raw_data is None or len(self.raw_data) < 2:
            print("\n尝试方法2: 手动解析...")
            self._parse_manually()

        # 如果方法2失败，尝试方法3：逐行解析
        if self.raw_data is None or len(self.raw_data) < 2:
            print("\n尝试方法3: 逐行解析...")
            self._parse_line_by_line()

        if self.raw_data is not None and len(self.raw_data) > 1:
            self._process_data()
            return self.parsed_data
        else:
            raise ValueError("无法解析文件，可能是格式不正确或文件损坏")

    def _parse_manually(self):
        """手动解析文件"""
        try:
            # 读取所有行
            with open(self.filepath, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            print(f"总行数: {len(lines)}")

            # 找到真正的数据开始行
            data_start = 0
            for i, line in enumerate(lines):
                # 寻找包含日期时间的行（如 "29.12.2025"）
                if re.search(r'\d{1,2}\.\d{1,2}\.\d{4}', line):
                    data_start = i
                    print(f"在第 {i+1} 行找到数据开始")
                    break

            if data_start == 0:
                print("未找到数据开始行，尝试第二行")
                data_start = 1 if len(lines) > 1 else 0

            # 获取表头（假设在数据开始的前一行）
            if data_start > 0:
                header_line = lines[data_start - 1].strip()
                print(f"表头行: {header_line[:100]}...")

            # 解析数据行
            data_lines = []
            for line in lines[data_start:]:
                line = line.strip()
                if line and not line.startswith('#'):  # 跳过空行和注释
                    data_lines.append(line)

            print(f"找到 {len(data_lines)} 行数据")

            if len(data_lines) > 0:
                # 创建DataFrame
                # 这里需要根据实际格式进一步解析
                self.raw_data = pd.DataFrame([line.split(';') for line in data_lines])
                print(f"创建DataFrame，形状: {self.raw_data.shape}")

        except Exception as e:
            print(f"手动解析失败: {e}")

    def _parse_line_by_line(self):
        """逐行解析，处理复杂格式"""
        records = []

        try:
            with open(self.filepath, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()

                    # 跳过空行和明显不是数据的行
                    if not line or line.startswith('#') or '当地时间' in line:
                        continue

                    # 尝试解析数据行
                    record = self._parse_data_line(line, line_num)
                    if record:
                        records.append(record)

                    # 只处理前100行用于测试
                    if line_num > 100:
                        break

            if records:
                self.raw_data = pd.DataFrame(records)
                print(f"成功解析 {len(records)} 行数据")

        except Exception as e:
            print(f"逐行解析失败: {e}")

    def _parse_data_line(self, line, line_num):
        """解析单行数据"""
        # 示例行: 29.12.2025 23:00;"9.9";"761.8";"765.7";"-0.3";"53";"从北方吹来的风";"1";"";"5";"";"云量发展情况没有进行观测或无法观测。 ";"";"";"3.4";"18.1";"";"";"2500或更高，或无云。";"";"";"8.0";"0.8";"无降水";"12";"";"";"";"";

        # 分割字段
        parts = line.split(';')

        if len(parts) < 5:  # 太短，可能不是有效数据
            return None

        try:
            record = {}

            # 解析日期时间（第一部分）
            datetime_part = parts[0].strip('"')
            if ' ' in datetime_part:
                date_part, time_part = datetime_part.split(' ', 1)
                try:
                    dt = datetime.strptime(f"{date_part} {time_part}", "%d.%m.%Y %H:%M")
                    record['datetime'] = dt
                except:
                    record['datetime'] = pd.NaT

            # 解析其他字段
            field_names = ['T', 'Po', 'P', 'Pa', 'U', 'DD', 'Ff', 'ff10', 'ff3',
                          'N', 'WW', 'W1', 'W2', 'Tn', 'Tx', 'Cl', 'Nh', 'H',
                          'Cm', 'Ch', 'VV', 'Td', 'RRR', 'tR', 'E', 'Tg', "E'", 'sss']

            for i, field in enumerate(field_names):
                if i + 1 < len(parts):
                    value = parts[i + 1].strip('"')
                    record[field] = value

            return record

        except Exception as e:
            print(f"解析第 {line_num} 行失败: {e}")
            return None

    def _process_data(self):
        """处理解析后的数据"""
        if self.raw_data is None or len(self.raw_data) == 0:
            return

        print(f"\n处理数据，原始形状: {self.raw_data.shape}")

        # 创建解析后的DataFrame
        self.parsed_data = pd.DataFrame()

        # 处理日期时间
        if 'datetime' in self.raw_data.columns:
            self.parsed_data['datetime'] = pd.to_datetime(self.raw_data['datetime'], errors='coerce')
        elif 'T' in self.raw_data.columns:
            # 尝试从第一列推断
            first_col = self.raw_data.iloc[:, 0]
            self.parsed_data['datetime'] = pd.to_datetime(first_col, format='%d.%m.%Y %H:%M', errors='coerce')

        # 移除无效日期
        valid_mask = self.parsed_data['datetime'].notna()
        self.parsed_data = self.parsed_data[valid_mask].copy()

        print(f"有效日期记录: {len(self.parsed_data)}")

        if len(self.parsed_data) == 0:
            print("警告: 没有有效的数据记录")
            return

        # 解析数值字段
        self._parse_numeric_fields()

        # 添加派生字段
        self._add_derived_fields()

        print(f"最终数据形状: {self.parsed_data.shape}")

    def _parse_numeric_fields(self):
        """解析数值字段"""
        # 需要解析的数值字段
        numeric_fields = {
            'T': 'temperature',
            'Tx': 'temp_max',
            'Tn': 'temp_min',
            'U': 'humidity',
            'Ff': 'wind_speed',
            'RRR': 'precipitation',
            'sss': 'snow_depth',
            'VV': 'visibility',
            'Td': 'dew_point'
        }

        for rp5_field, new_name in numeric_fields.items():
            if rp5_field in self.raw_data.columns:
                self.parsed_data[new_name] = self.raw_data[rp5_field].apply(self._safe_float)
            else:
                self.parsed_data[new_name] = np.nan

        # 解析风向
        if 'DD' in self.raw_data.columns:
            self.parsed_data['wind_direction'] = self.raw_data['DD'].apply(self._parse_wind_dir)

        # 解析天气
        if 'WW' in self.raw_data.columns:
            self.parsed_data['weather'] = self.raw_data['WW'].apply(self._parse_weather)

    def _safe_float(self, value):
        """安全转换为浮点数"""
        if pd.isna(value):
            return np.nan

        try:
            str_val = str(value).strip().strip('"')

            # 处理空值和特殊文本
            if str_val == '' or str_val.lower() in ['nan', 'na', 'null', '无']:
                return np.nan

            # 处理特殊描述
            if '无降水' in str_val:
                return 0.0
            if '或更高' in str_val or '或无' in str_val:
                return np.nan

            # 尝试转换
            return float(str_val)
        except:
            # 尝试提取数字
            nums = re.findall(r"[-+]?\d*\.\d+|\d+", str(value))
            return float(nums[0]) if nums else np.nan

    def _parse_wind_dir(self, value):
        """解析风向"""
        if pd.isna(value):
            return np.nan

        value_str = str(value).strip('"')

        # 简单映射
        dir_map = {
            '北': 'N', '东北': 'NE', '东': 'E', '东南': 'SE',
            '南': 'S', '西南': 'SW', '西': 'W', '西北': 'NW',
        }

        for chinese, english in dir_map.items():
            if chinese in value_str:
                return english

        return np.nan

    def _parse_weather(self, value):
        """解析天气现象"""
        if pd.isna(value):
            return 'unknown'

        value_str = str(value).strip('"')

        if '晴' in value_str:
            return 'clear'
        elif '云' in value_str:
            return 'cloudy'
        elif '雨' in value_str:
            return 'rain'
        elif '雪' in value_str:
            return 'snow'
        elif '雾' in value_str:
            return 'fog'
        else:
            return 'unknown'

    def _add_derived_fields(self):
        """添加派生字段"""
        # 日期相关
        self.parsed_data['date'] = self.parsed_data['datetime'].dt.date
        self.parsed_data['year'] = self.parsed_data['datetime'].dt.year
        self.parsed_data['month'] = self.parsed_data['datetime'].dt.month
        self.parsed_data['day'] = self.parsed_data['datetime'].dt.day

        # 标记
        self.parsed_data['has_snow'] = self.parsed_data['snow_depth'] > 0
        self.parsed_data['is_rainy'] = self.parsed_data['precipitation'] > 0.1

        # 季节
        self.parsed_data['season'] = self.parsed_data['month'].apply(
            lambda m: 'winter' if m in [12,1,2] else
                     'spring' if m in [3,4,5] else
                     'summer' if m in [6,7,8] else 'autumn'
        )

    def get_summary(self):
        """获取数据摘要"""
        if self.parsed_data is None:
            print("请先调用 parse_file_smart()")
            return None

        summary = {
            'total_records': len(self.parsed_data),
            'date_range': (self.parsed_data['datetime'].min(),
                          self.parsed_data['datetime'].max()),
            'fields': {},
            'snow_info': {}
        }

        # 字段信息
        for col in self.parsed_data.columns:
            non_na = self.parsed_data[col].notna().sum()
            summary['fields'][col] = {
                'non_na': non_na,
                'na_percent': 100 * (1 - non_na/len(self.parsed_data))
            }

        # 积雪信息
        if 'snow_depth' in self.parsed_data.columns:
            snow_data = self.parsed_data[self.parsed_data['snow_depth'] > 0]
            summary['snow_info'] = {
                'snow_days': len(snow_data),
                'max_depth': snow_data['snow_depth'].max() if len(snow_data) > 0 else 0,
                'avg_depth': snow_data['snow_depth'].mean() if len(snow_data) > 0 else 0
            }

        return summary

# 使用示例
if __name__ == "__main__":
    # 替换为你的文件路径
    filepath = "data/hangzhou_weather.csv"

    if not os.path.exists(filepath):
        print(f"文件不存在: {filepath}")
        exit(1)

    parser = RP5Parser(filepath)

    try:
        data = parser.parse_file_smart()

        if data is not None and len(data) > 0:
            print(f"\n{'='*60}")
            print("解析成功！")
            print(f"{'='*60}")

            summary = parser.get_summary()
            print(f"总记录数: {summary['total_records']}")
            print(f"时间范围: {summary['date_range'][0]} 到 {summary['date_range'][1]}")

            if summary['snow_info']['snow_days'] > 0:
                print(f"\n积雪信息:")
                print(f"  积雪天数: {summary['snow_info']['snow_days']}")
                print(f"  最大积雪深度: {summary['snow_info']['max_depth']} cm")
                print(f"  平均积雪深度: {summary['snow_info']['avg_depth']:.1f} cm")

            # 查看前几行
            print(f"\n数据前3行:")
            print(data[['datetime', 'temperature', 'precipitation', 'snow_depth']].head(3))

            # 保存清洗后的数据
            output_path = "data/hangzhou_parsed.csv"
            data.to_csv(output_path, index=False, encoding='utf-8')
            print(f"\n解析后的数据已保存到: {output_path}")

        else:
            print("解析失败或数据为空")

    except Exception as e:
        print(f"解析失败: {e}")
        import traceback
        traceback.print_exc()