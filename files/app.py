# ============================================================
#  app.py  –  Flask Web Server (Smart Retail AI) 
#  Hỗ trợ Upload Video + Telegram Ảnh
#  Chạy lệnh: python app.py
# ============================================================
import os
import uuid
import threading
import time
import json
import cv2
from datetime import datetime
from flask import (
    Flask, render_template, jsonify, request,
    redirect, send_from_directory, Response
)
from werkzeug.utils import secure_filename

from config import (
    FLASK_HOST, FLASK_PORT, SECRET_KEY,
    CAPTURES_DIR, UPLOAD_DIR,
    ALLOWED_VIDEO_EXTS, MAX_VIDEO_SIZE_MB,
    PROCESS_EVERY_N_FRAMES,
    TELEGRAM_TOKEN, TELEGRAM_CHAT_ID
)
from database import (
    init_db, save_customer, get_recent_customers,
    get_stats, get_customer_count_today,
    get_today_gender_stats, get_today_stats,
    create_video_job, update_video_job, get_video_job,
)
from recommender import recommend, refresh_cache
from telegram_bot import notify_customer, send_test_notification, send_telegram_message

# ── Tạo thư mục cần thiết ──────────────────────────────────
os.makedirs(CAPTURES_DIR, exist_ok=True)
os.makedirs(UPLOAD_DIR, exist_ok=True)

# ── Global variables for video streaming ───────────────────
_video_streams = {}
_video_stream_lock = threading.Lock()
_video_results = {}


def update_video_frame(video_id, frame):
    with _video_stream_lock:
        if video_id not in _video_streams:
            _video_streams[video_id] = {'frame': None, 'frame_count': 0, 'processing': True}
        _video_streams[video_id]['frame'] = frame
        _video_streams[video_id]['frame_count'] += 1


def get_video_frame(video_id):
    with _video_stream_lock:
        if video_id in _video_streams:
            return _video_streams[video_id].get('frame')
    return None


def finish_video_stream(video_id):
    with _video_stream_lock:
        if video_id in _video_streams:
            _video_streams[video_id]['processing'] = False


def update_realtime_result(video_id, detection):
    with _video_stream_lock:
        if video_id not in _video_results:
            _video_results[video_id] = {'detections': [], 'stats': {'male': 0, 'female': 0, 'age_groups': {}}}
        _video_results[video_id]['detections'].append(detection)
        if detection['gender'] == 'Nam':
            _video_results[video_id]['stats']['male'] += 1
        else:
            _video_results[video_id]['stats']['female'] += 1
        age = detection['age_group']
        _video_results[video_id]['stats']['age_groups'][age] = _video_results[video_id]['stats']['age_groups'].get(age, 0) + 1


def get_realtime_result(video_id):
    with _video_stream_lock:
        if video_id in _video_results:
            return _video_results[video_id].copy()
    return {'detections': [], 'stats': {'male': 0, 'female': 0, 'age_groups': {}}}


# ── Flask App ───────────────────────────────────────────────
app = Flask(__name__, template_folder="templates")
app.secret_key = SECRET_KEY
app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024 * 1024

ALLOWED_EXTENSIONS = {'.mp4', '.avi', '.mov', '.mkv', '.webm', '.mpg', '.mpeg', '.flv', '.wmv'}


def allowed_file(filename):
    return '.' in filename and os.path.splitext(filename)[1].lower() in ALLOWED_EXTENSIONS


def save_capture_image(frame, box, track_id):
    """Lưu ảnh crop khách hàng - TRẢ VỀ ĐƯỜNG DẪN TUYỆT ĐỐI"""
    try:
        x1, y1, x2, y2 = [int(v) for v in box]
        pad = 50
        h, w = frame.shape[:2]
        x1 = max(0, x1 - pad)
        y1 = max(0, y1 - pad)
        x2 = min(w, x2 + pad)
        y2 = min(h, y2 + pad)
        crop = frame[y1:y2, x1:x2]
        if crop.size == 0:
            print(f"[Capture] ⚠️ Crop rỗng cho track {track_id}")
            return ""
        
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


