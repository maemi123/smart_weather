"""
测试RP5数据解析
"""
import sys
import os

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from history_analyzer import HistoryAnalyzer

def main():
    print("测试RP5数据解析器")
    print("=" * 60)

    # 创建分析器实例
    analyzer = HistoryAnalyzer(data_path="data/hangzhou_weather.csv")

    # 尝试加载数据
    data = analyzer.load_data()

    if data is not None:
        print(f"\n✅ 数据加载完成")
        print(f"数据形状: {data.shape}")
        print(f"数据列: {data.columns.tolist()}")

        # 显示数据类型信息
        print(f"\n数据类型:")
        print(data.dtypes)

        # 显示前几行 - 根据实际列名调整
        print(f"\n前3行数据:")
        if 'datetime' in data.columns:
            display_cols = ['datetime', 'temperature', 'precipitation', 'snow_depth']
        else:
            # 如果是模拟数据，使用模拟数据的列名
            display_cols = data.columns[:4].tolist()

        available_cols = [col for col in display_cols if col in data.columns]
        if available_cols:
            print(data[available_cols].head(3))
        else:
            print("没有找到要显示的列")

        # 测试年度分析
        years = analyzer.get_available_years()
        print(f"\n可用年份: {years}")

        if years:
            test_year = years[-1]  # 测试最近一年
            print(f"\n测试分析 {test_year} 年:")

            try:
                result = analyzer.analyze_year(test_year)

                print(f"平均温度: {result['stats'].get('avg_temp', 'N/A')}°C")
                print(f"总降水量: {result['stats'].get('total_precip', 'N/A')}mm")
                print(f"积雪日数: {result['stats'].get('snow_days', 'N/A')}天")

                if result.get('extremes'):
                    print("\n极端事件:")
                    for event in result['extremes']:
                        print(f"  {event.get('rank', '?')}. {event.get('type', '未知')} - {event.get('date', '未知日期')} ({event.get('value', '未知值')})")
                else:
                    print("\n没有检测到极端事件")

            except Exception as e:
                print(f"分析年份时出错: {e}")
                import traceback
                traceback.print_exc()

    else:
        print("❌ 数据加载失败")

if __name__ == "__main__":
    main()