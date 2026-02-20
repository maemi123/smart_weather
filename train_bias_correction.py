"""
随机森林误差校正训练脚本
对 ECMWF（通过 Open-Meteo 获取）的预报数据进行校正
"""
import os
import re
import json
import pickle
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from sklearn.ensemble import RandomForestRegressor, RandomForestClassifier
from sklearn.metrics import mean_absolute_error, mean_squared_error, accuracy_score, precision_score, recall_score, f1_score
import warnings
warnings.filterwarnings('ignore')

FORECAST_DIR = 'data/openmeteo'
OBSERVED_FILE = 'data/hangzhou_observed_20260111_20260221.csv'
MODELS_DIR = 'models'
TRAIN_END_DATE = '2026-02-10'
MAX_LEAD_HOURS = 168

FEATURE_COLUMNS = [
    'forecast_temp', 'forecast_rhum', 'forecast_wspd', 'forecast_pres',
    'hour', 'month', 'day_of_week', 'is_day', 'is_weekend',
    'lead_hours', 'lead_category',
    'hour_sin', 'hour_cos'
]

TARGET_COLUMNS = {
    'temp': 'temp',
    'rhum': 'rhum',
    'wspd': 'wspd'
}

def infer_issue_time(forecast_date, file_timestamp):
    """
    根据文件生成时间推断起报时间
    - 凌晨两点半后(02:30~14:29): EC12Z → 前一天20:00
    - 下午十四点半后(14:30~次日02:29): EC00Z → 当天08:00
    
    Args:
        forecast_date: 预报起始日期 (datetime.date)
        file_timestamp: 文件生成时间戳字符串，格式如 '20260215_041555'
    
    Returns:
        issue_time: 起报时间 (datetime)
    """
    time_part = file_timestamp.split('_')[1]
    hour = int(time_part[:2])
    minute = int(time_part[2:4])
    file_hour_decimal = hour + minute / 60
    
    if file_hour_decimal < 2.5:
        issue_time = datetime.combine(forecast_date, datetime.min.time()) + timedelta(hours=8)
    elif file_hour_decimal < 14.5:
        issue_time = datetime.combine(forecast_date - timedelta(days=1), datetime.min.time()) + timedelta(hours=20)
    else:
        issue_time = datetime.combine(forecast_date, datetime.min.time()) + timedelta(hours=8)
    
    return issue_time

def parse_filename(filename):
    """
    解析文件名，提取预报日期和生成时间戳
    
    Args:
        filename: 文件名，如 'HGH_forecast_2026-02-15_20260215_041555.csv'
    
    Returns:
        forecast_date: 预报起始日期
        file_timestamp: 文件生成时间戳
    """
    pattern = r'HGH_forecast_(\d{4}-\d{2}-\d{2})_(\d{8}_\d{6})\.csv'
    match = re.match(pattern, filename)
    if match:
        forecast_date = datetime.strptime(match.group(1), '%Y-%m-%d').date()
        file_timestamp = match.group(2)
        return forecast_date, file_timestamp
    return None, None

def load_forecast_data():
    """
    加载所有预报文件，提取关键字段
    
    Returns:
        DataFrame with columns: target_time, issue_time, lead_hours, forecast_*
    """
    all_forecasts = []
    files = [f for f in os.listdir(FORECAST_DIR) if f.startswith('HGH_forecast_') and f.endswith('.csv')]
    
    print(f"找到 {len(files)} 个预报文件")
    
    for filename in files:
        forecast_date, file_timestamp = parse_filename(filename)
        if forecast_date is None:
            continue
        
        issue_time = infer_issue_time(forecast_date, file_timestamp)
        
        filepath = os.path.join(FORECAST_DIR, filename)
        try:
            df = pd.read_csv(filepath)
        except Exception as e:
            print(f"  [警告] 读取 {filename} 失败: {e}")
            continue
        
        df['issue_time'] = issue_time
        df['file_timestamp'] = file_timestamp
        
        df['target_time'] = pd.to_datetime(df['datetime_beijing'])
        df['lead_hours'] = (df['target_time'] - df['issue_time']).dt.total_seconds() / 3600
        
        df = df.rename(columns={
            'temperature_2m': 'forecast_temp',
            'relative_humidity_2m': 'forecast_rhum',
            'wind_speed_10m': 'forecast_wspd',
            'pressure_msl': 'forecast_pres',
            'wind_direction_10m': 'forecast_wdir',
            'precipitation': 'forecast_prcp'
        })
        
        all_forecasts.append(df)
    
    if not all_forecasts:
        return None
    
    combined = pd.concat(all_forecasts, ignore_index=True)
    print(f"加载预报数据: {len(combined)} 条记录")
    
    return combined

