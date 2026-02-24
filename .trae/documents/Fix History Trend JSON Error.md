问题根因已定位：Jinja 里用点号访问字典键时，`temp_data.values` 会优先解析为 Python 字典的内置方法 `dict.values`（一个 builtin_function_or_method），而不是我们传入的键 `"values"` 对应的列表，所以在 `|tojson` 时触发 `Object of type builtin_function_or_method is not JSON serializable`。

## 根因
- 模板 [history_trend.html](file:///d:/pythonProject/smart_weather/templates/history_trend.html) 中多处使用 `temp_data.values` / `precip_data.values`。
- 对 dict 来说，`.values` 是方法名，Jinja 会取到方法对象而非键值列表。

## 修改方案
1. 修改 [history_trend.html](file:///d:/pythonProject/smart_weather/templates/history_trend.html) ：把所有 `xxx.values / xxx.years / xxx.hot_days ...` 的点号访问改为下标访问：
   - `temp_data['years']`、`temp_data['values']`、`temp_data['trend_line']`、`temp_data['rate']`
   - `precip_data['years']`、`precip_data['values']`、`precip_data['rainy_days']`、`precip_data['rate']`
   - `extreme_data['years']`、`extreme_data['hot_days']`、`extreme_data['cold_days']`、`extreme_data['snow_days']`
2. 重启服务并打开 `http://127.0.0.1:5000/history/trend` 验证页面正常渲染三张 Plotly 图。

## 预期结果
- 不再出现 JSON 序列化 builtin_function_or_method 的报错。
- 趋势页能正常显示：气温趋势、降水与雨日、极端天气（高温/低温/降雪）三张图。