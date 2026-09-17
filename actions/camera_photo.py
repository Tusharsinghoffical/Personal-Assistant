"""
Action to capture and display photos and screenshots.
Supports:
  - take_photo: Capture photo from webcam and save it
  - take_screenshot: Capture full screen screenshot and save it
  - show_photo: Display/open the captured photo
  - show_screenshot: Display/open the captured screenshot
  - open_camera: Start live camera stream in Mark HUD
  - close_camera: Stop live camera stream in Mark HUD
"""
from __future__ import annotations

import os
import sys
import time
import subprocess
from datetime import datetime
from pathlib import Path

# Captures directory
CAPTURES_DIR = Path.home() / "Pictures" / "Mark_Captures"
CAPTURES_DIR.mkdir(parents=True, exist_ok=True)

_LATEST_PHOTO: Path | None = None
_LATEST_SCREENSHOT: Path | None = None


def _get_latest_file(pattern: str) -> Path | None:
    """Find the most recent file matching pattern in CAPTURES_DIR."""
    try:
        files = list(CAPTURES_DIR.glob(pattern))
        if not files:
            return None
        files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
        return files[0]
    except Exception:
        return None


def _capture_webcam_qt(out_path: Path) -> bool:
    """Capture a webcam photo via isolated Qt process."""
    code = f'''
import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtMultimedia import QCamera, QMediaCaptureSession, QImageCapture, QMediaDevices
from PyQt6.QtCore import QTimer

app = QApplication([])
cams = QMediaDevices.videoInputs()
if not cams:
    sys.exit(1)

cam = QCamera(cams[0])
session = QMediaCaptureSession()
session.setCamera(cam)
cap = QImageCapture()
session.setImageCapture(cap)

def on_saved(id, path):
    sys.exit(0)

def on_err(id, err, err_str):
    sys.exit(2)

cap.imageSaved.connect(on_saved)
cap.errorOccurred.connect(on_err)

cam.start()
QTimer.singleShot(700, lambda: cap.captureToFile(sys.argv[1]))
QTimer.singleShot(4000, lambda: sys.exit(3))
sys.exit(app.exec())
'''
    try:
        proc = subprocess.run(
            [sys.executable, "-c", code, str(out_path)],
            capture_output=True,
            text=True,
            timeout=8,
        )
        return out_path.exists() and out_path.stat().st_size > 1000
    except Exception as e:
        print(f"[CameraPhoto] Qt capture error: {e}")
        return False


def _capture_webcam_cv2(out_path: Path) -> bool:
    """Fallback capture using cv2 if available."""
    try:
        import cv2
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            return False
        for _ in range(5):
            cap.read()
        ret, frame = cap.read()
        cap.release()
        if ret and frame is not None:
            cv2.imwrite(str(out_path), frame)
            return out_path.exists() and out_path.stat().st_size > 1000
    except Exception:
        pass
    return False


def capture_photo() -> tuple[Path | None, bytes | None]:
    """Capture photo from camera and return (file_path, image_bytes)."""
    global _LATEST_PHOTO
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    target_path = CAPTURES_DIR / f"Photo_{timestamp}.jpg"

    ok = _capture_webcam_qt(target_path)
    if not ok:
        ok = _capture_webcam_cv2(target_path)

    if ok and target_path.exists():
        _LATEST_PHOTO = target_path
        try:
            img_bytes = target_path.read_bytes()
            return target_path, img_bytes
        except Exception:
            return target_path, None
    return None, None


def capture_screenshot() -> tuple[Path | None, bytes | None]:
    """Capture screenshot and return (file_path, image_bytes)."""
    global _LATEST_SCREENSHOT
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    target_path = CAPTURES_DIR / f"Screenshot_{timestamp}.png"

    # Try Qt screen grab first
    try:
        from PyQt6.QtWidgets import QApplication
        from PyQt6.QtGui import QGuiApplication
        app = QApplication.instance() or QApplication([])
        screen = QGuiApplication.primaryScreen()
        if screen:
            pixmap = screen.grabWindow(0)
            if pixmap.save(str(target_path)):
                _LATEST_SCREENSHOT = target_path
                return target_path, target_path.read_bytes()
    except Exception as e:
        print(f"[CameraPhoto] Qt screen grab failed: {e}")

    # Fallback to pyautogui / mss
    try:
        import pyautogui
        sc = pyautogui.screenshot()
        sc.save(str(target_path))
        if target_path.exists():
            _LATEST_SCREENSHOT = target_path
            return target_path, target_path.read_bytes()
    except Exception as e:
        print(f"[CameraPhoto] PyAutoGUI screen grab failed: {e}")

    return None, None


def open_file_in_viewer(path: Path) -> bool:
    """Open image in default OS photo viewer."""
    try:
        if sys.platform == "win32":
            os.startfile(str(path))
            return True
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])
            return True
        else:
            subprocess.Popen(["xdg-open", str(path)])
            return True
    except Exception as e:
        print(f"[CameraPhoto] Could not open viewer: {e}")
        return False


