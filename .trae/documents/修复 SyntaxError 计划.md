# 修复 SyntaxError 计划

我已确认问题的根源：在 `app.py` 中，`history_yearly` 函数的异常处理块（`except Exception as e`）似乎被错误地放置到了 `api_wind_rose` 函数的下方，或者是因为缩进/结构问题导致的语法错误。

具体来看，`app.py` 的第 847 行是 `@app.route('/api/wind_rose')`，这之前是 `history_yearly` 函数。但在 `history_yearly` 函数内部，似乎缺少了一个 `except` 块来闭合前面的 `try` 块（或者 `except` 块放错了位置）。

仔细检查代码：
*   `history_yearly` 函数开始于第 768 行。
*   第 770 行有一个 `try:`。
*   在第 846 行 `return render_template(...)` 结束了正常的逻辑。
*   紧接着第 847 行是 `@app.route('/api/wind_rose')`。
*   而 `history_yearly` 的 `except` 块似乎出现在了更后面（第 874 行 `except Exception as e:`），这显然是不对的。`api_wind_rose` 函数被插入到了 `history_yearly` 的 `try...except` 结构中间。

此外，`api_wind_rose` 函数内部（第 848-872 行）也有一个 `try...except` 块，但它的结构看起来是完整的。

**真正的错误结构是这样的：**

```python
def history_yearly(year):
    try:
        # ... 代码 ...
        return render_template(...)

@app.route('/api/wind_rose')  <-- 这里插入了新函数，打破了 history_yearly 的 try 块
def api_wind_rose():
    # ...
    return ...

    except Exception as e:  <-- 这个 except 变成了孤儿，因为它原本属于 history_yearly
        # ...
```

## 修复步骤

1.  **移动代码**：将 `api_wind_rose` 函数的定义移动到 `history_yearly` 函数的完整定义之后（包括其 `except` 块）。
2.  **验证结构**：确保每个函数都有完整的 `try...except` 结构，且互不嵌套。

## 具体操作

我将使用 `SearchReplace` 工具，将 `api_wind_rose` 函数整体剪切，并粘贴到 `history_yearly` 函数的 `except` 块之后。

请确认是否执行此修复？