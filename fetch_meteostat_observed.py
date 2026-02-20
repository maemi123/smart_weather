"""
Meteostat 实况数据收集脚本
获取杭州萧山机场 (58457) 逐小时观测数据，用于机器学习误差校正模型训练
"""
import meteostat
from datetime import datetime, timedelta
import pandas as pd
from tqdm import tqdm
import time
import os
import shutil

STATION_ID = '58457'
STATION_NAME = '杭州萧山机场'
START_DATE = datetime(2026, 1, 11, 0, 0, 0)
END_DATE = datetime(2026, 2, 21, 23, 59, 59)
OUTPUT_DIR = 'data'
OUTPUT_FILENAME = 'hangzhou_observed_20260111_20260221.csv'

FIELD_MAPPING = {
    'temp': 'temp',
    'rhum': 'rhum',
    'prcp': 'prcp',
    'wdir': 'wdir',
    'wspd': 'wspd',
    'pres': 'pres',
    'cldc': 'cldc',
    'coco': 'coco'
}

OUTPUT_COLUMNS = ['datetime', 'temp', 'rhum', 'prcp', 'wdir', 'wspd', 'pres', 'cldc', 'coco']

def clear_meteostat_cache():
    cache_dir = os.path.expanduser("~/.meteostat/cache")
    if os.path.exists(cache_dir):
        try:
            shutil.rmtree(cache_dir)
            print("[OK] Meteostat 缓存已清理")
        except Exception as e:
            print(f"[警告] 清理缓存失败: {e}")

def fetch_with_retry(station_id, start, end, max_retries=3):
    for attempt in range(max_retries):
        try:
            ts = meteostat.hourly(station=station_id, start=start, end=end)
            df = ts.fetch()
            return df
        except Exception as e:
            if attempt < max_retries - 1:
                print(f"  [重试 {attempt + 1}/{max_retries}] {e}")
                time.sleep(2)
            else:
                print(f"  [失败] 获取数据失败: {e}")
                return None
    return None

def fetch_data_in_batches(station_id, start, end, batch_days=30):
    all_data = []
    current_start = start
    batch_num = 0
    failed_batches = []
    
    total_days = (end - start).days + 1
    total_batches = (total_days + batch_days - 1) // batch_days
    
    print(f"\n[进度] 获取数据中...")
    
    with tqdm(total=total_batches, desc="批次进度") as pbar:
        while current_start <= end:
            batch_num += 1
            current_end = min(current_start + timedelta(days=batch_days), end)
            
            pbar.set_description(f"批次{batch_num} ({current_start.strftime('%Y-%m-%d')} ~ {current_end.strftime('%Y-%m-%d')})")
            
            df = fetch_with_retry(station_id, current_start, current_end)
            
            if df is not None and not df.empty:
                all_data.append(df)
            else:
                failed_batches.append({
                    'batch': batch_num,
                    'start': current_start.strftime('%Y-%m-%d'),
                    'end': current_end.strftime('%Y-%m-%d')
                })
            
            current_start = current_end + timedelta(seconds=1)
            time.sleep(1)
            pbar.update(1)
    
    if failed_batches:
        print(f"\n[警告] 以下批次获取失败:")
        for fb in failed_batches:
            print(f"  批次{fb['batch']}: {fb['start']} ~ {fb['end']}")
    
    if all_data:
        combined_df = pd.concat(all_data)
        return combined_df
    return None

def process_data(df):
    if df is None or df.empty:
        return None
    
    df = df.copy()
    
    df.columns = [str(col) for col in df.columns]
    
    df.index = pd.to_datetime(df.index)
    df.index = df.index.tz_localize('UTC').tz_convert('Asia/Shanghai')
    df.index = df.index.tz_localize(None)
    
    df = df.reset_index()
    df = df.rename(columns={'index': 'datetime', 'time': 'datetime'})
    
    df['datetime'] = df['datetime'].dt.strftime('%Y-%m-%d %H:%M')
    
    available_cols = [col for col in FIELD_MAPPING.keys() if col in df.columns]
    df = df[['datetime'] + available_cols]
    
    for col in OUTPUT_COLUMNS[1:]:
        if col not in df.columns:
            df[col] = pd.NA
    
    df = df[OUTPUT_COLUMNS]
    
    return df