def camera_photo_action(
    parameters: dict,
    player=None,
    speak=None,
    response=None,
    session_memory=None,
) -> str:
    global _LATEST_PHOTO, _LATEST_SCREENSHOT
    action = str(parameters.get("action", "")).strip().lower()

    if not action:
        # Check raw parameters for intent
        desc = str(parameters.get("description", "")).lower()
        if any(w in desc for w in ("photo", "camera", "picture", "selfie", "tasveer")):
            if any(w in desc for w in ("dikhao", "show", "open", "dekhna")):
                action = "show_photo"
            else:
                action = "take_photo"
        elif any(w in desc for w in ("screenshot", "screen shot", "snip")):
            if any(w in desc for w in ("dikhao", "show", "open", "dekhna")):
                action = "show_screenshot"
            else:
                action = "take_screenshot"
        else:
            action = "take_photo"

    # 1. Take Photo
    if action in ("take_photo", "capture_photo", "click_photo", "photo"):
        if player and hasattr(player, "write_log"):
            player.write_log("CAM: Capturing photo...")
        photo_path, img_bytes = capture_photo()
        if photo_path and photo_path.exists():
            if player and hasattr(player, "show_camera_frame") and img_bytes:
                player.show_camera_frame(img_bytes)
            if player and hasattr(player, "write_log"):
                player.write_log(f"CAM: Photo saved: {photo_path.name}")
            return f"Photo captured successfully! Saved at: {photo_path}."
        else:
            return "Could not capture photo. Please make sure the camera is connected and not in use by another app."

    # 2. Take Screenshot
    elif action in ("take_screenshot", "screenshot", "capture_screen", "screen_shot"):
        if player and hasattr(player, "write_log"):
            player.write_log("SYS: Capturing screenshot...")
        sc_path, img_bytes = capture_screenshot()
        if sc_path and sc_path.exists():
            if player and hasattr(player, "show_camera_frame") and img_bytes:
                player.show_camera_frame(img_bytes)
            if player and hasattr(player, "write_log"):
                player.write_log(f"SYS: Screenshot saved: {sc_path.name}")
            return f"Screenshot captured successfully! Saved at: {sc_path}."
        else:
            return "Could not capture screenshot."

    # 3. Show Photo
    elif action in ("show_photo", "view_photo", "open_photo", "display_photo"):
        target = _LATEST_PHOTO or _get_latest_file("Photo_*.jpg")
        if not target or not target.exists():
            return "No photo found. Say 'meri photo lo' or 'take photo' first."
        if player and hasattr(player, "show_camera_frame"):
            try:
                player.show_camera_frame(target.read_bytes())
            except Exception:
                pass
        open_file_in_viewer(target)
        if player and hasattr(player, "write_log"):
            player.write_log(f"CAM: Displaying {target.name}")
        return f"Displaying photo: {target.name}"

    # 4. Show Screenshot
    elif action in ("show_screenshot", "view_screenshot", "open_screenshot", "display_screenshot"):
        target = _LATEST_SCREENSHOT or _get_latest_file("Screenshot_*.png")
        if not target or not target.exists():
            return "No screenshot found. Say 'screenshot lo' or 'take screenshot' first."
        if player and hasattr(player, "show_camera_frame"):
            try:
                player.show_camera_frame(target.read_bytes())
            except Exception:
                pass
        open_file_in_viewer(target)
        if player and hasattr(player, "write_log"):
            player.write_log(f"SYS: Displaying {target.name}")
        return f"Displaying screenshot: {target.name}"

    # 5. Open Camera Stream
    elif action in ("open_camera", "start_camera", "camera_on"):
        if player and hasattr(player, "start_camera_stream"):
            player.start_camera_stream()
            if player and hasattr(player, "write_log"):
                player.write_log("CAM: Camera stream started")
            return "Camera feed turned on."
        return "Camera stream not available."

    # 6. Close Camera Stream
    elif action in ("close_camera", "stop_camera", "camera_off"):
        if player and hasattr(player, "stop_camera_stream"):
            player.stop_camera_stream()
            if player and hasattr(player, "write_log"):
                player.write_log("CAM: Camera stream stopped")
            return "Camera feed turned off."
        return "Camera stream closed."

    return f"Unknown camera action: '{action}'."


TOOL = {
    "name": "camera_photo",
    "description": (
        "Capture, view and manage webcam photos and desktop screenshots. "
        "Use this tool when the user says: "
        "- 'camera on karke photo lo', 'meri photo lo', 'take photo', 'click picture': action='take_photo' "
        "- 'screenshot lo', 'screen capture karo', 'take a screenshot': action='take_screenshot' "
        "- 'photo dikhao', 'meri photo dikhao', 'show photo': action='show_photo' "
        "- 'screenshot dikhao', 'jo screenshot liya tha wo dikhao', 'show screenshot': action='show_screenshot' "
        "- 'camera on karo', 'open camera': action='open_camera' "
        "- 'camera band karo', 'close camera': action='close_camera'"
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "enum": [
                    "take_photo",
                    "take_screenshot",
                    "show_photo",
                    "show_screenshot",
                    "open_camera",
                    "close_camera",
                ],
                "description": (
                    "The action to perform: "
                    "'take_photo' (capture photo from camera), "
                    "'take_screenshot' (capture screen screenshot), "
                    "'show_photo' (display/open the latest taken photo), "
                    "'show_screenshot' (display/open the latest screenshot), "
                    "'open_camera' (turn on live camera feed in HUD), "
                    "'close_camera' (turn off live camera feed)"
                ),
            },
            "description": {
                "type": "STRING",
                "description": "Optional user command text or context."
            }
        },
        "required": ["action"],
    },
    "handler": camera_photo_action,
}
