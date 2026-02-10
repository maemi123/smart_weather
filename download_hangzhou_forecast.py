#!/usr/bin/env python3
"""
下载杭州单点预报数据（实用版）
"""

import cdsapi
import os
from datetime import datetime, timedelta


def download_hangzhou_forecast():
    """下载杭州未来3天预报"""

    # 创建缓存目录
    os.makedirs('data/ecmwf', exist_ok=True)

    today = datetime.now().strftime('%Y-%m-%d')
    filename = f'data/ecmwf/hangzhou_forecast_{today}.grib'

    if os.path.exists(filename):
        print(f"📁 使用缓存文件: {filename}")
        return filename

    print("🌍 下载杭州单点预报数据...")
    print("⏳ 这可能需要几分钟...")

    try:
        c = cdsapi.Client(timeout=300)

        # 下载未来3天的单点数据
        # 注意：ERA5是再分析数据，我们用它模拟预报数据
        c.retrieve(
            'reanalysis-era5-single-levels',
            {
                'product_type': 'reanalysis',
                'variable': [
                    '2m_temperature',  # 温度
                    'total_precipitation',  # 总降水
                    'mean_sea_level_pressure',  # 海平面气压
                    '10m_u_component_of_wind',  # 10米U风
                    '10m_v_component_of_wind',  # 10米V风
                ],
                'year': '2024',
                'month': '01',
                'day': ['01', '02', '03'],  # 3天
                'time': [
                    '00:00', '06:00', '12:00', '18:00',  # 每天4个时次
                ],
                'area': [30.3, 120.2, 30.2, 120.3],  # 杭州单点（很小区域）
                'format': 'grib',
            },
            filename
        )

        if os.path.exists(filename):
            size = os.path.getsize(filename)
            print(f"✅ 下载完成: {filename} ({size:,} bytes)")
            return filename
        else:
            print("❌ 文件未创建")
            return None

    except Exception as e:
        print(f"❌ 下载失败: {e}")
        print("💡 使用模拟数据进行开发")
        return None


if __name__ == "__main__":
    result = download_hangzhou_forecast()

    if result:
        # 测试读取
        try:
            import xarray as xr

            ds = xr.open_dataset(result, engine='cfgrib')
            print(f"\n📊 数据信息:")
            print(f"   变量: {list(ds.data_vars)}")
            print(f"   时间维度: {ds.sizes.get('time', 0)} 个时次")
            print(f"   数据时间: {ds.time.values[:3] if 'time' in ds else 'N/A'}")
            ds.close()
        except Exception as e:
            print(f"读取失败: {e}")
    else:
        print("使用模拟数据继续开发")