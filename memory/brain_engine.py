"""
Brain Engine — Cognitive Lifelong Human-Brain-Like Memory Container for Mark.
Inspired by how a human child observes, learns, understands, and permanently
retains knowledge, habits, commands, and experiences throughout life.

Continuous Cognitive Architecture:
  1. Semantic & Conceptual Memory (Facts, preferences, learned knowledge, projects)
  2. Procedural & Command Memory (Every command given by the user, actions taken, execution outcomes)
  3. Episodic Dialogue Journal (Autobiographical memory of conversational turns and shared experiences)
  4. Behavioral Rules & Habits (Guidelines, instructions, and standing preferences taught by user)
  5. Continuous Auto-Intake (Captures, analyzes, and consolidates memory from every spoken utterance and command)
  6. Deep Introspection & Recall ('Apni jaake memory dekho' — holistic cognitive self-examination)
"""
from __future__ import annotations

import json
import re
import sys
import threading
from datetime import datetime
from pathlib import Path
from typing import Any


def _get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


BASE_DIR = _get_base_dir()
BRAIN_STORE_PATH = BASE_DIR / "memory" / "brain_store.json"
LONG_TERM_PATH = BASE_DIR / "memory" / "long_term.json"
_lock = threading.RLock()


def _empty_brain() -> dict[str, Any]:
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return {
        "version": "3.0",
        "created_at": now_str,
        "last_updated": now_str,
        "meta": {
            "total_learnings": 0,
            "total_commands": 0,
            "total_episodes": 0,
            "retention_policy": "Lifelong permanent retention",
        },
        "memories": [],
        "commands_history": [],
        "dialogue_journal": [],
        "rules_and_habits": [],
    }


