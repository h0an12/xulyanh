# ============================================================
#  main.py  –  Camera Realtime Mode (WITH TELEGRAM IMAGE)
#  Chạy: python main.py
#  Dùng camera trực tiếp thay vì upload video
# ============================================================
import cv2
import os
import threading
import time
import numpy as np
from datetime import datetime
from flask import Flask, render_template, jsonify, Response, send_from_directory

from config      import (
    PROCESS_EVERY_N_FRAMES, CAPTURES_DIR, FLASK_HOST, FLASK_PORT, SECRET_KEY
)
from camera_shared import shared_camera
from detector    import (
    detect_persons, analyze_face_async, get_analysis_result,
    smooth_analysis, start_analysis_worker
)
from tracker     import CentroidTracker
from recommender import recommend, refresh_cache
from telegram_bot import notify_customer, send_telegram_message
from database    import (
    init_db, save_customer, get_recent_customers,
    get_stats, get_customer_count_today,
    get_today_gender_stats, get_today_stats
)

os.makedirs(CAPTURES_DIR, exist_ok=True)

# ── Flask ───────────────────────────────────────────────────
web_app = Flask(__name__, template_folder="templates")
web_app.secret_key = SECRET_KEY

# ── AI State ────────────────────────────────────────────────
tracker          = CentroidTracker()
frame_count      = 0
track_info       = {}
processed_ids    = set()
pending_analysis = set()
pending_frames   = {}          # track_id → (frame, box) chờ kết quả
draw_lock        = threading.Lock()
ai_overlay_enabled = True


# ═══════════════════════════════════════════════════════════
#  AI FUNCTIONS
# ═══════════════════════════════════════════════════════════

def capture_customer(frame, box, track_id) -> str:
    """Lưu ảnh crop khách hàng - TRẢ VỀ ĐƯỜNG DẪN TUYỆT ĐỐI"""
    try:
        x1, y1, x2, y2 = box
        pad = 15
        h, w = frame.shape[:2]
        x1 = max(0, x1 - pad)
        y1 = max(0, y1 - pad)
        x2 = min(w, x2 + pad)
        y2 = min(h, y2 + pad)
        crop = frame[y1:y2, x1:x2]
        if crop.size == 0:
            print(f"[Capture] ⚠️ Crop rỗng cho track {track_id}")
            return ""
        
        # Resize để đồng nhất
        crop = cv2.resize(crop, (400, 400))
        ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        filename = f"customer_{track_id}_{ts}.jpg"
        path = os.path.join(CAPTURES_DIR, filename)
        
        # Đảm bảo thư mục tồn tại
        os.makedirs(CAPTURES_DIR, exist_ok=True)
        
        success = cv2.imwrite(path, crop, [cv2.IMWRITE_JPEG_QUALITY, 90])
        if success:
            abs_path = os.path.abspath(path)
            print(f"[Capture] ✅ Đã lưu ảnh: {abs_path} ({os.path.getsize(abs_path)} bytes)")
            return abs_path
        return ""
    except Exception as e:
        print(f"[Capture] ❌ Lỗi: {e}")
        return ""


def process_detection_result(tid, frame, box, result):
    """Xử lý kết quả nhận diện và gửi Telegram KÈM ẢNH"""
    global track_info, processed_ids
    try:
        result = smooth_analysis(tid, result)
        gender    = result["gender"]
        age_group = result["age_group"]
        
        # Bỏ qua nếu không rõ
        if gender == "Không rõ" or age_group == "Không rõ":
            print(f"[AI] ID:{tid} ⏳ Chưa rõ: {gender}/{age_group}")
            return False

        with draw_lock:
            if tid in processed_ids:
                return True
            
            track_info[tid] = {"gender": gender, "age_group": age_group}
            rec      = recommend(age_group, gender)
            img_path = capture_customer(frame, box, tid)
            ts       = save_customer(tid, gender, age_group, rec["products"], rec["promotion"], img_path)
            
            # ========== GỬI TELEGRAM VỚI ẢNH ==========
            try:
                print(f"\n{'='*60}")
                print(f"[Telegram] ===== CAMERA: KHÁCH #{tid} =====")
                print(f"[Telegram] Giới tính: {gender}")
                print(f"[Telegram] Độ tuổi: {age_group}")
                print(f"[Telegram] Đường dẫn ảnh: {img_path}")
                print(f"[Telegram] Sản phẩm: {rec['products'][:3]}")
                print(f"[Telegram] Khuyến mãi: {rec['promotion']}")
                print(f"{'='*60}")
                
                result = notify_customer(tid, gender, age_group, rec["products"], rec["promotion"], img_path, ts)
                
                if result:
                    print(f"[Telegram] ✅ ĐÃ GỬI THÀNH CÔNG cho khách #{tid}")
                else:
                    print(f"[Telegram] ❌ GỬI THẤT BẠI cho #{tid}")
            except Exception as e:
                print(f"[Telegram] ❌ Lỗi: {e}")
                import traceback
                traceback.print_exc()
            # ==========================================
                
            processed_ids.add(tid)
            print(f"[AI] ID:{tid:03d} ✅ {gender} | {age_group}")
            return True
    except Exception as e:
        print(f"[AI] Process error track {tid}: {e}")
        return False


