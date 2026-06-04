@echo off
chcp 65001 >nul
echo [Smart Retail] Khoi dong Web Server (Upload Video Mode)...
call venv\Scripts\activate.bat
python app.py
pause