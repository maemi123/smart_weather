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
    
    def get_advice(self, crop_name, stage, weather_summary, alerts=None):
        """
        获取农事建议
        
        参数:
        - crop_name: 作物名称 (如 "单季晚稻")
        - stage: 当前生长阶段 (如 "抽穗扬花期")
        - weather_summary: 未来几天天气简述
        - alerts: 相关的预警信息列表 (可选)
        """
        if not crop_name:
            crop_name = "未知作物"
        if not stage:
            stage = "未知阶段"
        if not weather_summary:
            weather_summary = "暂无天气摘要"
        if alerts is None:
            alerts = []

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

        try:
            payload = {
                "model": "deepseek-chat",
                "messages": [
                    {"role": "system", "content": "你是一个专业的农业气象助手，输出必须是纯净的JSON格式。"},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.7,
                "max_tokens": 800
            }
            
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {DEEPSEEK_API_KEY}"
            }
            
            response = requests.post(DEEPSEEK_API_URL, headers=headers, json=payload, timeout=20)
            
            if response.status_code == 200:
                result = response.json()
                content = result['choices'][0]['message']['content']
                
                # 尝试清理 markdown 代码块标记
                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0].strip()
                elif "```" in content:
                    content = content.split("```")[1].split("```")[0].strip()
                    
                advice_data = json.loads(content)
                return {"success": True, "data": advice_data}
            else:
                advice_data = self._fallback_advice(crop_name, stage, weather_summary, alerts)
                return {"success": True, "data": advice_data, "note": f"AI接口返回{response.status_code}，已降级为规则建议"}
                
        except Exception as e:
            advice_data = self._fallback_advice(crop_name, stage, weather_summary, alerts)
            return {"success": True, "data": advice_data, "note": f"AI调用异常({str(e)})，已降级为规则建议"}

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
