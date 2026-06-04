# Smart Retail AI System - Hướng dẫn cài đặt

## Cài đặt thư viện

```bash
pip install opencv-python-headless flask flask-cors requests numpy
```

## Cấu trúc thư mục

```
smart-retail-ai/
│
├── smart_retail_system.py    ← Backend chính (Python)
├── dashboard.html            ← Web Dashboard
├── retail_data.db            ← Tự tạo khi chạy (SQLite)
│
├── [Tùy chọn - Mô hình DNN]
│   ├── gender_deploy.prototxt
│   ├── gender_net.caffemodel
│   ├── age_deploy.prototxt
│   └── age_net.caffemodel
```

## Tải mô hình DNN (để tăng độ chính xác)

```bash
# Tải về từ repo GilLevi/AgeGenderDeepLearning
wget https://github.com/GilLevi/AgeGenderDeepLearning/raw/master/gender_net.caffemodel
wget https://raw.githubusercontent.com/GilLevi/AgeGenderDeepLearning/master/gender_deploy.prototxt
wget https://github.com/GilLevi/AgeGenderDeepLearning/raw/master/age_net.caffemodel
wget https://raw.githubusercontent.com/GilLevi/AgeGenderDeepLearning/master/age_deploy.prototxt
```

## Chạy hệ thống

```bash
python smart_retail_system.py
```

Sau đó mở dashboard.html trong trình duyệt.

## API Endpoints

| Endpoint | Mô tả |
|---|---|
| GET /api/stats | Thống kê tổng hợp |
| GET /api/video_feed | Stream video MJPEG |
| GET /health | Kiểm tra server |

## Telegram

Đã cấu hình sẵn TOKEN và CHAT_ID trong file Python.
Hệ thống gửi thông báo tự động khi phát hiện khách mới.
