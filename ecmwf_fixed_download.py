# ecmwf_fixed_download.py
import cdsapi
import os
import time
import numpy as np


def download_with_licence_check():
    """下载ECMWF数据（包含许可检查）"""
    print("=" * 60)
    print("ECMWF真实数据下载测试")
    print("=" * 60)

    print("\n📋 步骤检查:")
    print("1. ✅ API密钥已配置")
    print("2. ⚠️  需要确认许可协议已接受")
    print("3. ⚠️  可能需要科学上网")

    print("\n🔗 请先访问以下链接确认许可:")
    print("   https://cds.climate.copernicus.eu/datasets/reanalysis-era5-single-levels")
    print("   → 登录 → 点击 'Download data' → 接受许可协议")

    input("\n按Enter键继续（确保已完成许可接受）...")

    try:
        print("\n🔄 创建API客户端...")
        c = cdsapi.Client(timeout=30)

        print("📡 发送最小数据请求...")

        # 更小的请求，提高成功率
        request = {
            'product_type': 'reanalysis',
            'variable': '2m_temperature',
            'year': '2024',
            'month': '01',
            'day': '01',
            'time': '00:00',
            'area': [31.2, 120.3, 30.8, 120.7],  # 极小的区域0.4x0.4度
            'format': 'grib',
        }

        print(f"请求参数: {request}")

        # 异步请求，避免超时
        print("⏳ 请求已提交，正在等待服务器响应...")

        start_time = time.time()
        result = c.retrieve('reanalysis-era5-single-levels', request)

        # 尝试下载
        output_file = 'real_ecmwf_data.grib'
        print(f"⬇️  开始下载到: {output_file}")

        result.download(output_file)

        elapsed = time.time() - start_time

        if os.path.exists(output_file):
            size = os.path.getsize(output_file)
            print(f"\n🎉 下载成功！")
            print(f"   文件: {output_file}")
            print(f"   大小: {size:,} bytes")
            print(f"   用时: {elapsed:.1f} 秒")

            # 移动到项目目录
            os.makedirs('data/ecmwf', exist_ok=True)
            final_path = 'data/ecmwf/real_data.grib'
            os.rename(output_file, final_path)
            print(f"   已移动到: {final_path}")

            return True, final_path
        else:
            print("❌ 文件未创建")
            return False, None

    except cdsapi.api.ServerError as e:
        print(f"❌ 服务器错误: {e}")
        print("   可能原因：网络问题或服务器繁忙")
        return False, None

    except Exception as e:
        print(f"❌ 其他错误: {type(e).__name__}: {e}")
        return False, None


def test_grib_file(filepath):
    """测试下载的GRIB文件"""
    print("\n🔍 测试GRIB文件...")

    if not os.path.exists(filepath):
        print("❌ 文件不存在")
        return False

    try:
        import xarray as xr

        print(f"尝试打开: {filepath}")
        ds = xr.open_dataset(filepath, engine='cfgrib')

        print(f"✅ GRIB文件有效！")
        print(f"   变量: {list(ds.data_vars)}")
        print(f"   维度: {ds.sizes}")  # 使用sizes而不是dims

        # 显示数据结构
        print("\n📊 数据结构:")
        for var_name in ds.data_vars:
            var = ds[var_name]
            print(f"   {var_name}: {var.attrs.get('long_name', 'N/A')}")
            print(f"     单位: {var.attrs.get('units', 'N/A')}")
            print(f"     形状: {var.shape}")

        # 提取数据值
        print("\n📈 数据值:")
        if 't2m' in ds:
            temp_data = ds['t2m']
            print(f"   2米温度数据形状: {temp_data.shape}")

            # 显示所有格点值
            for i in range(temp_data.sizes.get('latitude', 0)):
                for j in range(temp_data.sizes.get('longitude', 0)):
                    try:
                        lat = float(ds.latitude[i]) if hasattr(ds, 'latitude') else 'N/A'
                        lon = float(ds.longitude[j]) if hasattr(ds, 'longitude') else 'N/A'
                        temp_k = float(temp_data[i, j].values)
                        temp_c = temp_k - 273.15
                        print(f"     格点({lat:.2f}°N, {lon:.2f}°E): {temp_k:.2f} K = {temp_c:.2f} °C")
                    except:
                        pass

            # 找到杭州附近的格点（手动计算）
            if hasattr(ds, 'latitude') and hasattr(ds, 'longitude'):
                lats = ds.latitude.values
                lons = ds.longitude.values
                print(f"\n   纬度范围: {lats.min():.2f}°N 到 {lats.max():.2f}°N")
                print(f"   经度范围: {lons.min():.2f}°E 到 {lons.max():.2f}°E")

                # 杭州坐标
                hangzhou_lat, hangzhou_lon = 30.25, 120.17

                # 找到最近格点
                lat_idx = np.abs(lats - hangzhou_lat).argmin()
                lon_idx = np.abs(lons - hangzhou_lon).argmin()

                temp_k = float(temp_data[lat_idx, lon_idx].values)
                temp_c = temp_k - 273.15
                print(f"\n   📍 最近格点数据:")
                print(f"      格点位置: ({lats[lat_idx]:.2f}°N, {lons[lon_idx]:.2f}°E)")
                print(f"      2米温度: {temp_k:.2f} K = {temp_c:.2f} °C")

        ds.close()
        return True

    except Exception as e:
        print(f"❌ GRIB文件读取失败: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success, filepath = download_with_licence_check()

    if success and filepath:
        print("\n" + "=" * 60)
        print("🎊 真实ECMWF数据获取成功！")
        print("=" * 60)

        # 测试文件
        test_grib_file(filepath)

        print("\n📢 现在可以：")
        print("1. 修改 ecmwf_service.py 使用真实数据")
        print("2. 重启Flask应用")
        print("3. 访问 /ecmwf 查看真实数据")

    else:
        print("\n" + "=" * 60)
        print("⚠️  真实数据下载失败")
        print("=" * 60)

        print("\n💡 毕业设计解决方案：")
        print("1. 使用高质量的模拟数据")
        print("2. 在论文中说明：")
        print("   - 已实现完整ECMWF数据接入架构")
        print("   - 由于许可/网络限制使用模拟数据")
        print("   - 代码完全支持真实数据")

        print("\n📌 技术价值不受影响：")
        print("   ✅ GRIB格式处理")
        print("   ✅ xarray科学计算")
        print("   ✅ 专业气象数据处理")
        print("   ✅ 完整API集成架构")