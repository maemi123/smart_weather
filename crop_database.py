# crop_database.py
# 浙江省典型农作物气象知识库
# 包含：水稻、龙井茶、杨梅、柑橘、小白菜

from datetime import datetime

class CropDatabase:
    """作物数据库管理类"""
    
    def __init__(self):
        # 定义作物数据
        self.crops = {
            "rice": {
                "name": "单季晚稻",
                "category": "粮食作物",
                "icon": "🌾",
                "stages": [
                    {"name": "播种育秧期", "start": "05-15", "end": "06-15", "temp_min": 15, "temp_opt": 25, "temp_max": 35, "water_need": "high"},
                    {"name": "移栽返青期", "start": "06-16", "end": "07-10", "temp_min": 20, "temp_opt": 28, "temp_max": 38, "water_need": "high"},
                    {"name": "分蘖期", "start": "07-11", "end": "08-05", "temp_min": 22, "temp_opt": 30, "temp_max": 38, "water_need": "medium"},
                    {"name": "拔节孕穗期", "start": "08-06", "end": "09-05", "temp_min": 20, "temp_opt": 28, "temp_max": 35, "water_need": "high"},
                    {"name": "抽穗扬花期", "start": "09-06", "end": "09-25", "temp_min": 20, "temp_opt": 26, "temp_max": 32, "water_need": "medium"},
                    {"name": "灌浆结实期", "start": "09-26", "end": "10-25", "temp_min": 15, "temp_opt": 22, "temp_max": 28, "water_need": "low"},
                    {"name": "成熟收获期", "start": "10-26", "end": "11-15", "temp_min": 10, "temp_opt": 18, "temp_max": 25, "water_need": "none"},
                    {"name": "越冬休闲期", "start": "11-16", "end": "05-14", "temp_min": -5, "temp_opt": 8, "temp_max": 20, "water_need": "none"}
                ],
                "gdd_base": 10, # 基础积温温度
                "gdd_total": 2200, # 全生育期所需积温
                "gdd_start": "04-15",
                "risks": {
                    "high_temp": {"threshold": 35, "desc": "高温热害", "stage": ["抽穗扬花期", "灌浆结实期"]},
                    "low_temp": {"threshold": 17, "desc": "寒露风(低温冷害)", "stage": ["抽穗扬花期"]},
                    "heavy_rain": {"threshold": 50, "desc": "暴雨倒伏", "stage": ["成熟收获期"]}
                }
            },
            "tea": {
                "name": "西湖龙井",
                "category": "经济作物",
                "icon": "🍵",
                "stages": [
                    {"name": "越冬期", "start": "11-01", "end": "02-15", "temp_min": -5, "temp_opt": 5, "temp_max": 15, "water_need": "low"},
                    {"name": "萌芽期", "start": "02-16", "end": "03-10", "temp_min": 4, "temp_opt": 12, "temp_max": 20, "water_need": "medium"},
                    {"name": "采摘期(春茶)", "start": "03-11", "end": "04-30", "temp_min": 10, "temp_opt": 18, "temp_max": 25, "water_need": "medium"},
                    {"name": "新梢生长期", "start": "05-01", "end": "09-30", "temp_min": 15, "temp_opt": 25, "temp_max": 35, "water_need": "high"},
                    {"name": "秋茶采摘期", "start": "10-01", "end": "10-31", "temp_min": 15, "temp_opt": 20, "temp_max": 28, "water_need": "medium"}
                ],
                "gdd_base": 10,
                "gdd_total": 380,
                "gdd_start": "01-01",
                "risks": {
                    "frost": {"threshold": 4, "desc": "倒春寒(霜冻害)", "stage": ["萌芽期", "采摘期(春茶)"]},
                    "heat": {"threshold": 35, "desc": "高温烧灼", "stage": ["新梢生长期"]},
                    "drought": {"threshold": 30, "desc": "干旱落叶", "stage": ["新梢生长期"]} # 这里指连续无雨天数，需特殊处理
                }
            },
            "bayberry": {
                "name": "杨梅",
                "category": "水果",
                "icon": "🍒",
                "stages": [
                    {"name": "休眠期", "start": "12-01", "end": "02-28", "temp_min": -2, "temp_opt": 5, "temp_max": 15, "water_need": "low"},
                    {"name": "开花期", "start": "03-01", "end": "04-10", "temp_min": 5, "temp_opt": 15, "temp_max": 25, "water_need": "medium"},
                    {"name": "果实发育期", "start": "04-11", "end": "06-05", "temp_min": 15, "temp_opt": 22, "temp_max": 30, "water_need": "high"},
                    {"name": "成熟采摘期", "start": "06-06", "end": "07-05", "temp_min": 20, "temp_opt": 25, "temp_max": 32, "water_need": "medium"},
                    {"name": "花芽分化期", "start": "07-06", "end": "11-30", "temp_min": 15, "temp_opt": 25, "temp_max": 35, "water_need": "medium"}
                ],
                "gdd_base": 10,
                "gdd_total": 950,
                "gdd_start": "01-01",
                "risks": {
                    "heavy_rain": {"threshold": 20, "desc": "暴雨落果/烂果", "stage": ["成熟采摘期"]},
                    "wind": {"threshold": 10, "desc": "大风落果", "stage": ["成熟采摘期"]},
                    "high_humidity": {"threshold": 90, "desc": "高湿烂果", "stage": ["成熟采摘期"]}
                }
            },
            "citrus": {
                "name": "柑橘",
                "category": "水果",
                "icon": "🍊",
                "stages": [
                    {"name": "花芽分化期", "start": "01-01", "end": "03-31", "temp_min": 0, "temp_opt": 10, "temp_max": 20, "water_need": "low"},
                    {"name": "抽梢开花期", "start": "04-01", "end": "05-15", "temp_min": 12, "temp_opt": 20, "temp_max": 28, "water_need": "medium"},
                    {"name": "生理落果期", "start": "05-16", "end": "06-30", "temp_min": 18, "temp_opt": 25, "temp_max": 32, "water_need": "medium"},
                    {"name": "果实膨大期", "start": "07-01", "end": "09-30", "temp_min": 20, "temp_opt": 28, "temp_max": 35, "water_need": "high"},
                    {"name": "成熟采收期", "start": "10-01", "end": "12-31", "temp_min": 10, "temp_opt": 18, "temp_max": 25, "water_need": "low"}
                ],
                "gdd_base": 12,
                "gdd_total": 1800,
                "gdd_start": "01-01",
                "risks": {
                    "freeze": {"threshold": -2, "desc": "严重冻害", "stage": ["花芽分化期", "成熟采收期"]},
                    "sunburn": {"threshold": 38, "desc": "日灼病", "stage": ["果实膨大期"]}
                }
            },
            "bokchoy": {
                "name": "小白菜",
                "category": "蔬菜",
                "icon": "🥬",
                "stages": [
                    {"name": "发芽期", "start": "03-01", "end": "03-05", "days": 5, "temp_min": 5, "temp_opt": 20, "temp_max": 30, "water_need": "high"},
                    {"name": "幼苗期", "start": "03-06", "end": "03-20", "days": 15, "temp_min": 5, "temp_opt": 22, "temp_max": 28, "water_need": "medium"},
                    {"name": "莲座期", "start": "03-21", "end": "04-10", "days": 20, "temp_min": 5, "temp_opt": 20, "temp_max": 25, "water_need": "high"},
                    {"name": "成熟期", "start": "04-11", "end": "04-25", "days": 10, "temp_min": 5, "temp_opt": 18, "temp_max": 25, "water_need": "medium"}
                ],
                "note": "全年可种，周期短，按天数计算阶段",
                "gdd_base": 5,
                "gdd_total": 400,
                "gdd_start": "user",
                "risks": {
                    "heat": {"threshold": 32, "desc": "高温热害", "stage": ["all"]},
                    "flood": {"threshold": 50, "desc": "暴雨渍涝", "stage": ["all"]}
                }
            }
        }

    def get_all_crops(self):
        """获取所有作物列表"""
        return [{"id": k, "name": v["name"], "icon": v["icon"]} for k, v in self.crops.items()]

    def get_crop_info(self, crop_id):
        """获取单个作物详细信息"""
        return self.crops.get(crop_id)

    def get_current_stage(self, crop_id, current_date=None):
        """根据日期获取作物当前生长阶段"""
        if current_date is None:
            current_date = datetime.now()
            
        crop = self.crops.get(crop_id)
        if not crop:
            return None
            
        # 特殊处理全年种植的蔬菜
        if crop_id == "bokchoy":
            # 简单起见，假设处于生长旺盛期(莲座期)
            return crop["stages"][2]
            
        month_day = current_date.strftime("%m-%d")
        
        for stage in crop["stages"]:
            # 处理跨年阶段，如越冬期 11-01 到 02-15
            if stage["start"] > stage["end"]:
                if month_day >= stage["start"] or month_day <= stage["end"]:
                    return stage
            else:
                if stage["start"] <= month_day <= stage["end"]:
                    return stage
                    
        return None

    def get_water_need_value(self, level):
        """将需水等级转换为数值 (mm/day)"""
        mapping = {
            "high": 8,
            "medium": 5,
            "low": 3,
            "none": 0
        }
        return mapping.get(level, 0)

# 单例实例
crop_db = CropDatabase()
