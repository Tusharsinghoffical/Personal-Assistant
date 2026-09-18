"""
data_parser.py — Advanced Data Parsing action for Mark LIII.

Inspired by the Jarvis "Advanced Data Parsing" feature:
  → Instant processing of datasets: CSV, JSON, TXT, LOG, XML files.
  → Extracts insights, summaries, statistics, and pattern detection.

Reuses:
  - core/action_utils.generate_content_resilient  (LLM analysis)
  - pathlib.Path                                   (file reading, same as file_controller.py)
  - core/action_utils.get_base_dir                (resolves relative paths)

Supports modes: summarize | extract | stats | find
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from core.action_utils import generate_content_resilient, get_base_dir

BASE_DIR = get_base_dir()

# Max chars sent to Gemini — keeps token cost low while covering most files
_MAX_CONTENT_CHARS = 12_000

# Supported extensions
_SUPPORTED = {".csv", ".json", ".txt", ".log", ".xml", ".md", ".tsv", ".yaml", ".yml"}


def _resolve_path(raw_path: str) -> Path:
    """Resolve absolute or relative (from BASE_DIR) file path."""
    p = Path(raw_path)
    if p.is_absolute():
        return p
    # Try relative to cwd, then relative to project root
    candidates = [Path.cwd() / p, BASE_DIR / p]
    for c in candidates:
        if c.exists():
            return c
    return p  # return as-is; error handling later


def _read_file(path: Path) -> str:
    """Read file content with smart truncation for large files."""
    suffix = path.suffix.lower()

    if suffix not in _SUPPORTED:
        raise ValueError(
            f"Unsupported file type '{suffix}'. "
            f"Supported: {', '.join(sorted(_SUPPORTED))}"
        )

    raw = path.read_text(encoding="utf-8", errors="replace")

    # For JSON: pretty-print for readability
    if suffix == ".json":
        try:
            parsed = json.loads(raw)
            raw = json.dumps(parsed, indent=2, ensure_ascii=False)
        except json.JSONDecodeError:
            pass  # use raw text as-is

    # Truncate with notice if too large
    if len(raw) > _MAX_CONTENT_CHARS:
        raw = raw[:_MAX_CONTENT_CHARS]
        raw += f"\n\n[...File truncated at {_MAX_CONTENT_CHARS} chars for analysis...]"

    return raw


def _build_prompt(mode: str, content: str, query: str, filename: str) -> str:
    mode_instructions = {
        "summarize": (
            "Provide a clear, concise summary of this data. "
            "What does it contain? What are the key points or trends? "
            "Keep the summary to 3-5 sentences."
        ),
        "stats": (
            "Analyze this data statistically. "
            "Report: row/entry counts, unique values, distributions, min/max/averages "
            "where applicable, and any notable outliers or anomalies. "
            "Be specific with numbers."
        ),
        "extract": (
            f"Extract the following from the data: {query or 'all key information, names, values, and patterns'}. "
            "Present extracted items clearly, organized by category if possible."
        ),
        "find": (
            f"Search this data for: {query or 'any notable patterns or anomalies'}. "
            "Report exact matches, related entries, and surrounding context. "
            "If not found, say so clearly."
        ),
    }

    instruction = mode_instructions.get(mode, mode_instructions["summarize"])

    return f"""You are Mark's data analysis module. A file has been provided for analysis.

File: {filename}
Mode: {mode.upper()}

Task: {instruction}

--- FILE CONTENT START ---
{content}
--- FILE CONTENT END ---

Rules:
- Be precise and factual. Only report what is actually in the data.
- Use the same language the user is likely using (detect from context, default to English).
- Format your response clearly. Use bullet points or a table if it helps readability.
- Do NOT add disclaimers like "As an AI..." — just give the analysis.
"""


def data_parser_action(
    parameters: dict,
    player=None,
    session_memory=None,
) -> str:
    raw_path = (
        parameters.get("file_path")
        or parameters.get("path")
        or parameters.get("file")
        or ""
    ).strip()

    mode  = (parameters.get("mode", "summarize") or "summarize").strip().lower()
    query = (parameters.get("query", "") or "").strip()

    if not raw_path:
        return (
            "Please provide a file path to analyze. "
            "Example: 'is file ko analyze karo: C:/Users/data.csv'"
        )

    valid_modes = {"summarize", "stats", "extract", "find"}
    if mode not in valid_modes:
        mode = "summarize"

    path = _resolve_path(raw_path)

    if player:
        player.write_log(f"[DataParser] {mode}: {path.name}")
    print(f"[DataParser] 📊 mode={mode!r}  file={path}")

    # ── Read file ──────────────────────────────────────────────────────────────
    if not path.exists():
        return f"File not found: {path}. Please check the path and try again."

    try:
        content = _read_file(path)
    except ValueError as e:
        return str(e)
    except PermissionError:
        return f"Permission denied — cannot read '{path.name}'."
    except Exception as e:
        return f"Failed to read file '{path.name}': {e}"

    if not content.strip():
        return f"File '{path.name}' appears to be empty."

    # ── Gemini analysis ────────────────────────────────────────────────────────
    prompt = _build_prompt(mode, content, query, path.name)

    try:
        result = generate_content_resilient(contents=prompt)
        if player:
            player.write_log(f"Mark (data): {result[:80]}...")
        return result
    except Exception as e:
        print(f"[DataParser] ❌ Analysis failed: {e}")
        # Graceful fallback — give basic stats without LLM
        lines  = content.splitlines()
        words  = len(re.findall(r"\S+", content))
        return (
            f"LLM analysis unavailable ({e}). "
            f"Basic stats for '{path.name}': "
            f"{len(lines)} lines, ~{words} words, {len(content)} characters."
        )


# ── Tool declaration (auto-discovered by core/action_loader.py) ──────────────
TOOL = {
    "name": "parse_data",
    "description": (
        "Reads and analyzes data files (CSV, JSON, TXT, LOG, XML, YAML, MD). "
        "Use when user wants to understand a file's contents, get statistics, "
        "extract specific information, or find patterns. "
        "Modes: 'summarize' (default overview), 'stats' (numbers/counts/averages), "
        "'extract' (pull specific info), 'find' (search for something)."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "file_path": {
                "type": "STRING",
                "description": "Full path to the file to analyze. E.g. 'C:/Users/data.csv'"
            },
            "mode": {
                "type": "STRING",
                "description": "Analysis mode: summarize | stats | extract | find  (default: summarize)"
            },
            "query": {
                "type": "STRING",
                "description": (
                    "What to extract or find (used in 'extract' and 'find' modes). "
                    "E.g. 'all email addresses', 'total sales', 'error entries'"
                )
            }
        },
        "required": ["file_path"]
    },
    "handler": data_parser_action,
}
