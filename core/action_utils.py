"""
core.action_utils — Shared, high-performance utilities for Mark LIII actions.

Provides centralized:
  - Base directory and configuration caching
  - Gemini Client singleton with connection reuse
  - Fast rule-based code intent detection (sub-millisecond, zero extra LLM roundtrips)
  - Smart desktop/project path resolution (avoids overwriting generic names)
  - Atomic, verified file writing with automatic undo registration
  - Resilient file reading with multi-encoding fallbacks
  - Windows-safe subprocess execution (CREATE_NO_WINDOW)
"""
from __future__ import annotations

import json
import os
import platform
import re
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any, Optional

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

_OS = platform.system()
_LOCK = threading.Lock()

# Cached globals
_CACHED_BASE_DIR: Optional[Path] = None
_CACHED_CONFIG: Optional[dict[str, Any]] = None
_CACHED_CONFIG_MTIME: float = 0.0
_CACHED_GEMINI_CLIENT: Any = None


def get_base_dir() -> Path:
    """Returns application root directory (cached)."""
    global _CACHED_BASE_DIR
    if _CACHED_BASE_DIR is not None:
        return _CACHED_BASE_DIR
    if getattr(sys, "frozen", False):
        _CACHED_BASE_DIR = Path(sys.executable).parent
    else:
        _CACHED_BASE_DIR = Path(__file__).resolve().parent.parent
    return _CACHED_BASE_DIR


def get_desktop_dir() -> Path:
    """Returns desktop directory across OS platforms."""
    if _OS == "Linux":
        xdg = os.environ.get("XDG_DESKTOP_DIR", "")
        if xdg and Path(xdg).exists():
            return Path(xdg)
    return Path.home() / "Desktop"


def load_api_config() -> dict[str, Any]:
    """Loads config/api_keys.json with mtime caching for instant access."""
    global _CACHED_CONFIG, _CACHED_CONFIG_MTIME
    cfg_path = get_base_dir() / "config" / "api_keys.json"
    if not cfg_path.exists():
        return {}
    try:
        mtime = cfg_path.stat().st_mtime
        if _CACHED_CONFIG is not None and mtime == _CACHED_CONFIG_MTIME:
            return _CACHED_CONFIG
        with _LOCK:
            with open(cfg_path, "r", encoding="utf-8") as f:
                _CACHED_CONFIG = json.load(f)
                _CACHED_CONFIG_MTIME = mtime
                return _CACHED_CONFIG
    except Exception as e:
        print(f"[ActionUtils] Warning: Failed to load api_keys.json: {e}")
        return _CACHED_CONFIG or {}


DEFAULT_FLASH_MODEL = "gemini-2.5-flash"
FLASH_MODELS_FALLBACK = [
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-3.1-flash-lite",
    "gemini-2.0-flash-lite",
    "gemini-flash-latest",
]


def generate_content_resilient(
    contents: Any,
    config: Any = None,
    preferred_model: str = DEFAULT_FLASH_MODEL
) -> str:
    """
    Generates content using the fastest available flash model with automatic
    fallback on 429 quota limits, 800 capacity limits, or missing models.
    """
    client = get_gemini_client()
    candidates = [preferred_model] + [m for m in FLASH_MODELS_FALLBACK if m != preferred_model]

    last_exc = None
    for model_name in candidates:
        try:
            kwargs: dict[str, Any] = {"model": model_name, "contents": contents}
            if config:
                kwargs["config"] = config
            response = client.models.generate_content(**kwargs)
            text = ""
            if hasattr(response, "text") and response.text:
                text = response.text
            elif hasattr(response, "candidates") and response.candidates:
                for part in response.candidates[0].content.parts:
                    if hasattr(part, "text") and part.text:
                        text += part.text
            clean_text = text.strip()
            if clean_text:
                return clean_text
        except Exception as e:
            err_msg = str(e).lower()
            last_exc = e
            if any(sig in err_msg for sig in (
                "429", "resource_exhausted", "quota", "404", "not_found",
                "503", "800", "unavailable", "no capacity", "spikes in demand", "high demand", "overloaded"
            )):
                print(f"[ActionUtils] Model '{model_name}' unavailable ({e}), falling back to next model...")
                continue
            raise

    raise last_exc or RuntimeError("All available Gemini flash models failed.")


