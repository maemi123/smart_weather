# 修复 UnboundLocalError 计划

我已确认问题的根源：在 `app.py` 的 `history_yearly` 函数中，我在构造 `ai_prompt` 时（第 818 行）引用了 `comfort_data` 变量，但此时 `comfort_data` 还没有被定义。

`comfort_data` 的定义目前在第 847 行，也就是在构造 `ai_prompt` 之后。这就导致了 `UnboundLocalError: cannot access local variable 'comfort_data' where it is not associated with a value`。

## 修复步骤

1.  **移动代码**：将 `comfort_data` 的获取逻辑（第 847-850 行）向上移动，放置在构造 `ai_prompt` 之前（即第 811 行之前）。
2.  **验证**：确保在 `ai_prompt` 中引用 `comfort_data` 时，它已经被正确赋值。

## 具体操作

我将使用 `SearchReplace` 工具，将 `comfort_data` 的获取逻辑提前到 `ai_prompt` 构造之前。

请确认是否执行此修复？