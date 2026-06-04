# ============================================================
#  tracker.py  –  Centroid Tracker (FIXED)
#  - Xử lý edge-case khi D matrix shape bất đối xứng
#  - Thread-safe với lock
# ============================================================
import numpy as np
import threading
from collections import OrderedDict
from config import MAX_DISAPPEARED, MAX_DISTANCE


class CentroidTracker:
    def __init__(self, max_disappeared=None, max_distance=None):
        self.next_id        = 1
        self.objects        = OrderedDict()   # track_id → centroid [cx, cy]
        self.boxes          = OrderedDict()   # track_id → (x1,y1,x2,y2)
        self.disappeared    = OrderedDict()   # track_id → frames mất dấu
        self.max_disappeared= max_disappeared or MAX_DISAPPEARED
        self.max_distance   = max_distance    or MAX_DISTANCE
        self.total_tracks   = 0
        self._lock          = threading.Lock()

    # ── PUBLIC ──────────────────────────────────────────────

    def update(self, rects):
        """
        Cập nhật tracker với list bounding boxes [(x1,y1,x2,y2), ...].
        Trả về dict {track_id: (x1,y1,x2,y2)}.
        """
        with self._lock:
            return self._update_internal(rects)

    def get_active_count(self):
        with self._lock:
            return len(self.objects)

    def get_total_tracks(self):
        with self._lock:
            return self.total_tracks

    # ── INTERNAL ────────────────────────────────────────────

    def _register(self, centroid, bbox):
        self.objects[self.next_id]     = centroid
        self.boxes[self.next_id]       = bbox
        self.disappeared[self.next_id] = 0
        self.total_tracks += 1
        self.next_id      += 1

    def _deregister(self, track_id):
        self.objects.pop(track_id,     None)
        self.boxes.pop(track_id,       None)
        self.disappeared.pop(track_id, None)

    def _update_internal(self, rects):
        # Không có detection: tăng disappeared counter
        if not rects:
            for tid in list(self.disappeared):
                self.disappeared[tid] += 1
                if self.disappeared[tid] > self.max_disappeared:
                    self._deregister(tid)
            return dict(self.boxes)

        # Tính input centroids
        input_centroids = np.array([
            [(x1 + x2) // 2, (y1 + y2) // 2]
            for x1, y1, x2, y2 in rects
        ], dtype=np.float32)

        # Chưa có track nào → đăng ký tất cả
        if not self.objects:
            for c, b in zip(input_centroids, rects):
                self._register(c, b)
            return dict(self.boxes)

        track_ids       = list(self.objects.keys())
        track_centroids = np.array(list(self.objects.values()), dtype=np.float32)

        # Ma trận khoảng cách (n_tracks × n_detections)
        D = np.linalg.norm(
            track_centroids[:, np.newaxis] - input_centroids[np.newaxis, :],
            axis=2
        )  # shape: (n_tracks, n_detections)

        # FIXED: greedy matching an toàn cho mọi shape
        used_rows = set()
        used_cols = set()

        # Sắp xếp theo khoảng cách tăng dần
        if D.size > 0:
            flat_idx = np.argsort(D, axis=None)
            for idx in flat_idx:
                row = idx // D.shape[1]
                col = idx %  D.shape[1]
                if row in used_rows or col in used_cols:
                    continue
                if D[row, col] > self.max_distance:
                    break
                tid = track_ids[row]
                self.objects[tid]     = input_centroids[col]
                self.boxes[tid]       = rects[col]
                self.disappeared[tid] = 0
                used_rows.add(row)
                used_cols.add(col)

        # Tracks không được match
        for row in range(len(track_ids)):
            if row not in used_rows:
                tid = track_ids[row]
                self.disappeared[tid] += 1
                if self.disappeared[tid] > self.max_disappeared:
                    self._deregister(tid)

        # Detections mới chưa được match
        for col in range(len(rects)):
            if col not in used_cols:
                self._register(input_centroids[col], rects[col])

        return dict(self.boxes)
