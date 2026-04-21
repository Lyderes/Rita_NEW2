"""Compatibility entrypoint for legacy `rita_assistant.py` usage.

This keeps old launch habits while delegating to the modular RITA architecture.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

EDGE_DIR = Path(__file__).resolve().parent / "edge"
if str(EDGE_DIR) not in sys.path:
    sys.path.append(str(EDGE_DIR))


def main() -> None:
    from src.config import load_config
    from src.conversation.voice_assistant import VoiceAssistant

    mode = os.getenv("RITA_MODE", "voice").strip().lower()
    text_mode = mode == "text"

    config = load_config()
    assistant = VoiceAssistant(config=config, text_mode=text_mode)

    print("RITA iniciada desde rita_assistant.py (compatibilidad).")
    print(f"RITA: {assistant.greet()}")

    while True:
        user_text = assistant.listen_user()
        if not user_text:
            if text_mode:
                continue
            print("No se obtuvo transcripcion valida. Intenta de nuevo.")
            continue

        if text_mode:
            print(f"Tu: {user_text}")

        result = assistant.run_turn(user_text)
        print(f"RITA: {result.rita_text}")
        if result.should_exit:
            break


if __name__ == "__main__":
    main()
