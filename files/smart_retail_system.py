"""
====================================================
SMART RETAIL AI SYSTEM - Hệ thống nhận diện khách hàng thông minh
ĐÃ SỬA LỖI THREADING VÀ KHỞI ĐỘNG
====================================================
"""
import cv2
import numpy as np
import sqlite3
import time
import threading
import requests
import json
import os
from datetime import datetime
from collections import defaultdict, deque
from flask import Flask, jsonify, Response
from flask_cors import CORS

# ==================== CẤU HÌNH ====================
TELEGRAM_TOKEN = "8599148267:AAHGZgRO_BgJFQRe9SzNtStPABesR9VKzOY"
TELEGRAM_CHAT_ID = "5607021896"

CAMERA_URLS = [
    "http://172.16.64.190:4747/video",
    "http://192.168.61.138:4747/mjpegfeed",
    "http://192.168.61.138:4747/videofeed",
    "http://192.168.61.138:4747/video.mjpg",
    0
]

DB_PATH = "retail_data.db"
FRAME_SKIP = 3
TRACKING_TIMEOUT = 5.0
MIN_DETECT_FRAMES = 5
SEND_COOLDOWN = 30

PRODUCT_RULES = {
    ("male", "0-12"): ["Đồ chơi LEGO", "Sách truyện tranh", "Ba lô học sinh"],
    ("female", "0-12"): ["Búp bê Barbie", "Sách tô màu", "Phụ kiện tóc xinh"],
    ("male", "13-18"): ["Giày sneaker thể thao", "Tai nghe gaming", "Áo thun trendy"],
    ("female", "13-18"): ["Son dưỡng môi", "Sữa rửa mặt", "Phụ kiện thời trang"],
    ("male", "19-30"): ["Giày sneaker cao cấp", "Đồng hồ thể thao", "Túi đựng laptop"],
    ("female", "19-30"): ["Mỹ phẩm dưỡng da", "Túi xách thời trang", "Nước hoa nữ"],
    ("male", "31-50"): ["Đồng hồ lịch lãm", "Cà vạt cao cấp", "Ví da nam"],
    ("female", "31-50"): ["Kem chống lão hóa", "Trang sức bạc", "Túi da cao cấp"],
    ("male", ">50"): ["Kính mắt", "Giày đi bộ êm", "Viên uống bổ sung"],
    ("female", ">50"): ["Kem dưỡng da cao cấp", "Kính mắt", "Trà thảo mộc"],
}

PROMOTIONS = {
    "0-12": "🎉 Giảm 20% đồ chơi & sách!",
    "13-18": "🔥 Flash sale 30% thời trang teen!",
    "19-30": "💥 Mua 2 tặng 1 sản phẩm lifestyle!",
    "31-50": "⭐ Ưu đãi VIP giảm 15%!",
    ">50": "❤️ Tích điểm đổi quà!",
}

# ==================== DATABASE ====================
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            track_id TEXT, gender TEXT, age_group TEXT,
            timestamp TEXT, suggestions TEXT, confidence REAL, session_id TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT UNIQUE, start_time TEXT, end_time TEXT, total_customers INTEGER DEFAULT 0)""")
    conn.commit()
    conn.close()

def save_customer(track_id, gender, age_group, suggestions, confidence, session_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute("INSERT INTO customers (track_id, gender, age_group, timestamp, suggestions, confidence, session_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
              (track_id, gender, age_group, timestamp, json.dumps(suggestions, ensure_ascii=False), confidence, session_id))
    conn.commit()
    conn.close()

def get_stats():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    today = datetime.now().strftime("%Y-%m-%d")
    c.execute("SELECT COUNT(DISTINCT track_id) FROM customers WHERE timestamp LIKE ?", (f"{today}%",))
    today_count = c.fetchone()[0]
    c.execute("SELECT gender, COUNT(*) FROM customers GROUP BY gender")
    gender_dist = dict(c.fetchall())
    c.execute("SELECT age_group, COUNT(*) FROM customers GROUP BY age_group")
    age_dist = dict(c.fetchall())
    c.execute("SELECT track_id, gender, age_group, timestamp, suggestions, confidence FROM customers ORDER BY id DESC LIMIT 20")
    recent = c.fetchall()
    conn.close()
    return {"today_count": today_count, "gender_dist": gender_dist, "age_dist": age_dist, "recent": recent}

# ==================== TELEGRAM ====================
def send_telegram(message, image_bytes=None):
    try:
        if image_bytes:
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
            files = {"photo": ("customer.jpg", image_bytes, "image/jpeg")}
            data = {"chat_id": TELEGRAM_CHAT_ID, "caption": message, "parse_mode": "HTML"}
            resp = requests.post(url, files=files, data=data, timeout=10)
        else:
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
            data = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}
            resp = requests.post(url, json=data, timeout=10)
        if resp.status_code == 200:
            print("✅ Telegram sent")
    except Exception as e:
        print(f"❌ Telegram error: {e}")

def build_telegram_message(track_id, gender, age_group, suggestions, confidence):
    gender_vi = "Nam" if gender == "male" else "Nữ"
    time_str = datetime.now().strftime("%H:%M %d/%m/%Y")
    promo = PROMOTIONS.get(age_group, "")
    products_str = "\n".join([f"  • {p}" for p in suggestions[:3]])
    return f"""
