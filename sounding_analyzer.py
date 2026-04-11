import pandas as pd
import numpy as np
import metpy.calc as mpcalc
from metpy.units import units
import requests
import json
from typing import Dict, Any
import os
from dotenv import load_dotenv

class SoundingAnalyzer:
    """探空数据分析器"""

    def __init__(self):
        # AI API配置 (复用app.py中的配置)
        load_dotenv()  # 加载.env文件
        self.api_key = os.getenv('DEEPSEEK_API_KEY')
        self.api_url = "https://api.deepseek.com/v1/chat/completions"

    def analyze(self, data: pd.DataFrame, indices: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        对探空数据进行全面分析
        
        参数:
        - data: 包含层级数据的DataFrame
        - indices: 已有的指数数据 (可选)
        
        返回:
        - 包含参数、风险评估和AI分析的字典
        """
        # 1. 计算/整理关键参数
        parameters = self._calculate_parameters(data, indices)
        
        # 2. 强对流风险评估
        risk_assessment = self._assess_severe_weather_risk(parameters)
        
        # 3. 提取分层具体数据
        layer_data = self._get_layer_data(data)
        
        # 4. 生成AI分析报告
        ai_analysis = self._generate_ai_report(parameters, risk_assessment, layer_data)
        
        return {
            "parameters": parameters,
            "risk_assessment": risk_assessment,
            "layer_data": layer_data,
            "ai_analysis": ai_analysis
        }

    def _get_layer_data(self, data: pd.DataFrame) -> Dict:
        """提取关键层级的数据 (Surface, 925, 850, 700, 500 hPa)"""
        if data.empty:
            return {}
            
        target_levels = [925, 850, 700, 500]
        layers = {}
        
        # 1. 地面层 (取第一行)
        sfc = data.iloc[0]
        layers["Surface"] = {
            "pres": f"{sfc.get('PRES', 'N/A')} hPa",
            "temp": f"{sfc.get('TEMP', 'N/A')}°C",
            "dwpt": f"{sfc.get('DWPT', 'N/A')}°C",
            "wind": f"{sfc.get('DRCT', 'N/A')}° {sfc.get('SPED', 'N/A')}m/s"
        }
        
        # 2. 高空层
        for level in target_levels:
            # 寻找最接近该气压的层 (误差范围 ±10 hPa)
            # 注意：实际探空数据可能不包含标准层，这里简单取最接近的
            try:
                # 计算与目标气压的差值绝对值
                data['pres_diff'] = abs(data['PRES'] - level)
                nearest_idx = data['pres_diff'].idxmin()
                row = data.loc[nearest_idx]
                
                # 如果差值太大 (>20hPa)，说明缺失该层
                if row['pres_diff'] > 20:
                    layers[f"{level}hPa"] = "数据缺失"
                else:
                    layers[f"{level}hPa"] = {
                        "hght": f"{row.get('HGHT', 'N/A'):.0f}m",
                        "temp": f"{row.get('TEMP', 'N/A')}°C",
                        "dwpt": f"{row.get('DWPT', 'N/A')}°C",
                        "relh": f"{row.get('RELH', 'N/A')}%",
                        "wind": f"{row.get('DRCT', 'N/A')}° {row.get('SPED', 'N/A')}m/s"
                    }
            except Exception:
                 layers[f"{level}hPa"] = "数据读取错误"
                 
        return layers

    def _prepare_profile_frame(self, data: pd.DataFrame) -> pd.DataFrame:
        """清洗探空廓线，确保计算时压力单调、关键列有效。"""
        required = ['PRES', 'TEMP', 'DWPT']
        df = data.dropna(subset=required).copy()
        if df.empty:
            return df

        for column in ['PRES', 'TEMP', 'DWPT', 'HGHT', 'DRCT', 'SPED']:
            if column in df.columns:
                df[column] = pd.to_numeric(df[column], errors='coerce')

        df = df.dropna(subset=required)
        df = df[df['PRES'] > 0]
        df = df.drop_duplicates(subset=['PRES'], keep='first')
        df = df.sort_values('PRES', ascending=False).reset_index(drop=True)
        return df

    def _calculate_parameters(self, data: pd.DataFrame, indices: Dict = None) -> Dict:
        """计算关键气象参数"""
        params = indices.copy() if indices else {}
        
        # 确保基本参数存在
        default_keys = ['CAPE', 'CIN', 'K_INDEX', 'TOTAL_TOTALS', 'LIFTED_INDEX', 'PRECIP_WATER', 'SHEAR_06KM']
        for key in default_keys:
            if key not in params:
                params[key] = None

        # 尝试使用MetPy补充计算缺失参数
        try:
            profile_df = self._prepare_profile_frame(data)
            if not profile_df.empty and 'PRES' in profile_df.columns and 'TEMP' in profile_df.columns and 'DWPT' in profile_df.columns:
                # 准备数据单位
                p = profile_df['PRES'].values * units.hPa
                T = profile_df['TEMP'].values * units.degC
                Td = profile_df['DWPT'].values * units.degC
                parcel_prof = None
                 
                # 1. 计算CAPE和CIN (如果缺失)
                if params['CAPE'] is None or params['CIN'] is None:
                    try:
                        # 计算气块路径
                        parcel_prof = mpcalc.parcel_profile(p, T[0], Td[0]).to('degC')
                        cape, cin = mpcalc.cape_cin(p, T, Td, parcel_prof)
                         
                        if params['CAPE'] is None:
                            cape_value = float(cape.magnitude)
                            params['CAPE'] = cape_value if cape_value >= 0 else None
                        if params['CIN'] is None:
                            params['CIN'] = float(cin.magnitude)
                    except Exception as e:
                        print(f"MetPy CAPE/CIN calc failed: {e}")

                # 2. 计算K指数 (如果缺失)
                if params['K_INDEX'] is None:
                    try:
                        k_index = mpcalc.k_index(p, T, Td)
                        params['K_INDEX'] = float(k_index.magnitude)
                    except Exception:
                        pass

                # 3. 计算抬升指数 (LI) (如果缺失)
                if params['LIFTED_INDEX'] is None:
                    try:
                        if parcel_prof is None:
                            parcel_prof = mpcalc.parcel_profile(p, T[0], Td[0]).to('degC')
                        # lifted_index(pressure, temperature, parcel_profile)
                        li = mpcalc.lifted_index(p, T, parcel_prof)
                        params['LIFTED_INDEX'] = float(li[0].magnitude)
                    except Exception:
                        pass
                
                # 4. 计算总指数 (Total Totals) (如果缺失)
                if params['TOTAL_TOTALS'] is None:
                    try:
                        tt = mpcalc.total_totals_index(p, T, Td)
                        params['TOTAL_TOTALS'] = float(tt.magnitude)
                    except Exception:
                        pass

                # 5. 计算可降水量 (Precipitable Water) (如果缺失)
                if params['PRECIP_WATER'] is None:
                    try:
                        pw = mpcalc.precipitable_water(p, Td)
                        params['PRECIP_WATER'] = float(pw.magnitude)
                    except Exception:
                        pass

                # 6. 计算0-6km风切变 (如果缺失)
                if params['SHEAR_06KM'] is None:
                    try:
                        # 检查是否有风场数据
                        if 'DRCT' in profile_df.columns and 'SPED' in profile_df.columns and 'HGHT' in profile_df.columns:
                            # 转换风速风向为U/V分量
                            wind_speed = profile_df['SPED'].values * units('m/s')
                            wind_dir = profile_df['DRCT'].values * units.degrees
                            u, v = mpcalc.wind_components(wind_speed, wind_dir)
                             
                            # 计算0-6km切变
                            # bulk_shear返回: (u_shear, v_shear)
                            # depth=6000m
                            u_shear, v_shear = mpcalc.bulk_shear(
                                p,
                                u,
                                v,
                                height=profile_df['HGHT'].values * units.meters,
                                depth=6000 * units.meters
                            )
                             
                            # 计算切变矢量的大小 (magnitude)
                            shear_mag = np.sqrt(u_shear**2 + v_shear**2)
                            params['SHEAR_06KM'] = float(shear_mag.magnitude)
                    except Exception as e:
                        print(f"MetPy Shear calc failed: {e}")

        except Exception as e:
            print(f"MetPy calculation error: {e}")
        
        # 格式化输出：将所有None转为"N/A"，数值保留1位小数
        formatted_params = {}
        for k, v in params.items():
            key_lower = k.lower()
            if key_lower == 'cape' and isinstance(v, (int, float)) and v < 0:
                formatted_params[key_lower] = "N/A"
            elif v is not None and isinstance(v, (int, float)):
                formatted_params[key_lower] = round(v, 1)
            else:
                formatted_params[key_lower] = v if v is not None else "N/A"
                
        return formatted_params

    def _assess_severe_weather_risk(self, params: Dict) -> Dict:
        """评估强对流风险"""
        cape = params.get('cape')
        shear = params.get('shear_06km')
        k_index = params.get('k_index')
        
        risk_level = "低"
        risk_color = "success" # green
        description = "大气层结较为稳定，无明显强对流风险。"
        potential_hazards = []
        
        # 简单的风险矩阵逻辑
        # 1. CAPE判断能量
        has_energy = False
        if isinstance(cape, (int, float)) and cape > 1000:
            has_energy = True
            
        # 2. 垂直风切变判断动力条件
        has_shear = False
        if isinstance(shear, (int, float)) and shear > 12: # m/s
            has_shear = True
            
        # 3. K指数判断水汽和层结
        unstable = False
        if isinstance(k_index, (int, float)) and k_index > 35:
            unstable = True

        # 综合判定
        if has_energy and has_shear:
            risk_level = "高"
            risk_color = "danger"
            description = "具备强对流发生的潜势（高能量+强切变），需警惕超级单体风暴。"
            potential_hazards = ["短时强降水", "雷暴大风", "冰雹"]
            if cape > 2500:
                potential_hazards.append("极端雷暴")
                
        elif has_energy or (unstable and has_shear):
            risk_level = "中"
            risk_color = "warning"
            description = "存在一定的对流潜势，可能发展为雷阵雨天气。"
            potential_hazards = ["雷电", "短时阵雨"]
            if isinstance(cape, (int, float)) and cape > 1500:
                potential_hazards.append("局地小冰雹")
                
        elif unstable:
            risk_level = "较低"
            risk_color = "info"
            description = "层结不稳定，可能出现分散性阵雨或雷雨。"
            potential_hazards = ["阵雨"]

        return {
            "level": risk_level,
            "color": risk_color,
            "description": description,
            "hazards": potential_hazards
        }

    def _generate_ai_report(self, params: Dict, risk: Dict, layer_data: Dict = None) -> Dict:
        """调用AI生成分析报告"""
        
        # 构造提示词
        prompt = f"""
        请作为一名气象专家，根据以下探空数据，生成一份通俗易懂但内容丰富的大气分析报告。
        不要只关注强对流，请全面分析天气状况（如晴好、降水、降雪、能见度、体感等）。
        
        【宏观参数】：
        - CAPE (能量): {params.get('cape', '未知')} J/kg (值越大越不稳定)
        - CIN (抑制): {params.get('cin', '未知')} J/kg
        - K指数: {params.get('k_index', '未知')} (>35可能雷雨)
        - 抬升指数 (LI): {params.get('lifted_index', '未知')} (<0不稳定)
        - 0-6km风切变: {params.get('shear_06km', '未知')} m/s
        - 整层可降水量 (PW): {params.get('precip_water', '未知')} mm
        
        【分层实况】(用于判断温湿结构、降水相态等):
        {json.dumps(layer_data, indent=2, ensure_ascii=False) if layer_data else "暂无分层数据"}
        
        【系统评估】：
        - 风险等级: {risk.get('level')}
        - 潜在灾害: {', '.join(risk.get('hazards', []))}
        
        请输出JSON格式，包含以下字段：
        1. "professional": 专业分析（200字以内）。请分析：
           - 大气层结稳定性（稳定/条件不稳定/极不稳定）
           - 水汽条件（湿层厚度、整层水量）
           - 0℃层与降水相态（如果地面温度低，分析是雨/雪/雨夹雪）
           - 逆温层分析（如有，对能见度的影响）
           
        2. "simple": 通俗比喻（50字以内，例如"今天的大气像一块压缩饼干，非常稳定..."或"像一锅烧开的水..."）。
        
        3. "impacts": 行业与生活影响（每项一句话）：
           - "aviation": 航空（颠簸、积冰、能见度）
           - "agriculture": 农业（降水、光照、温湿条件）
           - "daily": 日常生活（洗晒指数、穿衣舒适度、出行建议）
        """
        
        try:
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }
            data = {
                "model": "deepseek-chat",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.7,
                "response_format": {"type": "json_object"}
            }
            
            response = requests.post(self.api_url, headers=headers, json=data, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                content = result['choices'][0]['message']['content']
                return json.loads(content)
            else:
                print(f"AI API Error: {response.status_code}")
                return self._get_fallback_report(params)
                
        except Exception as e:
            print(f"AI Analysis Failed: {e}")
            return self._get_fallback_report(params)

    def _get_fallback_report(self, params: Dict) -> Dict:
        """生成备用报告（当AI服务不可用时）"""
        cape = params.get('cape')
        is_stable = True
        
        if isinstance(cape, (int, float)) and cape > 500:
            is_stable = False
            
        return {
            "professional": "AI服务暂时不可用。根据参数判断，" + ("大气层结较为稳定。" if is_stable else "存在一定对流潜势。"),
            "simple": "今天天气" + ("比较平静。" if is_stable else "有点暴躁。"),
            "impacts": {
                "aviation": "请参考官方航空气象预报。",
                "agriculture": "关注天气变化。",
                "daily": "出行请查看最新短临预报。"
            }
        }
