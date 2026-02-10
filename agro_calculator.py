# agro_calculator.py
# 农业气象指标计算引擎

import pandas as pd
import numpy as np
from datetime import datetime

class AgroCalculator:
    """计算农业气象关键指标"""
    
    @staticmethod
    def calculate_gdd(daily_temps, base_temp):
        """
        计算活动积温 (Growing Degree Days)
        GDD = Σ max(0, (Tmax + Tmin)/2 - Tbase)
        
        参数:
        - daily_temps: list of dict, [{'date': '2024-01-01', 'tmax': 15, 'tmin': 5}, ...]
        - base_temp: float, 基础温度
        """
        gdd_total = 0
        gdd_daily = []
        
        for day in daily_temps:
            avg_temp = (day['tmax'] + day['tmin']) / 2
            gdd = max(0, avg_temp - base_temp)
            gdd_total += gdd
            gdd_daily.append({
                "date": day['date'],
                "gdd": round(gdd, 1),
                "cumulative": round(gdd_total, 1)
            })
            
        return gdd_total, gdd_daily

    @staticmethod
    def calculate_water_balance(precip, et0):
        """
        计算水分平衡
        Balance = 降水量 - 蒸散发(ET0)
        """
        return precip - et0

    @staticmethod
    def calculate_suitability_score(crop_stage_info, current_weather):
        """
        计算气象适宜度评分 (0-100)
        
        参数:
        - crop_stage_info: dict, 作物当前阶段信息 (temp_min, temp_opt, temp_max, etc.)
        - current_weather: dict, 当前/预报天气 (temp_avg, precip, humidity)
        """
        if not crop_stage_info or not current_weather:
            return 0, ["数据缺失"]
            
        score = 100
        deductions = []
        
        # 1. 温度评分 (权重 50%)
        t_avg = current_weather.get('temp_avg')
        t_min_req = crop_stage_info.get('temp_min')
        t_opt_req = crop_stage_info.get('temp_opt')
        t_max_req = crop_stage_info.get('temp_max')
        
        if t_avg < t_min_req:
            # 低温扣分
            diff = t_min_req - t_avg
            loss = min(40, diff * 5)
            score -= loss
            deductions.append(f"温度偏低{diff:.1f}℃ (-{loss})")
        elif t_avg > t_max_req:
            # 高温扣分
            diff = t_avg - t_max_req
            loss = min(40, diff * 5)
            score -= loss
            deductions.append(f"温度偏高{diff:.1f}℃ (-{loss})")
        else:
            # 偏离最适温度微调
            diff = abs(t_avg - t_opt_req)
            if diff > 3:
                loss = min(10, (diff-3) * 2)
                score -= loss
        
        # 2. 水分评分 (权重 30%)
        # 简化逻辑：基于需水量描述
        water_need = crop_stage_info.get('water_need') # high, medium, low
        precip = current_weather.get('precip', 0)
        humidity = current_weather.get('humidity', 60)
        
        if water_need == 'high':
            if precip < 1 and humidity < 50:
                score -= 15
                deductions.append("缺水 (-15)")
        elif water_need == 'low':
            if precip > 20:
                score -= 20
                deductions.append("降水过多 (-20)")
            elif humidity > 90:
                score -= 10
                deductions.append("湿度过大 (-10)")
                
        # 3. 极端天气一票否决
        wind_speed = current_weather.get('wind_speed', 0)
        if wind_speed > 15: # >7级风
            score -= 30
            deductions.append("大风风险 (-30)")
            
        return max(0, score), deductions

agro_calculator = AgroCalculator()
