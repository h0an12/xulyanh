# ============================================================
#  telegram_bot.py  –  Gửi thông báo Telegram KÈM ẢNH
#  Hỗ trợ: Camera Realtime + Upload Video
# ============================================================
import os
import requests
from datetime import datetime
from config import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, CAPTURES_DIR

# Màu cho console
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'

print(f"{BLUE}{'='*60}{RESET}")
print(f"{BLUE}  TELEGRAM BOT INITIALIZATION{RESET}")
print(f"{BLUE}{'='*60}{RESET}")
print(f"[Telegram] Token: {TELEGRAM_TOKEN[:10]}...{TELEGRAM_TOKEN[-5:] if TELEGRAM_TOKEN and len(TELEGRAM_TOKEN) > 15 else 'None'}")
print(f"[Telegram] Chat ID: {TELEGRAM_CHAT_ID}")
print(f"[Telegram] Captures dir: {os.path.abspath(CAPTURES_DIR)}")
print(f"{BLUE}{'='*60}{RESET}\n")


def find_image_path(image_path):
    """Tìm đường dẫn tuyệt đối của ảnh"""
    if not image_path:
        return None
    
    # Nếu đã là đường dẫn tuyệt đối và tồn tại
    if os.path.isabs(image_path) and os.path.exists(image_path):
        return image_path
    
    # Các đường dẫn cần thử
    paths_to_try = [
        image_path,
        os.path.abspath(image_path),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), image_path),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), CAPTURES_DIR, os.path.basename(image_path)),
        os.path.join(os.getcwd(), image_path),
        os.path.join(os.getcwd(), CAPTURES_DIR, os.path.basename(image_path)),
        os.path.join(CAPTURES_DIR, os.path.basename(image_path)),
    ]
    
    for path in paths_to_try:
        if path and os.path.exists(path):
            print(f"[Telegram] ✅ Tìm thấy ảnh: {path}")
            return path
    
    return None


def compress_image_if_needed(image_path, max_size_mb=9):
    """Nén ảnh nếu quá lớn"""
    try:
        file_size = os.path.getsize(image_path)
        if file_size <= max_size_mb * 1024 * 1024:
            return image_path
        
        print(f"[Telegram] 🔄 Nén ảnh ({file_size/1024/1024:.1f}MB -> <{max_size_mb}MB)...")
        from PIL import Image
        
        img = Image.open(image_path)
        # Tính tỷ lệ nén
        ratio = (max_size_mb * 1024 * 1024 / file_size) ** 0.5
        new_size = (int(img.width * ratio), int(img.height * ratio))
        img.thumbnail(new_size, Image.LANCZOS)
        
        compressed_path = image_path.replace('.jpg', '_compressed.jpg').replace('.jpeg', '_compressed.jpg')
        img.save(compressed_path, 'JPEG', quality=75, optimize=True)
        
        print(f"[Telegram] ✅ Nén thành công: {os.path.getsize(compressed_path)/1024/1024:.1f}MB")
        return compressed_path
    except Exception as e:
        print(f"[Telegram] ⚠️ Không nén được: {e}")
        return image_path


