# ============================================================
#  camera_shared.py  –  Shared Camera (thread-safe)
#  Hỗ trợ nhiều camera index và URL
# ============================================================
import cv2
import threading
import time
import numpy as np
from config import CAMERA_INDEX, CAMERA_WIDTH, CAMERA_HEIGHT, CAMERA_FPS


class SharedCamera:
    def __init__(self, camera_source=None):
        """
        camera_source: có thể là index (int) hoặc URL (string)
        Nếu None, dùng CAMERA_INDEX từ config
        """
        self.cap           = None
        self.latest_frame  = None
        self.lock          = threading.Lock()
        self._running      = False
        self._thread       = None
        self._fps          = 0
        self._fps_counter  = 0
        self._fps_time     = time.time()
        self.camera_source = camera_source if camera_source is not None else CAMERA_INDEX
        self.width         = CAMERA_WIDTH
        self.height        = CAMERA_HEIGHT
        self._frame_count  = 0
        self._last_frame_time = 0

    # ── PUBLIC ────────────────────────────────────────────────

    def start(self):
        """Mở camera và bắt đầu thread đọc frame."""
        # Thử mở camera với nhiều backend khác nhau
        backends = [cv2.CAP_DSHOW, cv2.CAP_ANY, cv2.CAP_V4L2, cv2.CAP_FFMPEG]
        
        for backend in backends:
            try:
                if isinstance(self.camera_source, int):
                    self.cap = cv2.VideoCapture(self.camera_source, backend)
                else:
                    self.cap = cv2.VideoCapture(self.camera_source)
                    
                if self.cap.isOpened():
                    print(f"[Camera] ✅ Mở được camera với backend: {backend}")
                    break
                else:
                    self.cap.release()
                    self.cap = None
            except Exception as e:
                print(f"[Camera] Backend {backend} thất bại: {e}")
                continue
        
        if self.cap is None or not self.cap.isOpened():
            # Thử lần cuối không backend
            try:
                if isinstance(self.camera_source, int):
                    self.cap = cv2.VideoCapture(self.camera_source)
                else:
                    self.cap = cv2.VideoCapture(self.camera_source)
            except Exception as e:
                print(f"[Camera] ❌ Không thể mở camera {self.camera_source}: {e}")
                return False
                
        if not self.cap.isOpened():
            print(f"[Camera] ❌ Không mở được camera source={self.camera_source}")
            return False

        # Set properties
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH,  self.width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        self.cap.set(cv2.CAP_PROP_FPS,          CAMERA_FPS)
        
        # Đọc thử một frame
        ret, test_frame = self.cap.read()
        if not ret or test_frame is None:
            print(f"[Camera] ⚠️ Camera mở nhưng không đọc được frame")
            # Vẫn tiếp tục, có thể sẽ đọc được sau
            
        self.width  = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        actual_fps = self.cap.get(cv2.CAP_PROP_FPS)
        
        print(f"[Camera] ✅ Opened ({self.width}x{self.height}) @ {actual_fps:.1f} FPS")
        
        self._running = True
        self._thread  = threading.Thread(target=self._read_loop, daemon=True)
        self._thread.start()
        return True

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=3)
        if self.cap:
            self.cap.release()
        self.cap = None
        print("[Camera] Stopped")

    def is_running(self):
        return self._running

    def get_fps(self):
        return round(self._fps, 1)
    
    def get_frame_count(self):
        return self._frame_count

    def get_latest_frame(self):
        """Lấy frame mới nhất (non-blocking). Trả về None nếu chưa có."""
        with self.lock:
            if self.latest_frame is None:
                return None
            return self.latest_frame.copy()

    def read(self, timeout=1.0):
        """Đọc frame với timeout. Trả về (ok, frame, fps)."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            frame = self.get_latest_frame()
            if frame is not None:
                return True, frame, self._fps
            time.sleep(0.01)
        return False, None, 0

    def get_camera_info(self):
        """Lấy thông tin camera"""
        return {
            "source": str(self.camera_source),
            "width": self.width,
            "height": self.height,
            "fps": self._fps,
            "frame_count": self._frame_count,
            "running": self._running
        }

    # ── INTERNAL ──────────────────────────────────────────────

    def _read_loop(self):
        """Thread liên tục đọc frame từ camera."""
        print("[Camera] Read loop started")
        while self._running:
            if self.cap is None or not self.cap.isOpened():
                time.sleep(0.1)
                continue
                
            try:
                ok, frame = self.cap.read()
                if not ok or frame is None:
                    # Thử re-open camera nếu mất kết nối
                    print("[Camera] ⚠️ Mất kết nối camera, thử kết nối lại...")
                    self._reconnect_camera()
                    time.sleep(0.5)
                    continue

                # Cập nhật frame
                with self.lock:
                    self.latest_frame = frame
                self._frame_count += 1

                # Tính FPS
                self._fps_counter += 1
                now = time.time()
                elapsed = now - self._fps_time
                if elapsed >= 1.0:
                    self._fps = self._fps_counter / elapsed
                    self._fps_counter = 0
                    self._fps_time = now
                    
            except Exception as e:
                print(f"[Camera] Read error: {e}")
                time.sleep(0.1)
                
        print("[Camera] Read loop stopped")
    
    def _reconnect_camera(self):
        """Thử kết nối lại camera"""
        if self.cap:
            self.cap.release()
            
        backends = [cv2.CAP_DSHOW, cv2.CAP_ANY, cv2.CAP_V4L2, cv2.CAP_FFMPEG]
        for backend in backends:
            try:
                if isinstance(self.camera_source, int):
                    new_cap = cv2.VideoCapture(self.camera_source, backend)
                else:
                    new_cap = cv2.VideoCapture(self.camera_source)
                    
                if new_cap.isOpened():
                    self.cap = new_cap
                    self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
                    self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
                    print(f"[Camera] ✅ Reconnected with backend: {backend}")
                    return True
                else:
                    new_cap.release()
            except:
                continue
        return False


# Singleton instance
shared_camera = SharedCamera()