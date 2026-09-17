"""
Brain Memory Action — Cognitive human-brain-like memory interface for Mark.
Enables Mark to:
  - learn / teach: Continuously acquire new knowledge, rules, habits, and preferences (spaced repetition & reinforcement)
  - introspect / inspect: Deeply examine its own brain memory container ('apni jaake memory dekho aur samjho')
  - commands / history: Review past commands and user instructions
  - search / recall: Fast semantic and keyword search across stored memories and past actions
  - overview / stats: Comprehensive cognitive brain statistics and status
  - forget / unlearn: Delete or update outdated memories
"""
from __future__ import annotations

from typing import Any
from memory.brain_engine import (
    learn, search, introspect, forget, load_brain,
    search_commands, record_command, get_brain_stats
)


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
            notes=notes,
            source="explicit_command"
        )
        return res["message"]

    # 2. Introspection ("Apni jaake memory dekho and samjho")
    if action in ("introspect", "inspect", "check_memory", "examine", "explain_memory", "dekho"):
        search_query = query or content or None
        return introspect(search_query)

    # 3. Commands History ("Maine kya command diya tha", "Past commands")
    if action in ("commands", "history", "actions", "past_commands"):
        search_term = query or content
        cmds = search_commands(search_term, limit=8)
        if not cmds:
            return "Brain store me koi matching command nahi mili."
        lines = [f"Found {len(cmds)} recorded command(s):"]
        for idx, c in enumerate(cmds, 1):
            lines.append(f"{idx}. [{c.get('timestamp')}] \"{c.get('command')}\" -> {c.get('action')} ({c.get('status')})")
        return "\n".join(lines)

    # 4. Search & Recall
    if action in ("search", "recall", "find", "lookup"):
        search_term = query or content
        matches = search(search_term, limit=6, include_commands=True)
        if not matches:
            return f"No memories found matching '{search_term}'."
        lines = [f"Found {len(matches)} relevant memory item(s):"]
        for idx, m in enumerate(matches, 1):
            reinf = f" (Reinforced {m.get('reinforcement_count', 1)}x)" if m.get("reinforcement_count", 1) > 1 else ""
            cat = m.get('category', 'knowledge').upper()
            lines.append(f"{idx}. [{cat}] {m.get('topic')}{reinf}: {m.get('content')}")
        return "\n".join(lines)

    # 5. Cognitive Brain Overview & Statistics
    if action in ("overview", "stats", "summary", "status"):
        return introspect(None)

    # 6. Forget / Unlearn
    if action in ("forget", "unlearn", "delete", "remove"):
        target = query or content
        if not target:
            return "Please specify what memory to forget."
        return forget(target)

    # Fallback to introspect
    return introspect(query or content)


# ── Tool declaration (auto-discovered by core/action_loader.py) ──────────────
TOOL = {
    "name": "brain_memory",
    "description": (
        "Mark's permanent human-child-like cognitive brain container and memory system. "
        "Use whenever the user asks to inspect/check memory ('apni jaake memory dekho', 'apni memory check karo', 'kya yaad hai', 'what do you remember?'), "
        "when user teaches or wants something remembered ('ye yaad rakho', 'note this rule', 'learn this', 'teach: ...'), "
        "when user asks about past commands ('maine kya bola tha', 'past commands dikhao'), "
        "or to search specific concepts and rules in memory."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": (
                    "Brain action to perform: "
                    "'introspect' (examine memory container, explain what Mark remembers on a topic or overall) | "
                    "'teach' (learn/remember new fact, habit, or rule) | "
                    "'commands' (recall recent commands and actions) | "
                    "'search' (search specific concepts/facts) | "
                    "'overview' (brain memory stats & status) | "
                    "'forget' (unlearn a specific memory)"
                )
            },
            "query": {
                "type": "STRING",
                "description": "Topic, keyword, question, or phrase to search or introspect (e.g. 'apni memory', 'commands', 'AMS project', 'rules', 'Tushar')"
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
