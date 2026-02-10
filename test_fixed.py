"""
测试修复版RP5解析
"""
import sys
import os
import io

# 解决Windows下VS Code输出中文乱码问题
# 强制将stdout和stderr设置为utf-8编码
if sys.platform.startswith('win'):
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8')

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from history_analyzer import HistoryAnalyzer


def main():
    print("测试修复版RP5数据解析")
    print("=" * 60)

    analyzer = HistoryAnalyzer(data_path="data/hangzhou_weather.csv")

    # 强制重新加载
    data = analyzer.load_data(force_reload=True)

    if data is not None:
        print(f"\n[OK] 数据加载成功！")
        print(f"数据形状: {data.shape}")

        # 检查关键列
        key_cols = ['datetime', 'temperature', 'precipitation', 'snow_depth']
        for col in key_cols:
            if col in data.columns:
                valid = data[col].notna().sum()
                print(f"{col}: {valid} 个有效值")

        # 测试年度分析
        years = analyzer.get_available_years()
        if years:
            print(f"\n可用年份: {years}")

            # 测试最近一年
            test_year = years[-1]
            print(f"\n分析 {test_year} 年:")

            try:
                result = analyzer.analyze_year(test_year)

                print(f"平均温度: {result['stats'].get('avg_temp', 'N/A')}°C")
                print(f"总降水量: {result['stats'].get('total_precip', 'N/A')}mm")
                print(f"积雪日数: {result['stats'].get('snow_days', 'N/A')}天")

                if result.get('extremes'):
                    print("\n极端事件:")
                    for event in result['extremes']:
                        print(f"  {event['rank']}. {event['type']} - {event['date']} ({event['value']})")

            except Exception as e:
                print(f"分析出错: {e}")
                import traceback
                traceback.print_exc()


if __name__ == "__main__":
    main()