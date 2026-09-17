"""
Brain Engine — Cognitive Human-Brain-Like Memory System for Mark.
Implements the continuous Cognitive Loop:
  LEARN -> STORE -> RECALL -> INTROSPECT -> REINFORCE / TEACH AGAIN -> EVOLVE

Stores memories in structured JSON with:
  - Concept & Topic tagging
  - Category (knowledge, rules, habits, preferences, experiences, concepts)
  - Importance level (1-5)
  - Reinforcement counter (spaced repetition / continuous teaching)
  - Semantic & lexical fuzzy search
  - Time-stamped learning history
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime
from pathlib import Path
from threading import RLock
from typing import Any


def _get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


BASE_DIR = _get_base_dir()
BRAIN_STORE_PATH = BASE_DIR / "memory" / "brain_store.json"
LONG_TERM_PATH = BASE_DIR / "memory" / "long_term.json"
_lock = RLock()


def _empty_brain() -> dict[str, Any]:
    return {
        "version": "2.0",
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total_learnings": 0,
        "memories": [],
    }


def load_brain() -> dict[str, Any]:
    """Load the brain store JSON."""
    if not BRAIN_STORE_PATH.exists():
        initial = _empty_brain()
        # Seed from long_term.json if available
        _seed_from_long_term(initial)
        save_brain(initial)
        return initial

    with _lock:
        try:
            data = json.loads(BRAIN_STORE_PATH.read_text(encoding="utf-8"))
            if isinstance(data, dict) and "memories" in data:
                return data
            return _empty_brain()
        except Exception as e:
            print(f"[BrainEngine] ⚠️ Load error: {e}")
            return _empty_brain()


def save_brain(brain: dict[str, Any]) -> None:
    """Save the brain store JSON atomically."""
    if not isinstance(brain, dict):
        return
    brain["total_learnings"] = len(brain.get("memories", []))
    BRAIN_STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _lock:
        BRAIN_STORE_PATH.write_text(
            json.dumps(brain, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )


def _seed_from_long_term(brain: dict[str, Any]) -> None:
    """Seed initial brain memories from long_term.json if present."""
    if not LONG_TERM_PATH.exists():
        return
    try:
        data = json.loads(LONG_TERM_PATH.read_text(encoding="utf-8"))
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for cat in ("identity", "preferences", "projects", "relationships", "wishes", "notes"):
            items = data.get(cat, {})
            if isinstance(items, dict):
                for key, val_obj in items.items():
                    val = val_obj.get("value") if isinstance(val_obj, dict) else str(val_obj)
                    if val and isinstance(val, str) and val.strip():
                        topic = key.replace("_", " ").title()
                        brain["memories"].append({
                            "id": f"seed_{cat}_{key}",
                            "topic": topic,
                            "content": val.strip(),
                            "category": "preference" if cat == "preferences" else ("concept" if cat == "projects" else "knowledge"),
                            "tags": [cat, key.lower()],
                            "importance": 4 if cat in ("identity", "projects") else 3,
                            "reinforcement_count": 1,
                            "learned_at": now_str,
                            "last_recalled_at": now_str,
                            "notes": f"Initial memory from {cat}"
                        })
    except Exception as e:
        print(f"[BrainEngine] Seed error: {e}")


def _extract_tags(text: str) -> list[str]:
    """Extract clean lowercase keyword tokens for fast indexing."""
    words = re.findall(r"\b[a-zA-Z0-9_\u0900-\u097F]{2,}\b", text.lower())
    stopwords = {
        "the", "and", "is", "in", "to", "of", "a", "that", "it", "with",
        "as", "for", "on", "was", "at", "by", "an", "be", "this", "from",
        "hai", "ki", "ka", "ke", "ko", "me", "se", "aur", "toh", "bhi", "ho"
    }
    return sorted(list({w for w in words if w not in stopwords}))[:12]


def learn(
    content: str,
    topic: str | None = None,
    category: str = "knowledge",
    importance: int = 3,
    tags: list[str] | None = None,
    notes: str = ""
) -> dict[str, Any]:
    """
    Learn a new concept or reinforce an existing memory.
    Continuous learning loop: If an existing memory on this topic is found,
    reinforce it (increment reinforcement_count, update content with new insights).
    """
    brain = load_brain()
    memories: list[dict[str, Any]] = brain.setdefault("memories", [])
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    clean_content = content.strip()
    clean_topic = (topic or "").strip()
    if not clean_topic:
        # Infer topic from first few words
        words = clean_content.split()
        clean_topic = " ".join(words[:4]).title() if words else "General Fact"

    clean_category = category.lower().strip()
    if clean_category not in ("knowledge", "rule", "habit", "preference", "experience", "relationship", "concept"):
        clean_category = "knowledge"

    auto_tags = _extract_tags(f"{clean_topic} {clean_content}")
    if tags:
        auto_tags = sorted(list(set(auto_tags + [t.lower().strip() for t in tags if t.strip()])))

    # Check if a memory with similar topic or content already exists (Reinforcement loop)
    existing_mem = None
    clean_topic_lower = clean_topic.lower()
    for m in memories:
        if m["topic"].lower() == clean_topic_lower or m["content"].lower() == clean_content.lower():
            existing_mem = m
            break

    if existing_mem:
        # Reinforce existing memory!
        existing_mem["reinforcement_count"] = existing_mem.get("reinforcement_count", 1) + 1
        existing_mem["importance"] = max(existing_mem.get("importance", 3), min(importance, 5))
        existing_mem["last_recalled_at"] = now_str
        # If new content is richer or different, update content with reinforcement log
        if existing_mem["content"] != clean_content:
            existing_mem["content"] = clean_content
        # Merge tags
        existing_mem["tags"] = sorted(list(set(existing_mem.get("tags", []) + auto_tags)))
        if notes:
            existing_mem["notes"] = f"{existing_mem.get('notes', '')}; {notes}".strip("; ")
        save_brain(brain)
        return {
            "status": "reinforced",
            "memory": existing_mem,
            "message": (
                f"Memory on '{clean_topic}' reinforced! "
                f"Reinforcement Level: {existing_mem['reinforcement_count']}x."
            )
        }
    else:
        # Create new brain memory node
        mem_id = f"mem_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{len(memories) + 1}"
        new_node = {
            "id": mem_id,
            "topic": clean_topic,
            "content": clean_content,
            "category": clean_category,
            "tags": auto_tags,
            "importance": min(max(importance, 1), 5),
            "reinforcement_count": 1,
            "learned_at": now_str,
            "last_recalled_at": now_str,
            "notes": notes
        }
        memories.append(new_node)
        save_brain(brain)
        return {
            "status": "learned",
            "memory": new_node,
            "message": f"Successfully learned and stored into brain memory: '{clean_topic}'."
        }


def search(query: str, category: str | None = None, limit: int = 6) -> list[dict[str, Any]]:
    """
    Cognitive search across all brain memories.
    Scores by exact topic match, tag match, lexical similarity, and reinforcement weight.
    """
    brain = load_brain()
    memories: list[dict[str, Any]] = brain.get("memories", [])
    if not memories:
        return []

    clean_query = query.strip().lower()
    query_tokens = _extract_tags(clean_query)
    results = []

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    for m in memories:
        if category and m.get("category", "").lower() != category.lower().strip():
            continue

        topic_lower = m.get("topic", "").lower()
        content_lower = m.get("content", "").lower()
        tags = [t.lower() for t in m.get("tags", [])]

        score = 0
        if clean_query:
            if clean_query == topic_lower:
                score += 50
            elif clean_query in topic_lower:
                score += 30
            elif clean_query in content_lower:
                score += 20

            # Token level matching
            for token in query_tokens:
                if token == topic_lower:
                    score += 15
                elif token in topic_lower:
                    score += 10
                if token in tags:
                    score += 8
                if token in content_lower:
                    score += 5

            # Importance & Reinforcement boost
            score += m.get("importance", 3) * 2
            score += min(m.get("reinforcement_count", 1), 5) * 3
        else:
            # Empty query returns newest or most reinforced
            score = m.get("importance", 3) + m.get("reinforcement_count", 1)

        if score > 0 or not clean_query:
            results.append((score, m))

    results.sort(key=lambda x: x[0], reverse=True)
    top_matches = [m for _, m in results[:limit]]

    # Update last_recalled_at for recalled memories
    with _lock:
        for m in top_matches:
            m["last_recalled_at"] = now_str
        save_brain(brain)

    return top_matches


def introspect(query: str | None = None) -> str:
    """
    Human-brain introspection.
    When user asks: 'Dekho apni memory and iske baare me batao' or 'What is in your memory?'.
    Synthesizes facts, rules, and concepts from its neural store.
    """
    brain = load_brain()
    memories: list[dict[str, Any]] = brain.get("memories", [])
    total = len(memories)

    if total == 0:
        return "Mere brain me abhi koi stored memories nahi hain. Aap mujhe kuch bhi sikha sakte hain (e.g. 'Ye yaad rakho ki...')."

    if query and query.strip():
        # Specific introspection on topic/query
        matches = search(query, limit=5)
        if not matches:
            return f"Maine apni memory me check kiya, lekin '{query}' ke baare me koi direct fact ya lesson nahi mila. Aap chahein toh mujhe iske baare me sikha sakte hain!"

        lines = [f"[Brain] Introspection for '{query}':"]
        for idx, m in enumerate(matches, 1):
            reinf = f" (Reinforced {m['reinforcement_count']}x)" if m.get("reinforcement_count", 1) > 1 else ""
            lines.append(f"\n{idx}. [{m.get('category', 'knowledge').upper()}] {m['topic']}{reinf}:")
            lines.append(f"   - Fact/Lesson: {m['content']}")
            if m.get("notes"):
                lines.append(f"   - Context: {m['notes']}")
            lines.append(f"   - Learned on: {m.get('learned_at', 'unknown')}")

        return "\n".join(lines)

    # Holistic Brain Overview
    categories: dict[str, int] = {}
    for m in memories:
        cat = m.get("category", "knowledge").title()
        categories[cat] = categories.get(cat, 0) + 1

    cat_breakdown = ", ".join(f"{c}: {cnt}" for c, cnt in categories.items())
    recent = sorted(memories, key=lambda x: x.get("learned_at", ""), reverse=True)[:4]

    lines = [
        f"[Brain] Cognitive Brain Status (Total Learnings: {total}):",
        f"- Memory Categories: {cat_breakdown}",
        "\n* Recently Learned & Reinforced Concepts:"
    ]
    for m in recent:
        lines.append(f"- [{m.get('category', 'knowledge')}] {m['topic']}: {m['content'][:90]}...")

    lines.append("\nAap mujhse kisi bhi specific topic par pooch sakte hain ya naya rule/fact sikha sakte hain!")
    return "\n".join(lines)


def forget(query: str) -> str:
    """Remove a memory matching the query from the brain store."""
    brain = load_brain()
    memories: list[dict[str, Any]] = brain.get("memories", [])
    clean_query = query.strip().lower()

    retained = []
    removed = []

    for m in memories:
        if clean_query in m["topic"].lower() or clean_query in m["content"].lower():
            removed.append(m["topic"])
        else:
            retained.append(m)

    if removed:
        brain["memories"] = retained
        save_brain(brain)
        return f"Forgotten {len(removed)} memory item(s): {', '.join(removed)}."
    return f"No memory found matching '{query}' to forget."
