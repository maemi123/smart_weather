import requests
import re
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import json


class SoundingDataParser:
    """怀俄明大学探空数据解析器（新版wsgi API）"""

    def __init__(self):
        self.base_url = "http://weather.uwyo.edu/wsgi/sounding"

    def fetch_sounding_data(self,
                            station_id: str = "58457",
                            target_time: Optional[datetime] = None,
                            data_type: str = "TEXT:LIST") -> Dict:
        """
        获取探空数据 (带自动回退机制)
        """
        # 如果没有指定时间，使用最近的有效时次
        is_auto_time = False
        if target_time is None:
            target_time = self.get_latest_valid_time()
            is_auto_time = True

        # 内部函数：执行单次请求
        def _do_fetch(time_val):
            params = {
                "datetime": time_val.strftime("%Y-%m-%d %H:%M:%S"),
                "id": station_id,
                "src": "BUFR",
                "type": data_type
            }
            print(f"📡 获取探空数据...")
            print(f"   站点: {station_id}")
            print(f"   时间: {time_val.strftime('%Y-%m-%d %H:%M UTC')}")
            
            try:
                response = requests.get(self.base_url, params=params, timeout=15)
                if response.status_code == 200:
                    content = response.text
                    # 检查是否包含有效数据（Wyoming有时返回HTML但不包含数据）
                    if "PRES   HGHT   TEMP" in content or "Station information" in content:
                        return {"success": True, "raw_data": content, "params": params, "time": time_val}
                    else:
                        return {"success": False, "error": "未找到数据", "raw_data": content}
                return {"success": False, "error": f"HTTP {response.status_code}"}
            except Exception as e:
                return {"success": False, "error": str(e)}

        # 1. 首次尝试
        result = _do_fetch(target_time)
        
        # 2. 如果失败且时间是自动生成的，尝试回退12小时
        # 场景：现在是12:30 UTC，请求12:00 UTC数据，但Wyoming还没发布
        if not result["success"] and is_auto_time:
            print(f"⚠️  当前时次获取失败 ({result.get('error')})，尝试回退到上一时次...")
            fallback_time = target_time - timedelta(hours=12)
            result = _do_fetch(fallback_time)
            
            if result["success"]:
                print(f"✅ 回退时次获取成功: {fallback_time.strftime('%Y-%m-%d %H:%M UTC')}")
            else:
                print("❌ 回退时次也获取失败")

        # 构造最终返回
        if result["success"]:
            return {
                "success": True,
                "raw_data": result["raw_data"],
                "params": result["params"],
                "station_id": station_id,
                "time": result["time"] # 返回实际获取成功的时间
            }
        else:
            return result

    def get_latest_valid_time(self) -> datetime:
        """获取最近的有效时次（00Z或12Z）"""
        now_utc = datetime.utcnow()

        # 最近的两个标准时次
        today_00z = now_utc.replace(hour=0, minute=0, second=0, microsecond=0)
        today_12z = now_utc.replace(hour=12, minute=0, second=0, microsecond=0)

        # 选择最近的一个
        diff_00z = abs((now_utc - today_00z).total_seconds())
        diff_12z = abs((now_utc - today_12z).total_seconds())

        if diff_00z < diff_12z:
            return today_00z if today_00z <= now_utc else today_00z - timedelta(days=1)
        else:
            return today_12z if today_12z <= now_utc else today_12z - timedelta(days=1)

    def parse_sounding_data(self, raw_data: str) -> Dict:
        """
        解析探空数据文本

        返回包含层级数据和指数数据的字典
        """
        print("\n🔍 开始解析探空数据...")

        result = {
            "header": {},
            "levels": [],
            "indices": {},
            "metadata": {}
        }

        # 1. 解析头部信息
        header_info = self._parse_header(raw_data)
        result["header"] = header_info

        # 2. 解析层级数据（表格部分）
        levels_data = self._parse_levels_table(raw_data)
        result["levels"] = levels_data

        # 3. 解析指数数据
        indices_data = self._parse_indices(raw_data)
        result["indices"] = indices_data

        # 4. 计算一些额外的指数（如果原始数据中没有）
        if levels_data:
            result["metadata"]["num_levels"] = len(levels_data)
            result["metadata"]["top_pressure"] = levels_data[-1]["PRES"] if levels_data else None
            result["metadata"]["bottom_pressure"] = levels_data[0]["PRES"] if levels_data else None

            # 计算平均风
            if all(k in levels_data[0] for k in ["DRCT", "SPED"]):
                directions = [l["DRCT"] for l in levels_data if l["DRCT"] is not None]
                speeds = [l["SPED"] for l in levels_data if l["SPED"] is not None]
                if directions and speeds:
                    result["metadata"]["avg_wind_direction"] = sum(directions) / len(directions)
                    result["metadata"]["avg_wind_speed"] = sum(speeds) / len(speeds)

        print(f"✅ 解析完成: {len(levels_data)} 个层级，{len(indices_data)} 个指数")

        return result

    def _parse_header(self, raw_data: str) -> Dict:
        """解析头部信息（站点、时间、位置）"""
        header = {}

        # 站点信息
        station_match = re.search(r'Observations for Station (\d+) at (\d+) UTC (\d+) (\w+) (\d{4})', raw_data)
        if station_match:
            header["station_id"] = station_match.group(1)
            header[
                "time_utc"] = f"{station_match.group(2)}Z {station_match.group(3)} {station_match.group(4)} {station_match.group(5)}"

        # 站点名称
        name_match = re.search(r'<H3>([^<]+)</H3>', raw_data)
        if name_match:
            header["station_name"] = name_match.group(1).strip()

        # 经纬度
        latlon_match = re.search(r'Latitude:\s*([\d\.]+)\s*Longitude:\s*([\d\.]+)', raw_data)
        if latlon_match:
            header["latitude"] = float(latlon_match.group(1))
            header["longitude"] = float(latlon_match.group(2))

        return header

    def _parse_levels_table(self, raw_data: str) -> List[Dict]:
        """
        解析层级数据表格

        表格格式：
           PRES   HGHT   TEMP   DWPT   RELH   MIXR   DRCT   SPED   THTA   THTE   THTV
            hPa      m      C      C      %   g/kg    deg    m/s      K      K      K
        """
        levels = []

        # 找到表格开始位置
        table_start = raw_data.find("-----------------------------------------------------------------------------")
        if table_start == -1:
            return levels

        # 找到表格内容开始（跳过头两行分隔线）
        lines = raw_data[table_start:].split('\n')

        # 列名在第一个分隔线后的一行
        col_names = []
        data_start = 0

        for i, line in enumerate(lines):
            if "PRES" in line and "HGHT" in line and "TEMP" in line:
                # 这是列名行，下一行是单位行，再下一行开始是数据
                col_names = line.strip().split()
                data_start = i + 3  # 跳过列名行、单位行和下一个分隔线
                break

        if not col_names:
            return levels

        # 解析数据行
        for line in lines[data_start:]:
            line = line.strip()

            # 遇到空行或下一个分隔线结束
            if not line or "---" in line:
                break

            # 分割数据（固定宽度或空格分割）
            # 使用空格分割并过滤空字符串
            parts = [p for p in line.split(' ') if p]

            # 确保有足够的数据列
            if len(parts) >= len(col_names):
                level_data = {}
                for j, col in enumerate(col_names):
                    try:
                        # 尝试转换为浮点数
                        level_data[col] = float(parts[j])
                    except ValueError:
                        # 如果转换失败，保留原字符串
                        level_data[col] = parts[j] if parts[j] != '****' else None

                levels.append(level_data)

        return levels

    def _parse_indices(self, raw_data: str) -> Dict:
        """解析探空指数"""
        indices = {}

        # 常见指数的正则表达式模式
        patterns = {
            "CAPE": r'CAPE\s*=\s*([\-\d\.]+)\s*J/kg',
            "CIN": r'CIN\s*=\s*([\-\d\.]+)\s*J/kg',
            "LIFTED_INDEX": r'Lifted index\s*=\s*([\-\d\.]+)',
            "K_INDEX": r'K index\s*=\s*([\-\d\.]+)',
            "TOTAL_TOTALS": r'Total Totals\s*=\s*([\-\d\.]+)',
            "PRECIP_WATER": r'Precipitable water\s*=\s*([\-\d\.]+)',
            "LCL_HEIGHT": r'LCL height\s*=\s*([\-\d\.]+)\s*m',
            "LFC_HEIGHT": r'LFC height\s*=\s*([\-\d\.]+)\s*m',
            "EL_HEIGHT": r'EL height\s*=\s*([\-\d\.]+)\s*m',
            "SHOWALTER_INDEX": r'Showalter index\s*=\s*([\-\d\.]+)',
            "SWEAT_INDEX": r'SWEAT index\s*=\s*([\-\d\.]+)',
            "BULK_SHEAR": r'Bulk shear\s*=\s*([\-\d\.]+)\s*m/s',
            "SHEAR_06KM": r'0-6km shear\s*=\s*([\-\d\.]+)\s*m/s',
            "MEAN_WIND": r'Mean wind\s*=\s*([\d\.]+)\s* m/s',
        }

        for name, pattern in patterns.items():
            match = re.search(pattern, raw_data, re.IGNORECASE)
            if match:
                try:
                    indices[name] = float(match.group(1))
                except ValueError:
                    indices[name] = match.group(1)

        return indices

    def save_to_csv(self, parsed_data: Dict, filename: str = "sounding_data.csv"):
        """将解析的数据保存为CSV文件"""
        # 确保保存目录存在
        import os
        save_dir = "data/upperair"
        if not os.path.exists(save_dir):
            os.makedirs(save_dir)
            
        # 如果文件名不包含路径，则添加到保存目录
        if not os.path.dirname(filename):
            filename = os.path.join(save_dir, filename)
            
        if "levels" in parsed_data and parsed_data["levels"]:
            df = pd.DataFrame(parsed_data["levels"])
            df.to_csv(filename, index=False, encoding='utf-8')
            print(f"📁 层级数据保存到: {filename}")

            # 保存指数数据为JSON
            if "indices" in parsed_data and parsed_data["indices"]:
                json_filename = filename.replace(".csv", "_indices.json")
                with open(json_filename, "w", encoding="utf-8") as f:
                    json.dump(parsed_data["indices"], f, indent=2, ensure_ascii=False)
                print(f"📁 指数数据保存到: {json_filename}")

            return True
        return False

    def get_summary_report(self, parsed_data: Dict) -> str:
        """生成数据摘要报告"""
        report = []

        if "header" in parsed_data:
            header = parsed_data["header"]
            report.append("=" * 60)
            report.append("探空数据摘要")
            report.append("=" * 60)
            report.append(f"站点: {header.get('station_name', '未知')} ({header.get('station_id', '未知')})")
            report.append(f"时间: {header.get('time_utc', '未知')}")
            report.append(f"位置: 纬度 {header.get('latitude', '未知')}, 经度 {header.get('longitude', '未知')}")

        if "metadata" in parsed_data:
            meta = parsed_data["metadata"]
            report.append(f"数据层级: {meta.get('num_levels', 0)} 层")
            report.append(f"气压范围: {meta.get('bottom_pressure', '未知')} - {meta.get('top_pressure', '未知')} hPa")

        if "indices" in parsed_data and parsed_data["indices"]:
            report.append("\n探空指数:")
            indices = parsed_data["indices"]
            for name, value in indices.items():
                # 转换名称显示
                display_name = name.replace("_", " ").title()
                report.append(f"  {display_name:20} = {value}")

        if "levels" in parsed_data and parsed_data["levels"]:
            levels = parsed_data["levels"]
            if levels:
                report.append(f"\n示例数据（前3层）:")
                for i, level in enumerate(levels[:3]):
                    report.append(f"  层{i + 1}: {level}")

        return "\n".join(report)


