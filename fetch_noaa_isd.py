import requests
import pandas as pd
import io
import os
from datetime import datetime
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

def get_session():
    """创建一个带有重试机制的 Session"""
    session = requests.Session()
    retry = Retry(
        total=5,  # 总重试次数
        backoff_factor=1,  # 重试间隔: 1s, 2s, 4s...
        status_forcelist=[500, 502, 503, 504],
        allowed_methods=["GET"]
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session

def fetch_iem_asos_history(year, station_code="ZSHC", output_file=None):
    """
    [推荐] 从 Iowa State University (IEM) 获取 ASOS/METAR 历史数据。
    这也是基于气象站实况数据的，来源于 METAR 报文，且下载速度通常比 NOAA 更快更稳。
    
    参数:
    - year: 年份 (例如 2024)
    - station_code: ICAO代码，杭州萧山为 "ZSHC"
    """
    # IEM ASOS 下载接口
    base_url = "https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py"
    
    # 构造起止时间
    start_date = f"{year}-01-01"
    end_date = f"{year}-12-31"
    
    print(f"尝试从 IEM (Iowa State Univ) 下载 {station_code} {year} 年数据...")
    
    params = {
        "station": station_code,
        "data": ["tmpc", "dwpc", "relh", "drct", "sknt", "mslp"],  # 温度, 露点, 湿度, 风向, 风速(节), 海压
        "year1": year, "month1": "1", "day1": "1",
        "year2": year + 1, "month2": "1", "day2": "1", # 跨年以确保包含年底
        "timezone": "UTC",  # 统一用 UTC，方便后续处理
        "format": "onlycomma",
        "latlon": "no",
        "missing": "null",
        "trace": "null",
        "direct": "no",
        "report_type": ["1", "2"] # METAR and SPECI
    }
    
    try:
        session = get_session()
        response = session.get(base_url, params=params, timeout=30)
        
        if response.status_code != 200:
            print(f"IEM 下载失败: HTTP {response.status_code}")
            return None
            
        # IEM 返回的是 CSV 格式，直接读取
        # 典型的列头: station,valid,tmpc,dwpc,relh,drct,sknt,mslp
        df = pd.read_csv(io.StringIO(response.content.decode('utf-8')))
        
        if df.empty:
            print("IEM 返回数据为空")
            return None
            
        # 重命名列以匹配统一格式
        # valid (UTC) -> datetime
        df['datetime'] = pd.to_datetime(df['valid'])
        
        # 转换单位: sknt (knots) -> m/s
        # 1 knot = 0.514444 m/s
        df['wind_speed'] = df['sknt'] * 0.514444
        
        # 选取并重命名需要的列
        df_clean = df.rename(columns={
            'tmpc': 'temperature',
            'dwpc': 'dewpoint',
            'mslp': 'pressure',
            'drct': 'wind_direction'
        })[['datetime', 'temperature', 'dewpoint', 'pressure', 'wind_speed', 'wind_direction']]
        
        # 排序
        df_clean = df_clean.sort_values('datetime')
        
        if output_file:
            df_clean.to_csv(output_file, index=False)
            print(f"IEM 数据已保存到: {output_file}")
            
        return df_clean
        
    except Exception as e:
        print(f"IEM 下载出错: {e}")
        return None

def fetch_noaa_isd_history(year, station_id="58457099999", output_file=None):
    """
    从 NOAA NCEI (National Centers for Environmental Information) 获取全球站点历史逐小时实况数据。
    这是最权威的地面观测实况数据源 (Ground Truth)，非再分析数据。
    
    参数:
    - year: 年份 (例如 2023)
    - station_id: 站点ID，格式为 USAF+WBAN。
        杭州萧山机场 (ZSHC) 的 ID 通常是 "58457099999" (58457是WMO ID)
    - output_file: 保存路径
    """
    base_url = f"https://www.ncei.noaa.gov/data/global-hourly/access/{year}/{station_id}.csv"
    print(f"尝试从 NOAA NCEI 下载 {year} 年的数据: {base_url} ...")
    
    try:
        session = get_session()
        response = session.get(base_url, timeout=60)  # 增加超时时间到60秒
        if response.status_code != 200:
            print(f"下载失败: HTTP {response.status_code}")
            return None
            
        print("下载成功，正在解析...")
        # NOAA CSV 格式说明:
        # TMP: 温度, 格式 +0123,1 (温度*10, 质量代码)
        # DEW: 露点
        # SLP: 海平面气压
        # WND: 风速风向
        
        # 读取原始 CSV
        df_raw = pd.read_csv(io.StringIO(response.content.decode('utf-8')))
        
        # 数据清洗列表
        records = []
        
        for _, row in df_raw.iterrows():
            try:
                # 解析时间
                dt = datetime.strptime(row['DATE'], "%Y-%m-%dT%H:%M:%S")
                
                # 解析温度 (TMP列格式: "+0200,1")
                # 9999 表示缺失
                tmp_str = row['TMP']
                temp_c = None
                if isinstance(tmp_str, str) and ',' in tmp_str:
                    val_str = tmp_str.split(',')[0]
                    if val_str != "+9999":
                        temp_c = int(val_str) / 10.0
                
                # 解析露点 (DEW列)
                dew_str = row['DEW']
                dew_c = None
                if isinstance(dew_str, str) and ',' in dew_str:
                    val_str = dew_str.split(',')[0]
                    if val_str != "+9999":
                        dew_c = int(val_str) / 10.0
                
                # 解析气压 (SLP列: 海平面气压, 格式 10132,1 => 1013.2 hPa)
                slp_str = row['SLP']
                pressure = None
                if isinstance(slp_str, str) and ',' in slp_str:
                    val_str = slp_str.split(',')[0]
                    if val_str != "99999":
                        pressure = int(val_str) / 10.0
                        
                # 解析风 (WND列: "320,1,N,0072,1...") -> 角度320, 速度7.2m/s
                wnd_str = row['WND']
                ws = None
                wd = None
                if isinstance(wnd_str, str) and ',' in wnd_str:
                    parts = wnd_str.split(',')
                    # 角度
                    if parts[0] != "999":
                        wd = int(parts[0])
                    # 速度 (单位 0.1 m/s)
                    if parts[3] != "9999":
                        ws = int(parts[3]) / 10.0

                records.append({
                    "datetime": dt,
                    "temperature": temp_c,
                    "dewpoint": dew_c,
                    "pressure": pressure,
                    "wind_speed": ws,
                    "wind_direction": wd
                })
            except Exception as e:
                continue

        df_clean = pd.DataFrame(records)
        
        # 简单过滤：去除全空的行
        df_clean.dropna(subset=['temperature', 'pressure'], how='all', inplace=True)
        
        if output_file:
            df_clean.to_csv(output_file, index=False)
            print(f"数据已保存到: {output_file}")
            print(df_clean.head())
        
        return df_clean

    except Exception as e:
        print(f"发生错误: {e}")
        return None

if __name__ == "__main__":
    # 示例：获取杭州萧山机场 (ZSHC) 2024年的数据
    year = 2024
    output_path = f"zshc_history_{year}.csv"
    
    print(f"=== 开始获取 {year} 年杭州萧山机场实况数据 ===")
    
    # 策略 1: 优先尝试 IEM (速度快，格式好)
    print("\n[策略 1] 尝试从 Iowa State University (IEM) 下载...")
    df = fetch_iem_asos_history(year, station_code="ZSHC", output_file=output_path)
    
    # 策略 2: 如果 IEM 失败，尝试 NOAA (权威，但服务器慢)
    if df is None or df.empty:
        print("\n[策略 2] IEM 下载失败或无数据，尝试从 NOAA NCEI 下载...")
        # 站点ID: 584570 (USAF) + 99999 (WBAN)
        station_id = "58457099999"
        df = fetch_noaa_isd_history(year, station_id, output_path)
    
    if df is not None and not df.empty:
        print(f"\n✅ 成功获取 {len(df)} 条记录！")
        print(df.head())
    else:
        print("\n❌ 所有数据源均下载失败。请检查网络连接（NOAA/IEM 服务器位于海外，可能需要网络环境支持）。")