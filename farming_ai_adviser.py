# farming_ai_adviser.py
# 农事AI顾问：基于 LLM 生成个性化建议

import os
import requests
import json

# 尝试从环境变量获取 API Key，如果没有则使用默认值或空
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"

class FarmingAIAdviser:
    """基于 DeepSeek 的智能农事顾问"""
    
    def _call_llm(self, prompt, max_tokens=800):
        """调用 LLM API 的通用方法"""
        try:
            payload = {
                "model": "deepseek-chat",
                "messages": [
                    {"role": "system", "content": "你是一个专业的农业气象助手。"},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.7,
                "max_tokens": max_tokens
            }
            
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {DEEPSEEK_API_KEY}"
            }
            
            response = requests.post(DEEPSEEK_API_URL, headers=headers, json=payload, timeout=20)
            
            if response.status_code == 200:
                result = response.json()
                return result['choices'][0]['message']['content']
            return None
        except Exception as e:
            print(f"LLM调用失败: {e}")
            return None

    def get_advice(self, crop_name, stage, weather_summary, alerts=None):
        """获取农事建议"""
        if not crop_name: crop_name = "未知作物"
        if not stage: stage = "未知阶段"
        if not weather_summary: weather_summary = "暂无天气摘要"
        if alerts is None: alerts = []

        if not DEEPSEEK_API_KEY:
            advice_data = self._fallback_advice(crop_name, stage, weather_summary, alerts)
            return {"success": True, "data": advice_data, "note": "未配置DEEPSEEK_API_KEY，已使用规则引擎生成建议"}
            
        # 构建 Prompt
        alert_text = "无特殊预警"
        if alerts and len(alerts) > 0:
            alert_text = "; ".join([f"{a['title']}: {a['message']}" for a in alerts])
            
        prompt = f"""
你是一位经验丰富的浙江农业专家。请根据以下信息为农民生成一份简明扼要的农事建议：

【基础信息】
- 作物：{crop_name}
- 当前阶段：{stage}
- 未来3-7天天气趋势：{weather_summary}
- 系统检测到的风险/提示：{alert_text}

【任务要求】
请输出一段 JSON 格式的建议，包含以下字段：
1. "summary": 一句话总结（30字以内，通俗易懂）。
2. "operations": 推荐的农事操作列表（如施肥、灌溉、打药等），每项包含 "action"（操作名）和 "detail"（具体做法，如用量、时间）。
3. "risks": 需要重点防范的气象风险及应对措施。
4. "tips": 给农民的一句贴心叮嘱。

请确保建议具体、可操作，并符合浙江地区的农业生产习惯。不要输出 JSON 以外的任何内容。
"""
        content = self._call_llm(prompt)
        
        if content:
            # 尝试清理 markdown 代码块标记
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
                
            try:
                advice_data = json.loads(content)
                return {"success": True, "data": advice_data}
            except:
                pass

        advice_data = self._fallback_advice(crop_name, stage, weather_summary, alerts)
        return {"success": True, "data": advice_data, "note": "AI返回解析失败或调用失败，已降级"}

    def generate_dashboard_summary(self, alerts, forecast_list, crop_status):
        """生成全域农情研判"""
        temps_avg = [d.get('temp_avg') for d in forecast_list if d.get('temp_avg') is not None]
        temps_min = [d.get('temp_min') for d in forecast_list if d.get('temp_min') is not None]
        temps_max = [d.get('temp_max') for d in forecast_list if d.get('temp_max') is not None]
        precip_total = sum([d.get('precip', 0) or 0 for d in forecast_list])
        precip_eff_total = sum([d.get('precip_eff', 0) or 0 for d in forecast_list])
        et0_total = sum([d.get('et0', 0) or 0 for d in forecast_list])
        wet_days = sum(1 for d in forecast_list if (d.get('precip', 0) or 0) >= 5)
        deficit_days = sum(1 for d in forecast_list if (d.get('precip_eff', 0) or 0) < 0)
        
        # 补充辐射和土壤湿度统计
        radiations = [d.get('radiation', 0) or 0 for d in forecast_list]
        radiation_avg = sum(radiations) / len(radiations) if radiations else 0
        soil_moistures = [d.get('soil_moisture', 0) or 0 for d in forecast_list]
        soil_moisture_avg = sum(soil_moistures) / len(soil_moistures) if soil_moistures else 0

        temp_summary = "暂无温度数据"
        if temps_avg and temps_min and temps_max:
            temp_summary = f"{min(temps_min):.1f}~{max(temps_max):.1f}℃，均温约{sum(temps_avg)/len(temps_avg):.1f}℃"

        alert_count = len(alerts)
        high_risk = len([a for a in alerts if a['level'] == 'high'])
        medium_risk = sum(1 for a in alerts if a.get('level') == 'medium') if alerts else 0

        top_alerts = "; ".join([f"{a.get('crop_name','')}·{a.get('title','')}" for a in alerts[:5]]) if alerts else "暂无显著风险"

        crop_scores = []
        for c in (crop_status or []):
            score = c.get('score', 0)
            crop_scores.append((score, c.get('name', ''), c.get('stage', '')))
        crop_scores_sorted = sorted(crop_scores, key=lambda x: x[0])
        worst_crops = "、".join([f"{c[1]}({c[0]}分)" for c in crop_scores_sorted[:2] if c[1]]) if crop_scores_sorted else "暂无评分"
        best_crops = "、".join([f"{c[1]}({c[0]}分)" for c in crop_scores_sorted[-2:] if c[1]]) if crop_scores_sorted else "暂无评分"

        analysis_points = []
        
        # 1. 温度分析
        temp_analysis = "气温适宜"
        if max(temps_max) > 35:
            temp_analysis = "存在高温热害风险"
        elif min(temps_min) < 5:
            temp_analysis = "需防范低温冷害"
        elif max(temps_max) - min(temps_min) > 15:
            temp_analysis = "昼夜温差大，利于积累但需防感冒"
            
        analysis_points.append(f"温度：未来7天{temp_summary}。{temp_analysis}。")

        # 2. 降水与水分分析
        precip_analysis = "水分平衡"
        if precip_eff_total < -10:
            precip_analysis = "水分亏缺明显，需安排灌溉"
        elif precip_eff_total > 50:
            precip_analysis = "降水充沛，低洼田块注意排涝"
        elif wet_days >= 3:
            precip_analysis = "阴雨天气较多，注意病害防控"
            
        analysis_points.append(f"水分：累计降水{precip_total:.1f}mm，净有效降水{precip_eff_total:.1f}mm。{precip_analysis}。")
        
        # 3. 辐射与墒情分析
        rad_analysis = "光照充足"
        if radiation_avg < 100: # 假设阈值
            rad_analysis = "光照不足，影响光合作用"
        
        soil_analysis = "墒情适宜"
        if soil_moisture_avg < 0.2: # 假设阈值
            soil_analysis = "土壤偏干"
        elif soil_moisture_avg > 0.4:
            soil_analysis = "土壤偏湿"
            
        analysis_points.append(f"环境：平均辐射{radiation_avg:.1f}W/m²，{rad_analysis}；平均土壤体积含水量{soil_moisture_avg:.2f}m³/m³，{soil_analysis}。")

        # 4. 风险分析
        if alerts:
            analysis_points.append(f"风险：高风险{high_risk}条，中风险{medium_risk}条。主要关注：{top_alerts}。")
        else:
            analysis_points.append("风险：未来7天无显著气象灾害预警，生产安全。")

        # 5. 适宜度分析
        analysis_points.append(f"适宜度：{best_crops}生长条件较好；{worst_crops}受限明显，需重点照看。")
        
        # 生成动态结论
        conclusions = []
        if high_risk > 0:
            conclusions.append("优先应对气象灾害风险")
        if precip_eff_total < -15 or soil_moisture_avg < 0.15:
            conclusions.append("重点解决水分亏缺问题")
        elif wet_days > 4 or precip_eff_total > 80:
            conclusions.append("严防田间积水与高湿病害")
        if min(temps_min) < 5:
            conclusions.append("做好保温防冻措施")
        
        conclusion = "，".join(conclusions) + "。" if conclusions else "气象条件总体平稳，建议按常规农事节奏开展生产。"
        action = "关注天气变化，合理安排农事。"
        if "水分" in conclusion:
            action = "利用早晚时段进行灌溉，避开高温时段。"
        elif "病害" in conclusion:
             action = "抢抓降雨间隙喷施保护性杀菌剂，疏通沟渠。"

        if not DEEPSEEK_API_KEY:
            analysis_list = "".join([f"<li>{p}</li>" for p in analysis_points])
            return f"""
            <div class="alert alert-info border-0 shadow-sm">
                <h5 class="alert-heading"><i class="fas fa-clipboard-list me-2"></i>全域农情简报</h5>
                <p class="mb-2">数据输入来源：未来7天逐日预报 + 作物适宜度评分 + 风险预警统计。</p>
                <ul class="mb-2">{analysis_list}</ul>
                <p class="mb-1">结论：{conclusion}</p>
                <p class="mb-0 fw-bold text-dark mt-2">{action}</p>
            </div>
            """

        data_pack = {
            "temp_summary": temp_summary,
            "precip_total": round(precip_total, 1),
            "et0_total": round(et0_total, 1),
            "precip_eff_total": round(precip_eff_total, 1),
            "wet_days": wet_days,
            "deficit_days": deficit_days,
            "radiation_avg": round(radiation_avg, 1),
            "soil_moisture_avg": round(soil_moisture_avg, 1),
            "alert_count": alert_count,
            "high_risk": high_risk,
            "medium_risk": medium_risk,
            "top_alerts": top_alerts,
            "best_crops": best_crops,
            "worst_crops": worst_crops
        }

        prompt = f"""
请作为浙江省首席农业气象专家，为全省农业生产生成一份“全域农情研判”。你必须展示分析过程和直观结论，避免套话。

【数据输入】
温度：{data_pack['temp_summary']}
降水：累计{data_pack['precip_total']}mm，ET0累计{data_pack['et0_total']}mm，净有效降水{data_pack['precip_eff_total']}mm
辐射与土壤：短波辐射均值{data_pack['radiation_avg']} W/m²，表层土壤湿度均值{data_pack['soil_moisture_avg']}%
时段分布：中到大雨日{data_pack['wet_days']}天，水分亏缺日{data_pack['deficit_days']}天
风险预警：总数{data_pack['alert_count']}条（高{data_pack['high_risk']}，中{data_pack['medium_risk']}）；{data_pack['top_alerts']}
适宜度对比：较好{data_pack['best_crops']}；偏弱{data_pack['worst_crops']}

【输出要求】
1. 输出HTML文本（不包含 ```html 标记），结构为<div class="alert alert-primary border-0 shadow-sm" style="background-color: #f0f7ff;">。
2. 包含标题：<h5 class="alert-heading text-primary"><i class="fas fa-bullhorn me-2"></i>全域农情研判</h5>。
3. 包含“分析过程”列表（<ul>），逐条解释温度、降水、辐射、土壤、风险和适宜度的判断依据。
4. 包含“直观结论”段落（<p>），总结对主要作物的影响与关键风险。
5. 结尾用 <p class="mb-0 fw-bold text-dark mt-2"> 给出1-2条行动要点。
6. 语气专业、权威、信息密度高。
"""
        content = self._call_llm(prompt)
        if content:
            if "```html" in content:
                content = content.split("```html")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            return content

        analysis_list = "".join([f"<li>{p}</li>" for p in analysis_points])
        if precip_eff_total <= -5:
            conclusion = f"净有效降水{precip_eff_total:.1f}mm，水分偏紧，需防叶片萎蔫与生长放缓。"
            action = "优先保障高需水作物灌溉与保水，避开高温时段浇水。"
        elif precip_eff_total >= 10:
            conclusion = f"净有效降水{precip_eff_total:.1f}mm，田间偏湿，病害风险上升。"
            action = "抓住短暂无雨时段开展作业并加强通风排湿。"
        else:
            conclusion = f"净有效降水{precip_eff_total:.1f}mm，水分基本平衡，管理以稳为主。"
            action = "关注未来两天温度起伏，适时调整灌溉与施肥节奏。"
        return f"""
        <div class="alert alert-warning border-0 shadow-sm">
            <h5 class="alert-heading text-dark"><i class="fas fa-bullhorn me-2"></i>全域农情研判</h5>
            <p class="mb-2">当前AI生成失败，已切换为数据化简报。</p>
            <ul class="mb-2">{analysis_list}</ul>
            <p class="mb-1">结论：{conclusion}</p>
            <p class="mb-0 fw-bold text-dark mt-2">行动要点：{action}</p>
        </div>
        """

    def _fallback_advice(self, crop_name, stage, weather_summary, alerts):
        risks = []
        operations = []

        for a in alerts[:5]:
            title = a.get("title", "")
            msg = a.get("message", "")
            action = a.get("action", "")
            if title or msg:
                risks.append(f"{title}：{msg}（建议：{action}）" if action else f"{title}：{msg}")

        weather_lower = str(weather_summary)
        if "降水" in weather_lower or "雨" in weather_lower:
            operations.append({"action": "安排农事", "detail": "有降水迹象时，尽量避开喷药和追肥，优先做排水沟、清园等不受雨影响的工作。"})
        else:
            operations.append({"action": "安排农事", "detail": "选择风小、无雨的白天进行施肥/喷药等作业，提前准备工具与物资。"})

        if "采摘" in stage:
            operations.append({"action": "采摘管理", "detail": "优先选择无雨时段采收，雨后适当晾干再入筐，减少机械损伤。"})
        if "萌芽" in stage or "开花" in stage:
            operations.append({"action": "防寒防护", "detail": "夜间低温时段注意覆盖保温或熏烟防霜，白天适当通风见光。"})
        if "越冬" in stage or "休闲" in stage:
            operations.append({"action": "田间整理", "detail": "检查沟渠与田埂，修整田块，备足薄膜/稻草等防寒物资，为春季管理做准备。"})

        if not risks:
            risks.append("暂无明显气象灾害信号，建议关注近3天温度与降水变化。")

        tips = "建议每天固定时段查看预警更新，关键操作尽量留出半天缓冲。"
        summary = f"{crop_name}{stage}阶段：以“避险+抓窗口”为主。"

        return {"summary": summary[:30], "operations": operations[:4], "risks": risks[:4], "tips": tips}

# 单例
ai_adviser = FarmingAIAdviser()
