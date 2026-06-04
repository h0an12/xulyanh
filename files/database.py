# ============================================================
#  database.py  –  SQLite Database (Smart Retail AI)
#  THÊM CỘT products_json ĐỂ LƯU SẢN PHẨM + VỊ TRÍ KỆ
# ============================================================
import sqlite3
import json
from datetime import datetime, date
from config import DATABASE_PATH


def get_conn():
    conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Khởi tạo database và tạo bảng nếu chưa có."""
    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS customers (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                track_id    INTEGER NOT NULL,
                gender      TEXT,
                age_group   TEXT,
                suggestions TEXT,
                promotion   TEXT,
                image_path  TEXT,
                timestamp   TEXT NOT NULL,
                products_json TEXT
            );

            CREATE TABLE IF NOT EXISTS video_jobs (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                video_id      TEXT UNIQUE NOT NULL,
                filename      TEXT,
                status        TEXT DEFAULT 'pending',
                progress      INTEGER DEFAULT 0,
                current_frame INTEGER DEFAULT 0,
                total_frames  INTEGER DEFAULT 0,
                result_json   TEXT,
                error         TEXT,
                created_at    TEXT NOT NULL,
                updated_at    TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_customers_ts      ON customers(timestamp);
            CREATE INDEX IF NOT EXISTS idx_customers_gender  ON customers(gender);
            CREATE INDEX IF NOT EXISTS idx_video_jobs_vid    ON video_jobs(video_id);
        """)
        
        # Thêm cột products_json nếu chưa có (migration)
        try:
            conn.execute("ALTER TABLE customers ADD COLUMN products_json TEXT")
        except sqlite3.OperationalError:
            pass  # Cột đã tồn tại
            
    print(f"[DB] Database ready: {DATABASE_PATH}")


# ── CUSTOMERS ──────────────────────────────────────────────

def save_customer(track_id, gender, age_group, products, promotion, image_path=""):
    """Lưu khách hàng mới kèm sản phẩm và vị trí kệ"""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    suggestions = ", ".join([p[0] for p in products[:3]]) if products else ""
    
    # Lưu cả tên sản phẩm và vị trí kệ dưới dạng JSON
    products_with_shelf = json.dumps([{"name": p[0], "shelf": p[1]} for p in products[:3]], ensure_ascii=False)
    
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO customers (track_id,gender,age_group,suggestions,promotion,image_path,timestamp,products_json) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (track_id, gender, age_group, suggestions, promotion, image_path, ts, products_with_shelf)
        )
    return ts


def get_recent_customers(limit=50):
    """Lấy danh sách khách hàng gần đây, kèm products_json"""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM customers ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    
    customers = []
    for r in rows:
        customer = dict(r)
        # Parse products_json nếu có
        if customer.get('products_json'):
            try:
                customer['products'] = json.loads(customer['products_json'])
            except:
                customer['products'] = []
        else:
            customer['products'] = []
        customers.append(customer)
    return customers


def get_customer_count_today():
    """Đếm số khách hôm nay."""
    today = date.today().isoformat()
    with get_conn() as conn:
        row = conn.execute(
            "SELECT COUNT(*) as cnt FROM customers WHERE timestamp LIKE ?",
            (today + "%",)
        ).fetchone()
    return row["cnt"] if row else 0


def get_today_gender_stats():
    """Thống kê Nam/Nữ hôm nay."""
    today = date.today().isoformat()
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT gender, COUNT(*) as cnt FROM customers "
            "WHERE timestamp LIKE ? GROUP BY gender",
            (today + "%",)
        ).fetchall()
    result = {"Nam": 0, "Nữ": 0}
    for r in rows:
        result[r["gender"]] = r["cnt"]
    return result


def get_today_stats():
    """Thống kê toàn bộ hôm nay."""
    today = date.today().isoformat()
    with get_conn() as conn:
        total = conn.execute(
            "SELECT COUNT(*) as cnt FROM customers WHERE timestamp LIKE ?",
            (today + "%",)
        ).fetchone()["cnt"]

        gender_rows = conn.execute(
            "SELECT gender, COUNT(*) as cnt FROM customers "
            "WHERE timestamp LIKE ? GROUP BY gender", (today + "%",)
        ).fetchall()

        age_rows = conn.execute(
            "SELECT age_group, COUNT(*) as cnt FROM customers "
            "WHERE timestamp LIKE ? GROUP BY age_group", (today + "%",)
        ).fetchall()

    gender_counts = {r["gender"]: r["cnt"] for r in gender_rows}
    age_counts    = {r["age_group"]: r["cnt"] for r in age_rows}
    return {
        "total":  total,
        "male":   gender_counts.get("Nam", 0),
        "female": gender_counts.get("Nữ", 0),
        "age_counts": age_counts,
    }


def get_stats():
    """Thống kê tổng quan toàn bộ thời gian."""
    with get_conn() as conn:
        total = conn.execute("SELECT COUNT(*) as cnt FROM customers").fetchone()["cnt"]

        gender_rows = conn.execute(
            "SELECT gender, COUNT(*) as cnt FROM customers GROUP BY gender"
        ).fetchall()

        age_rows = conn.execute(
            "SELECT age_group, COUNT(*) as cnt FROM customers GROUP BY age_group"
        ).fetchall()

        # Lượt khách theo giờ trong 24h qua
        hourly_rows = conn.execute("""
            SELECT CAST(strftime('%H', timestamp) AS INTEGER) as hour,
                   COUNT(*) as cnt
            FROM customers
            WHERE timestamp >= datetime('now', '-24 hours')
            GROUP BY hour ORDER BY hour
        """).fetchall()

    gender_counts = {r["gender"]: r["cnt"] for r in gender_rows}
    age_counts    = {r["age_group"]: r["cnt"] for r in age_rows}
    hourly        = [{"hour": r["hour"], "count": r["cnt"]} for r in hourly_rows]

    return {
        "total":      total,
        "male":       gender_counts.get("Nam", 0),
        "female":     gender_counts.get("Nữ", 0),
        "age_counts": age_counts,
        "hourly":     hourly,
    }


# ── VIDEO JOBS ─────────────────────────────────────────────

def create_video_job(video_id, filename):
    """Tạo job xử lý video mới."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO video_jobs (video_id,filename,status,created_at,updated_at) VALUES (?,?,?,?,?)",
            (video_id, filename, "pending", now, now)
        )


def update_video_job(video_id, **kwargs):
    """Cập nhật trạng thái job video."""
    kwargs["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    sets   = ", ".join(f"{k}=?" for k in kwargs)
    values = list(kwargs.values()) + [video_id]
    with get_conn() as conn:
        conn.execute(f"UPDATE video_jobs SET {sets} WHERE video_id=?", values)


def get_video_job(video_id):
    """Lấy thông tin job video."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM video_jobs WHERE video_id=?", (video_id,)
        ).fetchone()
    return dict(row) if row else None