def load_observed_data():
    """加载实况数据"""
    df = pd.read_csv(OBSERVED_FILE)
    df['datetime'] = pd.to_datetime(df['datetime'])
    df = df.rename(columns={
        'temp': 'obs_temp',
        'rhum': 'obs_rhum',
        'wspd': 'obs_wspd',
        'pres': 'obs_pres',
        'wdir': 'obs_wdir',
        'prcp': 'obs_prcp'
    })
    print(f"加载实况数据: {len(df)} 条记录")
    return df

def align_data(forecast_df, observed_df):
    """
    对齐预报和实况数据
    
    Returns:
        DataFrame with both forecast and observed values
    """
    forecast_df = forecast_df.copy()
    forecast_df['target_time'] = pd.to_datetime(forecast_df['target_time'])
    
    merged = forecast_df.merge(
        observed_df,
        left_on='target_time',
        right_on='datetime',
        how='inner'
    )
    
    print(f"对齐后数据: {len(merged)} 条记录")
    
    return merged

def create_features(df):
    """
    创建特征
    
    Args:
        df: 包含预报和实况数据的DataFrame
    
    Returns:
        DataFrame with features added
    """
    df = df.copy()
    
    df['hour'] = df['target_time'].dt.hour
    df['month'] = df['target_time'].dt.month
    df['day_of_week'] = df['target_time'].dt.dayofweek
    df['is_day'] = ((df['hour'] >= 6) & (df['hour'] < 18)).astype(int)
    df['is_weekend'] = (df['day_of_week'] >= 5).astype(int)
    
    def categorize_lead(hours):
        if hours <= 24:
            return 0
        elif hours <= 48:
            return 1
        elif hours <= 72:
            return 2
        elif hours <= 120:
            return 3
        else:
            return 4
    
    df['lead_category'] = df['lead_hours'].apply(categorize_lead)
    
    df['hour_sin'] = np.sin(2 * np.pi * df['hour'] / 24)
    df['hour_cos'] = np.cos(2 * np.pi * df['hour'] / 24)
    
    return df

def prepare_training_data(df, target_var):
    """
    准备训练数据
    
    按起报时间(issue_time)划分：
    - 训练集: issue_time <= 2026-01-31 的预报
    - 测试集: issue_time > 2026-01-31 的预报
    
    Args:
        df: 包含特征的DataFrame
        target_var: 目标变量名 ('temp', 'rhum', 'wspd')
    
    Returns:
        X_train, y_train, X_test, y_test, train_df, test_df
    """
    df = df.copy()
    
    obs_col = f'obs_{target_var}'
    df = df.dropna(subset=FEATURE_COLUMNS + [obs_col])
    
    train_end_dt = datetime.strptime(TRAIN_END_DATE, '%Y-%m-%d')
    train_mask = df['issue_time'] <= train_end_dt
    test_mask = df['issue_time'] > train_end_dt
    
    train_df = df[train_mask].copy()
    test_df = df[test_mask].copy()
    
    print(f"\n准备 {target_var} 训练数据:")
    print(f"  训练集: {len(train_df)} 条 (起报时间 <= {TRAIN_END_DATE})")
    print(f"  测试集: {len(test_df)} 条 (起报时间 > {TRAIN_END_DATE})")
    
    X_train = train_df[FEATURE_COLUMNS]
    y_train = train_df[obs_col]
    X_test = test_df[FEATURE_COLUMNS]
    y_test = test_df[obs_col]
    
    return X_train, y_train, X_test, y_test, train_df, test_df

