"""
Brain Memory — Human-brain-like cognitive memory system for Mark.
Enables Mark to:
  - learn / teach: Continuously acquire new knowledge, rules, user preferences, and habits (spaced repetition & reinforcement)
  - introspect / inspect: Examine its own memory ('dekho apni memory and iske baare me batao')
  - search / recall: Fast semantic and keyword search across stored memories
  - overview: Cognitive brain status and category breakdown
  - forget / unlearn: Delete or update outdated knowledge
"""
from __future__ import annotations

import json
from typing import Any

from memory.brain_engine import learn, search, introspect, forget, load_brain


def brain_memory_action(parameters: dict, player=None, speak=None) -> str:
    """Main handler for brain_memory tool."""
    params = parameters or {}
    action = str(params.get("action") or "introspect").lower().strip()
    query = str(params.get("query") or params.get("topic") or "").strip()
    content = str(params.get("content") or params.get("lesson") or params.get("fact") or "").strip()
    category = str(params.get("category") or "knowledge").lower().strip()
    importance = int(params.get("importance") or 3)
    notes = str(params.get("notes") or "").strip()

    print(f"[BrainMemory] Action: '{action}' | Query/Topic: '{query[:40]}' | Content: '{content[:50]}'")
    if player and hasattr(player, "write_log"):
        player.write_log(f"[Brain] {action}: {query[:30] or content[:30]}")

    # 1. Teach / Learn Loop
    if action in ("teach", "learn", "save", "remember", "store"):
        fact_text = content or query
        if not fact_text:
            return "Please provide what you want Mark to learn or remember."
        topic_text = query if content else None
        res = learn(
            content=fact_text,
            topic=topic_text,
            category=category,
            importance=importance,
            notes=notes
        )
        return res["message"]

    # 2. Introspection ("Dekho apni memory and iske baare me batao")
    if action in ("introspect", "inspect", "check_memory", "examine", "explain_memory"):
        search_query = query or content or None
        return introspect(search_query)

    # 3. Search & Recall
    if action in ("search", "recall", "find", "lookup"):
        search_term = query or content
        matches = search(search_term, limit=6)
        if not matches:
            return f"No memories found matching '{search_term}'."
        lines = [f"Found {len(matches)} relevant memory item(s):"]
        for idx, m in enumerate(matches, 1):
            reinf = f" (Reinforced {m.get('reinforcement_count', 1)}x)" if m.get("reinforcement_count", 1) > 1 else ""
            lines.append(f"{idx}. [{m.get('category', 'knowledge').upper()}] {m['topic']}{reinf}: {m['content']}")
        return "\n".join(lines)

    # 4. Cognitive Brain Overview
    if action in ("overview", "stats", "summary", "status"):
        return introspect(None)

    # 5. Forget / Unlearn
    if action in ("forget", "unlearn", "delete", "remove"):
        target = query or content
        if not target:
            return "Please specify what memory to forget."
        return forget(target)

    return f"Unknown brain action '{action}'. Supported: 'teach', 'introspect', 'search', 'overview', 'forget'."


# ── Tool declaration (auto-discovered by core/action_loader.py) ──────────────
TOOL = {
    "name": "brain_memory",
    "description": (
        "Cognitive human-brain-like memory system for Mark. "
        "Use when user wants Mark to learn or remember something ('ye yaad rakho', 'teach: ...', 'learn this rule'), "
        "when user asks Mark to inspect its own memory ('dekho apni memory and iske baare me batao', 'apni memory me check karo'), "
        "search memories ('memory search karo', 'recall what you know about X'), or provide brain overview."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": (
                    "Brain action to perform: "
                    "'teach' (learn/remember new fact or rule) | "
                    "'introspect' (examine memory on topic or summarize what Mark knows) | "
                    "'search' (search specific facts) | "
                    "'overview' (full cognitive summary) | "
                    "'forget' (unlearn a memory)"
                )
            },
            "query": {
                "type": "STRING",
                "description": "Topic, keyword, or question to search or introspect in memory (e.g. 'coding rules', 'Tushar', 'AMS project')"
            },
            "content": {
                "type": "STRING",
                "description": "The exact fact, lesson, preference, or rule to learn/teach"
            },
            "category": {
                "type": "STRING",
                "description": "Category of memory: 'knowledge' | 'rule' | 'habit' | 'preference' | 'concept' | 'relationship'"
            },
            "importance": {
                "type": "INTEGER",
                "description": "Importance level from 1 (minor) to 5 (critical rule/identity)"
            }
        },
        "required": ["action"]
    },
    "handler": brain_memory_action,
}