def draw_ai_overlay(frame):
    """Vẽ thông tin AI lên frame"""
    if frame is None:
        return np.zeros((480, 640, 3), dtype=np.uint8)

    if not ai_overlay_enabled:
        _draw_minimal_hud(frame)
        return frame

    with draw_lock:
        current_boxes = dict(tracker.boxes)

    h, w = frame.shape[:2]
    for tid, box in current_boxes.items():
        x1 = max(0, min(int(box[0]), w - 1))
        y1 = max(0, min(int(box[1]), h - 1))
        x2 = max(0, min(int(box[2]), w - 1))
        y2 = max(0, min(int(box[3]), h - 1))

        info    = track_info.get(tid, {})
        done    = tid in processed_ids
        pending = tid in pending_analysis

        color = (0, 255, 100) if done else ((0, 200, 255) if pending else (0, 165, 255))
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)

        if done and info:
            label = f"ID:{tid} | {info.get('gender','?')} | {info.get('age_group','?')}"
        elif pending:
            label = f"ID:{tid} | Analyzing..."
        else:
            label = f"ID:{tid} | Detected"

        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)
        ly = y1 - th - 10 if y1 - th - 10 > 0 else y2
        ty = y1 - 5 if y1 - th - 10 > 0 else y2 + th + 5

        cv2.rectangle(frame, (x1, ly), (x1 + tw + 10, ly + th + 10), color, -1)
        cv2.putText(frame, label, (x1 + 5, ty),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 1, cv2.LINE_AA)

    _draw_full_hud(frame)
    return frame


def _draw_full_hud(frame):
    """Vẽ HUD đầy đủ"""
    h, w = frame.shape[:2]
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (w, 45), (15, 15, 15), -1)
    cv2.addWeighted(overlay, 0.8, frame, 0.2, 0, frame)

    fps_val  = shared_camera.get_fps()
    cam_info = shared_camera.get_camera_info()
    
    hud_text = (
        f"Smart Retail AI | FPS:{fps_val:.1f} | "
        f"Detected:{len(tracker.boxes)} | "
        f"Pending:{len(pending_analysis)} | "
        f"Done:{len(processed_ids)}"
    )
    cv2.putText(frame, hud_text, (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 150), 1, cv2.LINE_AA)

    cv2.rectangle(frame, (0, h - 30), (w, h), (15, 15, 15), -1)
    cv2.putText(frame, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), (10, h - 8),
                cv2.FONT_HERSHEY_SIMPLEX, 0.4, (200, 200, 200), 1, cv2.LINE_AA)
    status = "AI ACTIVE" if ai_overlay_enabled else "AI PAUSED"
    cv2.putText(frame, status, (w - 120, h - 8),
                cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 100), 1, cv2.LINE_AA)


