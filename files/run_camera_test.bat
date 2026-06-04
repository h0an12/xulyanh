@echo off
chcp 65001 >nul
echo [Smart Retail] Kiem tra camera...
call venv\Scripts\activate.bat
python -c "
import cv2, sys

print('=' * 50)
print('  KIỂM TRA CAMERA')
print('=' * 50)

# Thử mở camera với index 0
print('\n[1] Thử camera index 0...')
cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
if not cap.isOpened():
    cap = cv2.VideoCapture(0)
if not cap.isOpened():
    print('[LOI] Khong mo duoc camera index 0!')
else:
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    print(f'[OK] Camera 0: {w}x{h} @ {fps:.1f} FPS')
    cap.release()

# Thử mở camera với index 1
print('\n[2] Thử camera index 1...')
cap = cv2.VideoCapture(1, cv2.CAP_DSHOW)
if not cap.isOpened():
    cap = cv2.VideoCapture(1)
if cap.isOpened():
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    print(f'[OK] Camera 1: {w}x{h}')
    cap.release()
else:
    print('[INFO] Khong tim thay camera index 1')

print('\n[3] Hiển thị camera test...')
print('    Nhấn S để chụp ảnh, Q để thoát')

# Mở camera để test
cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
if not cap.isOpened():
    cap = cv2.VideoCapture(0)
if not cap.isOpened():
    print('[LOI] Khong the mo camera de test!')
    sys.exit(1)

while True:
    ok, frame = cap.read()
    if not ok:
        print('[LOI] Khong doc duoc frame')
        break
    
    # Hiển thị thông tin
    cv2.putText(frame, 'Camera Test - S: chup anh, Q: thoat', (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
    cv2.putText(frame, f'Resolution: {frame.shape[1]}x{frame.shape[0]}', (10, 60),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
    
    cv2.imshow('Camera Test', frame)
    
    k = cv2.waitKey(1) & 0xFF
    if k == ord('q'):
        break
    if k == ord('s'):
        cv2.imwrite('camera_test.jpg', frame)
        print('[OK] Da chup anh: camera_test.jpg')

cap.release()
cv2.destroyAllWindows()
print('\n[OK] Test hoan tat!')
"
pause