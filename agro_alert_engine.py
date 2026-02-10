# agro_alert_engine.py
# 智能提示引擎：自动扫描作物风险与机会

from datetime import datetime, timedelta
from crop_database import crop_db
from agro_calculator import agro_calculator

class AgroAlertEngine:
    """农业气象预警与提示引擎"""
    
    def generate_alerts(self, forecast_data):
        """
        根据预报数据生成所有作物的提示列表
        
        参数:
        - forecast_data: list of dict, 未来7天预报
          [{'date': '2024-05-20', 'temp_min': 15, 'temp_max': 25, 'weather': '晴', 'precip': 0, 'wind': 2}, ...]
        """
        alerts = []
        current_date = datetime.now()
        
        # 获取所有作物
        crops = crop_db.get_all_crops()
        
        for crop_basic in crops:
            crop_id = crop_basic['id']
            crop_info = crop_db.get_crop_info(crop_id)
            crop_alerts_before = len(alerts)
            
            # 1. 确定当前生长阶段
            current_stage = crop_db.get_current_stage(crop_id)
            if not current_stage:
                continue
                
            stage_name = current_stage['name']
            stage_month_day = current_date.strftime("%m-%d")
            
            # 2. 扫描未来7天天气，匹配风险与机会
            for day_idx, day_weather in enumerate(forecast_data):
                day_date = day_weather['date']
                t_min = day_weather.get('temp_min')
                t_max = day_weather.get('temp_max')
                precip = day_weather.get('precip', 0)
                wind = day_weather.get('wind', 0)
                humidity = day_weather.get('humidity', 60)
                
                # --- A. 灾害风险预警 (红色/黄色) ---
                risks = crop_info.get('risks', {})
                
                # 低温/冻害
                if 'low_temp' in risks or 'frost' in risks or 'freeze' in risks:
                    risk_cfg = risks.get('low_temp') or risks.get('frost') or risks.get('freeze')
                    if risk_cfg and (stage_name in risk_cfg.get('stage', []) or "all" in risk_cfg.get('stage', [])):
                        if t_min is not None and t_min <= risk_cfg['threshold']:
                            alerts.append({
                                "type": "warning",
                                "level": "high",
                                "crop_id": crop_id,
                                "crop_name": crop_info['name'],
                                "title": f"{risk_cfg['desc']}预警",
                                "date": day_date,
                                "message": f"{day_date} 最低气温降至 {t_min}℃，需防范{risk_cfg['desc']}。",
                                "action": "覆盖保温 / 灌水防冻"
                            })
                            
                # 高温热害
                if 'high_temp' in risks or 'heat' in risks or 'sunburn' in risks:
                    risk_cfg = risks.get('high_temp') or risks.get('heat') or risks.get('sunburn')
                    if risk_cfg and (stage_name in risk_cfg.get('stage', []) or "all" in risk_cfg.get('stage', [])):
                        if t_max is not None and t_max >= risk_cfg['threshold']:
                            alerts.append({
                                "type": "warning",
                                "level": "medium",
                                "crop_id": crop_id,
                                "crop_name": crop_info['name'],
                                "title": "高温热害预警",
                                "date": day_date,
                                "message": f"{day_date} 最高气温达 {t_max}℃，可能影响生长。",
                                "action": "灌溉降温 / 遮阳"
                            })

                # 暴雨/强降水
                if 'heavy_rain' in risks or 'flood' in risks:
                    risk_cfg = risks.get('heavy_rain') or risks.get('flood')
                    if risk_cfg and (stage_name in risk_cfg.get('stage', []) or "all" in risk_cfg.get('stage', [])):
                        if precip is not None and precip >= risk_cfg['threshold']:
                            alerts.append({
                                "type": "warning",
                                "level": "high",
                                "crop_id": crop_id,
                                "crop_name": crop_info['name'],
                                "title": risk_cfg['desc'],
                                "date": day_date,
                                "message": f"{day_date} 预计降水量 {precip}mm，注意防涝。",
                                "action": "清理沟渠 / 及时排水"
                            })

                if 'wind' in risks:
                    risk_cfg = risks.get('wind')
                    if risk_cfg and (stage_name in risk_cfg.get('stage', []) or "all" in risk_cfg.get('stage', [])):
                        if wind is not None and wind >= risk_cfg['threshold']:
                            alerts.append({
                                "type": "warning",
                                "level": "medium",
                                "crop_id": crop_id,
                                "crop_name": crop_info['name'],
                                "title": risk_cfg['desc'],
                                "date": day_date,
                                "message": f"{day_date} 预计风速 {wind}m/s，注意防风加固。",
                                "action": "加固支撑 / 避免喷药"
                            })

                if 'high_humidity' in risks:
                    risk_cfg = risks.get('high_humidity')
                    if risk_cfg and (stage_name in risk_cfg.get('stage', []) or "all" in risk_cfg.get('stage', [])):
                        if humidity is not None and humidity >= risk_cfg['threshold']:
                            alerts.append({
                                "type": "warning",
                                "level": "medium",
                                "crop_id": crop_id,
                                "crop_name": crop_info['name'],
                                "title": risk_cfg['desc'],
                                "date": day_date,
                                "message": f"{day_date} 相对湿度约 {humidity}%，需防范高湿诱发问题。",
                                "action": "加强通风 / 雨后及时清园"
                            })

                # --- B. 农事操作机会 (绿色) ---
                # 示例：晴天适合施肥/喷药
                if precip < 1 and wind < 4 and t_max is not None:
                    # 仅在最近3天提示
                    if day_idx < 3:
                        if 15 < t_max < 30:
                            alerts.append({
                                "type": "opportunity",
                                "level": "info",
                                "crop_id": crop_id,
                                "crop_name": crop_info['name'],
                                "title": "适宜农事窗口",
                                "date": day_date,
                                "message": f"{day_date} 天气较好，风力适中，适合田间作业。",
                                "action": "施肥 / 喷药 / 修剪"
                            })
                        else:
                            alerts.append({
                                "type": "remind",
                                "level": "info",
                                "crop_id": crop_id,
                                "crop_name": crop_info['name'],
                                "title": "田间管理窗口",
                                "date": day_date,
                                "message": f"{day_date} 天气较平稳，适合巡查与整备工作。",
                                "action": "巡查苗情 / 清沟排水 / 加固防风"
                            })
                        
            # --- C. 生长阶段提醒 (蓝色) ---
            # 简单逻辑：如果今天在阶段开始的前5天内
            if current_stage:
                try:
                    curr_year = current_date.year
                    start_year = curr_year
                    if current_stage['start'] > current_stage['end'] and stage_month_day <= current_stage['end']:
                        start_year = curr_year - 1
                    start_str = f"{start_year}-{current_stage['start']}"
                    stage_start_date = datetime.strptime(start_str, "%Y-%m-%d")
                    
                    diff = (current_date - stage_start_date).days
                    if 0 <= diff <= 5:
                        alerts.append({
                            "type": "remind",
                            "level": "info",
                            "crop_id": crop_id,
                            "crop_name": crop_info['name'],
                            "title": "进入新生长阶段",
                            "date": current_date.strftime("%Y-%m-%d"),
                            "message": f"{crop_info['name']} 已进入 {stage_name}。",
                            "action": f"关注{current_stage.get('water_need', 'medium')}水分管理"
                        })
                except:
                    pass

            if len(alerts) == crop_alerts_before:
                alerts.append({
                    "type": "remind",
                    "level": "info",
                    "crop_id": crop_id,
                    "crop_name": crop_info['name'],
                    "title": "阶段管理提示",
                    "date": current_date.strftime("%Y-%m-%d"),
                    "message": f"{crop_info['name']} 当前为{stage_name}，请结合天气安排管理。",
                    "action": f"关注{current_stage.get('water_need', 'medium')}水分与病害风险"
                })

        # 按优先级排序 (High > Medium > Info)
        priority_map = {"high": 0, "medium": 1, "info": 2}
        alerts.sort(key=lambda x: (priority_map.get(x['level'], 3), x['date']))
        
        return alerts

agro_alert_engine = AgroAlertEngine()