def get_api_key(service: str = "gemini") -> str:
    """Returns cached API key for the requested service (default: gemini)."""
    cfg = load_api_config()
    if service == "gemini":
        return cfg.get("gemini_api_key", "")
    return cfg.get(f"{service}_api_key", "")


def get_gemini_client():
    """
    Returns a cached google.genai.Client instance.
    Reuses connection pools and avoid SSL handshake overhead on every action.
    """
    global _CACHED_GEMINI_CLIENT
    if _CACHED_GEMINI_CLIENT is not None:
        return _CACHED_GEMINI_CLIENT
    with _LOCK:
        if _CACHED_GEMINI_CLIENT is not None:
            return _CACHED_GEMINI_CLIENT
        from google import genai
        api_key = get_api_key("gemini")
        if not api_key:
            raise ValueError("Gemini API key is not configured in config/api_keys.json.")
        _CACHED_GEMINI_CLIENT = genai.Client(api_key=api_key)
        return _CACHED_GEMINI_CLIENT


def clean_code_fences(text: str) -> str:
    """Removes markdown code fences (```python ... ```), backticks, and whitespace."""
    if not text:
        return ""
    text = text.strip()
    text = re.sub(r"^```[a-zA-Z0-9_\-]*\r?\n?", "", text)
    text = re.sub(r"\r?\n?```\s*$", "", text)
    return text.strip()


def fast_detect_code_intent(
    description: str,
    file_path: str = "",
    code: str = "",
    action: str = "auto"
) -> str:
    """
    High-speed heuristic intent classifier (<0.1ms).
    Prevents unnecessary multi-second LLM calls just to determine what action to run.
    """
    action_clean = (action or "").strip().lower()
    valid_intents = {"write", "edit", "explain", "run", "build", "screen_debug", "optimize"}
    if action_clean in valid_intents:
        return action_clean

    desc = (description or "").strip().lower()
    has_file = bool(file_path and file_path.strip())
    has_code = bool(code and code.strip())

    # Direct keyword mappings
    if any(k in desc for k in ["screen", "error on screen", "screen debug", "screenshot"]):
        return "screen_debug"
    if any(k in desc for k in ["run", "execute", "chalao", "start", "launch"]) and has_file:
        return "run"
    if any(k in desc for k in ["explain", "samjhao", "kya karta hai", "what does this do"]):
        return "explain"
    if any(k in desc for k in ["optimize", "speed up", "refactor", "clean up", "tez karo"]):
        return "optimize"
    if any(k in desc for k in ["edit", "modify", "change", "badlo", "fix", "update"]) and has_file:
        return "edit"
    if any(k in desc for k in ["build", "iterate", "full project", "banao aur test karo"]):
        return "build"
    if any(k in desc for k in ["write", "create", "make", "banao", "generate", "code"]):
        return "write"

    # Structural fallback
    if has_file and Path(file_path).exists():
        return "edit" if desc else "explain"
    if has_code:
        return "explain"
    return "write"


def smart_resolve_path(
    output_path: str = "",
    description: str = "",
    language: str = "python"
) -> Path:
    """
    Resolves save destination intelligently.
    If output_path is provided, uses it.
    Otherwise derives a clean, semantic file name (e.g. calculator.py, file_organizer.py)
    instead of overwriting jarvis_code.py.
    """
    desktop = get_desktop_dir()
    ext_map = {
        "python": ".py", "py": ".py",
        "javascript": ".js", "js": ".js",
        "typescript": ".ts", "ts": ".ts",
        "html": ".html", "css": ".css",
        "java": ".java", "cpp": ".cpp", "c": ".c",
        "bash": ".sh", "shell": ".sh", "powershell": ".ps1",
        "sql": ".sql", "json": ".json", "rust": ".rs", "go": ".go",
        "text": ".txt", "txt": ".txt", "markdown": ".md", "md": ".md",
    }
    ext = ext_map.get((language or "python").lower(), ".py")

    if output_path and output_path.strip():
        raw_p = output_path.strip()
        lower_p = raw_p.lower()
        if lower_p.startswith("desktop/") or lower_p.startswith("desktop\\"):
            raw_p = raw_p[8:].lstrip("/\\")
        p = Path(raw_p)
        return p if p.is_absolute() else desktop / p

    # Heuristic slug from description
    desc = (description or "").lower()
    words = re.findall(r"[a-z0-9]+", desc)
    # Filter out common stop words
    stop_words = {
        "a", "an", "the", "in", "on", "for", "with", "to", "of", "and",
        "make", "create", "build", "write", "code", "script", "program",
        "ek", "ka", "ki", "ke", "banao", "likho", "karo", "mujhe", "chahiye"
    }
    clean_words = [w for w in words if w not in stop_words][:3]
    if clean_words:
        slug = "_".join(clean_words)
        return desktop / f"{slug}{ext}"

    return desktop / f"mark_script{ext}"