def send_telegram_photo(image_path, caption):
    """Gửi ảnh lên Telegram"""
    if not TELEGRAM_TOKEN or TELEGRAM_TOKEN == "":
        print("[Telegram] ❌ Chưa cấu hình TELEGRAM_TOKEN")
        return False
    
    # Tìm ảnh
    abs_path = find_image_path(image_path)
    if not abs_path:
        print(f"[Telegram] ❌ Không tìm thấy ảnh: {image_path}")
        return False
    
    # Kiểm tra kích thước
    file_size = os.path.getsize(abs_path)
    print(f"[Telegram] 📸 Kích thước ảnh: {file_size/1024:.1f} KB")
    
    if file_size == 0:
        print("[Telegram] ❌ File rỗng!")
        return False
    
    # Nén nếu cần
    send_path = compress_image_if_needed(abs_path)
    
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
        
        with open(send_path, 'rb') as f:
            files = {'photo': f}
            data = {
                'chat_id': TELEGRAM_CHAT_ID,
                'caption': caption,
                'parse_mode': 'HTML'
            }
            response = requests.post(url, files=files, data=data, timeout=30)
        
        # Xóa file nén tạm
        if send_path != abs_path and os.path.exists(send_path):
            os.remove(send_path)
        
        if response.status_code == 200:
            print(f"[Telegram] {GREEN}✅ ẢNH GỬI THÀNH CÔNG!{RESET}")
            return True
        else:
            print(f"[Telegram] {RED}❌ Lỗi HTTP {response.status_code}{RESET}")
            print(f"[Telegram] Response: {response.text[:200]}")
            return False
            
    except requests.exceptions.Timeout:
        print("[Telegram] ⏰ Timeout khi gửi ảnh")
        return False
    except Exception as e:
        print(f"[Telegram] ❌ Lỗi: {e}")
        return False


def send_telegram_message(text):
    """Gửi tin nhắn text"""
    if not TELEGRAM_TOKEN:
        return False
    
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        data = {
            'chat_id': TELEGRAM_CHAT_ID,
            'text': text,
            'parse_mode': 'HTML'
        }
        response = requests.post(url, json=data, timeout=15)
        
        if response.status_code == 200:
            print(f"[Telegram] {GREEN}✅ Tin nhắn gửi thành công{RESET}")
            return True
        else:
            print(f"[Telegram] {RED}❌ Lỗi HTTP {response.status_code}{RESET}")
            return False
    except Exception as e:
        print(f"[Telegram] ❌ Lỗi: {e}")
        return False


def notify_customer(track_id, gender, age_group, products, promotion, image_path="", timestamp=""):
    """Gửi thông báo khi phát hiện khách hàng mới - CÓ ẢNH"""
    
    print(f"\n{BLUE}{'='*60}{RESET}")
    print(f"{BLUE}📤 GỬI TELEGRAM CHO KHÁCH #{track_id}{RESET}")
    print(f"{BLUE}{'='*60}{RESET}")
    
    # Kiểm tra cấu hình
    if not TELEGRAM_TOKEN or TELEGRAM_TOKEN == "":
        print(f"{RED}[Telegram] ❌ Chưa cấu hình TELEGRAM_TOKEN{RESET}")
        print("[Telegram] 📝 Tạo file .env với nội dung:")
        print("   TELEGRAM_TOKEN=your_bot_token")
        print("   TELEGRAM_CHAT_ID=your_chat_id")
        return False
    
    # Bỏ qua nếu không rõ
    if gender == "Không rõ" or age_group == "Không rõ":
        print(f"{YELLOW}[Telegram] ⚠️ Bỏ qua: {gender}/{age_group}{RESET}")
        return False
    
    # Thời gian
    if not timestamp:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Format sản phẩm
    product_lines = []
    for i, p in enumerate(products[:3], 1):
        if isinstance(p, (tuple, list)):
            name = p[0]
            shelf = p[1] if len(p) > 1 else "Kệ A1"
        elif isinstance(p, dict):
            name = p.get('name', str(p))
            shelf = p.get('shelf', 'Kệ A1')
        else:
            name = str(p)
            shelf = "Kệ A1"
        product_lines.append(f"   {i}. {name} → {shelf}")
    
    product_text = "\n".join(product_lines) if product_lines else "   📝 Đang cập nhật..."
    
    # Tạo nội dung tin nhắn
    gender_icon = "👨" if gender == "Nam" else "👩"
    gender_text = "Nam" if gender == "Nam" else "Nữ"
    
    message = (
        f"🛒 <b>KHÁCH HÀNG MỚI PHÁT HIỆN</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🔹 <b>Mã số:</b> #{track_id}\n"
        f"🔹 <b>Giới tính:</b> {gender_icon} {gender_text}\n"
        f"🔹 <b>Độ tuổi:</b> {age_group}\n"
        f"🔹 <b>Thời gian:</b> {timestamp}\n"
        f"\n🎁 <b>🎯 GỢI Ý SẢN PHẨM</b>\n"
        f"{product_text}\n"
        f"\n💝 <b>🎉 KHUYẾN MÃI ĐẶC BIỆT</b>\n"
        f"   ✨ {promotion}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🤖 <i>Smart Retail AI System</i>"
    )
    
    print(f"[Telegram] Nội dung tin nhắn:")
    print(f"{YELLOW}{message}{RESET}\n")
    
    # KIỂM TRA VÀ GỬI ẢNH
    if image_path and image_path.strip():
        print(f"[Telegram] 📸 Đường dẫn ảnh: {image_path}")
        
        # Kiểm tra file tồn tại
        if os.path.exists(image_path):
            file_size = os.path.getsize(image_path)
            print(f"[Telegram] 📸 Kích thước ảnh: {file_size/1024:.1f} KB")
            return send_telegram_photo(image_path, message)
        else:
            print(f"{RED}[Telegram] ❌ File ảnh KHÔNG TỒN TẠI!{RESET}")
            print(f"[Telegram] 📝 Gửi tin nhắn text thay thế...")
            return send_telegram_message(message)
    else:
        print(f"{YELLOW}[Telegram] 📝 Không có ảnh đính kèm, gửi text{RESET}")
        return send_telegram_message(message)


