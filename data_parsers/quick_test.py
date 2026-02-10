def quick_test():
    """快速测试修改后的解析器"""
    from rp5_parser import RP5Parser  # 假设你的文件名为 rp5_parser.py

    parser = RP5Parser("data/hangzhou_weather.csv")

    # 测试日期解析
    test_dates = [
        "29.12.2025 23:00",
        "28.12.2025 23:00",
        "01.01.2020 00:00"
    ]

    print("测试日期解析:")
    for dt_str in test_dates:
        result = parser._parse_datetime(dt_str)
        print(f"  {dt_str} -> {result}")

    # 测试数值解析
    test_values = [
        "9.9",
        "无降水",
        "2500或更高，或无云。",
        "0.8",
        ""
    ]

    print("\n测试数值解析:")
    for val in test_values:
        result = parser._parse_numeric(val)
        print(f"  '{val}' -> {result}")

    # 测试风向解析
    test_winds = [
        "从北方吹来的风",
        "从西北偏北方向吹来的风",
        "从东南偏东方向吹来的风"
    ]

    print("\n测试风向解析:")
    for wind in test_winds:
        result = parser._parse_wind_direction(wind)
        print(f"  '{wind}' -> {result}")


if __name__ == "__main__":
    quick_test()