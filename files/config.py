# ============================================================
#  config.py  –  Cấu hình toàn bộ hệ thống Smart Retail AI
# ============================================================
import os
from dotenv import load_dotenv

load_dotenv()

# ── FLASK ──────────────────────────────────────────────────
FLASK_HOST  = os.getenv("FLASK_HOST", "0.0.0.0")
FLASK_PORT  = int(os.getenv("FLASK_PORT", 5000))
SECRET_KEY  = os.getenv("SECRET_KEY", "smart-retail-secret-2024")

# ── CAMERA ─────────────────────────────────────────────────
CAMERA_INDEX        = int(os.getenv("CAMERA_INDEX", 0))
CAMERA_WIDTH        = int(os.getenv("CAMERA_WIDTH", 1280))
CAMERA_HEIGHT       = int(os.getenv("CAMERA_HEIGHT", 720))
CAMERA_FPS          = int(os.getenv("CAMERA_FPS", 30))

# ── AI PROCESSING ──────────────────────────────────────────
PROCESS_EVERY_N_FRAMES = int(os.getenv("PROCESS_EVERY_N_FRAMES", 5))
YOLO_MODEL_PATH        = os.getenv("YOLO_MODEL_PATH", "yolov8n.pt")
YOLO_CONFIDENCE        = float(os.getenv("YOLO_CONFIDENCE", 0.5))
FACE_ANALYSIS_WORKERS  = int(os.getenv("FACE_ANALYSIS_WORKERS", 2))

# ── TRACKER ────────────────────────────────────────────────
MAX_DISAPPEARED = int(os.getenv("MAX_DISAPPEARED", 30))
MAX_DISTANCE    = int(os.getenv("MAX_DISTANCE", 150))

# ── PATHS ──────────────────────────────────────────────────
CAPTURES_DIR      = os.getenv("CAPTURES_DIR", "captures")
UPLOAD_DIR        = os.getenv("UPLOAD_DIR", "uploads")
DATABASE_PATH     = os.getenv("DATABASE_PATH", "smart_retail.db")
CUSTOMER_CSV      = os.getenv("CUSTOMER_CSV", "customer_interactions.csv")
TRANSACTION_CSV   = os.getenv("TRANSACTION_CSV", "transaction_history.csv")

# ── TELEGRAM ───────────────────────────────────────────────
TELEGRAM_TOKEN   = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# ── VIDEO UPLOAD ───────────────────────────────────────────
MAX_VIDEO_SIZE_MB   = int(os.getenv("MAX_VIDEO_SIZE_MB", 2048))  # 2GB
ALLOWED_VIDEO_EXTS  = {'.mp4', '.avi', '.mov', '.mkv', '.webm', '.mpg', '.mpeg', '.flv', '.wmv'}

# ── PRODUCT RULES (FALLBACK) ───────────────────────────────
PRODUCT_RULES = {
    ("Trẻ em (0–12)",    "Nam"): [("Đồ chơi xe hơi", "Kệ A1"), ("Bút màu", "Kệ B3"), ("Bánh kẹo trẻ em", "Kệ C2")],
    ("Trẻ em (0–12)",    "Nữ"): [("Búp bê", "Kệ A2"), ("Bánh kẹo trẻ em", "Kệ C2"), ("Bút màu", "Kệ B3")],
    ("Thiếu niên (13–18)","Nam"): [("Giày sneaker", "Kệ E1"), ("Ba lô học sinh", "Kệ F2"), ("Tai nghe", "Kệ G3")],
    ("Thiếu niên (13–18)","Nữ"): [("Mỹ phẩm học sinh", "Kệ H1"), ("Ba lô học sinh", "Kệ F2"), ("Giày sneaker", "Kệ E1")],
    ("Thanh niên (19–30)","Nam"): [("Tai nghe", "Kệ G3"), ("Giày sneaker", "Kệ E1"), ("Đồng hồ thể thao", "Kệ I1")],
    ("Thanh niên (19–30)","Nữ"): [("Son môi", "Kệ H2"), ("Kem dưỡng da", "Kệ J1"), ("Nước hoa", "Kệ J3")],
    ("Trung niên (31–50)","Nam"): [("Áo sơ mi", "Kệ L1"), ("Cà phê", "Kệ M2"), ("Sách kinh doanh", "Kệ N1")],
    ("Trung niên (31–50)","Nữ"): [("Kem dưỡng da lão hóa", "Kệ K3"), ("Túi xách", "Kệ L2"), ("Nước hoa", "Kệ J3")],
    ("Cao tuổi (>50)",    "Nam"): [("Thực phẩm bổ sung canxi", "Kệ O2"), ("Dép êm", "Kệ P1"), ("Sách", "Kệ N2")],
    ("Cao tuổi (>50)",    "Nữ"): [("Thực phẩm bổ sung canxi", "Kệ O2"), ("Kem dưỡng da lão hóa", "Kệ K3"), ("Trà thảo mộc", "Kệ O3")],
}

PROMOTIONS = {
    "Trẻ em (0–12)":    "Mua 2 tặng 1 đồ chơi – chỉ hôm nay!",
    "Thiếu niên (13–18)":"Giảm 15% cho học sinh, sinh viên",
    "Thanh niên (19–30)":"Tích điểm x2 khi mua từ 500K",
    "Trung niên (31–50)":"Freeship đơn hàng từ 300K",
    "Cao tuổi (>50)":    "Ưu đãi thành viên cao cấp – Giảm 20%",
}