def send_test_notification():
    """Gửi thông báo test"""
    print(f"\n{BLUE}{'='*60}{RESET}")
    print(f"{BLUE}  📡 GỬI TEST TELEGRAM{RESET}")
    print(f"{BLUE}{'='*60}{RESET}")
    
    # Test tin nhắn
    print("\n📤 Test 1: Gửi tin nhắn text...")
    result1 = send_telegram_message(
        "🤖 <b>Smart Retail AI System</b>\n\n"
        "✅ Hệ thống đã khởi động thành công!\n"
        "📸 Sẽ gửi ảnh kèm theo khi phát hiện khách hàng mới.\n\n"
        f"🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )
    
    # Test ảnh
    print("\n📤 Test 2: Tạo và gửi ảnh test...")
    try:
        import cv2
        import numpy as np
        
        # Tạo thư mục
        os.makedirs(CAPTURES_DIR, exist_ok=True)
        
        # Tạo ảnh test
        img = np.ones((400, 600, 3), dtype=np.uint8) * 25
        cv2.rectangle(img, (20, 20), (580, 380), (91, 82, 245), 3)
        cv2.putText(img, "SMART RETAIL AI", (120, 100), 
                    cv2.FONT_HERSHEY_SIMPLEX, 1.2, (91, 82, 245), 3)
        cv2.putText(img, "Telegram Integration Test", (100, 170),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 207, 168), 2)
        cv2.putText(img, f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", (100, 250),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1)
        cv2.putText(img, "✅ Image sent successfully!", (100, 320),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (61, 184, 112), 1)
        
        test_path = os.path.join(CAPTURES_DIR, "telegram_test_image.jpg")
        cv2.imwrite(test_path, img)
        
        result2 = send_telegram_photo(
            test_path,
            "📸 <b>Ảnh test từ Smart Retail AI</b>\n\n✅ Hệ thống có thể gửi ảnh thành công!"
        )
        
        if os.path.exists(test_path):
            os.remove(test_path)
            
    except Exception as e:
        print(f"❌ Lỗi tạo ảnh test: {e}")
        result2 = False
    
    print(f"\n{BLUE}{'='*60}{RESET}")
    if result1 and result2:
        print(f"{GREEN}✅ TEST THÀNH CÔNG!{RESET}")
        print("   Kiểm tra Telegram để xem tin nhắn và ảnh.")
    else:
        print(f"{RED}⚠️ TEST CÓ VẤN ĐỀ{RESET}")
        print("   Kiểm tra lại TOKEN và CHAT_ID trong file .env")
    print(f"{BLUE}{'='*60}{RESET}\n")
    
    return result1 and result2


if __name__ == "__main__":
    send_test_notification()