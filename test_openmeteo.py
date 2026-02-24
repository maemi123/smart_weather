import requests
import json
from datetime import datetime, timedelta


def test_openmeteo_api():
    """测试Open-Meteo API能获取多少天数据"""

    base_url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": 30.25,  # 杭州
        "longitude": 120.17,
        "hourly": "temperature_2m",
        "timezone": "Asia/Shanghai"
    }

    print("🔍 测试Open-Meteo API数据限制")
    print("=" * 60)

    # 测试不同的天数
    test_days = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]

    for days in test_days:
        test_params = params.copy()
        test_params["forecast_days"] = days

        print(f"\n测试获取 {days} 天数据...")
        print(f"请求参数: forecast_days={days}")

        try:
            response = requests.get(base_url, params=test_params, timeout=10)

            if response.status_code == 200:
                data = response.json()

                # 分析返回的数据
                hourly_data = data.get("hourly", {})
                timestamps = hourly_data.get("time", [])
                temperatures = hourly_data.get("temperature_2m", [])

                print(f"✅ 请求成功")
                print(f"   返回时间点数量: {len(timestamps)}")
                print(f"   返回温度值数量: {len(temperatures)}")

                if timestamps:
                    print(f"   时间范围: {timestamps[0]} 到 {timestamps[-1]}")

                    # 计算实际天数
                    if len(timestamps) >= 2:
                        first_time = datetime.fromisoformat(timestamps[0].replace('Z', '+00:00'))
                        last_time = datetime.fromisoformat(timestamps[-1].replace('Z', '+00:00'))
                        hours_diff = (last_time - first_time).total_seconds() / 3600
                        actual_days = hours_diff / 24
                        print(f"   实际覆盖天数: {actual_days:.1f} 天 ({hours_diff:.0f} 小时)")

                # 检查是否有缺失数据
                if temperatures:
                    null_count = temperatures.count(None)
                    print(f"   空值数量: {null_count}")

            elif response.status_code == 400:
                print(f"❌ 请求失败 (400 Bad Request)")
                error_data = response.json()
                print(f"   错误信息: {json.dumps(error_data, ensure_ascii=False)}")

                # 检查是否是天数限制
                if "reason" in error_data:
                    print(f"   限制原因: {error_data['reason']}")

            else:
                print(f"❌ 请求失败: HTTP {response.status_code}")
                print(f"   响应: {response.text[:200]}...")

        except Exception as e:
            print(f"❌ 请求异常: {str(e)}")

    print("\n" + "=" * 60)
    print("📊 API限制测试总结")
    print("=" * 60)

    # 测试不同模型的限制
    print("\n🔬 测试不同模型的限制:")
    models_to_test = ["best_match", "ecmwf_ifs", "gfs_seamless", "gem_global", "icon_global"]

    for model in models_to_test:
        print(f"\n测试模型: {model}")
        test_params = params.copy()
        test_params["forecast_days"] = 7
        test_params["models"] = model

        try:
            response = requests.get(base_url, params=test_params, timeout=10)

            if response.status_code == 200:
                data = response.json()
                timestamps = data.get("hourly", {}).get("time", [])
                print(f"  ✅ 支持7天，返回 {len(timestamps)} 个时间点")
            elif response.status_code == 400:
                error_data = response.json()
                print(f"  ❌ 不支持7天: {error_data.get('reason', '未知错误')}")
            else:
                print(f"  ❌ 请求失败: HTTP {response.status_code}")

        except Exception as e:
            print(f"  ❌ 测试异常: {str(e)}")

    print("\n" + "=" * 60)

    # 测试历史数据（如果可以的话）
    print("\n📅 测试历史数据获取:")

    today = datetime.now()
    past_date = (today - timedelta(days=1)).strftime("%Y-%m-%d")

    history_params = params.copy()
    history_params["forecast_days"] = 1
    history_params["past_days"] = 2  # 尝试获取过去2天

    try:
        response = requests.get(base_url, params=history_params, timeout=10)

        if response.status_code == 200:
            data = response.json()
            timestamps = data.get("hourly", {}).get("time", [])
            print(f"✅ 可以获取历史数据")
            print(f"   总时间点数量: {len(timestamps)}")
            if timestamps:
                print(f"   时间范围: {timestamps[0]} 到 {timestamps[-1]}")
        else:
            print(f"❌ 无法获取历史数据: HTTP {response.status_code}")

    except Exception as e:
        print(f"❌ 历史数据测试异常: {str(e)}")


def test_alternative_api():
    """测试备用API（心知天气）"""
    print("\n" + "=" * 60)
    print("🌐 测试备用API: 心知天气")
    print("=" * 60)

    # 心知天气API
    api_key = "1"  # 你的心知天气API Key
    url = "https://api.seniverse.com/v3/weather/daily.json"

    params = {
        "key": api_key,
        "location": "hangzhou",
        "language": "zh-Hans",
        "unit": "c",
        "start": 0,
        "days": 10  # 尝试获取10天
    }

    try:
        print(f"\n请求心知天气 {params['days']} 天数据...")
        response = requests.get(url, params=params, timeout=10)

        if response.status_code == 200:
            data = response.json()
            results = data.get("results", [])

            if results:
                daily_data = results[0].get("daily", [])
                print(f"✅ 请求成功")
                print(f"   返回天数: {len(daily_data)}")

                for i, day in enumerate(daily_data[:5]):  # 显示前5天
                    print(f"   第{i + 1}天: {day['date']} {day['text_day']} "
                          f"{day['low']}~{day['high']}°C")

                if len(daily_data) >= 7:
                    print(f"\n🎉 心知天气支持获取 {len(daily_data)} 天数据！")
                else:
                    print(f"\n⚠️ 心知天气只返回 {len(daily_data)} 天数据")
            else:
                print(f"❌ 返回数据格式异常")
                print(f"   响应: {response.text[:200]}")
        else:
            print(f"❌ 请求失败: HTTP {response.status_code}")
            print(f"   响应: {response.text[:200]}")

    except Exception as e:
        print(f"❌ 请求异常: {str(e)}")


if __name__ == "__main__":
    print("🚀 开始气象API限制测试")
    print("=" * 60)

    # 测试Open-Meteo
    test_openmeteo_api()

    # 测试心知天气
    test_alternative_api()

    print("\n" + "=" * 60)
    print("✅ 测试完成")
    print("=" * 60)

    # 给出建议
    print("\n💡 建议:")
    print("1. 如果Open-Meteo只能获取3天，考虑使用心知天气")
    print("2. 或者组合使用：Open-Meteo获取详细小时数据 + 心知天气获取多天趋势")
    print("3. 也可以考虑其他免费API：和风天气、AccuWeather等")