# ============================================================
#  detector.py  –  YOLO Detection + DeepFace Async Analysis (IMPROVED)
# ============================================================
import cv2
import threading
import queue
import time
import numpy as np
from collections import defaultdict
from config import YOLO_MODEL_PATH, YOLO_CONFIDENCE, FACE_ANALYSIS_WORKERS

_yolo_model = None
_yolo_lock = threading.Lock()
_deepface_lock = threading.Lock()


def _get_yolo():
    global _yolo_model
    if _yolo_model is None:
        with _yolo_lock:
            if _yolo_model is None:
                from ultralytics import YOLO
                _yolo_model = YOLO(YOLO_MODEL_PATH)
                print(f"[Detector] ✅ YOLO loaded: {YOLO_MODEL_PATH}")
    return _yolo_model


def detect_persons(frame):
    if frame is None or frame.size == 0:
        return []
    try:
        model = _get_yolo()
        results = model(frame, classes=[0], conf=0.3, iou=0.5, verbose=False)
        boxes = []
        for r in results:
            if r.boxes is None:
                continue
            for box in r.boxes:
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                conf = float(box.conf[0])
                if (x2 - x1) > 20 and (y2 - y1) > 40:
                    boxes.append((x1, y1, x2, y2, conf))
        return boxes
    except Exception as e:
        print(f"[Detector] detect_persons error: {e}")
        return []


_analysis_queue = queue.Queue(maxsize=20)
_result_store = {}
_result_lock = threading.Lock()
_smooth_buffer = defaultdict(list)
_SMOOTH_N = 5


def preprocess_face(face_img):
    """Tiền xử lý ảnh khuôn mặt - IMPROVED"""
    if face_img is None or face_img.size == 0:
        return None
    
    try:
        # Resize về kích thước chuẩn
        face_img = cv2.resize(face_img, (224, 224))
        
        # Cải thiện chất lượng ảnh
        if len(face_img.shape) == 3:
            # CLAHE để cải thiện độ tương phản
            lab = cv2.cvtColor(face_img, cv2.COLOR_BGR2LAB)
            l, a, b = cv2.split(lab)
            clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
            l = clahe.apply(l)
            lab = cv2.merge((l, a, b))
            face_img = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
            
            # Giảm nhiễu
            face_img = cv2.bilateralFilter(face_img, 9, 75, 75)
        
        return face_img
    except Exception as e:
        print(f"[Detector] preprocess_face error: {e}")
        return face_img


def analyze_face_async(track_id, face_img):
    if face_img is None or face_img.size == 0:
        return
    try:
        face_img = preprocess_face(face_img)
        if face_img is not None:
            _analysis_queue.put_nowait((track_id, face_img))
    except queue.Full:
        pass


def get_analysis_result(track_id):
    with _result_lock:
        return _result_store.pop(track_id, None)


def clear_buffer(track_id):
    _smooth_buffer.pop(track_id, None)


def smooth_analysis(track_id, result):
    _smooth_buffer[track_id].append(result)
    if len(_smooth_buffer[track_id]) > _SMOOTH_N * 2:
        _smooth_buffer[track_id].pop(0)

    buf = _smooth_buffer[track_id]
    if len(buf) < 3:
        return result

    from collections import Counter
    genders = Counter(r["gender"] for r in buf if r.get("gender") not in ["Không rõ", "Unknown"])
    age_groups = Counter(r["age_group"] for r in buf if r.get("age_group") not in ["Không rõ", "Unknown"])

    gender = genders.most_common(1)[0][0] if genders else result.get("gender", "Không rõ")
    age_group = age_groups.most_common(1)[0][0] if age_groups else result.get("age_group", "Không rõ")
    return {"gender": gender, "age_group": age_group, "age_raw": result.get("age_raw", 0)}


def _deepface_worker():
    print("[DeepFace Worker] Started")
    while True:
        try:
            track_id, face_img = _analysis_queue.get(timeout=1.0)
        except queue.Empty:
            continue

        try:
            from deepface import DeepFace

            if face_img is None or face_img.size == 0:
                result = {"gender": "Không rõ", "age_group": "Không rõ", "age_raw": 0}
                with _result_lock:
                    _result_store[track_id] = result
                _analysis_queue.task_done()
                continue

            with _deepface_lock:
                analysis = DeepFace.analyze(
                    face_img,
                    actions=["gender", "age"],
                    enforce_detection=False,
                    silent=True,
                    detector_backend='opencv'
                )

            if isinstance(analysis, list):
                analysis = analysis[0]

            raw_gender = analysis.get("dominant_gender", "")
            age = int(analysis.get("age", 0))

            # Ánh xạ giới tính chính xác hơn
            raw_gender_lower = raw_gender.lower()
            if raw_gender_lower in ["man", "male", "nam", "m"]:
                gender = "Nam"
            elif raw_gender_lower in ["woman", "female", "nữ", "nu", "f"]:
                gender = "Nữ"
            else:
                # Thử lấy ký tự đầu tiên
                if raw_gender_lower and raw_gender_lower[0] == 'm':
                    gender = "Nam"
                elif raw_gender_lower and raw_gender_lower[0] == 'f':
                    gender = "Nữ"
                else:
                    gender = "Không rõ"

            # Phân loại độ tuổi
            if age <= 12:
                age_group = "Trẻ em (0–12)"
            elif age <= 18:
                age_group = "Thiếu niên (13–18)"
            elif age <= 30:
                age_group = "Thanh niên (19–30)"
            elif age <= 50:
                age_group = "Trung niên (31–50)"
            else:
                age_group = "Cao tuổi (>50)"

            result = {"gender": gender, "age_group": age_group, "age_raw": age}
            
            if gender != "Không rõ":
                print(f"[DeepFace] ID:{track_id} → {gender}, tuổi: {age} → {age_group}")

        except Exception as e:
            if "Face could not be detected" not in str(e):
                print(f"[DeepFace Worker] Error: {e}")
            result = {"gender": "Không rõ", "age_group": "Không rõ", "age_raw": 0}

        with _result_lock:
            _result_store[track_id] = result

        _analysis_queue.task_done()


def start_analysis_worker():
    for i in range(max(1, FACE_ANALYSIS_WORKERS)):
        t = threading.Thread(target=_deepface_worker, daemon=True, name=f"DeepFace-{i}")
        t.start()
    print(f"[Detector] ✅ {max(1, FACE_ANALYSIS_WORKERS)} DeepFace worker(s) started")