def _draw_minimal_hud(frame):
    """Vẽ HUD tối giản"""
    h, w = frame.shape[:2]
    cv2.rectangle(frame, (0, 0), (w, 35), (0, 0, 0), -1)
    cv2.putText(frame, "Smart Retail AI – LIVE",
                (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 150), 2)
    cv2.putText(frame, datetime.now().strftime("%H:%M:%S"),
                (w - 100, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)


def ai_processing_loop():
    """Vòng lặp xử lý AI trong thread riêng"""
    global frame_count, pending_analysis
    print("[AI Thread] Started")
    
    while shared_camera.is_running():
        try:
            ok, frame, _ = shared_camera.read(timeout=1.0)
            if not ok or frame is None:
                time.sleep(0.01)
                continue

            frame_count += 1
            
            # Xử lý detection mỗi N frame
            if frame_count % PROCESS_EVERY_N_FRAMES == 0:
                boxes_raw = detect_persons(frame)
                rects = [(x1, y1, x2, y2) for x1, y1, x2, y2, _ in boxes_raw]
                tracker.update(rects)

                # Gửi phân tích cho từng khuôn mặt mới
                for tid, box in tracker.boxes.items():
                    if tid not in pending_analysis and tid not in processed_ids:
                        x1, y1, x2, y2 = box
                        h, w = frame.shape[:2]
                        x1 = max(0, x1)
                        y1 = max(0, y1)
                        x2 = min(w, x2)
                        y2 = min(h, y2)
                        face = frame[y1:y2, x1:x2]
                        if face.size > 0 and face.shape[0] >= 60 and face.shape[1] >= 60:
                            analyze_face_async(tid, face)
                            pending_analysis.add(tid)
                            pending_frames[tid] = (frame.copy(), box)

            # Xử lý kết quả phân tích
            for tid in list(pending_analysis):
                result = get_analysis_result(tid)
                if result is not None:
                    frame_saved, box_saved = pending_frames.get(tid, (frame, tracker.boxes.get(tid, (0, 0, 100, 100))))
                    success = process_detection_result(tid, frame_saved, box_saved, result)
                    if success:
                        pending_analysis.discard(tid)
                        pending_frames.pop(tid, None)

            time.sleep(0.01)
        except Exception as e:
            print(f"[AI Thread] Error: {e}")
            time.sleep(0.1)
    
    print("[AI Thread] Stopped")


# ═══════════════════════════════════════════════════════════
#  FLASK ROUTES
# ═══════════════════════════════════════════════════════════

@web_app.route("/")
def index():
    return render_template("index.html")


@web_app.route("/dashboard")
def dashboard():
    return render_template("dashboard.html")


@web_app.route("/upload")
def upload_page():
    return render_template("upload.html")


@web_app.route("/upload-realtime")
def upload_realtime_page():
    return render_template("upload_realtime.html")


@web_app.route("/video_feed")
def video_feed():
    return Response(_gen_web_frames(),
                    mimetype="multipart/x-mixed-replace; boundary=frame")


def _gen_web_frames():
    """Tạo MJPEG stream cho web"""
    print("[WebStream] Started")
    while True:
        try:
            frame = shared_camera.get_latest_frame()
            if frame is None:
                time.sleep(0.05)
                continue
            frame = draw_ai_overlay(frame.copy())
            _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 75])
            yield (b"--frame\r\n"
                   b"Content-Type: image/jpeg\r\n\r\n" + buf.tobytes() + b"\r\n")
            time.sleep(0.033)
        except GeneratorExit:
            break
        except Exception as e:
            print(f"[WebStream] {e}")
            time.sleep(0.5)


@web_app.route("/api/stats")
def api_stats():
    return jsonify(get_stats())


@web_app.route("/api/stats/today")
def api_stats_today():
    return jsonify(get_today_stats())


@web_app.route("/api/stats/today/gender")
def api_today_gender():
    return jsonify(get_today_gender_stats())


@web_app.route("/api/customers")
def api_customers():
    return jsonify(get_recent_customers(limit=50))


@web_app.route("/api/customers/today")
def api_today():
    return jsonify({"count": get_customer_count_today()})


@web_app.route("/api/camera_status")
def camera_status():
    cam_info = shared_camera.get_camera_info()
    return jsonify({
        "available":  shared_camera.is_running(),
        "fps":        shared_camera.get_fps(),
        "ai_active":  ai_overlay_enabled,
        "detected":   len(tracker.boxes),
        "processing": len(pending_analysis),
        "processed":  len(processed_ids),
        "frame_count": cam_info.get("frame_count", 0),
        "resolution": f"{cam_info.get('width', 0)}x{cam_info.get('height', 0)}"
    })


@web_app.route("/captures/<path:filename>")
def serve_capture(filename):
    return send_from_directory(CAPTURES_DIR, filename)


@web_app.route("/api/telegram/test")
def test_telegram():
    """Test Telegram API"""
    from telegram_bot import send_test_notification
    result = send_test_notification()
    return jsonify({
        "success": result,
        "message": "Test completed. Check your Telegram!"
    })


# ═══════════════════════════════════════════════════════════
#  WEB SERVER
# ═══════════════════════════════════════════════════════════

def run_web_server():
    """Chạy Flask web server"""
    web_app.run(host=FLASK_HOST, port=FLASK_PORT, debug=False, threaded=True, use_reloader=False)


# ═══════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════

