@echo off
chcp 65001 >nul
echo [Smart Retail] Khoi dong Camera Realtime Mode...
call venv\Scripts\activate.bat
python main.py
pause