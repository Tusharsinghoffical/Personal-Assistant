# web_search.py — High-speed web search & information gathering for Mark LIII
import re
import threading
import time
from pathlib import Path

from core.action_utils import get_base_dir, get_gemini_client

BASE_DIR = get_base_dir()

# In-memory query cache with TTL (5 minutes)
_CACHE_LOCK = threading.Lock()
_CACHE: dict[str, tuple[float, str]] = {}
_CACHE_TTL = 300.0  # 5 minutes


def _get_cached(key: str) -> str | None:
    now = time.monotonic()
    with _CACHE_LOCK:
        if key in _CACHE:
            ts, val = _CACHE[key]
            if now - ts < _CACHE_TTL:
                return val
            del _CACHE[key]
    return None


def _set_cached(key: str, val: str) -> None:
    if not val or len(val.strip()) < 10:
        return
    now = time.monotonic()
    with _CACHE_LOCK:
        _CACHE[key] = (now, val)


def _gemini_search(query: str) -> str:
    client   = get_gemini_client()
    response = client.models.generate_content(
        model="gemini-flash-latest",
        contents=query,
        config={"tools": [{"google_search": {}}]},
    )

    text = ""
    for part in response.candidates[0].content.parts:
        if hasattr(part, "text") and part.text:
            text += part.text

    text = text.strip()
    if not text:
        raise ValueError("Gemini returned an empty response.")
    return text


def _ddg_search(query: str, max_results: int = 6) -> list[dict]:
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=RuntimeWarning)
        try:
            from ddgs import DDGS
        except ImportError:
            from duckduckgo_search import DDGS

    results = []
    try:
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_results):
                results.append({
                    "title":   r.get("title",  ""),
                    "snippet": r.get("body",   ""),
                    "url":     r.get("href",   ""),
                })
    except Exception as e:
        print(f"[WebSearch] ⚠️ DDG text failed: {e}")
    return results


def _ddg_news(query: str, max_results: int = 8) -> list[dict]:
    """DDG news search — returns actual articles, not website homepages."""
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=RuntimeWarning)
        try:
            from ddgs import DDGS
        except ImportError:
            from duckduckgo_search import DDGS

    results = []
    try:
        with DDGS() as ddgs:
            for r in ddgs.news(query, max_results=max_results):
                results.append({
                    "title":   r.get("title",  ""),
                    "snippet": r.get("body",   ""),
                    "url":     r.get("url",    ""),
                    "source":  r.get("source", ""),
                })
    except Exception as e:
        print(f"[WebSearch] ⚠️ DDG news() failed ({e}) — falling back to text search")
        results = _ddg_search(query, max_results=max_results)
    return results


def _format_ddg(query: str, results: list[dict]) -> str:
    if not results:
        return f"No results found for: {query}"

    lines = [f"Search results for: {query}\n"]
    for i, r in enumerate(results, 1):
        if r.get("title"):   lines.append(f"{i}. {r['title']}")
        if r.get("snippet"): lines.append(f"   {r['snippet']}")
        if r.get("url"):     lines.append(f"   Source: {r['url']}")
        lines.append("")
    return "\n".join(lines).strip()


def _format_news(query: str, results: list[dict]) -> str:
    if not results:
        return f"No news found for: {query}"

    lines = [f"Latest news: {query}\n"]
    for i, r in enumerate(results, 1):
        title = r.get("title", "")
        if not title:
            continue
        src = f"  [{r['source']}]" if r.get("source") else ""
        lines.append(f"{i}. {title}{src}")
        if r.get("snippet"):
            lines.append(f"   {r['snippet'][:140]}")
        if r.get("url"):
            lines.append(f"   {r['url']}")
        lines.append("")
    return "\n".join(lines).strip()


def _fast_race(primary_fn, fallback_fn, timeout: float = 4.5) -> str:
    """
    Races primary (e.g. Gemini) against fallback (e.g. DDG) with a quick timeout.
    Returns whichever delivers valid data first, ensuring zero long freezes.
    """
    box = [None]
    lock = threading.Lock()
    done = threading.Event()

    def _worker(fn):
        try:
            res = fn()
            if res and len(res.strip()) > 40:
                with lock:
                    if box[0] is None:
                        box[0] = res
                done.set()
        except Exception:
            pass

    t1 = threading.Thread(target=_worker, args=(primary_fn,), daemon=True)
    t2 = threading.Thread(target=_worker, args=(fallback_fn,), daemon=True)
    t1.start()
    t2.start()

    done.wait(timeout=timeout)
    if box[0] is not None:
        return box[0]

    # If neither finished within timeout, give one final 2s grace to either
    done.wait(timeout=2.0)
    return box[0] or ""


# ── Modes ──────────────────────────────────────────────────────────────────────

def _search(query: str) -> str:
    cached = _get_cached(f"search:{query.lower()}")
    if cached:
        return cached

    def _try_gemini():
        return _gemini_search(query)

    def _try_ddg():
        res = _ddg_search(query, max_results=6)
        return _format_ddg(query, res)

    # Fast race with 4.5s threshold
    result = _fast_race(_try_gemini, _try_ddg, timeout=4.5)
    if not result:
        # Final synchronous fallback attempt
        try:
            result = _try_ddg()
        except Exception as e:
            result = f"Search failed: {e}"

    _set_cached(f"search:{query.lower()}", result)
    return result