def fill_missing_hours(df, start, end):
    start_dt = datetime(start.year, start.month, start.day, 0, 0)
    end_dt = datetime(end.year, end.month, end.day, 23, 0)
    
    all_hours = pd.date_range(start=start_dt, end=end_dt, freq='h')
    all_hours_str = all_hours.strftime('%Y-%m-%d %H:%M').tolist()
    
    df_full = pd.DataFrame({'datetime': all_hours_str})
    df_full = df_full.merge(df, on='datetime', how='left')
    
    return df_full

def print_statistics(df):
    print("\n" + "=" * 60)
    print("数据统计信息")
    print("=" * 60)
    
    total_rows = len(df)
    print(f"\n总记录数: {total_rows}")
    
    print("\n字段完整性:")
    for col in OUTPUT_COLUMNS[1:]:
        if col in df.columns:
            non_null = df[col].notna().sum()
            ratio = non_null / total_rows * 100 if total_rows > 0 else 0
            print(f"  {col:<6}: {ratio:6.1f}% ({non_null}/{total_rows})")
    
    df['date'] = df['datetime'].str[:10]
    daily_counts = df.groupby('date').size()
    
    print("\n每日数据条数:")
    for date, count in daily_counts.items():
        status = "✓" if count == 24 else f"⚠ 缺{24-count}小时"
        print(f"  {date}: {count:2d}条 {status}")
    
    missing_dates = []
    expected_dates = pd.date_range(start=START_DATE.date(), end=END_DATE.date(), freq='D')
    actual_dates = set(daily_counts.index)
    
    for date in expected_dates:
        date_str = date.strftime('%Y-%m-%d')
        if date_str not in actual_dates:
            missing_dates.append(date_str)
    
    if missing_dates:
        print(f"\n完全缺失的日期:")
        for d in missing_dates:
            print(f"  {d}")

def main():
    print("=" * 60)
    print("Meteostat 实况数据收集")
    print("=" * 60)
    
    print(f"\n站点: {STATION_ID} ({STATION_NAME})")
    print(f"时间范围: {START_DATE.strftime('%Y-%m-%d %H:%M')} ~ {END_DATE.strftime('%Y-%m-%d %H:%M')}")
    
    total_days = (END_DATE - START_DATE).days + 1
    total_hours = total_days * 24
    print(f"总天数: {total_days}天")
    print(f"预期小时数: {total_hours}小时")
    
    clear_meteostat_cache()
    
    raw_df = fetch_data_in_batches(STATION_ID, START_DATE, END_DATE)
    
    if raw_df is None or raw_df.empty:
        print("\n[错误] 未能获取任何数据！")
        return
    
    print(f"\n[OK] 获取到 {len(raw_df)} 条原始记录")
    
    processed_df = process_data(raw_df)
    
    if processed_df is None:
        print("\n[错误] 数据处理失败！")
        return
    
    print(f"[OK] 处理后 {len(processed_df)} 条记录")
    
    final_df = fill_missing_hours(processed_df, START_DATE, END_DATE)
    print(f"[OK] 填充后 {len(final_df)} 条记录（含缺失小时）")
    
    print_statistics(final_df)
    
    if 'date' in final_df.columns:
        final_df = final_df.drop(columns=['date'])
    
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
    
    output_path = os.path.join(OUTPUT_DIR, OUTPUT_FILENAME)
    final_df.to_csv(output_path, index=False, encoding='utf-8')
    
    print(f"\n[保存] {output_path}")
    print("\n完成！")
    print("=" * 60)

if __name__ == "__main__":
    main()
