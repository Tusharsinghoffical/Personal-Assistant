"""
news_headlines.py — Dedicated news headlines action for Mark LIII.
Wraps web_search._news() with a clean TOOL interface so Mark can
be called directly by 'news_headlines' tool name without going through
the multi-mode web_search dispatcher.
"""
# Reuses: actions/web_search._news(), _gemini_search(), _ddg_news()
from actions.web_search import _news


def news_headlines_action(
    parameters: dict,
    player=None,
    session_memory=None,
) -> str:
    topic = parameters.get("topic", "").strip()

    if player:
        player.write_log(f"[News] Fetching headlines: {topic or 'top world'}")
    print(f"[News] 📰 Fetching headlines — topic={topic!r}")

    return _news(topic)


# ── Tool declaration (auto-discovered by core/action_loader.py) ──────────────
TOOL = {
    "name": "news_headlines",
    "description": (
        "Fetches the latest news headlines from the web. "
        "Use when user asks for 'news', 'headlines', 'kya ho raha hai', "
        "'aaj ki khabar', 'latest news', or any current events question. "
        "Leave topic empty for top world news. Provide a topic for specific category."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "topic": {
                "type": "STRING",
                "description": (
                    "Optional topic or category (e.g. 'India', 'technology', "
                    "'sports', 'business', 'entertainment'). "
                    "Leave empty for top world headlines."
                )
            }
        },
        "required": []
    },
    "handler": news_headlines_action,
}