def load_brain() -> dict[str, Any]:
    """Load the brain store JSON and seamlessly migrate to Version 3.0 container schema."""
    if not BRAIN_STORE_PATH.exists():
        initial = _empty_brain()
        _seed_from_long_term(initial)
        save_brain(initial)
        return initial

    with _lock:
        try:
            raw = BRAIN_STORE_PATH.read_text(encoding="utf-8")
            data = json.loads(raw)
            if not isinstance(data, dict):
                data = _empty_brain()

            # Ensure Version 3.0 schema integrity
            data.setdefault("version", "3.0")
            data.setdefault("created_at", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            data.setdefault("last_updated", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            meta = data.setdefault("meta", {})
            data.setdefault("memories", [])
            data.setdefault("commands_history", [])
            data.setdefault("dialogue_journal", [])
            data.setdefault("rules_and_habits", [])

            meta["total_learnings"] = len(data["memories"])
            meta["total_commands"] = len(data["commands_history"])
            meta["total_episodes"] = len(data["dialogue_journal"])
            meta.setdefault("retention_policy", "Lifelong permanent retention")

            # Extract any rules from memories into rules_and_habits if missing
            rule_topics = {r.get("topic", "").lower() for r in data["rules_and_habits"]}
            for m in data["memories"]:
                if m.get("category") == "rule" and m.get("topic", "").lower() not in rule_topics:
                    data["rules_and_habits"].append({
                        "rule": m.get("content", ""),
                        "topic": m.get("topic", ""),
                        "importance": m.get("importance", 4),
                        "learned_at": m.get("learned_at", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
                    })
                    rule_topics.add(m.get("topic", "").lower())

            return data
        except Exception as e:
            print(f"[BrainEngine] ⚠️ Load error: {e}")
            return _empty_brain()


def save_brain(brain: dict[str, Any]) -> None:
    """Save the brain store JSON atomically with thread safety."""
    if not isinstance(brain, dict):
        return
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    brain["last_updated"] = now_str
    meta = brain.setdefault("meta", {})
    meta["total_learnings"] = len(brain.get("memories", []))
    meta["total_commands"] = len(brain.get("commands_history", []))
    meta["total_episodes"] = len(brain.get("dialogue_journal", []))

    BRAIN_STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    temp_path = BRAIN_STORE_PATH.with_suffix(".tmp")
    with _lock:
        try:
            temp_path.write_text(
                json.dumps(brain, indent=2, ensure_ascii=False),
                encoding="utf-8"
            )
            temp_path.replace(BRAIN_STORE_PATH)
        except Exception as e:
            print(f"[BrainEngine] ⚠️ Save error: {e}")
            if temp_path.exists():
                try:
                    temp_path.unlink()
                except Exception:
                    pass


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
                        category = "preference" if cat == "preferences" else ("concept" if cat == "projects" else "knowledge")
                        brain["memories"].append({
                            "id": f"seed_{cat}_{key}",
                            "topic": topic,
                            "content": val.strip(),
                            "category": category,
                            "tags": [cat, key.lower()],
                            "importance": 4 if cat in ("identity", "projects") else 3,
                            "reinforcement_count": 1,
                            "learned_at": now_str,
                            "last_recalled_at": now_str,
                            "notes": f"Initial memory from {cat}",
                            "source": "seed"
                        })
    except Exception as e:
        print(f"[BrainEngine] Seed error: {e}")


def _extract_tags(text: str) -> list[str]:
    """Extract clean lowercase keyword tokens for fast indexing (supports English and Hindi)."""
    words = re.findall(r"\b[a-zA-Z0-9_\u0900-\u097F]{2,}\b", text.lower())
    stopwords = {
        "the", "and", "is", "in", "to", "of", "a", "that", "it", "with",
        "as", "for", "on", "was", "at", "by", "an", "be", "this", "from",
        "hai", "hain", "ki", "ka", "ke", "ko", "me", "se", "aur", "toh", "bhi", "ho", "karo", "mera", "meri", "mere"
    }
    return sorted(list({w for w in words if w not in stopwords}))[:14]


def learn(
    content: str,
    topic: str | None = None,
    category: str = "knowledge",
    importance: int = 3,
    tags: list[str] | None = None,
    notes: str = "",
    source: str = "user"
) -> dict[str, Any]:
    """
    Learn a new concept or reinforce an existing memory.
    Continuous Spaced-Repetition Loop: If an existing memory on this topic or fact is found,
    it reinforces it (increments reinforcement_count, updates content, refreshes timestamp).
    """
    brain = load_brain()
    memories: list[dict[str, Any]] = brain.setdefault("memories", [])
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    clean_content = content.strip()
    clean_topic = (topic or "").strip()
    if not clean_topic:
        words = clean_content.split()
        clean_topic = " ".join(words[:4]).title() if words else "General Fact"

    clean_category = category.lower().strip()
    valid_categories = ("knowledge", "rule", "habit", "preference", "experience", "relationship", "concept", "command")
    if clean_category not in valid_categories:
        clean_category = "knowledge"

    auto_tags = _extract_tags(f"{clean_topic} {clean_content}")
    if tags:
        auto_tags = sorted(list(set(auto_tags + [t.lower().strip() for t in tags if t.strip()])))

    # Check if a memory with similar topic or content already exists (Reinforcement loop)
    existing_mem = None
    clean_topic_lower = clean_topic.lower()
    clean_content_lower = clean_content.lower()

    for m in memories:
        if m.get("topic", "").lower() == clean_topic_lower:
            existing_mem = m
            break
        if m.get("content", "").lower() == clean_content_lower:
            existing_mem = m
            break

    if existing_mem:
        # Reinforce existing memory!
        existing_mem["reinforcement_count"] = existing_mem.get("reinforcement_count", 1) + 1
        existing_mem["importance"] = max(existing_mem.get("importance", 3), min(importance, 5))
        existing_mem["last_recalled_at"] = now_str
        if existing_mem.get("content") != clean_content and len(clean_content) > len(existing_mem.get("content", "")):
            existing_mem["content"] = clean_content
        existing_mem["tags"] = sorted(list(set(existing_mem.get("tags", []) + auto_tags)))
        if notes:
            existing_mem["notes"] = f"{existing_mem.get('notes', '')}; {notes}".strip("; ")
        
        # If it's a rule, reinforce rule container
        if clean_category == "rule" or existing_mem.get("category") == "rule":
            _sync_rule(brain, clean_topic, clean_content, existing_mem["importance"], now_str)

        save_brain(brain)
        return {
            "status": "reinforced",
            "memory": existing_mem,
            "message": f"Memory on '{clean_topic}' reinforced! (Reinforcement Level: {existing_mem['reinforcement_count']}x)"
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
            "notes": notes,
            "source": source
        }
        memories.append(new_node)

        if clean_category == "rule":
            _sync_rule(brain, clean_topic, clean_content, new_node["importance"], now_str)

        save_brain(brain)
        return {
            "status": "learned",
            "memory": new_node,
            "message": f"Successfully learned and stored into brain memory: '{clean_topic}'."
        }


def _sync_rule(brain: dict[str, Any], topic: str, content: str, importance: int, timestamp: str) -> None:
    rules = brain.setdefault("rules_and_habits", [])
    topic_lower = topic.lower()
    for r in rules:
        if r.get("topic", "").lower() == topic_lower:
            r["rule"] = content
            r["importance"] = importance
            r["updated_at"] = timestamp
            return
    rules.append({
        "topic": topic,
        "rule": content,
        "importance": importance,
        "learned_at": timestamp
    })


def record_command(
    command_text: str,
    action_taken: str = "",
    tool_used: str = "",
    status: str = "executed",
    notes: str = ""
) -> dict[str, Any]:
    """
    Permanently records every command given by the user into procedural command memory.
    Like a child remembering instructions given by parents or teachers.
    """
    clean_cmd = (command_text or "").strip()
    if not clean_cmd:
        return {}

    brain = load_brain()
    cmd_history: list[dict[str, Any]] = brain.setdefault("commands_history", [])
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cmd_id = f"cmd_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{len(cmd_history) + 1}"
    entry = {
        "id": cmd_id,
        "timestamp": now_str,
        "command": clean_cmd,
        "action": action_taken or clean_cmd,
        "tool": tool_used or "system",
        "status": status,
        "notes": notes
    }

    cmd_history.append(entry)

    # Detect if the command is a persistent directive / rule
    lower_cmd = clean_cmd.lower()
    is_standing_rule = any(k in lower_cmd for k in ("hamesha", "always", "kabhi mat", "never", "rule", "aage se", "from now on", "daily", "har roz"))
    if is_standing_rule:
        learn(
            content=clean_cmd,
            topic=f"Rule: {clean_cmd[:30]}",
            category="rule",
            importance=5,
            notes="Extracted from recurring command directive",
            source="command"
        )

    save_brain(brain)
    try:
        print(f"[BrainEngine] [CMD] Command recorded: '{clean_cmd[:50]}'")
    except Exception:
        pass
    return entry


def record_interaction(
    user_input: str,
    assistant_response: str,
    tools_called: list[dict[str, Any]] | None = None
) -> None:
    """
    Autobiographical episodic memory intake loop.
    Captures conversation turns, automatically identifies facts, preferences,
    and user commands, and stores them permanently into the cognitive brain container.
    """
    u_text = (user_input or "").strip()
    a_text = (assistant_response or "").strip()
    if not u_text and not a_text:
        return

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    brain = load_brain()
    journal: list[dict[str, Any]] = brain.setdefault("dialogue_journal", [])

    # Create episode record
    ep_id = f"ep_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{len(journal) + 1}"
    episode = {
        "id": ep_id,
        "timestamp": now_str,
        "user": u_text,
        "mark": a_text,
        "tools": [t.get("name") if isinstance(t, dict) else str(t) for t in (tools_called or [])]
    }
    journal.append(episode)

    # ── HEURISTIC COGNITIVE EXTRACTOR (Zero-latency background parsing) ─────
    u_lower = u_text.lower()

    # 1. Check for command patterns (if not already recorded by tool handler)
    command_triggers = ("open", "kholo", "chalao", "play", "search", "dhundo", "set", "kardo", "dikhao", "show", "batao", "band karo", "close", "record", "screenshot", "run")
    if any(u_lower.startswith(w) or f" {w} " in u_lower for w in command_triggers):
        # Record as command in command history if not already in recent 3
        recent_cmds = [c.get("command", "").lower() for c in brain.get("commands_history", [])[-3:]]
        if u_lower not in recent_cmds:
            record_command(u_text, action_taken=a_text[:60], tool_used="conversation_intake")

    # 2. Check for explicit learning phrases
    learn_patterns = [
        r"(?:ye|yeh)\s+yaad\s+rakh(?:o|na)\s*(?:ki)?\s*(.+)",
        r"remember\s+that\s+(.+)",
        r"teach:\s*(.+)",
        r"note\s+karo\s*(?:ki)?\s*(.+)",
        r"(?:hamesha|always)\s+(.+)",
        r"mera\s+naam\s+(.+)\s+hai",
        r"my\s+name\s+is\s+(.+)",
        r"mujhe\s+(.+)\s+pasand\s+hai",
        r"i\s+like\s+(.+)",
        r"i\s+love\s+(.+)",
    ]

    for pat in learn_patterns:
        m = re.search(pat, u_text, re.IGNORECASE)
        if m:
            extracted_fact = m.group(1).strip().strip(".?!")
            if len(extracted_fact) > 3:
                category = "rule" if any(k in u_lower for k in ("hamesha", "always", "rule", "yaad rakhna")) else "preference"
                topic = "User Guideline" if category == "rule" else "User Fact"
                learn(
                    content=extracted_fact,
                    topic=topic,
                    category=category,
                    importance=4,
                    notes=f"Auto-learned from statement: '{u_text}'",
                    source="auto_intake"
                )
                break

    save_brain(brain)


def search(
    query: str,
    category: str | None = None,
    limit: int = 8,
    include_commands: bool = False
) -> list[dict[str, Any]]:
    """
    Cognitive search across all brain memories and optionally commands.
    Scores by exact topic match, tag match, lexical similarity, and reinforcement weight.
    """
    brain = load_brain()
    memories: list[dict[str, Any]] = brain.get("memories", [])
    if not memories and not include_commands:
        return []

    clean_query = query.strip().lower()
    query_tokens = _extract_tags(clean_query)
    results = []
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Search core memories
    for m in memories:
        if category and m.get("category", "").lower() != category.lower().strip():
            continue

        topic_lower = m.get("topic", "").lower()
        content_lower = m.get("content", "").lower()
        tags = [t.lower() for t in m.get("tags", [])]

        score = 0
        if clean_query:
            if clean_query == topic_lower:
                score += 60
            elif clean_query in topic_lower:
                score += 35
            elif clean_query in content_lower:
                score += 25

            for token in query_tokens:
                if token == topic_lower:
                    score += 20
                elif token in topic_lower:
                    score += 12
                if token in tags:
                    score += 10
                if token in content_lower:
                    score += 6

            score += m.get("importance", 3) * 3
            score += min(m.get("reinforcement_count", 1), 10) * 4
        else:
            score = m.get("importance", 3) + m.get("reinforcement_count", 1)

        if score > 0 or not clean_query:
            results.append((score, m))

    # Optionally search commands history
    if include_commands:
        commands = brain.get("commands_history", [])
        for c in commands:
            cmd_lower = c.get("command", "").lower()
            score = 0
            if clean_query in cmd_lower:
                score += 30
            for token in query_tokens:
                if token in cmd_lower:
                    score += 10
            if score > 0:
                results.append((score, {
                    "topic": f"Command: {c.get('command')[:25]}",
                    "content": f"{c.get('command')} -> {c.get('action')} ({c.get('status')})",
                    "category": "command",
                    "timestamp": c.get("timestamp"),
                    "importance": 3,
                    "reinforcement_count": 1
                }))

    results.sort(key=lambda x: x[0], reverse=True)
    top_matches = [m for _, m in results[:limit]]

    # Update last_recalled_at for recalled memories
    with _lock:
        for m in top_matches:
            if "last_recalled_at" in m:
                m["last_recalled_at"] = now_str
        save_brain(brain)

    return top_matches


def search_commands(query: str = "", limit: int = 10) -> list[dict[str, Any]]:
    """Retrieve commands from history, newest first."""
    brain = load_brain()
    cmds = brain.get("commands_history", [])
    if not cmds:
        return []

    if not query.strip():
        return cmds[-limit:][::-1]

    clean_q = query.strip().lower()
    matched = []
    for c in reversed(cmds):
        if clean_q in c.get("command", "").lower() or clean_q in c.get("action", "").lower():
            matched.append(c)
            if len(matched) >= limit:
                break
    return matched


def introspect(query: str | None = None) -> str:
    """
    Human-brain introspection engine for Mark.
    Responds to: 'Apni jaake memory dekho', 'Check your memory', 'What do you remember?'.
    Synthesizes facts, commands, rules, and conversation history with genuine cognitive understanding.
    """
    brain = load_brain()
    memories: list[dict[str, Any]] = brain.get("memories", [])
    commands: list[dict[str, Any]] = brain.get("commands_history", [])
    journal: list[dict[str, Any]] = brain.get("dialogue_journal", [])
    rules: list[dict[str, Any]] = brain.get("rules_and_habits", [])

    total_learnings = len(memories)
    total_commands = len(commands)
    total_episodes = len(journal)

    clean_q = (query or "").strip().lower()

    # 1. If user specifically asks about past commands ("maine kya command diya", "commands kya the", "what commands")
    is_command_query = any(k in clean_q for k in ("command", "orders", "instructions", "kya bola tha karne ko", "action"))
    if is_command_query:
        recent_cmds = commands[-6:][::-1]
        if not recent_cmds:
            return "Maine apne brain container me dekha, abhi tak koi recorded command history nahi hai. Lekin ab se aap jo bhi command denge, main sab yaad rakhunga!"
        lines = ["[Brain] ⚡ Recorded Commands History (Procedural Memory):"]
        for idx, c in enumerate(recent_cmds, 1):
            lines.append(f"{idx}. [{c.get('timestamp')}] Command: \"{c.get('command')}\" -> Result: {c.get('action')}")
        lines.append(f"\nTotal Commands Remembered: {total_commands}. Sab permanently saved hain.")
        return "\n".join(lines)

    # 2. Specific topic search / query in memory
    if clean_q and clean_q not in ("all", "overview", "full", "dekho", "check", "apni memory", "memory dekho"):
        matches = search(clean_q, limit=6, include_commands=True)
        if matches:
            lines = [f"[Brain] 🧠 Introspection Results for '{query}':"]
            for idx, m in enumerate(matches, 1):
                reinf = f" (Reinforced {m.get('reinforcement_count', 1)}x)" if m.get("reinforcement_count", 1) > 1 else ""
                cat = m.get('category', 'knowledge').upper()
                lines.append(f"\n{idx}. [{cat}] {m.get('topic')}{reinf}:")
                lines.append(f"   - Fact/Detail: {m.get('content')}")
                if m.get('notes'):
                    lines.append(f"   - Context: {m.get('notes')}")
                if m.get('learned_at'):
                    lines.append(f"   - Learned: {m.get('learned_at')}")
            return "\n".join(lines)

    # 3. Comprehensive Brain Introspection ("Apni jaake memory dekho aur samjho")
    lines = [
        "🧠 [MARK BRAIN COGNITIVE CONTAINER — MEMORY INSPECTION]",
        f"Sir, maine apne brain container ko deeply inspect kar liya hai. Jaise ek insaan ya bachha seekhta hai aur hamesha yaad rakhta hai, mere dimaag me aapka saara data permanently stored aur organized hai:",
        f"\n📊 Brain Memory Statistics:",
        f"  • Total Learned Concepts & Facts: {total_learnings}",
        f"  • Total Commands Remembered: {total_commands}",
        f"  • Total Conversation Episodes: {total_episodes}",
        f"  • Retention Policy: Lifelong Permanent Retention",
    ]

    # Active Rules & Standing Directives
    if rules:
        lines.append("\n📜 Active Rules & Behavioral Guidelines (Aapke sikhaye hue niyam):")
        for idx, r in enumerate(rules[-4:], 1):
            lines.append(f"  {idx}. {r.get('topic')}: \"{r.get('rule')}\"")

    # Important Personal & Project Knowledge
    key_memories = sorted(memories, key=lambda x: (x.get("importance", 1), x.get("reinforcement_count", 1)), reverse=True)[:5]
    if key_memories:
        lines.append("\n🌟 Core Facts & Project Context (Sabse important baatein):")
        for m in key_memories:
            reinf = f" [{m.get('reinforcement_count', 1)}x reinforced]" if m.get('reinforcement_count', 1) > 1 else ""
            lines.append(f"  • [{m.get('category', 'knowledge').title()}] {m.get('topic')}{reinf}: {m.get('content')}")

    # Recent User Commands
    recent_cmds = commands[-4:][::-1]
    if recent_cmds:
        lines.append("\n⚡ Recently Executed Commands (Holiye me diye gaye orders):")
        for c in recent_cmds:
            lines.append(f"  • \"{c.get('command')}\" ({c.get('timestamp')})")

    # Recent Conversations
    if journal:
        last_ep = journal[-1]
        lines.append(f"\n💬 Last Conversation Topic: User: \"{last_ep.get('user', '')[:60]}\"")

    lines.append("\nSir, aap mujhe koi bhi nayi baat sikha sakte hain ya kisi bhi past command ke baare me pooch sakte hain!")
    return "\n".join(lines)


def forget(query: str) -> str:
    """Remove a memory matching the query from the brain store."""
    brain = load_brain()
    memories: list[dict[str, Any]] = brain.get("memories", [])
    clean_query = query.strip().lower()

    retained = []
    removed = []

    for m in memories:
        if clean_query in m.get("topic", "").lower() or clean_query in m.get("content", "").lower():
            removed.append(m.get("topic", "untitled"))
        else:
            retained.append(m)

    if removed:
        brain["memories"] = retained
        save_brain(brain)
        return f"Forgotten {len(removed)} memory item(s): {', '.join(removed)}."
    return f"No memory found matching '{query}' to forget."


def get_brain_stats() -> dict[str, Any]:
    """Returns brain container summary for HUD/Dashboard."""
    brain = load_brain()
    meta = brain.get("meta", {})
    return {
        "version": brain.get("version", "3.0"),
        "total_learnings": len(brain.get("memories", [])),
        "total_commands": len(brain.get("commands_history", [])),
        "total_episodes": len(brain.get("dialogue_journal", [])),
        "total_rules": len(brain.get("rules_and_habits", [])),
        "last_updated": brain.get("last_updated", ""),
    }
