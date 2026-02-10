def inspect_precipitation_raw():
    """直接查看原始降水数据"""
    import pandas as pd

    # 读取2025年7月18日附近的数据
    df = pd.read_csv(
        "data/hangzhou_weather.csv",
        encoding='utf-8',
        delimiter=';',
        index_col=0
    )

    df = df.reset_index()
    df['datetime'] = pd.to_datetime(df['index'], format='%d.%m.%Y %H:%M', errors='coerce')

    # 筛选2025年7月18日
    target_date = pd.Timestamp('2025-07-18')
    mask = (df['datetime'] >= target_date) & (df['datetime'] < target_date + pd.Timedelta(days=1))
    day_data = df[mask].copy()

    print(f"2025年7月18日数据 ({len(day_data)}条记录)")
    print("=" * 80)

    # 显示所有列的值
    for idx, row in day_data.iterrows():
        print(f"\n时间: {row['datetime']}")
        print(f"  RRR(降水): '{row['RRR']}'")
        print(f"  tR(时段): '{row['tR']}'")
        print(f"  WW(天气): '{row['WW']}'")
        print(f"  T(温度): '{row['T']}'")

    # 检查降水列的值
    print(f"\nRRR列所有值:")
    rrr_values = day_data['RRR'].unique()
    for val in rrr_values:
        count = (day_data['RRR'] == val).sum()
        print(f"  '{val}': {count}次")

    print(f"\ntR列所有值:")
    tr_values = day_data['tR'].unique()
    for val in tr_values:
        count = (day_data['tR'] == val).sum()
        print(f"  '{val}': {count}次")


if __name__ == "__main__":
    inspect_precipitation_raw()