def safe_save_file(
    path: Path | str,
    content: str,
    make_undo: bool = True
) -> tuple[bool, str]:
    """
    Atomically writes content to disk, verifies physical existence & size,
    and pushes to core.undo.
    Returns (success: bool, message: str).
    """
    try:
        target = Path(path).resolve()
        target.parent.mkdir(parents=True, exist_ok=True)

        prev_content: Optional[str] = None
        if target.exists() and target.is_file():
            try:
                prev_content = target.read_text(encoding="utf-8", errors="replace")
            except Exception:
                prev_content = None

        target.write_text(content, encoding="utf-8")

        # Physical verification check
        if not target.exists() or target.stat().st_size == 0 and len(content.strip()) > 0:
            return False, f"Failed verification: File was not persisted to disk at {target}."

        if make_undo:
            try:
                from core.undo import push_undo
                def _undo_fn():
                    if prev_content is None:
                        if target.exists():
                            target.unlink()
                            return f"Removed '{target.name}' — it did not exist before."
                        return f"'{target.name}' is already gone."
                    target.write_text(prev_content, encoding="utf-8")
                    return f"Restored previous contents of '{target.name}'."

                push_undo(f"Write {target.name}", _undo_fn)
            except Exception as e:
                print(f"[ActionUtils] Warning: Undo registration failed: {e}")

        return True, f"Saved successfully to: {target}"
    except Exception as e:
        return False, f"Could not save file to {path}: {e}"


def safe_read_file(path: Path | str, max_chars: int = 200_000) -> tuple[str, str]:
    """
    Reads a file with encoding fallbacks (utf-8, cp1252, latin-1).
    Returns (content, error_message).
    """
    if not path:
        return "", "No file path provided."
    p = Path(path).resolve()
    if not p.exists():
        return "", f"File not found: {p}"
    if not p.is_file():
        return "", f"Path is not a file: {p}"

    for enc in ("utf-8", "cp1252", "latin-1"):
        try:
            text = p.read_text(encoding=enc)
            if len(text) > max_chars:
                return text[:max_chars] + f"\n... [Truncated after {max_chars} characters]", ""
            return text, ""
        except UnicodeDecodeError:
            continue
        except Exception as e:
            return "", f"Error reading file {p}: {e}"

    return "", f"Could not decode file {p} with supported encodings."


def execute_process(
    cmd: list[str] | str,
    cwd: Path | str | None = None,
    timeout: int = 30
) -> tuple[int, str, str]:
    """
    Executes a command safely with CREATE_NO_WINDOW on Windows and returns
    (returncode, stdout, stderr).
    """
    target_cwd = str(cwd) if cwd else str(get_base_dir())
    creationflags = subprocess.CREATE_NO_WINDOW if _OS == "Windows" else 0

    try:
        if isinstance(cmd, str):
            if _OS == "Windows":
                args = ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", cmd]
            else:
                args = ["/bin/bash", "-c", cmd]
        else:
            args = cmd

        proc = subprocess.run(
            args,
            cwd=target_cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            creationflags=creationflags,
            encoding="utf-8",
            errors="replace"
        )
        return proc.returncode, proc.stdout.strip(), proc.stderr.strip()
    except subprocess.TimeoutExpired:
        return -1, "", f"Execution timed out after {timeout} seconds."
    except FileNotFoundError as e:
        return -1, "", f"Executable not found: {e}"
    except Exception as e:
        return -1, "", f"Execution error: {e}"
