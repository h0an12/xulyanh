<h2 align="center">
    <a href="https://dainam.edu.vn/vi/khoa-cong-nghe-thong-tin">
    🎓 Faculty of Information Technology (DaiNam University)
    </a>
</h2>
 
<h2 align="center">
    ỨNG DỤNG SMART RETAIL AI - NHẬN DIỆN KHÁCH HÀNG VÀ GỢI Ý SẢN PHẨM
</h2>

<div align="center">
    <p align="center">
        <img alt="AIoTLab Logo" width="170" src="https://github.com/user-attachments/assets/711a2cd8-7eb4-4dae-9d90-12c0a0a208a2" />
        <img alt="AIoTLab Logo" width="180" src="https://github.com/user-attachments/assets/dc2ef2b8-9a70-4cfa-9b4b-f6c2f25f1660" />
        <img alt="DaiNam University Logo" width="200" src="https://github.com/user-attachments/assets/77fe0fd1-2e55-4032-be3c-b1a705a1b574" />
    </p>

[![AIoTLab](https://img.shields.io/badge/AIoTLab-green?style=for-the-badge)](https://www.facebook.com/DNUAIoTLab)
[![Faculty of Information Technology](https://img.shields.io/badge/Faculty%20of%20Information%20Technology-blue?style=for-the-badge)](https://dainam.edu.vn/vi/khoa-cong-nghe-thong-tin)
[![DaiNam University](https://img.shields.io/badge/DaiNam%20University-orange?style=for-the-badge)](https://dainam.edu.vn)

</div>

---

# 1. Giới thiệu hệ thống

Hệ thống **Smart Retail AI** là ứng dụng sử dụng trí tuệ nhân tạo nhằm phát hiện, phân tích khách hàng (giới tính, độ tuổi) và đề xuất sản phẩm phù hợp kèm vị trí kệ trong siêu thị theo thời gian thực.

Dự án được xây dựng bằng các công nghệ hiện đại:
- **YOLOv8** để phát hiện người trong khung hình.
- **DeepFace** để phân tích giới tính và độ tuổi từ khuôn mặt.
- **CentroidTracker** để theo dõi khách hàng qua các frame.
- **Flask** cung cấp giao diện web và API.
- **Telegram Bot** gửi thông báo kèm ảnh khi phát hiện khách hàng mới.
- **SQLite** lưu trữ dữ liệu khách hàng và lịch sử giao dịch.

Hệ thống gồm 2 chế độ hoạt động chính:

1. **Chế độ Camera Realtime (`main.py`)**
   - Kết nối trực tiếp với camera (USB hoặc IP).
   - Nhận diện và phân tích khách hàng ngay khi xuất hiện.
   - Hiển thị kết quả trực tiếp trên cửa sổ OpenCV và Web Dashboard.
   - Gửi thông báo Telegram kèm ảnh chụp khuôn mặt khách hàng.

2. **Chế độ Upload Video (`app.py`)**
   - Cho phép người dùng tải video lên để phân tích.
   - Xử lý toàn bộ video, nhận diện tất cả khách hàng xuất hiện.
   - Gửi thông báo Telegram cho từng khách hàng được phát hiện.
   - Phù hợp để phân tích dữ liệu từ camera an ninh, video ghi hình.

---

# 2. Công nghệ sử dụng

- **Python 3.8+**
- **YOLOv8** (Ultralytics) - Phát hiện người
- **DeepFace** - Phân tích giới tính & độ tuổi
- **OpenCV** - Xử lý ảnh và video
- **Flask** - Web server & API
- **SQLite3** - Cơ sở dữ liệu
- **Telegram Bot API** - Gửi thông báo
- **HTML/CSS/JavaScript** - Giao diện web (Dashboard, Upload, Realtime)

---

# 3. Hình ảnh các chức năng

## 1. Giao diện Dashboard thống kê khách hàng

<img width="1920" height="1080" alt="Screenshot (114)" src="https://github.com/user-attachments/assets/9f0b4675-1593-480c-9977-98fd51ddf8d8" />

*Biểu đồ phân bố giới tính, độ tuổi, lượt khách theo giờ*

---

## 2. Gợi ý sản phẩm kèm vị trí kệ theo thời gian thực

<img width="1405" height="646" alt="kh" src="https://github.com/user-attachments/assets/ba3cd357-d013-4b17-b06d-df3ba0592849" />

*Hiển thị ngay sản phẩm phù hợp và vị trí kệ khi phát hiện khách hàng*

---

## 3. Thông báo Telegram kèm ảnh khách hàng

<img width="559" height="754" alt="screenshot_1780579787" src="https://github.com/user-attachments/assets/53a7703b-39c1-4643-8926-bafcaa0a50ca" />


*Gửi thông báo đầy đủ thông tin: ID, giới tính, độ tuổi, sản phẩm gợi ý, khuyến mãi và ảnh chụp khuôn mặt*

---

## 4. Upload video và phân tích

<img width="1690" height="912" alt="ip" src="https://github.com/user-attachments/assets/d4f1304b-bfa2-456b-a15e-22173f3824a3" />

*Upload video, AI tự động phân tích từng khung hình và hiển thị kết quả realtime*

---

<h2>4. Hướng dẫn cài đặt và sử dụng</h2>

<h3>Bước 1: Clone project</h3>

```bash
git clone https://github.com/YourUsername/smart-retail-ai.git
cd smart-retail-ai
```
<h3>Bước 2: Chạy file cài đặt tự động (Windows)</h3>
```bash
setup.bat
```bash
Hoặc cài thủ công:
```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```bash
<h3>Bước 3: Cấu hình Telegram (tùy chọn)</h3>
```bash

```
<h3>Bước 4: Chạy hệ thống</h3>
Chế độ Camera Realtime:
```bash
python main.py
```
Chế độ Upload Video (Web Server):
```bash
python app.py
```
<h3>Bước 5: Truy cập giao diện web</h3>
Mở trình duyệt và truy cập: http://localhost:5000

Trang chủ: Hiển thị camera feed và gợi ý realtime

Dashboard: /dashboard - Thống kê biểu đồ

Upload video: /upload - Phân tích video
# 5. Cấu trúc thư mục

```text
smart-retail-ai/
├── app.py
├── main.py
├── config.py
├── database.py
├── detector.py
├── tracker.py
├── recommender.py
├── telegram_bot.py
├── camera_shared.py
├── requirements.txt
├── setup.bat
├── run_app.bat
├── run_camera.bat
├── .env
├── templates/
├── captures/
├── uploads/
├── customer_interactions.csv
└── transaction_history.csv
```

# 6. API Endpoints

- GET /
- GET /dashboard
- GET /upload
- POST /upload
- GET /video_stream/<video_id>
- GET /api/stats
- GET /api/stats/today
- GET /api/customers
- GET /api/telegram/test
- GET /api/check_captures

# 7. Quy trình hoạt động

Camera/Video → YOLOv8 → DeepFace → Tracker → Recommendation → SQLite → Dashboard/Telegram

# 8. Kết quả đạt được

- Nhận diện khách hàng realtime
- Phân tích độ tuổi, giới tính
- Gợi ý sản phẩm
- Dashboard thống kê
- Telegram thông báo

# 9. Hướng phát triển

- Nhận diện cảm xúc
- Recommendation bằng ML
- Hỗ trợ nhiều camera
- Cloud Deployment

# 10. Thông tin liên hệ

Tác giả: [Lê Bá Hoan]
GitHub: https://github.com/h0an12
Email: lebahoan1812@gmail.com
