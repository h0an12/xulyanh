@echo off
chcp 65001 >nul
echo ============================================
echo   Smart Retail AI - Cai dat tu dong
echo ============================================
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo [LOI] Chua cai Python! Tai tai: https://www.python.org/downloads/
    pause & exit /b 1
)
echo [OK] Python da cai dat

echo.
echo [1/5] Tao virtual environment...
python -m venv venv
if errorlevel 1 (echo [LOI] Khong tao duoc venv & pause & exit /b 1)
call venv\Scripts\activate.bat

echo [2/5] Nang cap pip...
pip install --upgrade pip -q

echo [3/5] Cai dat thu vien...
pip install -r requirements.txt
if errorlevel 1 (echo [LOI] Cai dat that bai! Kiem tra ket noi mang. & pause & exit /b 1)

echo [4/5] Tao file cau hinh...
if not exist .env (
    copy .env.example .env >nul 2>&1
    echo [OK] Da tao file .env (dien TELEGRAM_TOKEN neu can)
) else (
    echo [OK] .env da ton tai - giu nguyen
)

echo [5/5] Kiem tra thu vien...
python -c "import cv2, flask, numpy; print('[OK] Core libs OK')"
python -c "from ultralytics import YOLO; print('[OK] YOLO OK')"
python -c "from deepface import DeepFace; print('[OK] DeepFace OK')"
python -c "import dotenv; print('[OK] dotenv OK')"

echo.
echo ============================================
echo   Cai dat hoan tat!
echo.
echo   Cach chay:
echo   Option A - Chi upload video (khong can camera):
echo     python app.py
echo     Truy cap: http://localhost:5000
echo.
echo   Option B - Dung camera truc tiep:
echo     python main.py
echo.
echo   Kiem tra camera truoc:
echo     run_camera_test.bat
echo ============================================
pause