# ═══════════════════════════════════════════════════════════
#  HTML PAGES
# ═══════════════════════════════════════════════════════════

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/dashboard")
def dashboard():
    return render_template("dashboard.html")


@app.route("/upload")
def upload_page():
    return render_template("upload.html")


@app.route("/upload-realtime")
def upload_realtime_page():
    return render_template("upload_realtime.html")


@app.route("/upload", methods=["POST"])
def upload_video():
    print("\n" + "=" * 60)
    print("[UPLOAD] 🔵 BẮT ĐẦU XỬ LÝ UPLOAD")
    
    if "video" not in request.files:
        return jsonify({"error": "Không tìm thấy file video"}), 400

    file = request.files["video"]
    if file.filename == "":
        return jsonify({"error": "Chưa chọn file"}), 400
    
    if not allowed_file(file.filename):
        return jsonify({"error": f"Định dạng không hỗ trợ"}), 400
    
    try:
        ext = os.path.splitext(file.filename)[1].lower()
        video_id = str(uuid.uuid4())
        filename = f"{video_id}{ext}"
        video_path = os.path.join(UPLOAD_DIR, filename)
        
        file.save(video_path)
        
        if not os.path.exists(video_path):
            return jsonify({"error": "Không thể lưu file"}), 500
        
        create_video_job(video_id, filename)
        
        t = threading.Thread(
            target=process_video_job,
            args=(video_id, video_path),
            daemon=True
        )
        t.start()
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({"video_id": video_id, "success": True})
        
        return render_template("processing.html", video_id=video_id)
        
    except Exception as e:
        print(f"[UPLOAD] ❌ LỖI: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"Lỗi server: {str(e)}"}), 500


@app.route("/processing/<video_id>")
def processing_page(video_id):
    return render_template("processing.html", video_id=video_id)


@app.route('/video_stream/<video_id>')
def video_stream(video_id):
    def generate():
        last_frame_count = -1
        while True:
            job = get_video_job(video_id)
            if job and job.get('status') in ['completed', 'error']:
                break
            
            frame = get_video_frame(video_id)
            if frame is not None and frame.size > 0:
                frame_with_overlay = draw_processing_overlay(frame.copy(), job)
                _, buf = cv2.imencode('.jpg', frame_with_overlay, [cv2.IMWRITE_JPEG_QUALITY, 70])
                yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + buf.tobytes() + b'\r\n')
            else:
                time.sleep(0.1)
                continue
            time.sleep(0.05)
    
    return Response(generate(), mimetype='multipart/x-mixed-replace; boundary=frame')


