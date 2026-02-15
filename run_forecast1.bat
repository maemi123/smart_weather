@echo off
cd /d "D:\pythonProject\smart_weather"
call venv\Scripts\activate
python openmeteo_collector1.py
pause