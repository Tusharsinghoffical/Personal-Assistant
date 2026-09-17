"""
Action to dynamically control Mark's emotional state and HUD visual mood.
Allows Mark to express and switch between:
  - angry: Fiery red HUD, intense/heated attitude (e.g. when user shouts or during heated arguments)
  - happy: Bright golden HUD, laughing, joyous celebrations
  - sad: Deep blue HUD, heartbroken, crying, compassionate sorrow
  - singing: Vibrant violet HUD, musical singing and humming
  - normal: Default cyan HUD, calm baseline
"""

def emotion_action(
    parameters: dict,
    player=None,
    session_memory=None,
) -> str:
    emotion = str(parameters.get("emotion", "normal")).lower().strip()
    reason  = str(parameters.get("reason", "")).strip()

    valid_emotions = {
        "angry": "😡 ANGRY MODE activated",
        "happy": "😄 HAPPY MODE activated",
        "sad": "😢 SAD / HEARTBROKEN MODE activated",
        "singing": "🎶 SINGING / MUSICAL MODE activated",
        "excited": "⚡ EXCITED MODE activated",
        "love": "💖 LOVE MODE activated",
        "surprised": "😲 SURPRISED MODE activated",
        "normal": "● Normal baseline restored",
        "calm": "● Calm baseline restored",
    }

    status_msg = valid_emotions.get(emotion, f"Emotion set to {emotion}")

    if player and hasattr(player, "set_emotion"):
        try:
            player.set_emotion(emotion)
        except Exception as e:
            print(f"[Emotion] UI update error: {e}")

    log_msg = f"{status_msg} — {reason}" if reason else status_msg
    print(f"[Emotion] {log_msg}")

    return status_msg


TOOL = {
    "name": "emotion_control",
    "description": (
        "Controls your emotional state and HUD visual mood. "
        "Call this tool to visually express emotions: "
        "use 'angry' when you or the user get mad, shout, or argue; "
        "use 'happy' when laughing, celebrating, or hearing wonderful news; "
        "use 'sad' when crying, grieving, or comforting in tragedy; "
        "use 'singing' when singing lines or humming a melody; "
        "use 'excited' when thrilled, hyped, or eager; "
        "use 'love' when affectionate or deeply fond; "
        "use 'normal' to return to calm baseline once the emotional peak passes."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "emotion": {
                "type": "STRING",
                "enum": ["angry", "happy", "sad", "singing", "excited", "love", "surprised", "normal"],
                "description": "The emotion to display: 'angry', 'happy', 'sad', 'singing', 'excited', 'love', 'surprised', or 'normal'",
            },
            "reason": {
                "type": "STRING",
                "description": "Brief explanation of why your emotion changed (e.g., 'User yelled at me', 'Hilarious joke', 'Heartbreaking news', 'Singing a song')",
            }
        },
        "required": ["emotion"]
    },
    "handler": emotion_action,
}
