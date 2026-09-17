"""
Video Creator — Real-time video content creation, screen recording, and multimedia synthesis.
Capabilities:
  - start_screen_record: Begin recording screen to MP4 in the background
  - stop_screen_record: Stop active screen recording and save MP4
  - record_clip: Record a short screen or webcam clip (e.g. 5-30 seconds)
  - create_video_story: Synthesize an automated, stylish presentation video from topic/script
  - show_video: Open the latest recorded video in OS media player
"""
from __future__ import annotations

import os
import sys
import time
import threading
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

# Recordings directory
RECORDINGS_DIR = Path.home() / "Videos" / "Mark_Recordings"
RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)

_ACTIVE_RECORDER: ScreenRecorder | None = None
_LATEST_VIDEO: Path | None = None


def _find_ffmpeg() -> str:
    """Locate ffmpeg executable."""
    # Check PATH or common winget paths
    try:
        proc = subprocess.run(["where.exe", "ffmpeg"], capture_output=True, text=True, timeout=3)
        if proc.returncode == 0:
            lines = [l.strip() for l in proc.stdout.splitlines() if l.strip()]
            if lines:
                return lines[0]
    except Exception:
        pass
    return "ffmpeg"


class ScreenRecorder:
    """Background screen video recorder using Qt frame capture piped to ffmpeg."""
    def __init__(self, out_path: Path, fps: int = 15):
        self.out_path = out_path
        self.fps = fps
        self.running = False
        self.thread: threading.Thread | None = None
        self.proc: subprocess.Popen | None = None

    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self._record_loop, daemon=True)
        self.thread.start()

    def _record_loop(self):
        from PyQt6.QtWidgets import QApplication
        from PyQt6.QtGui import QGuiApplication
        from PyQt6.QtCore import QBuffer, QIODevice

        app = QApplication.instance() or QApplication([])
        screen = QGuiApplication.primaryScreen()
        if not screen:
            self.running = False
            return

        ffmpeg_bin = _find_ffmpeg()
        cmd = [
            ffmpeg_bin, "-y",
            "-f", "image2pipe",
            "-vcodec", "png",
            "-framerate", str(self.fps),
            "-i", "-",
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-preset", "ultrafast",
            str(self.out_path)
        ]

        try:
            self.proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
        except Exception as e:
            print(f"[VideoCreator] FFmpeg start error: {e}")
            self.running = False
            return

        frame_interval = 1.0 / self.fps

        while self.running:
            t0 = time.time()
            try:
                pix = screen.grabWindow(0)
                buf = QBuffer()
                buf.open(QIODevice.OpenModeFlag.WriteOnly)
                pix.save(buf, "PNG")
                png_bytes = bytes(buf.data())
                if self.proc and self.proc.stdin:
                    self.proc.stdin.write(png_bytes)
            except Exception as e:
                print(f"[VideoCreator] Frame grab error: {e}")
                break

            elapsed = time.time() - t0
            sleep_time = frame_interval - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

        # Finalize
        if self.proc and self.proc.stdin:
            try:
                self.proc.stdin.close()
                self.proc.wait(timeout=5)
            except Exception:
                pass

    def stop(self):
        self.running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=3)
        if self.proc:
            try:
                self.proc.terminate()
            except Exception:
                pass


def create_dynamic_video_story(topic: str, points: list[str], out_path: Path) -> bool:
    """Generate a high-production animated title video clip from text points."""
    width, height = 1280, 720
    fps = 24
    seconds_per_slide = 3.0
    frames_per_slide = int(fps * seconds_per_slide)

    ffmpeg_bin = _find_ffmpeg()
    cmd = [
        ffmpeg_bin, "-y",
        "-f", "image2pipe",
        "-vcodec", "png",
        "-framerate", str(fps),
        "-i", "-",
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-preset", "medium",
        str(out_path)
    ]

    try:
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as e:
        print(f"[VideoCreator] Video synth start error: {e}")
        return False

    slides_content = [{"title": topic, "subtitle": "Automated Multimedia Synthesis by Mark"}]
    for idx, pt in enumerate(points):
        slides_content.append({"title": f"Key Insight #{idx + 1}", "subtitle": pt})

    for s_idx, slide in enumerate(slides_content):
        # Base image
        for f in range(frames_per_slide):
            # Dynamic gradient background
            img = Image.new("RGB", (width, height), (15, 23, 42))
            draw = ImageDraw.Draw(img)

            # Draw sleek HUD frame
            glow_color = (0, 210, 255) if s_idx == 0 else (168, 85, 247)
            draw.rectangle([30, 30, width - 30, height - 30], outline=glow_color, width=3)
            draw.rectangle([35, 35, width - 35, height - 35], outline=(30, 41, 59), width=1)

            # Draw header
            draw.text((60, 60), "MARK // MULTIMEDIA STUDIO", fill=(148, 163, 184))
            draw.text((width - 250, 60), datetime.now().strftime("%Y-%m-%d %H:%M"), fill=(148, 163, 184))

            # Draw main title
            title_text = slide["title"]
            draw.text((80, 240), title_text, fill=(255, 255, 255))

            # Draw subtitle/point
            sub_text = slide["subtitle"]
            draw.text((80, 350), sub_text, fill=(226, 232, 240))

            # Dynamic progress bar
            progress = (f + 1) / frames_per_slide
            bar_w = int((width - 160) * progress)
            draw.rectangle([80, height - 80, 80 + bar_w, height - 74], fill=glow_color)

            # Output frame to ffmpeg
            import io
            b = io.BytesIO()
            img.save(b, format="PNG")
            proc.stdin.write(b.getvalue())

    try:
        proc.stdin.close()
        proc.wait(timeout=10)
        return out_path.exists() and out_path.stat().st_size > 1000
    except Exception as e:
        print(f"[VideoCreator] Video synth finalize error: {e}")
        return False


