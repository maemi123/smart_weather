@echo off
setlocal ENABLEDELAYEDEXPANSION

REM 切换到项目根目录
cd /d "%~dp0"

REM 使用项目虚拟环境的 Python，如果不存在则回退到系统 Python
set "PYTHON=%~dp0.venv\Scripts\python.exe"
if not exist "%PYTHON%" (
  echo [WARN] 未找到虚拟环境 .venv，使用系统 Python
  set "PYTHON=python"
)

REM 启动 Flask 应用（入口文件为 app.py，内部有 app.run(debug=True)）
echo [INFO] 正在启动 Flask 开发服务器...
"%PYTHON%" app.py

endlocal