def _news(query: str) -> str:
    cached = _get_cached(f"news:{query.lower()}")
    if cached:
        return cached

    gemini_query = f"latest news today: {query}" if query else "top world news today"
    ddg_query    = query if query else "world news today"

    def _try_gemini():
        return _gemini_search(gemini_query)

    def _try_ddg():
        res = _ddg_news(ddg_query, max_results=8)
        return _format_news(ddg_query, res)

    result = _fast_race(_try_gemini, _try_ddg, timeout=4.5)
    if not result:
        try:
            result = _try_ddg()
        except Exception as e:
            result = f"News search failed: {e}"

    _set_cached(f"news:{query.lower()}", result)
    return result


def _research(query: str) -> str:
    cached = _get_cached(f"research:{query.lower()}")
    if cached:
        return cached

    research_query = (
        f"Comprehensive, detailed explanation of: {query}. "
        "Include background context, key facts, current state, and important nuances."
    )
    try:
        res = _gemini_search(research_query)
    except Exception as e:
        print(f"[WebSearch] ⚠️ Research Gemini failed ({e}) — DDG fallback...")
        results = _ddg_search(query, max_results=10)
        res = _format_ddg(query, results)

    _set_cached(f"research:{query.lower()}", res)
    return res


def _price(query: str) -> str:
    cached = _get_cached(f"price:{query.lower()}")
    if cached:
        return cached

    price_query = f"current price of {query} — how much does it cost today"
    try:
        res = _gemini_search(price_query)
    except Exception as e:
        print(f"[WebSearch] ⚠️ Price Gemini failed ({e}) — DDG fallback...")
        results = _ddg_search(f"{query} price buy", max_results=6)
        res = _format_ddg(query, results)

    _set_cached(f"price:{query.lower()}", res)
    return res


def _compare(items: list[str], aspect: str) -> str:
    cache_key = f"compare:{':'.join(sorted(items))}:{aspect.lower()}"
    cached = _get_cached(cache_key)
    if cached:
        return cached

    query = (
        f"Compare {', '.join(items)} in terms of {aspect}. "
        "Give specific facts and data."
    )
    try:
        res = _gemini_search(query)
    except Exception as e:
        print(f"[WebSearch] ⚠️ Gemini compare failed: {e} — falling back to DDG")
        all_results: dict[str, list] = {}
        for item in items:
            try:
                all_results[item] = _ddg_search(f"{item} {aspect}", max_results=3)
            except Exception:
                all_results[item] = []

        lines = [f"Comparison — {aspect.upper()}", "─" * 40]
        for item in items:
            lines.append(f"\n▸ {item}")
            for r in all_results.get(item, [])[:2]:
                if r.get("snippet"):
                    lines.append(f"  • {r['snippet']}")
                if r.get("url"):
                    lines.append(f"    {r['url']}")
        res = "\n".join(lines)

    _set_cached(cache_key, res)
    return res


# ── Public entry point ─────────────────────────────────────────────────────────

def web_search(
    parameters: dict,
    response=None,
    player=None,
    session_memory=None,
) -> str:
    params = parameters or {}
    query  = params.get("query", "").strip()
    mode   = params.get("mode",  "search").lower().strip()
    items  = params.get("items", [])
    aspect = params.get("aspect", "general").strip() or "general"

    if not query and not items:
        return "Please provide a search query."

    if items and mode not in ("compare",):
        mode = "compare"

    if player:
        player.write_log(f"[Search:{mode}] {query or ', '.join(items)}")

    print(f"[WebSearch] 🔍 mode={mode!r}  query={query!r}")

    try:
        if mode == "compare" and items:
            return _compare(items, aspect)
        if mode == "news":
            return _news(query)
        if mode == "research":
            return _research(query)
        if mode == "price":
            return _price(query)
        return _search(query)

    except Exception as e:
        print(f"[WebSearch] ❌ All backends failed: {e}")
        return f"Search failed: {e}"


# ── Tool declaration (auto-discovered by core/action_loader.py) ──────────────
TOOL = {
    "name": "web_search",
    "description": "Searches the web quickly. Use for ANY question about current facts, events, prices, or information. Modes: 'search' (default), 'news' (latest headlines), 'research' (deep comprehensive answer), 'price' (product cost lookup), 'compare' (side-by-side comparison).",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "query": {
                "type": "STRING",
                "description": "Search query or topic"
            },
            "mode": {
                "type": "STRING",
                "description": "search | news | research | price | compare"
            },
            "items": {
                "type": "ARRAY",
                "items": {
                    "type": "STRING"
                },
                "description": "Items to compare (compare mode)"
            },
            "aspect": {
                "type": "STRING",
                "description": "Comparison aspect: price | specs | reviews | features"
            }
        },
        "required": [
            "query"
        ]
    },
    "handler": web_search,
}
