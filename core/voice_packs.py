"""
Energetic Voice Pack & Startup Audio Engine for MARK-LIII.

Plays dynamic high-energy startup sound effects + voice packs when waking up,
triggering reactor visualizer pulses and instant audio feedback without blocking.
"""
from __future__ import annotations

import os
import random
import threading
from pathlib import Path
from typing import Optional

BASE_DIR = Path(__file__).resolve().parent.parent
SOUNDS_DIR = BASE_DIR / "sounds" / "wake_up"

VOICE_PACK_LINES = {
    "wake_1.wav": "Hey there! Systems are all online and fully charged. Ready whenever you are, let's do this!",
    "wake_2.wav": "Good to see you! Neural cores are active and arc reactor is at full power. What are we working on today?",
    "wake_3.wav": "Mark online! All diagnostics are looking super green and ready. How can I help you, sir?",
    "wake_4.wav": "Hey! Systems engaged and running perfectly smooth. Ready for action!",
    "wake_hindi.wav": "Hey! Main bilkul ready hoon aur saare systems active hain. Boliye, kya karna hai?",
}


def get_available_wake_sounds() -> list[Path]:
    """Return all available .wav files in the wake_up sounds directory."""
    if not SOUNDS_DIR.exists():
        return []
    return [p for p in SOUNDS_DIR.glob("*.wav") if p.is_file()]


def play_wake_sound(ui=None, specific_name: Optional[str] = None) -> Optional[str]:
    """
    Play a random or specific energetic wake-up voice line in a background thread.
    Synchronizes the HUD Arc Reactor pulse animation and returns the spoken text.
    """
    files = get_available_wake_sounds()
    if not files:
        return None

    if specific_name:
        candidates = [f for f in files if f.name == specific_name]
        chosen = candidates[0] if candidates else random.choice(files)
    else:
        chosen = random.choice(files)

    spoken_text = VOICE_PACK_LINES.get(chosen.name, "Mark online! Systems fully operational.")

    def _worker():
        try:
            # Trigger high-energy HUD pulse & state
            if ui:
                try:
                    ui.set_state("SPEAKING")
                    if hasattr(ui, "hud"):
                        ui.hud.speaking = True
                        ui.hud.emotion = "EXCITED"
                        for _ in range(3):
                            ui.hud.trigger_pulse()
                    if hasattr(ui, "write_log"):
                        ui.write_log(f"MARK: {spoken_text}")
                except Exception:
                    pass

            # Native zero-latency Windows sound playback
            import winsound
            winsound.PlaySound(str(chosen), winsound.SND_FILENAME)

        except Exception as e:
            # Fallback to sounddevice if winsound fails
            try:
                import sounddevice as sd
                import wave
                import numpy as np
                with wave.open(str(chosen), "rb") as wf:
                    sr = wf.getframerate()
                    frames = wf.readframes(wf.getnframes())
                    arr = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
                    sd.play(arr, sr)
                    sd.wait()
            except Exception:
                pass
        finally:
            if ui:
                try:
                    if hasattr(ui, "hud"):
                        ui.hud.speaking = False
                    ui.set_state("LISTENING")
                except Exception:
                    pass

    t = threading.Thread(target=_worker, daemon=True, name="WakeSoundPlayback")
    t.start()
    return spoken_text
