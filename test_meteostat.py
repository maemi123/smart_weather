"""
Meteostat 数据获取测试脚本
测试杭州萧山机场 (58457) 昨日和今日逐小时观测数据
"""
import meteostat
from datetime import datetime, timedelta
import pandas as pd
import os
import shutil

def test_meteostat():
    print("=" * 60)
    print("Meteostat 数据获取测试")
    print("=" * 60)
    
    cache_dir = os.path.expanduser("~/.meteostat/cache")
    if os.path.exists(cache_dir):
        try:
            shutil.rmtree(cache_dir)
            print("[OK] 缓存已清理")
        except:
            pass
    
    station_id = '58457'
    
    print(f"\n【站点信息】")
    print(f"站点ID: {station_id}")
    print(f"站点名称: 杭州萧山机场")
    
    now = datetime.now()
    yesterday = now - timedelta(days=1)
    
    start_yesterday = yesterday.replace(hour=0, minute=0, second=0, microsecond=0)
    end_yesterday = start_yesterday + timedelta(days=1)
    
    start_today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end_today = now + timedelta(hours=1)
    
    print(f"\n【时间范围】")
    print(f"昨日: {start_yesterday.strftime('%Y-%m-%d %H:%M')} - {end_yesterday.strftime('%Y-%m-%d %H:%M')}")
    print(f"今日: {start_today.strftime('%Y-%m-%d %H:%M')} - {end_today.strftime('%Y-%m-%d %H:%M')}")
    
    print(f"\n【获取昨日数据】")
    ts_yesterday = meteostat.hourly(station=station_id, start=start_yesterday, end=end_yesterday)
    df_yesterday = ts_yesterday.fetch()
    print(f"获取到 {len(df_yesterday)} 条记录")
    
    print(f"\n【获取今日数据】")
    ts_today = meteostat.hourly(station=station_id, start=start_today, end=end_today)
    df_today = ts_today.fetch()
    print(f"获取到 {len(df_today)} 条记录")
    
    print("\n" + "=" * 60)
    print("1. 所有字段名称")
    print("=" * 60)
    
    all_columns = [str(col) for col in df_yesterday.columns.tolist()]
    print(f"字段数量: {len(all_columns)}")
    
    field_desc = {
        'temp': '温度 (°C)',
        'rhum': '相对湿度 (%)',
        'prcp': '降水量 (mm)',
        'snwd': '积雪深度 (mm)',
        'wdir': '风向 (°)',
        'wspd': '风速 (km/h)',
        'wpgt': '阵风 (km/h)',
        'pres': '气压 (hPa)',
        'tsun': '日照时长 (分钟)',
        'cldc': '云量 (okta)',
        'coco': '天气状况代码'
    }
    
    for i, col in enumerate(all_columns, 1):
        col_name = col if isinstance(col, str) else str(col)
        desc = field_desc.get(col_name, '')
        print(f"  {i}. {col_name:<8} {desc}")
    
    print("\n" + "=" * 60)
    print("2. 昨日第一条数据")
    print("=" * 60)
    
    if not df_yesterday.empty:
        first_row = df_yesterday.iloc[0]
        print(f"时间: {df_yesterday.index[0]}")
        for col in df_yesterday.columns:
            val = first_row[col]
            col_name = str(col)
            if pd.notna(val):
                print(f"  {col_name}: {val}")
            else:
                print(f"  {col_name}: <空>")
    else:
        print("昨日数据为空！")
    
    print("\n" + "=" * 60)
    print("3. 字段数据完整性统计（非空比例）")
    print("=" * 60)
    
    df_combined = pd.concat([df_yesterday, df_today])
    total_rows = len(df_combined)
    print(f"总记录数: {total_rows}")
    
    completeness = []
    for col in df_combined.columns:
        non_null_count = df_combined[col].notna().sum()
        non_null_ratio = non_null_count / total_rows * 100 if total_rows > 0 else 0
        col_name = str(col)
        completeness.append({
            '字段': col_name,
            '非空数': non_null_count,
            '总数': total_rows,
            '非空比例': f"{non_null_ratio:.1f}%"
        })
    
    completeness_df = pd.DataFrame(completeness)
    completeness_df = completeness_df.sort_values('非空数', ascending=False)
    print(completeness_df.to_string(index=False))
    
    print("\n" + "=" * 60)
    print("4. 数据更新延迟分析")
    print("=" * 60)
    
    print(f"\n当前时间: {now.strftime('%Y-%m-%d %H:%M:%S')}")
    
    if not df_combined.empty:
        latest_time = df_combined.index.max()
        print(f"最新数据时间: {latest_time}")
        
        if pd.notna(latest_time):
            delay = now - latest_time.to_pydatetime()
            delay_hours = delay.total_seconds() / 3600
            print(f"数据延迟: {delay_hours:.1f} 小时")
            
            if delay_hours < 2:
                print("状态: 数据更新及时")
            elif delay_hours < 6:
                print("状态: 数据略有延迟")
            elif delay_hours < 24:
                print("状态: 数据延迟较大")
            else:
                print("状态: 数据严重延迟")
            
            print(f"\n昨日数据时间范围:")
            if not df_yesterday.empty:
                print(f"  开始: {df_yesterday.index.min()}")
                print(f"  结束: {df_yesterday.index.max()}")
                print(f"  记录数: {len(df_yesterday)}")
            else:
                print("  无数据")
            
            print(f"\n今日数据时间范围:")
            if not df_today.empty:
                print(f"  开始: {df_today.index.min()}")
                print(f"  结束: {df_today.index.max()}")
                print(f"  记录数: {len(df_today)}")
            else:
                print("  无数据")
                
            print(f"\n数据更新最晚时次分析:")
            if delay_hours > 0:
                cutoff_time = now - timedelta(hours=delay_hours)
                print(f"  数据截止时间约: {cutoff_time.strftime('%Y-%m-%d %H:00')}")
                print(f"  即约 {delay_hours:.0f} 小时前的数据之后没有更新")
    else:
        print("无任何数据！")
    
    print("\n" + "=" * 60)
    print("5. 完整数据预览（昨日+今日）")
    print("=" * 60)
    
    df_display = df_combined.copy()
    df_display.columns = [str(col) for col in df_display.columns]
    print(df_display.to_string())
    
    return df_yesterday, df_today

if __name__ == "__main__":
    df_yesterday, df_today = test_meteostat()