def draw_processing_overlay(frame, job):
    h, w = frame.shape[:2]
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (w, 80), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.6, frame, 0.4, 0, frame)
    
    progress = job.get('progress', 0) if job else 0
    current_frame = job.get('current_frame', 0) if job else 0
    total_frames = job.get('total_frames', 0) if job else 0
    
    status_text = f"🔍 Đang xử lý: {progress}%"
    frame_text = f"Frame: {current_frame}/{total_frames}" if total_frames > 0 else f"Frame: {current_frame}"
    
    cv2.putText(frame, status_text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 100), 2)
    cv2.putText(frame, frame_text, (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1)
    
    if progress > 0:
        bar_width = int(w * progress / 100)
        cv2.rectangle(frame, (0, h - 5), (bar_width, h), (0, 200, 100), -1)
    
    return frame


# ═══════════════════════════════════════════════════════════
#  VIDEO PROCESSING
# ═══════════════════════════════════════════════════════════

def process_video_job(video_id, video_path):
    """Xử lý video upload - CÓ GỬI ẢNH TELEGRAM"""
    try:
        from detector import detect_persons, analyze_face_async, get_analysis_result, smooth_analysis, start_analysis_worker
        from tracker import CentroidTracker
        
        start_analysis_worker()
        update_video_job(video_id, status="processing", progress=0)
        
        with _video_stream_lock:
            _video_results[video_id] = {'detections': [], 'stats': {'male': 0, 'female': 0, 'age_groups': {}}}

        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            update_video_job(video_id, status="error", error="Không mở được video")
            finish_video_stream(video_id)
            return

        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 1
        update_video_job(video_id, total_frames=total_frames)
        print(f"[VideoJob] 🎬 Bắt đầu xử lý: {video_id} | {total_frames} frames")

        tracker = CentroidTracker()
        frame_count = 0
        processed_ids = set()
        pending = set()
        detections = []
        pending_frames = {}

        while True:
            ok, frame = cap.read()
            if not ok:
                break

            frame_count += 1
            progress = min(int(frame_count / total_frames * 95), 95)
            
            if frame_count % 5 == 0:
                update_video_frame(video_id, frame)
                
            if frame_count % 30 == 0:
                update_video_job(video_id, progress=progress, current_frame=frame_count)

            if frame_count % PROCESS_EVERY_N_FRAMES == 0:
                boxes_raw = detect_persons(frame)
                rects = [(x1, y1, x2, y2) for x1, y1, x2, y2, _ in boxes_raw]
                tracker.update(rects)

                for tid, box in tracker.boxes.items():
                    if tid not in pending and tid not in processed_ids:
                        x1, y1, x2, y2 = [int(v) for v in box]
                        h, w = frame.shape[:2]
                        pad = 50
                        x1 = max(0, x1 - pad)
                        y1 = max(0, y1 - pad)
                        x2 = min(w, x2 + pad)
                        y2 = min(h, y2 + pad)
                        face = frame[y1:y2, x1:x2]
                        if face.size > 0 and face.shape[0] >= 60 and face.shape[1] >= 60:
                            analyze_face_async(tid, face)
                            pending.add(tid)
                            pending_frames[tid] = (frame.copy(), (x1, y1, x2, y2))

            # Xử lý kết quả phân tích
            for tid in list(pending):
                result = get_analysis_result(tid)
                if result is None:
                    continue
                result = smooth_analysis(tid, result)
                
                if tid in processed_ids:
                    pending.discard(tid)
                    continue

                gender = result["gender"]
                age_group = result["age_group"]
                
                # Bỏ qua nếu không rõ
                if gender == "Không rõ" or age_group == "Không rõ":
                    if tid in pending_frames:
                        retry = pending_frames[tid].get('retry', 0) + 1
                        pending_frames[tid] = (pending_frames[tid][0], pending_frames[tid][1], retry)
                        if retry > 8:
                            print(f"[AI] ID:{tid} - Bỏ qua do không rõ sau {retry} lần")
                            pending.discard(tid)
                            pending_frames.pop(tid, None)
                    continue

                rec = recommend(age_group, gender)

                # LƯU ẢNH
                frame_saved, box_saved = pending_frames.get(tid, (None, None))
                img_path = ""
                
                if frame_saved is not None and box_saved is not None:
                    print(f"[Capture] 📸 Đang lưu ảnh cho khách #{tid}...")
                    img_path = save_capture_image(frame_saved, box_saved, tid)
                    if img_path:
                        print(f"[Capture] ✅ ĐÃ LƯU ẢNH: {img_path}")
                    else:
                        print(f"[Capture] ❌ LƯU ẢNH THẤT BẠI cho #{tid}")

                ts = save_customer(tid, gender, age_group, rec["products"], rec["promotion"], img_path)
                
                # ========== GỬI TELEGRAM VỚI ẢNH ==========
                print(f"\n{'='*60}")
                print(f"[Telegram] ===== UPLOAD: KHÁCH #{tid} =====")
                print(f"[Telegram] Giới tính: {gender}")
                print(f"[Telegram] Độ tuổi: {age_group}")
                print(f"[Telegram] Đường dẫn ảnh: {img_path}")
                print(f"{'='*60}")
                
                try:
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

                detection_info = {
                    "track_id": tid, 
                    "gender": gender, 
                    "age_group": age_group,
                    "products": [{"name": p[0], "shelf": p[1]} for p in rec["products"][:3]],
                    "promotion": rec["promotion"], 
                    "timestamp": ts,
                    "suggestion": ", ".join([p[0] for p in rec["products"][:3]])
                }
                detections.append(detection_info)
                update_realtime_result(video_id, detection_info)
                
                processed_ids.add(tid)
                pending.discard(tid)
                pending_frames.pop(tid, None)

        cap.release()

        male = sum(1 for d in detections if d["gender"] == "Nam")
        female = sum(1 for d in detections if d["gender"] == "Nữ")
        age_groups = {}
        for d in detections:
            ag = d["age_group"]
            age_groups[ag] = age_groups.get(ag, 0) + 1

        result_json = json.dumps({
            "total_customers": len(detections),
            "detections": detections,
            "stats": {"male": male, "female": female, "age_groups": age_groups},
        }, ensure_ascii=False)

        update_video_job(video_id, status="completed", progress=100, result_json=result_json)
        finish_video_stream(video_id)
        print(f"[VideoJob] ✅ {video_id} → {len(detections)} khách")

        # Gửi tổng kết qua Telegram
        if len(detections) > 0:
            summary = (
                f"📊 <b>KẾT QUẢ PHÂN TÍCH VIDEO</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"👥 Tổng khách: <b>{len(detections)}</b>\n"
                f"👨 Nam: {male}  |  👩 Nữ: {female}\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"✅ Đã gửi {len(detections)} thông báo kèm ảnh!"
            )
            send_telegram_message(summary)

    except Exception as e:
        import traceback
        traceback.print_exc()
        update_video_job(video_id, status="error", error=str(e))
        finish_video_stream(video_id)


# ═══════════════════════════════════════════════════════════
#  API ENDPOINTS
# ═══════════════════════════════════════════════════════════

@app.route("/api/upload/status/<video_id>")
def api_upload_status(video_id):
    job = get_video_job(video_id)
    if not job:
        return jsonify({"error": "Không tìm thấy job"}), 404
    return jsonify({
        "status": job["status"],
        "progress": job["progress"],
        "current_frame": job.get("current_frame", 0),
        "total_frames": job.get("total_frames", 0),
        "error": job.get("error"),
    })


@app.route("/api/upload/result/<video_id>")
def api_upload_result(video_id):
    job = get_video_job(video_id)
    if not job:
        return jsonify({"error": "Không tìm thấy job"}), 404
    if job["status"] != "completed":
        return jsonify({"error": "Job chưa hoàn thành", "status": job["status"]}), 400
    result = json.loads(job["result_json"]) if job["result_json"] else {}
    return jsonify(result)


@app.route("/api/upload/realtime/<video_id>")
def api_upload_realtime(video_id):
    job = get_video_job(video_id)
    if not job:
        return jsonify({"error": "Không tìm thấy job"}), 404
    result = get_realtime_result(video_id)
    result["status"] = job.get("status", "pending")
    result["progress"] = job.get("progress", 0)
    result["current_frame"] = job.get("current_frame", 0)
    result["total_frames"] = job.get("total_frames", 0)
    return jsonify(result)


@app.route("/api/stats")
def api_stats():
    return jsonify(get_stats())


@app.route("/api/stats/today")
def api_stats_today():
    return jsonify(get_today_stats())


@app.route("/api/stats/today/gender")
def api_today_gender():
    return jsonify(get_today_gender_stats())


@app.route("/api/customers")
def api_customers():
    limit = request.args.get("limit", 50, type=int)
    return jsonify(get_recent_customers(limit=limit))


@app.route("/api/customers/today")
def api_today():
    return jsonify({"count": get_customer_count_today()})


@app.route("/api/camera_status")
def api_camera_status():
    return jsonify({
        "available": False,
        "fps": 0,
        "ai_active": False,
        "detected": 0,
        "processing": 0,
        "processed": 0,
        "note": "Dùng /upload để phân tích video",
    })


@app.route("/captures/<path:filename>")
def serve_capture(filename):
    return send_from_directory(CAPTURES_DIR, filename)


@app.route("/api/telegram/test")
def test_telegram_api():
    """Test Telegram - Gửi tin nhắn và ảnh test"""
    result = send_test_notification()
    return jsonify({
        "success": result, 
        "message": "Telegram test completed. Check your Telegram!" if result else "Telegram test failed",
        "token_configured": bool(TELEGRAM_TOKEN),
        "chat_id_configured": bool(TELEGRAM_CHAT_ID)
    })


@app.route("/api/check_captures")
def check_captures():
    """Kiểm tra danh sách ảnh đã lưu"""
    if not os.path.exists(CAPTURES_DIR):
        return jsonify({"error": f"Thư mục {CAPTURES_DIR} không tồn tại"})
    
    files = os.listdir(CAPTURES_DIR)
    file_info = []
    for f in files[-20:]:
        path = os.path.join(CAPTURES_DIR, f)
        file_info.append({
            "name": f,
            "size": os.path.getsize(path),
            "path": os.path.abspath(path)
        })
    
    return jsonify({
        "captures_dir": os.path.abspath(CAPTURES_DIR),
        "total_files": len(files),
        "recent_files": file_info
    })


@app.errorhandler(404)
def page_not_found(e):
    return render_template("error.html", error_msg="Không tìm thấy trang yêu cầu"), 404


@app.errorhandler(500)
def internal_server_error(e):
    return render_template("error.html", error_msg="Lỗi máy chủ nội bộ"), 500


# ═══════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("  🛒  SMART RETAIL AI – WEB SERVER (UPLOAD VIDEO)")
    print("  📸 WITH TELEGRAM IMAGE SUPPORT")
    print("=" * 60)

    print("\n[1/5] Initializing database...")
    init_db()

    print("\n[2/5] Loading recommendation data from CSV...")
    refresh_cache()
    
    print("\n[3/5] Initializing DeepFace workers...")
    try:
        from detector import start_analysis_worker
        start_analysis_worker()
    except Exception as e:
        print(f"  ⚠️ Không thể khởi động worker: {e}")

    print("\n[4/5] Checking Telegram configuration...")
    if TELEGRAM_TOKEN and TELEGRAM_CHAT_ID:
        print(f"  ✅ Telegram configured")
        print(f"  📡 Token: {TELEGRAM_TOKEN[:10]}...{TELEGRAM_TOKEN[-5:]}")
        print(f"  📡 Chat ID: {TELEGRAM_CHAT_ID}")
        # Gửi thông báo khởi động
        try:
            send_telegram_message(
                "🤖 <b>Smart Retail AI System</b>\n\n"
                "✅ Web server (Upload Mode) đã khởi động thành công!\n"
                "📸 Sẽ gửi ảnh kèm theo khi phân tích video.\n\n"
                f"🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )
        except:
            pass
    else:
        print(f"  ⚠️ Telegram not configured")
        print("  📝 Để cấu hình, tạo file .env với:")
        print("     TELEGRAM_TOKEN=your_token")
        print("     TELEGRAM_CHAT_ID=your_chat_id")

    print("\n[5/5] Starting web server...")

    print(f"\n  🌐 Trang chủ     : http://localhost:{FLASK_PORT}")
    print(f"  📊 Dashboard     : http://localhost:{FLASK_PORT}/dashboard")
    print(f"  🎥 Upload Video  : http://localhost:{FLASK_PORT}/upload")
    print(f"  📡 API Stats     : http://localhost:{FLASK_PORT}/api/stats")
    print(f"  📡 Test Telegram : http://localhost:{FLASK_PORT}/api/telegram/test")
    print(f"  📸 Check Captures: http://localhost:{FLASK_PORT}/api/check_captures")
    print()

    app.run(host=FLASK_HOST, port=FLASK_PORT, debug=False, threaded=True, use_reloader=False)