def train_model(X_train, y_train):
    """
    训练随机森林模型
    
    Returns:
        trained model
    """
    model = RandomForestRegressor(
        n_estimators=100,
        max_depth=15,
        min_samples_split=5,
        min_samples_leaf=2,
        random_state=42,
        n_jobs=-1
    )
    
    model.fit(X_train, y_train)
    
    return model

def evaluate_model(model, X_test, y_test, test_df, target_var, forecast_col):
    """
    评估模型性能
    
    Returns:
        dict with evaluation metrics
    """
    y_pred = model.predict(X_test)
    y_forecast = test_df[forecast_col].values
    
    original_mae = mean_absolute_error(y_test, y_forecast)
    corrected_mae = mean_absolute_error(y_test, y_pred)
    
    original_rmse = np.sqrt(mean_squared_error(y_test, y_forecast))
    corrected_rmse = np.sqrt(mean_squared_error(y_test, y_pred))
    
    original_bias = np.mean(y_forecast - y_test)
    corrected_bias = np.mean(y_pred - y_test)
    
    improvement = (original_mae - corrected_mae) / original_mae * 100
    
    results = {
        'target': target_var,
        'original_mae': original_mae,
        'corrected_mae': corrected_mae,
        'original_rmse': original_rmse,
        'corrected_rmse': corrected_rmse,
        'original_bias': original_bias,
        'corrected_bias': corrected_bias,
        'improvement': improvement,
        'y_test': y_test,
        'y_pred': y_pred,
        'y_forecast': y_forecast,
        'test_df': test_df
    }
    
    return results

def evaluate_by_lead_time(results, target_var, forecast_col):
    """按预报时效分组评估"""
    test_df = results['test_df'].copy()
    y_test = results['y_test']
    y_pred = results['y_pred']
    y_forecast = results['y_forecast']
    
    test_df['y_test'] = y_test.values if hasattr(y_test, 'values') else y_test
    test_df['y_pred'] = y_pred
    test_df['y_forecast'] = y_forecast
    
    lead_bins = [
        (0, 24, '0-24h'),
        (24, 48, '24-48h'),
        (48, 72, '48-72h'),
        (72, 120, '72-120h'),
        (120, 168, '120-168h')
    ]
    
    lead_results = []
    
    for min_lead, max_lead, label in lead_bins:
        mask = (test_df['lead_hours'] > min_lead) & (test_df['lead_hours'] <= max_lead)
        if mask.sum() == 0:
            continue
        
        subset = test_df[mask]
        
        orig_mae = mean_absolute_error(subset['y_test'], subset['y_forecast'])
        corr_mae = mean_absolute_error(subset['y_test'], subset['y_pred'])
        improvement = (orig_mae - corr_mae) / orig_mae * 100 if orig_mae > 0 else 0
        
        lead_results.append({
            'lead_time': label,
            'samples': mask.sum(),
            'original_mae': orig_mae,
            'corrected_mae': corr_mae,
            'improvement': improvement
        })
    
    return pd.DataFrame(lead_results)

