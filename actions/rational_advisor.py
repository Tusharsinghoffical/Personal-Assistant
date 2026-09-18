"""
rational_advisor.py — Logical counterpart / rational feedback system for Mark LIII.

Inspired by the Jarvis "Rational Counterpart" feature:
  → When user is about to do something risky, impulsive, or irreversible,
    Mark gives balanced, logical analysis: risks + benefits + recommendation.

Reuses:
  - core/action_utils.generate_content_resilient (LLM call)
  - memory/brain_engine.search()                 (user context)
"""
from __future__ import annotations

from core.action_utils import generate_content_resilient


def _build_prompt(action: str, context: str, user_memory: str) -> str:
    return f"""You are Mark's rational advisor module — the logical, analytical counterpart
to human impulsiveness.

The user is considering the following action:
  ACTION: {action}
  CONTEXT PROVIDED: {context or "(none)"}

User profile from memory:
{user_memory or "(no stored user data)"}

Your task:
1. Risks     — What could go wrong? List 2-3 real risks concisely.
2. Benefits  — What's genuinely good about this decision? 1-2 honest points.
3. My Take   — Give ONE clear, direct recommendation. Be honest, not sycophantic.
   If the action is fine → say so.
   If it's risky → say so directly.

Rules:
- Speak in the same language the user used (detected from ACTION/CONTEXT).
  If context is in Hindi/Hinglish → respond in Hinglish. English → English.
- Be direct, warm, and brief. Max 5-6 sentences total.
- Do NOT start with "As an AI..." or "I understand..." — just give the analysis.
- Format: short paragraphs, no bullet points, conversational.
"""


def rational_advisor_action(
    parameters: dict,
    player=None,
    session_memory=None,
) -> str:
    action  = parameters.get("action",  "").strip()
    context = parameters.get("context", "").strip()
    topic   = parameters.get("topic",   "").strip()

    # Support 'topic' as alias for 'action'
    if not action and topic:
        action = topic

    if not action:
        return "Please describe the action or decision you want me to analyze."

    if player:
        player.write_log(f"[RationalAdvisor] Analyzing: {action[:60]}")
    print(f"[RationalAdvisor] 🧠 Analyzing action: {action[:60]!r}")

    # Pull relevant user memory for personalized advice
    user_memory = ""
    try:
        from memory.brain_engine import search
        hits = search(action, limit=4)
        if hits:
            user_memory = "\n".join(
                f"- {m.get('topic', '')}: {m.get('content', '')[:120]}"
                for m in hits
            )
    except Exception as e:
        print(f"[RationalAdvisor] ⚠️ Memory recall skipped: {e}")

    prompt = _build_prompt(action, context, user_memory)

    try:
        result = generate_content_resilient(contents=prompt)
        if player:
            player.write_log(f"Mark (rational): {result[:80]}...")
        return result
    except Exception as e:
        print(f"[RationalAdvisor] ❌ LLM call failed: {e}")
        return (
            f"I couldn't fully analyze this right now ({e}), but here's a quick note: "
            f"always consider the reversibility and impact of '{action}' before proceeding."
        )


# ── Tool declaration (auto-discovered by core/action_loader.py) ──────────────
TOOL = {
    "name": "rational_advice",
    "description": (
        "Gives balanced, logical analysis before a risky or important decision. "
        "Use when user asks 'should I...?', 'kya karna chahiye?', 'mujhe advice do', "
        "or is about to do something irreversible (delete, uninstall, quit job, big purchase, etc.). "
        "Provides: risks, benefits, and a clear recommendation."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": (
                    "The action or decision the user is considering. "
                    "E.g. 'delete all my files', 'quit my job', 'buy a new laptop'"
                )
            },
            "context": {
                "type": "STRING",
                "description": (
                    "Optional extra context the user provided about why they want to do this. "
                    "Helps give more accurate advice."
                )
            },
            "topic": {
                "type": "STRING",
                "description": "Alias for 'action' — the subject to get advice about."
            }
        },
        "required": ["action"]
    },
    "handler": rational_advisor_action,
}
