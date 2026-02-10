import cdsapi
import xarray as xr
import pandas as pd
import os
from datetime import datetime, timedelta


class ECMWFService1:
    def __init__(self):
        self.client = cdsapi.Client()
        self.cache_dir = 'data/ecmwf'
        os.makedirs(self.cache_dir, exist_ok=True)

    def download_era5_daily(self, year=2024, month=1, variables=['2m_temperature']):
        """下载ERA5日平均数据（用于历史分析）"""
        import cdsapi
        import os

        filename = f"{self.cache_dir}/era5_{year}_{month}.grib"

        if os.path.exists(filename):
            print(f"使用缓存文件: {filename}")
            return filename

        print(f"开始下载真实ERA5数据: {year}-{month}")

        try:
            # 初始化客户端
            c = cdsapi.Client()

            # 真实的API请求
            c.retrieve(
                'reanalysis-era5-single-levels',
                {
                    'product_type': 'reanalysis',
                    'variable': variables,
                    'year': str(year),
                    'month': f'{month:02d}',
                    'day': ['01', '02', '03', '04', '05'],  # 先下载5天测试
                    'time': ['00:00', '06:00', '12:00', '18:00'],
                    'area': [32, 118, 28, 122],  # 杭州区域 [北纬, 西经, 南纬, 东经]
                    'format': 'grib',
                },
                filename
            )
            print(f"✅ 真实数据下载完成: {filename}")
            return filename
        except Exception as e:
            print(f"❌ 真实数据下载失败: {e}")
            print("可能的原因：")
            print("1. API配置不正确，检查.cdsapirc文件格式")
            print("2. 网络连接问题")
            print("3. 配额限制")
            return None

    def get_real_time_forecast(self):
        """获取实时预报数据（简化版）"""
        import cdsapi
        from datetime import datetime, timedelta

        today = datetime.now().strftime('%Y-%m-%d')
        filename = f"{self.cache_dir}/forecast_{today}.grib"

        if os.path.exists(filename):
            return filename

        try:
            c = cdsapi.Client()

            # 下载最近的分析数据作为"预报"演示
            c.retrieve(
                'reanalysis-era5-single-levels',
                {
                    'product_type': 'reanalysis',
                    'variable': ['2m_temperature', 'total_precipitation'],
                    'date': today,
                    'time': '00:00',
                    'area': [32, 118, 28, 122],
                    'format': 'grib',
                },
                filename
            )
            return filename
        except Exception as e:
            print(f"预报数据获取失败: {e}")
            return None

    def download_hres_forecast(self, forecast_date=None):
        """下载HRES高分辨率预报数据"""
        if forecast_date is None:
            forecast_date = datetime.now().strftime('%Y-%m-%d')

        filename = f"{self.cache_dir}/hres_{forecast_date}.grib"

        if os.path.exists(filename):
            print(f"使用缓存文件: {filename}")
            return filename

        print(f"开始下载HRES预报数据: {forecast_date}")

        # 注意：HRES数据可能需要不同的数据集名称
        # 实际使用时需要查询最新文档
        try:
            self.client.retrieve(
                'reanalysis-era5-single-levels',  # 先用ERA5测试
                {
                    'product_type': 'forecast',
                    'variable': ['2m_temperature', 'total_precipitation'],
                    'date': forecast_date,
                    'time': '00:00',
                    'area': [32, 118, 28, 122],
                    'format': 'grib',
                },
                filename
            )
            return filename
        except Exception as e:
            print(f"HRES下载失败，降级使用模拟数据: {e}")
            return self.create_mock_ecmwf_data()

    def read_grib_data(self, filepath):
        """读取GRIB文件"""
        try:
            # 尝试用cfgrib打开
            ds = xr.open_dataset(filepath, engine='cfgrib')
            print(f"成功读取GRIB文件，变量: {list(ds.data_vars)}")
            return ds
        except Exception as e:
            print(f"读取GRIB失败: {e}")
            return None

    def extract_hangzhou_data(self, ds):
        """从数据集中提取杭州的数据"""
        if ds is None:
            return None

        result = {}

        for var_name in ds.data_vars:
            var_data = ds[var_name]
            print(f"处理变量 {var_name}, 维度: {var_data.dims}")

            if 'time' in var_data.dims:
                # 简化提取逻辑
                if var_name == 't2m':
                    # 温度从开尔文转摄氏度
                    values_k = var_data.values
                    values_c = values_k - 273.15
                    result[var_name] = {
                        'values': values_c.tolist(),
                        'times': var_data.time.values.tolist(),
                        'units': '°C',
                        'name': '2米温度'
                    }
                else:
                    result[var_name] = {
                        'values': var_data.values.tolist(),
                        'times': var_data.time.values.tolist(),
                        'units': var_data.attrs.get('units', 'unknown'),
                        'name': var_data.attrs.get('long_name', var_name)
                    }

        return result

    def create_mock_ecmwf_data(self):
        """创建模拟的ECMWF数据（用于测试）"""
        print("生成模拟ECMWF数据...")
        import numpy as np

        # 创建模拟数据集 - 简化版本
        times = pd.date_range('2024-06-01', periods=6, freq='h')  # 改为小写'h'

        # 创建xarray数据集 - 简化结构
        ds = xr.Dataset(
            {
                't2m': (
                ['time'], np.array([290, 291, 292, 293, 292, 291]), {'units': 'K', 'long_name': '2 metre temperature'}),
                'tp': (
                ['time'], np.array([0, 0, 0.5, 1.2, 0.3, 0]), {'units': 'm', 'long_name': 'Total precipitation'}),
            },
            coords={
                'time': times,
                'latitude': xr.DataArray([30.25], dims=['latitude']),
                'longitude': xr.DataArray([120.17], dims=['longitude']),
            }
        )

        print(f"模拟数据创建成功，维度: {dict(ds.dims)}")
        return ds

    def test_api_connection(self):
        """测试API连接"""
        try:
            import cdsapi
            client = cdsapi.Client()

            # 测试一个极小的请求
            test_params = {
                'product_type': 'reanalysis',
                'variable': '2m_temperature',
                'year': '2024',
                'month': '01',
                'day': '01',
                'time': '00:00',
                'area': [31, 120, 30, 121],  # 1x1度的小区域
                'format': 'grib',
            }

            print("测试ECMWF API连接...")
            result = client.retrieve('reanalysis-era5-single-levels', test_params)

            if result.reply.get('state') == 'completed':
                print("✅ API连接测试成功")
                return True
            else:
                print(f"⚠️ API响应异常: {result.reply}")
                return False

        except Exception as e:
            # 修复Unicode错误：使用ASCII字符
            print(f"[ERROR] API连接失败: {e}")
            return False

    def get_demo_real_data(self):
        """获取演示用的真实数据（小文件）"""
        try:
            import cdsapi
            import os

            filename = f"{self.cache_dir}/demo_real_data.grib"

            if os.path.exists(filename):
                return filename

            print("正在下载演示数据...")
            c = cdsapi.Client()

            # 下载一个非常小的文件用于演示
            c.retrieve(
                'reanalysis-era5-single-levels',
                {
                    'product_type': 'reanalysis',
                    'variable': '2m_temperature',
                    'year': '2024',
                    'month': '01',
                    'day': ['01', '02'],  # 只下2天
                    'time': ['00:00', '12:00'],  # 只下2个时次
                    'area': [31, 120, 30, 121],  # 1x1度小区域
                    'format': 'grib',
                },
                filename
            )

            if os.path.exists(filename):
                print(f"✅ 演示数据下载完成: {filename}")
                return filename
            else:
                print("❌ 演示数据下载失败")
                return None

        except Exception as e:
            print(f"❌ 真实数据获取失败: {e}")
            return None


# 测试代码
if __name__ == "__main__":
    service = ECMWFService()

    # 测试1：下载ERA5数据
    print("\n=== 测试1: 下载ERA5数据 ===")
    era5_file = service.download_era5_daily(year=2023, month=7, variables=['2m_temperature'])

    if era5_file:
        ds = service.read_grib_data(era5_file)
        if ds is not None:
            hangzhou_data = service.extract_hangzhou_data(ds)
            print(f"杭州数据提取成功: {list(hangzhou_data.keys())}")

    # 测试2：使用模拟数据
    print("\n=== 测试2: 模拟数据测试 ===")
    mock_ds = service.create_mock_ecmwf_data()
    print(f"模拟数据集: {mock_ds}")