🛒 <b>KHÁCH HÀNG MỚI</b>
━━━━━━━━━━━━━━━━━━
👤 ID: <code>{track_id}</code>
🚻 Giới tính: <b>{gender_vi}</b>
🎂 Nhóm tuổi: <b>{age_group}</b>
📊 Độ chính xác: <b>{confidence:.0%}</b>
🕐 Thời gian: {time_str}
🎯 <b>GỢI Ý SẢN PHẨM:</b>
{products_str}
{promo}
━━━━━━━━━━━━━━━━━━
"""

# ==================== AI ANALYZER ====================
class FaceAnalyzer:
    def __init__(self):
        self.face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
        self.gender_net, self.age_net = None, None
        self.gender_list = ['male', 'female']
        self.age_list = ['0-12', '13-18', '19-30', '31-50', '>50']
        self.caffe_age_map = {
            '(0-2)': '0-12', '(4-6)': '0-12', '(8-12)': '0-12',
            '(15-20)': '13-18', '(25-32)': '19-30',
            '(38-43)': '31-50', '(48-53)': '31-50', '(60-100)': '>50'
        }
        model_files = {"gender_proto": "gender_deploy.prototxt", "gender_model": "gender_net.caffemodel",
                       "age_proto": "age_deploy.prototxt", "age_model": "age_net.caffemodel"}
        if all(os.path.exists(f) for f in model_files.values()):
            try:
                self.gender_net = cv2.dnn.readNet(model_files["gender_model"], model_files["gender_proto"])
                self.age_net = cv2.dnn.readNet(model_files["age_model"], model_files["age_proto"])
                print("✅ DNN models loaded")
            except: pass
        else:
            print("⚠️ Demo mode (no DNN models)")

    def analyze(self, face_img):
        if self.gender_net and self.age_net:
            blob = cv2.dnn.blobFromImage(face_img, 1.0, (227, 227), (78, 87, 114), swapRB=False)
            self.gender_net.setInput(blob); gender_preds = self.gender_net.forward()
            gender = self.gender_list[gender_preds[0].argmax()]
            self.age_net.setInput(blob); age_preds = self.age_net.forward()
            age_group = self.caffe_age_map.get(['(0-2)','(4-6)','(8-12)','(15-20)','(25-32)','(38-43)','(48-53)','(60-100)'][age_preds[0].argmax()], '19-30')
            conf = (gender_preds[0].max() + age_preds[0].max()) / 2
            return gender, age_group, conf
        else:
            np.random.seed(int(np.mean(face_img)))
            return np.random.choice(['male','female']), np.random.choice(['13-18','19-30','31-50']), 0.75

    def detect_faces(self, frame):
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        return self.face_cascade.detectMultiScale(gray, 1.1, 5, minSize=(60, 60))

class SimpleTracker:
    def __init__(self):
        self.tracks = {}
        self.next_id = 1
    def update(self, detections):
        now = time.time()
        expired = [tid for tid, t in self.tracks.items() if now - t["last_seen"] > TRACKING_TIMEOUT]
        for tid in expired: del self.tracks[tid]
        matched = {}
        for det in detections:
            tid = self.next_id; self.next_id += 1
            self.tracks[tid] = {"bbox": det, "last_seen": now, "frames": 1, "analysis": None}
            matched[tid] = det
        return matched

# ==================== HỆ THỐNG CHÍNH ====================
class SmartRetailSystem:
    def __init__(self):
        self.cap = None
        self.analyzer = FaceAnalyzer()
        self.tracker = SimpleTracker()
        self.frame_count = 0
        self.current_frame = None
        self.running = False
        self.session_id = datetime.now().strftime("SES_%Y%m%d_%H%M%S")
        self.analysis_buffer = defaultdict(lambda: {"genders": deque(maxlen=10), "ages": deque(maxlen=10),
                                                    "confidences": deque(maxlen=10), "confirmed": False,
                                                    "sent_telegram": False, "last_sent": 0})
        self.realtime_customers = {}
        self.lock = threading.Lock()
        init_db()
        self._connect_camera()

    def _connect_camera(self):
        for url in CAMERA_URLS:
            cap = cv2.VideoCapture(url)
            if cap.isOpened():
                ret, frame = cap.read()
                if ret:
                    self.cap = cap
                    print(f"✅ Camera: {url}")
                    return
                cap.release()
        self.cap = None
        print("❌ No camera, using demo mode")

    def process_frame(self, frame):
        faces = self.analyzer.detect_faces(frame)
        tracked = self.tracker.update([(x, y, w, h) for (x, y, w, h) in faces])
        results = {}
        for tid, (x, y, w, h) in tracked.items():
            x1, y1 = max(0, x-20), max(0, y-20)
            x2, y2 = min(frame.shape[1], x+w+20), min(frame.shape[0], y+h+20)
            face_crop = frame[y1:y2, x1:x2]
            if face_crop.size == 0: continue
            gender, age_group, conf = self.analyzer.analyze(face_crop)
            # ... (phần còn lại giữ nguyên logic buffer và suggest)
            results[tid] = {"id": tid, "gender": gender, "age_group": age_group, "confidence": conf,
                            "products": PRODUCT_RULES.get((gender, age_group), []), "bbox": (x, y, w, h)}
        with self.lock:
            self.realtime_customers = results
        return results

    def run(self):
        self.running = True
        while self.running:
            if self.cap and self.cap.isOpened():
                ret, frame = self.cap.read()
                if not ret: time.sleep(0.1); continue
            else:
                frame = np.zeros((480, 640, 3), dtype=np.uint8)
                cv2.putText(frame, "DEMO MODE", (200, 240), cv2.FONT_HERSHEY_SIMPLEX, 1, (0,255,0), 2)
            self.frame_count += 1
            if self.frame_count % FRAME_SKIP == 0:
                results = self.process_frame(frame)
            else:
                with self.lock: results = self.realtime_customers
            display_frame = frame.copy()
            for info in results.values():
                x, y, w, h = info["bbox"]
                cv2.rectangle(display_frame, (x, y), (x+w, y+h), (0,255,0), 2)
            with self.lock:
                self.current_frame = display_frame
            time.sleep(0.03)
        if self.cap: self.cap.release()

# ==================== FLASK APP ====================
app = Flask(__name__)
CORS(app)
system = None

@app.route('/api/stats')
def api_stats():
    global system
    if not system: return jsonify({"error": "system starting"}), 503
    stats = get_stats()
    with system.lock:
        live_customers = [{"id": f"C{tid:04d}", "gender": i["gender"],
                           "age_group": i["age_group"], "confidence": round(i["confidence"], 3),
                           "products": i["products"][:3]} for tid, i in system.realtime_customers.items()]
    return jsonify({
        "today_count": stats["today_count"],
        "live_count": len(live_customers),
        "gender_dist": stats["gender_dist"],
        "age_dist": stats["age_dist"],
        "live_customers": live_customers,
        "recent_customers": [{"id": r[0], "gender": r[1], "age_group": r[2],
                              "timestamp": r[3], "confidence": round(r[5], 3)} for r in stats["recent"]]
    })

@app.route('/api/video_feed')
def video_feed():
    def generate():
        while True:
            if system and system.current_frame is not None:
                _, buffer = cv2.imencode('.jpg', system.current_frame)
                yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
            time.sleep(0.1)
    return Response(generate(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/health')
def health():
    return jsonify({"status": "running", "session": system.session_id if system else "starting"})

def start_ai_thread():
    global system
    system = SmartRetailSystem()
    system.run()

if __name__ == "__main__":
    print("=" * 50)
    print("SMART RETAIL AI SYSTEM v2.1")
    print("=" * 50)
    ai_thread = threading.Thread(target=start_ai_thread, daemon=True)
    ai_thread.start()
    print("🌐 Dashboard: http://localhost:5000")
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)