#!/usr/bin/env python3
"""
诊断真实ECMWF GRIB文件结构
"""

import xarray as xr
import os

filepath = 'data/ecmwf/real_data.grib'

print(f"📂 诊断文件: {filepath}")
print(f"📊 文件大小: {os.path.getsize(filepath):,} bytes")

try:
    # 用不同方式尝试打开
    print("\n1. 尝试用cfgrib打开...")
    ds = xr.open_dataset(filepath, engine='cfgrib')
    print(f"   ✅ 成功打开")
    print(f"   数据集类型: {type(ds)}")
    print(f"   变量: {list(ds.data_vars)}")

    # 详细检查每个变量
    for var_name in ds.data_vars:
        var = ds[var_name]
        print(f"\n   🔍 变量 '{var_name}':")
        print(f"      形状: {var.shape}")
        print(f"      维度: {var.dims}")
        print(f"      属性: {var.attrs}")

        # 尝试访问数据
        try:
            print(f"      数据类型: {var.dtype}")
            print(f"      数据示例: {var.values.flatten()[:3]}...")
        except:
            print(f"      数据访问失败")

    # 检查坐标
    print(f"\n2. 坐标系统:")
    for coord_name in ds.coords:
        coord = ds[coord_name]
        print(f"   {coord_name}: {coord.values} (shape: {coord.shape})")

    # 检查全局属性
    print(f"\n3. 全局属性:")
    for key, value in ds.attrs.items():
        print(f"   {key}: {value}")

    ds.close()

except Exception as e:
    print(f"❌ cfgrib打开失败: {e}")

    # 尝试用其他方式
    try:
        print("\n尝试用gribapi打开...")
        import cfgrib

        ds_list = cfgrib.open_datasets(filepath)
        print(f"   找到 {len(ds_list)} 个数据集")
        for i, ds in enumerate(ds_list):
            print(f"   数据集 {i}: {list(ds.data_vars)}")
    except Exception as e2:
        print(f"❌ 其他方式也失败: {e2}")

print("\n" + "=" * 60)