# 测试函数
def test_full_workflow():
    """完整的工作流程测试"""
    print("=" * 60)
    print("探空数据完整获取与解析测试")
    print("=" * 60)

    # 1. 创建解析器
    parser = SoundingDataParser()

    # 2. 获取数据（使用你测试成功的参数）
    test_time = datetime(2026, 2, 5, 12, 0, 0)  # 使用已知有效的时间
    fetch_result = parser.fetch_sounding_data(
        station_id="58457",
        target_time=test_time,
        data_type="TEXT:LIST"
    )

    if not fetch_result["success"]:
        print("❌ 数据获取失败")
        return

    # 3. 解析数据
    parsed_data = parser.parse_sounding_data(fetch_result["raw_data"])

    # 4. 显示摘要
    report = parser.get_summary_report(parsed_data)
    print(report)

    # 5. 保存数据
    parser.save_to_csv(parsed_data, "sounding_test_output.csv")

    # 6. 显示详细数据
    print("\n" + "=" * 60)
    print("详细数据验证")
    print("=" * 60)

    if parsed_data.get("levels"):
        print(f"总层级数: {len(parsed_data['levels'])}")
        print("\n前5层数据:")
        for i, level in enumerate(parsed_data["levels"][:5]):
            print(f" [{i + 1}] PRES: {level.get('PRES', 'N/A'):7.1f} hPa | "
                  f"HGHT: {level.get('HGHT', 'N/A'):6.0f} m | "
                  f"TEMP: {level.get('TEMP', 'N/A'):5.1f} °C | "
                  f"DWPT: {level.get('DWPT', 'N/A'):5.1f} °C | "
                  f"RELH: {level.get('RELH', 'N/A'):3.0f}%")

    print("\n" + "=" * 60)
    print("✅ 测试完成！")
    print("=" * 60)
    print("下一步:")
    print("1. 可以基于这个解析器开发实时探空数据获取")
    print("2. 将数据用于AI强对流分析")
    print("3. 或者用于绘制探空图")


if __name__ == "__main__":
    # 运行完整测试
    test_full_workflow()

    # 也可以单独测试某些功能
    # parser = SoundingDataParser()
    # result = parser.fetch_sounding_data()
    # if result["success"]:
    #     parsed = parser.parse_sounding_data(result["raw_data"])
    #     print(parser.get_summary_report(parsed))