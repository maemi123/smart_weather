#!/usr/bin/env python3
"""
测试ECMWF API连接
"""

import os
import sys
from pathlib import Path

# 检查配置文件
config_path = Path.home() / '.cdsapirc'
print(f"🔍 检查配置文件: {config_path}")

if config_path.exists():
    with open(config_path, 'r') as f:
        content = f.read()
    print(f"✅ 配置文件存在")
    print(f"内容（隐藏密钥）: {content[:50]}...")
else:
    print("❌ 配置文件不存在！")
    print("请创建 ~/.cdsapirc 文件")
    sys.exit(1)

# 尝试导入CDS API
try:
    import cdsapi

    print("✅ cdsapi 库已安装")

    # 测试连接
    print("🔄 测试API连接...")
    client = cdsapi.Client()

    # 尝试一个很小的请求
    test_request = {
        'product_type': 'reanalysis',
        'variable': '2m_temperature',
        'year': '2024',
        'month': '01',
        'day': '01',
        'time': '00:00',
        'area': [31, 120, 30, 121],  # 很小的杭州区域
        'format': 'grib',
    }

    print("正在发送测试请求...")

    # 使用try-except捕获具体错误
    try:
        result = client.retrieve('reanalysis-era5-single-levels', test_request)
        print("✅ API连接成功！")
        print(f"请求ID: {result.reply['request_id']}")

        # 尝试下载一个小文件
        test_file = 'test_data.grib'
        result.download(test_file)

        if os.path.exists(test_file):
            print(f"✅ 数据下载成功: {test_file} ({os.path.getsize(test_file)} bytes)")
            os.remove(test_file)  # 清理测试文件
        else:
            print("❌ 文件下载失败")

    except cdsapi.api.ClientException as e:
        print(f"❌ API请求错误: {e}")
    except Exception as e:
        print(f"❌ 其他错误: {type(e).__name__}: {e}")

except ImportError:
    print("❌ cdsapi 库未安装")
    print("运行: pip install cdsapi")
except Exception as e:
    print(f"❌ 连接测试失败: {e}")

print("\n📋 诊断信息:")
print(f"Python版本: {sys.version}")
print(f"当前目录: {os.getcwd()}")
print(f"用户目录: {Path.home()}")

# 检查必要库
libs = ['xarray', 'cfgrib', 'netCDF4']
for lib in libs:
    try:
        __import__(lib)
        print(f"✅ {lib} 已安装")
    except ImportError:
        print(f"❌ {lib} 未安装")