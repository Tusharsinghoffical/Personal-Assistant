"""
Local wake-word detection for MARK ("Hey Mark").

Design goals:
  • ZERO cost when the feature is off — faster-whisper is imported ONLY inside
    start()/install helpers, never at module load. If the user never enables
    wake word, none of this touches the app.
  • ZERO latency on the audio path — the microphone callback only ever does a
    cheap, non-blocking queue push (feed()); the actual detection runs in
    this module's own background thread, so the real-time audio thread and the
    Gemini stream are never slowed.
  • Fully local & offline — audio fed here never leaves the machine.
  • Listens for "Hey Mark" / "Mark" locally using the faster-whisper engine.
"""
from __future__ import annotations

import collections
import queue
import re
import subprocess
import sys
import threading
from pathlib import Path
from typing import Callable

# Tunable energy threshold for voice activity onset
DEFAULT_THRESHOLD = 300.0
SAMPLE_RATE = 16000

# Matches "mark", "hey mark", "ok mark", "hello mark", "marck", "marc" or Hindi "मार्क"
WAKE_PATTERN = re.compile(
    r'\b(mark|marc|marck|hey mark|ok mark|hello mark)\b|मार्क|माक',
    re.IGNORECASE
)


def is_installed() -> bool:
    """True if the faster-whisper package is importable."""
    try:
        import importlib.util
        return importlib.util.find_spec("faster_whisper") is not None
    except Exception:
        return False


def is_ready() -> bool:
    """True if faster-whisper is installed and the tiny model is available."""
    if not is_installed():
        return False
    try:
        cache_dir = Path.home() / ".cache" / "huggingface" / "hub"
        has_model = any(cache_dir.glob("*faster-whisper-tiny*"))
        return bool(has_model)
    except Exception:
        return True


def install_and_download(logger: Callable[[str], None] = print) -> tuple[bool, str]:
    """
    One-click setup for the UI button: pip-install faster-whisper if missing, then
    download/cache the tiny model. Returns (ok, message). Never raises.
    """
    try:
        if not is_installed():
            logger("Wake word: installing faster-whisper (one-time)…")
            r = subprocess.run(
                [sys.executable, "-m", "pip", "install", "faster-whisper"],
                capture_output=True, text=True,
            )
            if r.returncode != 0:
                tail = (r.stderr or r.stdout or "").strip().splitlines()[-1:] or [""]
                return False, f"pip install failed: {tail[0][:160]}"

        logger("Wake word: caching local model…")
        from faster_whisper import WhisperModel
        WhisperModel("tiny", device="cpu", compute_type="int8")
        logger("Wake word: ready.")
        return True, "Wake word ('Hey Mark') installed and ready."
    except Exception as e:
        return False, f"setup error: {e}"


class WakeWordDetector:
    """
    Runs local speech detection in a dedicated thread. The mic thread calls feed() with
    raw int16 frames; detections invoke on_detect() (called from this thread).
    """

    def __init__(self, on_detect: Callable[[], None],
                 threshold: float = DEFAULT_THRESHOLD,
                 logger: Callable[[str], None] = print):
        self._on_detect = on_detect
        self._threshold = threshold
        self._logger    = logger
        self._queue: queue.Queue = queue.Queue(maxsize=60)
        self._thread: threading.Thread | None = None
        self._running = False
        self._model = None
        self._ready = False

    def start(self) -> bool:
        """Load the model and spawn the inference thread. Returns True on success.
        Safe to call again — a no-op if already running. Never raises."""
        if self._running:
            return True
        try:
            from faster_whisper import WhisperModel
            self._model = WhisperModel("tiny", device="cpu", compute_type="int8")
        except Exception as e:
            self._logger(f"Wake word: could not load model — {e}")
            self._model = None
            return False
        self._running = True
        self._ready = True
        self._thread = threading.Thread(target=self._loop, daemon=True, name="WakeWordThread")
        self._thread.start()
        self._logger("Wake word: listening for 'Hey Mark'.")
        return True

    def stop(self) -> None:
        self._running = False
        # unblock the thread if it's waiting on the queue
        try:
            self._queue.put_nowait(None)
        except Exception:
            pass
        self._model = None
        self._ready = False

    @property
    def ready(self) -> bool:
        return self._ready

    def feed(self, frame_int16) -> None:
        """Called from the mic callback (real-time thread). Must stay cheap and
        never block — the frame is copied and dropped if the queue is backed up."""
        if not self._running:
            return
        try:
            data = frame_int16[:, 0].copy() if getattr(frame_int16, "ndim", 1) > 1 else frame_int16.copy()
            self._queue.put_nowait(data)
        except queue.Full:
            pass
        except Exception:
            pass

    def _loop(self) -> None:
        import numpy as np

        pre_buffer = collections.deque(maxlen=3)  # preserve leading consonant (~192ms)
        speech_frames = []
        is_speaking = False
        silence_chunks = 0
        ambient_rms = 120.0

        while self._running:
            try:
                frame = self._queue.get()
                if frame is None or not self._running:
                    break

                frame_f32 = frame.astype(np.float32)
                rms = float(np.sqrt(np.mean(frame_f32 * frame_f32)))

                if not is_speaking:
                    # Adaptively estimate room background noise
                    ambient_rms = 0.96 * ambient_rms + 0.04 * rms
                    speech_trigger = max(self._threshold, ambient_rms * 2.0)
                    if rms > speech_trigger:
                        is_speaking = True
                        speech_frames = list(pre_buffer) + [frame]
                        silence_chunks = 0
                    else:
                        pre_buffer.append(frame)
                else:
                    speech_frames.append(frame)
                    speech_continue = max(200.0, ambient_rms * 1.4)
                    if rms <= speech_continue:
                        silence_chunks += 1
                    else:
                        silence_chunks = 0

                    # Utterance boundary: ~250ms of silence after speaking, or capped at ~2.2s
                    if silence_chunks >= 4 or len(speech_frames) >= 35:
                        if len(speech_frames) >= 5 and self._model is not None:
                            audio_buf = np.concatenate(speech_frames).astype(np.float32) / 32768.0
                            try:
                                segments, _ = self._model.transcribe(
                                    audio_buf,
                                    language='en',
                                    beam_size=1,
                                    without_timestamps=True,
                                )
                                text = " ".join(s.text for s in segments).strip()
                                if text and WAKE_PATTERN.search(text):
                                    self._logger(f"Wake word detected ('{text}')")
                                    self._drain()
                                    speech_frames = []
                                    is_speaking = False
                                    silence_chunks = 0
                                    try:
                                        self._on_detect()
                                    except Exception as e:
                                        self._logger(f"Wake word: on_detect error — {e}")
                                    continue
                            except Exception as e:
                                self._logger(f"Wake word: transcribe error — {e}")

                        # Reset utterance state
                        speech_frames = []
                        is_speaking = False
                        silence_chunks = 0

            except Exception as e:
                self._logger(f"Wake word: inference error — {e}")

    def _drain(self) -> None:
        try:
            while True:
                self._queue.get_nowait()
        except Exception:
            pass
