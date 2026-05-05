import cv2
import zxingcpp
import numpy as np
import sqlite3
import os
import time
from datetime import datetime
from pypylon import pylon
from db import init_db, save_scan

# ── Config ────────────────────────────────────────────────────────────────────
SAVE_DIR        = "captures"
STORE_BLOB      = True       # Store image bytes IN the DB (set False for large volumes)
EXPOSURE_US     = 5000       # Basler exposure in microseconds — tune for your light
COOLDOWN_SEC    = 0.5        # Ignore re-reads of same QR within this window
# ──────────────────────────────────────────────────────────────────────────────

os.makedirs(SAVE_DIR, exist_ok=True)
init_db()

def setup_camera() -> pylon.InstantCamera:
    """Connect and configure the first available Basler camera."""
    camera = pylon.InstantCamera(pylon.TlFactory.GetInstance().CreateFirstDevice())
    camera.Open()

    # Basic settings — adjust to your lens/lighting
    camera.ExposureTime.SetValue(EXPOSURE_US)
    camera.PixelFormat.SetValue("BGR8")   # OpenCV-friendly
    camera.AcquisitionFrameRateEnable.SetValue(True)
    camera.AcquisitionFrameRate.SetValue(30)  # FPS cap

    print(f"[Camera] Connected: {camera.GetDeviceInfo().GetModelName()}")
    return camera

def decode_qr(frame: np.ndarray):
    """Decode QR codes using zxing-cpp (very fast, handles small/tilted codes)."""
    results = zxingcpp.read_barcodes(frame, formats=zxingcpp.BarcodeFormat.QRCode)
    return results  # list of Result objects

def process_frame(frame: np.ndarray, seen: dict) -> bool:
    """Detect QR, deduplicate, save to disk + DB. Returns True if QR found."""
    results = decode_qr(frame)
    if not results:
        return False

    for r in results:
        qr_value = r.text.strip()
        if not qr_value:
            continue

        # ── Cooldown deduplication (same QR on belt for multiple frames) ──
        now = time.time()
        if qr_value in seen and now - seen[qr_value] < COOLDOWN_SEC:
            continue
        seen[qr_value] = now

        # ── Draw bounding box ──
        pts = r.position
        poly = np.array([[pts.top_left.x, pts.top_left.y],
                         [pts.top_right.x, pts.top_right.y],
                         [pts.bottom_right.x, pts.bottom_right.y],
                         [pts.bottom_left.x, pts.bottom_left.y]], dtype=np.int32)
        cv2.polylines(frame, [poly], True, (0, 255, 0), 2)
        cv2.putText(frame, qr_value, (pts.top_left.x, pts.top_left.y - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

        # ── Save image to disk ──
        ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        filename = f"{ts}_{qr_value[:20]}.jpg"
        filepath = os.path.join(SAVE_DIR, filename)
        cv2.imwrite(filepath, frame, [cv2.IMWRITE_JPEG_QUALITY, 95])

        # ── Save to SQLite ──
        blob = open(filepath, "rb").read() if STORE_BLOB else None
        save_scan(qr_value, filepath, blob)

        print(f"[SCAN] {qr_value}  →  {filepath}")

    return True

def run():
    camera = setup_camera()
    seen = {}  # {qr_value: last_seen_timestamp}

    camera.StartGrabbing(pylon.GrabStrategy_LatestImageOnly)
    converter = pylon.ImageFormatConverter()
    converter.OutputPixelFormat = pylon.PixelType_BGR8packed
    converter.OutputBitAlignment = pylon.OutputBitAlignment_MsbAligned

    print("[Scanner] Running — press Q to quit")
    try:
        while camera.IsGrabbing():
            grab = camera.RetrieveResult(2000, pylon.TimeoutHandling_ThrowException)
            if not grab.GrabSucceeded():
                grab.Release()
                continue

            img = converter.Convert(grab)
            frame = img.GetArray()
            grab.Release()

            process_frame(frame, seen)

            # Optional live preview (disable for headless/production)
            cv2.imshow("QR Scanner", frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

    except KeyboardInterrupt:
        print("\n[Scanner] Stopped by user.")
    finally:
        camera.StopGrabbing()
        camera.Close()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    run()
