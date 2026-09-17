"""
Screen Analyzer — Advanced real-time screen analysis, OCR, and window telemetry.
Allows Mark to inspect the user's screen in real time:
  - analyze_screen: Captures the screen and uses visual reasoning (Gemini Vision) to answer questions, explain errors, or describe layout
  - list_windows: Enumerate all visible application windows on the desktop
  - read_screen_text: Extract visible text, error messages, code blocks, or URLs from the current screen
"""
from __future__ import annotations

import io
import json
import sys
import time
import subprocess
import platform
from pathlib import Path
from typing import Any

from actions.camera_photo import capture_screenshot

_OS = platform.system()

def _get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent

def _get_api_key() -> str:
    path = _get_base_dir() / "config" / "api_keys.json"
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f).get("gemini_api_key", "")


def get_open_windows() -> list[dict[str, Any]]:
    """List open applications with window titles on the current desktop."""
    windows = []
    try:
        import psutil
        for p in psutil.process_iter(['pid', 'name']):
            try:
                name = p.info.get('name') or ""
                # Filter common GUI apps on Windows
                if name.lower().endswith('.exe') and name.lower() not in (
                    'svchost.exe', 'explorer.exe', 'services.exe', 'smss.exe', 
                    'csrss.exe', 'wininit.exe', 'taskhostw.exe', 'runtimebroker.exe'
                ):
                    windows.append({"pid": p.info['pid'], "process": name})
            except Exception:
                continue
    except Exception as e:
        print(f"[ScreenAnalyzer] Window enumeration error: {e}")
    return windows[:25]


def analyze_screen_with_gemini(query: str, img_bytes: bytes) -> str:
    """Analyze the screen frame using Gemini Multimodal Vision."""
    api_key = _get_api_key()
    if not api_key:
        return "Gemini API key not configured. Cannot perform visual screen analysis."

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)
        prompt = (
            f"You are Mark, analyzing the user's computer screen in real-time. "
            f"Answer this question or command accurately based strictly on what is visible: '{query}'. "
            f"If there are error messages, code lines, open apps, or UI buttons, mention them clearly. "
            f"Be concise, technical, and direct."
        )

        image_part = types.Part.from_bytes(data=img_bytes, mime_type="image/png")
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[image_part, prompt]
        )
        return response.text.strip() if response and response.text else "Screen analyzed, but no conclusive answer returned."
    except Exception as e:
        print(f"[ScreenAnalyzer] Gemini visual analysis error: {e}")
        return f"Visual analysis encountered an error: {e}"


def screen_analyzer(parameters: dict, player=None, speak=None) -> str:
    """Entry point for screen_analyzer tool."""
    params = parameters or {}
    action = str(params.get("action") or "analyze_screen").lower().strip()
    query = str(params.get("query") or params.get("question") or "What is currently visible on my screen?").strip()

    print(f"[ScreenAnalyzer] Action: '{action}' | Query: '{query[:60]}'")
    if player and hasattr(player, "write_log"):
        player.write_log(f"[Vision] {action}: {query[:40]}")

    if action in ("list_windows", "windows", "open_apps"):
        wins = get_open_windows()
        if not wins:
            return "No foreground user applications detected."
        names = sorted(list({w['process'] for w in wins}))
        return f"Currently running applications ({len(names)}):\n• " + "\n• ".join(names[:15])

    if action in ("analyze_screen", "inspect", "read_screen", "screen_qa", "read_text"):
        # 1. Capture screen
        path, img_bytes = capture_screenshot()
        if not img_bytes:
            return "Failed to capture screen image for analysis."

        if player and hasattr(player, "show_camera_frame"):
            player.show_camera_frame(img_bytes)

        # 2. Run vision inference
        analysis = analyze_screen_with_gemini(query, img_bytes)
        return f"Screen Analysis Result:\n{analysis}"

    return f"Unknown action '{action}'. Supported: 'analyze_screen', 'list_windows', 'read_screen'."


# ── Tool declaration (auto-discovered by core/action_loader.py) ──────────────
TOOL = {
    "name": "screen_analyzer",
    "description": (
        "Advanced real-time screen analysis and vision intelligence. "
        "Use when the user asks 'screen par kya dikh raha hai?', 'analyze this error', 'read this code from screen', "
        "'what application is open?', or to inspect text, UI layout, and active windows."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "Action: 'analyze_screen' (visual Q&A of screen) | 'list_windows' (list active apps) | 'read_screen'"
            },
            "query": {
                "type": "STRING",
                "description": "Specific question or analysis request about the screen (e.g. 'What is the error on screen?', 'Summarize this webpage')"
            }
        },
        "required": ["action"]
    },
    "handler": screen_analyzer,
}