def get_latest_recording() -> Path | None:
    """Find the most recent MP4 in RECORDINGS_DIR."""
    try:
        files = list(RECORDINGS_DIR.glob("*.mp4"))
        if not files:
            return None
        files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
        return files[0]
    except Exception:
        return None


def video_creator(parameters: dict, player=None, speak=None) -> str:
    """Entry point for video_creator tool."""
    global _ACTIVE_RECORDER, _LATEST_VIDEO

    params = parameters or {}
    action = str(params.get("action") or "create_video_story").lower().strip()
    topic = str(params.get("topic") or params.get("title") or "Project Intelligence").strip()
    duration = int(params.get("duration") or 10)
    raw_points = params.get("points") or params.get("script") or []

    if isinstance(raw_points, str):
        points = [p.strip() for p in raw_points.split("\n") if p.strip()]
    elif isinstance(raw_points, list):
        points = [str(p).strip() for p in raw_points if str(p).strip()]
    else:
        points = []

    if not points:
        points = [
            f"Synthesizing high-fidelity audio-visual intelligence for: {topic}",
            "Autonomous multi-stage video generation and rendering completed.",
            "Ready for export and presentation."
        ]

    print(f"[VideoCreator] Action: '{action}' | Topic: '{topic}'")
    if player and hasattr(player, "write_log"):
        player.write_log(f"[Video] {action}: {topic[:40]}")

    if action in ("start_screen_record", "start_record", "record_screen"):
        if _ACTIVE_RECORDER and _ACTIVE_RECORDER.running:
            return "Screen recording is already active."

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = RECORDINGS_DIR / f"ScreenRecord_{timestamp}.mp4"
        _ACTIVE_RECORDER = ScreenRecorder(out_path, fps=15)
        _ACTIVE_RECORDER.start()
        _LATEST_VIDEO = out_path
        return f"Screen video recording started! Saving to: {out_path}. Say 'stop recording' when you are done."

    if action in ("stop_screen_record", "stop_record", "end_record"):
        if not _ACTIVE_RECORDER or not _ACTIVE_RECORDER.running:
            return "No active screen recording is in progress."

        _ACTIVE_RECORDER.stop()
        saved_path = _ACTIVE_RECORDER.out_path
        _ACTIVE_RECORDER = None
        _LATEST_VIDEO = saved_path
        return f"Screen video recording stopped and saved to: {saved_path}."

    if action in ("record_clip", "record_quick_clip"):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = RECORDINGS_DIR / f"Clip_{timestamp}.mp4"
        rec = ScreenRecorder(out_path, fps=15)
        rec.start()
        time.sleep(min(duration, 30))
        rec.stop()
        _LATEST_VIDEO = out_path
        return f"Recorded {duration}-second video clip saved to: {out_path}."

    if action in ("create_video_story", "make_video", "generate_video", "video_story"):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        clean_topic = "".join(c for c in topic if c.isalnum() or c in (" ", "_", "-")).strip()
        out_path = RECORDINGS_DIR / f"Story_{clean_topic[:20]}_{timestamp}.mp4"

        ok = create_dynamic_video_story(topic, points, out_path)
        if ok:
            _LATEST_VIDEO = out_path
            return f"Video story '{topic}' created successfully! Saved at: {out_path}."
        return f"Could not generate video story for '{topic}'. Check FFmpeg output."

    if action in ("show_video", "play_video", "open_video", "view_video"):
        video_file = _LATEST_VIDEO or get_latest_recording()
        if not video_file or not video_file.exists():
            return "No video recordings found in Videos/Mark_Recordings."

        try:
            if hasattr(os, "startfile"):
                os.startfile(str(video_file))
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(video_file)])
            else:
                subprocess.Popen(["xdg-open", str(video_file)])
            return f"Playing video: {video_file.name}."
        except Exception as e:
            return f"Failed to open video: {e}"

    return f"Unknown action '{action}'. Supported: start_screen_record, stop_screen_record, record_clip, create_video_story, show_video."


# ── Tool declaration (auto-discovered by core/action_loader.py) ──────────────
TOOL = {
    "name": "video_creator",
    "description": (
        "Real-time video content creation and screen recording. "
        "Allows Mark to record the computer screen into an MP4 video, create short video clips, "
        "generate animated presentation/story video clips from text/script, and open recorded videos."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": (
                    "Video action: 'start_screen_record' (start recording screen) | "
                    "'stop_screen_record' (finish & save video) | 'record_clip' (quick timed recording) | "
                    "'create_video_story' (generate video from slides/script) | 'show_video' (play latest video)"
                )
            },
            "topic": {
                "type": "STRING",
                "description": "Topic or title for video creation"
            },
            "points": {
                "type": "ARRAY",
                "items": {"type": "STRING"},
                "description": "Key bullet points, slides, or script lines for create_video_story"
            },
            "duration": {
                "type": "INTEGER",
                "description": "Duration in seconds for quick clip recording (default 10)"
            }
        },
        "required": ["action"]
    },
    "handler": video_creator,
}