def save_model(model, target_var, feature_columns):
    """保存模型和配置"""
    if not os.path.exists(MODELS_DIR):
        os.makedirs(MODELS_DIR)
    
    model_path = os.path.join(MODELS_DIR, f'rf_{target_var}.pkl')
    with open(model_path, 'wb') as f:
        pickle.dump(model, f)
    print(f"  模型已保存: {model_path}")
    
    config = {
        'feature_columns': feature_columns,
        'target_variable': target_var,
        'train_end_date': TRAIN_END_DATE,
        'max_lead_hours': MAX_LEAD_HOURS,
        'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }
    
    config_path = os.path.join(MODELS_DIR, f'config_{target_var}.json')
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
    print(f"  配置已保存: {config_path}")

def prepare_precip_data(df):
    """
    准备降水训练数据
    
    Returns:
        X_train, y_clf_train, y_reg_train, X_test, y_clf_test, y_reg_test, train_df, test_df
    """
    df = df.copy()
    
    df = df.dropna(subset=FEATURE_COLUMNS + ['obs_prcp', 'forecast_prcp'])
    
    df['has_precip'] = (df['obs_prcp'] > 0.1).astype(int)
    
    train_end_dt = datetime.strptime(TRAIN_END_DATE, '%Y-%m-%d')
    train_mask = df['issue_time'] <= train_end_dt
    test_mask = df['issue_time'] > train_end_dt
    
    train_df = df[train_mask].copy()
    test_df = df[test_mask].copy()
    
    print(f"\n准备降水训练数据:")
    print(f"  训练集: {len(train_df)} 条 (起报时间 <= {TRAIN_END_DATE})")
    print(f"  测试集: {len(test_df)} 条 (起报时间 > {TRAIN_END_DATE})")
    
    train_precip_count = train_df['has_precip'].sum()
    test_precip_count = test_df['has_precip'].sum()
    print(f"  训练集降水样本: {train_precip_count} ({train_precip_count/len(train_df)*100:.1f}%)")
    print(f"  测试集降水样本: {test_precip_count} ({test_precip_count/len(test_df)*100:.1f}%)")
    
    X_train = train_df[FEATURE_COLUMNS]
    y_clf_train = train_df['has_precip']
    y_reg_train = train_df['obs_prcp']
    
    X_test = test_df[FEATURE_COLUMNS]
    y_clf_test = test_df['has_precip']
    y_reg_test = test_df['obs_prcp']
    
    return X_train, y_clf_train, y_reg_train, X_test, y_clf_test, y_reg_test, train_df, test_df

def train_precip_classifier(X_train, y_train):
    """训练降水分类模型"""
    model = RandomForestClassifier(
        n_estimators=100,
        max_depth=10,
        min_samples_split=5,
        min_samples_leaf=2,
        random_state=42,
        n_jobs=-1,
        class_weight='balanced'
    )
    model.fit(X_train, y_train)
    return model

def train_precip_regressor(X_train, y_train):
    """训练降水回归模型（仅降水样本）"""
    model = RandomForestRegressor(
        n_estimators=100,
        max_depth=10,
        min_samples_split=5,
        min_samples_leaf=2,
        random_state=42,
        n_jobs=-1
    )
    model.fit(X_train, y_train)
    return model

def evaluate_precip_model(clf_model, reg_model, X_test, y_clf_test, y_reg_test, test_df):
    """
    评估降水模型
    
    Returns:
        dict with evaluation metrics
    """
    y_pred_proba = clf_model.predict_proba(X_test)[:, 1]
    y_pred_clf = (y_pred_proba > 0.5).astype(int)
    
    accuracy = accuracy_score(y_clf_test, y_pred_clf)
    precision = precision_score(y_clf_test, y_pred_clf, zero_division=0)
    recall = recall_score(y_clf_test, y_pred_clf, zero_division=0)
    f1 = f1_score(y_clf_test, y_pred_clf, zero_division=0)
    
    y_forecast = test_df['forecast_prcp'].values
    
    precip_mask = y_clf_test == 1
    if precip_mask.sum() > 0:
        X_precip = X_test[precip_mask]
        y_reg_precip = y_reg_test[precip_mask]
        y_forecast_precip = y_forecast[precip_mask]
        
        y_pred_reg = reg_model.predict(X_precip)
        
        mae_original = mean_absolute_error(y_reg_precip, y_forecast_precip)
        mae_corrected = mean_absolute_error(y_reg_precip, y_pred_reg)
        improvement = (mae_original - mae_corrected) / mae_original * 100 if mae_original > 0 else 0
    else:
        mae_original = 0
        mae_corrected = 0
        improvement = 0
    
    y_pred_combined = np.where(y_pred_clf == 1, reg_model.predict(X_test), 0)
    overall_mae_original = mean_absolute_error(y_reg_test, y_forecast)
    overall_mae_corrected = mean_absolute_error(y_reg_test, y_pred_combined)
    overall_improvement = (overall_mae_original - overall_mae_corrected) / overall_mae_original * 100 if overall_mae_original > 0 else 0
    
    results = {
        'accuracy': accuracy,
        'precision': precision,
        'recall': recall,
        'f1': f1,
        'mae_original': mae_original,
        'mae_corrected': mae_corrected,
        'improvement': improvement,
        'overall_mae_original': overall_mae_original,
        'overall_mae_corrected': overall_mae_corrected,
        'overall_improvement': overall_improvement,
        'precip_samples': precip_mask.sum(),
        'y_pred_clf': y_pred_clf,
        'y_pred_combined': y_pred_combined
    }
    
    return results

def print_precip_evaluation_report(results):
    """打印降水模型评估报告"""
    print(f"\n{'='*60}")
    print(f" 降水模型评估报告")
    print(f"{'='*60}")
    
    print(f"\n分类模型性能:")
    print(f"  准确率:   {results['accuracy']:.3f}")
    print(f"  精确率:   {results['precision']:.3f}")
    print(f"  召回率:   {results['recall']:.3f}")
    print(f"  F1分数:   {results['f1']:.3f}")
    
    print(f"\n回归模型性能 (仅降水样本, n={results['precip_samples']}):")
    print(f"  原始 MAE:  {results['mae_original']:.3f} mm")
    print(f"  校正 MAE:  {results['mae_corrected']:.3f} mm")
    print(f"  改进幅度:  {results['improvement']:.1f}%")
    
    print(f"\n整体降水MAE (所有样本):")
    print(f"  原始 MAE:  {results['overall_mae_original']:.3f} mm")
    print(f"  校正 MAE:  {results['overall_mae_corrected']:.3f} mm")
    print(f"  改进幅度:  {results['overall_improvement']:.1f}%")

def print_evaluation_report(results, lead_results, target_var):
    """打印评估报告"""
    print(f"\n{'='*60}")
    print(f" {target_var.upper()} 模型评估报告")
    print(f"{'='*60}")
    
    print(f"\n整体性能:")
    print(f"  原始 MAE:  {results['original_mae']:.3f}")
    print(f"  校正 MAE:  {results['corrected_mae']:.3f}")
    print(f"  改进幅度:  {results['improvement']:.1f}%")
    print(f"  原始 RMSE: {results['original_rmse']:.3f}")
    print(f"  校正 RMSE: {results['corrected_rmse']:.3f}")
    print(f"  原始偏差:  {results['original_bias']:.3f}")
    print(f"  校正偏差:  {results['corrected_bias']:.3f}")
    
    print(f"\n按预报时效分组:")
    print(f"  {'时效':<12} {'样本数':>8} {'原始MAE':>10} {'校正MAE':>10} {'改进%':>8}")
    print(f"  {'-'*50}")
    for _, row in lead_results.iterrows():
        print(f"  {row['lead_time']:<12} {row['samples']:>8} {row['original_mae']:>10.3f} {row['corrected_mae']:>10.3f} {row['improvement']:>7.1f}%")

def main():
    print("="*60)
    print(" 随机森林误差校正训练")
    print("="*60)
    
    print("\n[步骤1] 加载数据...")
    forecast_df = load_forecast_data()
    observed_df = load_observed_data()
    
    print("\n[步骤2] 数据对齐...")
    aligned_df = align_data(forecast_df, observed_df)
    
    aligned_df = aligned_df[aligned_df['lead_hours'] <= MAX_LEAD_HOURS]
    print(f"  过滤预报时效>{MAX_LEAD_HOURS}h后: {len(aligned_df)} 条")
    
    print("\n[步骤3] 特征工程...")
    feature_df = create_features(aligned_df)
    print(f"  特征列: {FEATURE_COLUMNS}")
    
    print("\n[步骤4] 模型训练与评估...")
    
    all_results = {}
    all_lead_results = {}
    
    for target_var in TARGET_COLUMNS.keys():
        print(f"\n{'='*40}")
        print(f" 训练 {target_var} 模型")
        print(f"{'='*40}")
        
        forecast_col = f'forecast_{target_var}'
        
        X_train, y_train, X_test, y_test, train_df, test_df = prepare_training_data(
            feature_df, target_var
        )
        
        if len(X_train) == 0 or len(X_test) == 0:
            print(f"  [跳过] 训练或测试数据不足")
            continue
        
        print(f"\n  训练模型...")
        model = train_model(X_train, y_train)
        
        print(f"  评估模型...")
        results = evaluate_model(model, X_test, y_test, test_df, target_var, forecast_col)
        lead_results = evaluate_by_lead_time(results, target_var, forecast_col)
        
        print_evaluation_report(results, lead_results, target_var)
        
        all_results[target_var] = results
        all_lead_results[target_var] = lead_results
        
        print(f"\n  保存模型...")
        save_model(model, target_var, FEATURE_COLUMNS)
    
    print(f"\n{'='*40}")
    print(f" 训练降水模型")
    print(f"{'='*40}")
    
    X_train, y_clf_train, y_reg_train, X_test, y_clf_test, y_reg_test, train_df_precip, test_df_precip = prepare_precip_data(feature_df)
    
    if len(X_train) > 0 and len(X_test) > 0:
        print(f"\n  训练降水分类模型...")
        precip_clf_model = train_precip_classifier(X_train, y_clf_train)
        
        precip_mask_train = y_reg_train > 0.1
        if precip_mask_train.sum() > 10:
            print(f"  训练降水回归模型 (降水样本: {precip_mask_train.sum()})...")
            precip_reg_model = train_precip_regressor(X_train[precip_mask_train], y_reg_train[precip_mask_train])
        else:
            print(f"  [警告] 训练集降水样本不足 ({precip_mask_train.sum()}), 使用全量数据训练")
            precip_reg_model = train_precip_regressor(X_train, y_reg_train)
        
        print(f"\n  评估降水模型...")
        precip_results = evaluate_precip_model(precip_clf_model, precip_reg_model, X_test, y_clf_test, y_reg_test, test_df_precip)
        
        print_precip_evaluation_report(precip_results)
        
        print(f"\n  保存降水模型...")
        save_model(precip_clf_model, 'precip_clf', FEATURE_COLUMNS)
        save_model(precip_reg_model, 'precip_reg', FEATURE_COLUMNS)
    else:
        print(f"  [跳过] 训练或测试数据不足")
        precip_results = None
    
    print("\n" + "="*60)
    print(" 训练完成!")
    print("="*60)
    
    print("\n[汇总] 各变量改进情况:")
    print(f"  {'变量':<8} {'原始MAE':>10} {'校正MAE':>10} {'改进%':>8}")
    print(f"  {'-'*40}")
    for var, res in all_results.items():
        print(f"  {var:<8} {res['original_mae']:>10.3f} {res['corrected_mae']:>10.3f} {res['improvement']:>7.1f}%")
    
    if precip_results:
        print(f"\n[降水模型汇总]")
        print(f"  分类准确率: {precip_results['accuracy']:.1%}")
        print(f"  降水MAE: {precip_results['mae_original']:.3f} → {precip_results['mae_corrected']:.3f} mm ({precip_results['improvement']:+.1f}%)")
        print(f"  整体MAE:  {precip_results['overall_mae_original']:.3f} → {precip_results['overall_mae_corrected']:.3f} mm ({precip_results['overall_improvement']:+.1f}%)")
    
    print("\n[使用示例]")
    print("""
    # 加载模型进行校正
    import pickle
    import pandas as pd
    import numpy as np
    
    # 1. 加载模型
    with open('models/rf_temp.pkl', 'rb') as f:
        temp_model = pickle.load(f)
    with open('models/rf_wspd.pkl', 'rb') as f:
        wspd_model = pickle.load(f)
    with open('models/rf_precip_clf.pkl', 'rb') as f:
        precip_clf = pickle.load(f)
    with open('models/rf_precip_reg.pkl', 'rb') as f:
        precip_reg = pickle.load(f)
    
    # 2. 准备特征 (与训练时相同的特征列)
    features = ['forecast_temp', 'forecast_rhum', 'forecast_wspd', 'forecast_pres',
                'hour', 'month', 'day_of_week', 'is_day', 'is_weekend',
                'lead_hours', 'lead_category', 'hour_sin', 'hour_cos']
    
    # 3. 对新预报进行校正
    corrected_temp = temp_model.predict(new_forecast[features])
    corrected_wspd = wspd_model.predict(new_forecast[features])
    
    # 4. 降水校正 (两阶段)
    has_precip = precip_clf.predict(new_forecast[features])
    precip_amount = precip_reg.predict(new_forecast[features])
    corrected_precip = np.where(has_precip == 1, precip_amount, 0)
    """)

if __name__ == "__main__":
    main()
