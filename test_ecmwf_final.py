#!/usr/bin/env python3
"""
ECMWF API最终测试（适配新API）
"""

import os
import sys
from pathlib import Path

print("=== ECMWF API 连接测试（新版本） ===\n")

# 检查配置文件
config_path = Path.home() / '.cdsapirc'
print("1. 检查配置文件...")
if config_path.exists():
    with open(config_path, 'r') as f:
        content = f.read()
    print(f"   ✅ 配置文件内容:")
    for line in content.strip().split('\n'):
        if 'key' in line:
            print(f"      🔑 {line.split(':')[0]}: {'*' * 20}")
        else:
            print(f"      🌐 {line}")
else:
    print("   ❌ 配置文件不存在")
    sys.exit(1)

# 测试连接
print("\n2. 测试API连接...")
try:
    import cdsapi

    print(f"   📦 cdsapi版本: {cdsapi.__version__}")

    # 创建客户端
    client = cdsapi.Client()
    print("   ✅ 客户端创建成功")

    # 测试最小请求
    print("\n3. 发送测试请求...")

    # 使用新版API的请求格式
    test_request = {
        'product_type': 'reanalysis',
        'variable': '2m_temperature',
        'year': '2024',
        'month': '01',
        'day': '01',
        'time': '12:00',
        'area': [31, 120, 30, 121],  # 杭州小区域
        'format': 'grib',
    }

    print(f"   请求参数: {test_request}")

    # 发送请求（不下载）
    print("   正在发送请求...")
    result = client.retrieve('reanalysis-era5-single-levels', test_request)

    print(f"   ✅ 请求成功!")
    print(f"   请求ID: {result.reply.get('request_id', 'N/A')}")
    print(f"   状态: {result.reply.get('state', 'N/A')}")

    # 可选下载
    print("\n4. 下载测试数据（约1MB）...")
    download_choice = input("   是否下载？(y/n): ").strip().lower()

    if download_choice == 'y':
        test_file = 'test_data.grib'
        print(f"   下载到: {test_file}")

        try:
            result.download(test_file)

            if os.path.exists(test_file):
                size = os.path.getsize(test_file)
                print(f"   ✅ 下载成功! 大小: {size:,} bytes")

                # 验证文件
                if size > 1000:  # 至少1KB
                    print(f"   📊 文件有效，可以用于演示")

                    # 移动到缓存目录
                    cache_dir = 'data/ecmwf'
                    os.makedirs(cache_dir, exist_ok=True)
                    final_path = os.path.join(cache_dir, 'real_demo.grib')
                    os.rename(test_file, final_path)
                    print(f"   📁 已移动到: {final_path}")

                    print("\n🎉 恭喜！真实ECMWF数据获取成功！")
                    print("   重启Flask应用查看真实数据")
                else:
                    print("   ⚠️ 文件太小，可能有问题")
                    os.remove(test_file)
            else:
                print("   ❌ 文件未创建")

        except Exception as e:
            print(f"   ❌ 下载失败: {e}")
    else:
        print("   ⏭️ 跳过下载")

    print("\n✅ API测试完成！")

except Exception as e:
    print(f"   ❌ 测试失败: {type(e).__name__}: {e}")
   