def run():
    global ai_overlay_enabled, processed_ids, pending_analysis, tracker, track_info
    
    print("\n" + "=" * 60)
    print("  🛒  SMART RETAIL AI – CAMERA REALTIME MODE")
    print("  📸 WITH TELEGRAM IMAGE SUPPORT")
    print("=" * 60)

    print("\n[1/6] Initializing database...")
    init_db()

    print("\n[2/6] Loading recommendation cache...")
    refresh_cache()

    print("\n[3/6] Starting AI workers (DeepFace)...")
    start_analysis_worker()

    print("\n[4/6] Initializing camera...")
    if not shared_camera.start():
        print("  ❌ Không mở được camera!")
        print("  🔄 Hệ thống vẫn chạy ở chế độ chờ upload video")
        print("  📤 Truy cập http://localhost:5000/upload để upload video phân tích")
        
        # Vẫn chạy web server nhưng không có AI thread
        web_thread = threading.Thread(target=run_web_server, daemon=True)
        web_thread.start()
        
        print(f"""
  ✅ WEB SERVER ĐANG CHẠY (chế độ upload video)
  ─────────────────────────────────────
  🌐 Dashboard : http://localhost:{FLASK_PORT}
  🎥 Upload    : http://localhost:{FLASK_PORT}/upload
  📊 Dashboard : http://localhost:{FLASK_PORT}/dashboard
  📡 Test Telegram: http://localhost:{FLASK_PORT}/api/telegram/test

  💡 Để dùng camera realtime, hãy:
     - Kiểm tra camera đã kết nối
     - Chạy run_camera_test.bat để test
     - Đảm bảo CAMERA_INDEX trong .env đúng
  """)
        
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n  👋 Goodbye!")
        return

    print("\n[5/6] Starting web server...")
    web_thread = threading.Thread(target=run_web_server, daemon=True)
    web_thread.start()
    time.sleep(1.5)

    print("\n[6/6] Starting AI processing thread...")
    ai_thread = threading.Thread(target=ai_processing_loop, daemon=True)
    ai_thread.start()

    # Gửi thông báo khởi động qua Telegram
    try:
        from config import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID
        if TELEGRAM_TOKEN and TELEGRAM_CHAT_ID:
            send_telegram_message(
                "🤖 <b>Smart Retail AI System</b>\n\n"
                "✅ Camera mode đã khởi động thành công!\n"
                "📸 Sẽ gửi ảnh kèm theo khi phát hiện khách hàng mới.\n\n"
                f"🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )
            print("[Telegram] ✅ Đã gửi thông báo khởi động")
    except Exception as e:
        print(f"[Telegram] ⚠️ Không gửi được thông báo khởi động: {e}")

    print(f"""
  ✅ TẤT CẢ SẴN SÀNG!
  ─────────────────────────────────────
  🌐 Dashboard : http://localhost:{FLASK_PORT}
  📷 Camera    : http://localhost:{FLASK_PORT}/video_feed
  📡 API Stats : http://localhost:{FLASK_PORT}/api/stats
  📡 Camera API: http://localhost:{FLASK_PORT}/api/camera_status
  📡 Test Telegram: http://localhost:{FLASK_PORT}/api/telegram/test

  ⌨️  Điều khiển cửa sổ camera:
     Q = Thoát
     P = Tạm dừng AI
     S = Hiển thị thống kê
""")

    paused = False
    try:
        while shared_camera.is_running():
            if not paused:
                frame = shared_camera.get_latest_frame()
                if frame is not None:
                    display_frame = draw_ai_overlay(frame.copy())
                    cv2.imshow("Smart Retail AI - Camera Realtime", display_frame)
            else:
                img = np.zeros((480, 640, 3), dtype=np.uint8)
                img[:] = (20, 20, 35)
                cv2.putText(img, "PAUSED – Press P to resume", (120, 240),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 255), 2)
                cv2.putText(img, f"Processed: {len(processed_ids)} customers", (150, 300),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 100), 1)
                cv2.imshow("Smart Retail AI - Camera Realtime", img)

            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                break
            elif key == ord('p'):
                paused = not paused
                ai_overlay_enabled = not paused
                print(f"  {'⏸  PAUSED' if paused else '▶  RESUMED'}")
            elif key == ord('s'):
                cam_info = shared_camera.get_camera_info()
                print(f"\n  📊 Stats:")
                print(f"     Detected:{len(tracker.boxes)} | Processing:{len(pending_analysis)} | Done:{len(processed_ids)}")
                print(f"     Today:{get_customer_count_today()} | FPS:{shared_camera.get_fps():.1f}")
                print(f"     Frame count:{cam_info.get('frame_count', 0)} | Resolution:{cam_info.get('width', 0)}x{cam_info.get('height', 0)}")
                print(f"     Telegram: {'✅ Đã cấu hình' if TELEGRAM_TOKEN else '❌ Chưa cấu hình'}")
            time.sleep(0.01)
    except KeyboardInterrupt:
        print("\n  ⚠️  Ctrl+C – đang thoát...")

    # Tổng kết
    print(f"\n  📊 TỔNG KẾT:")
    print(f"     ✅ Tổng khách nhận diện: {len(processed_ids)}")
    print(f"     📸 Ảnh đã lưu trong thư mục: {CAPTURES_DIR}")
    print(f"     📡 Telegram đã gửi: {len(processed_ids)} tin nhắn (nếu có ảnh)")
    
    shared_camera.stop()
    cv2.destroyAllWindows()
    print(f"\n  👋 Goodbye!\n")


if __name__ == "__main__":
    run()