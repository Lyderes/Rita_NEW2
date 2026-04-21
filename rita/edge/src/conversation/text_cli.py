from __future__ import annotations

from src.config import load_config
from src.conversation.voice_assistant import VoiceAssistant


def main() -> None:
    config = load_config()
    try:
        assistant = VoiceAssistant(config=config, text_mode=True)
    except Exception as exc:
        print(f"No se pudo iniciar el modo texto: {exc}")
        return

    print("RITA (texto) inicializada. Escribe 'salir' para terminar.")
    print(f"RITA: {assistant.greet()}")

    while True:
        try:
            user_text = assistant.listen_user()
            if not user_text:
                continue

            result = assistant.run_turn(user_text)
            print(f"RITA: {result.rita_text}")
            if result.should_exit:
                break
        except KeyboardInterrupt:
            print("\nSesion finalizada por teclado.")
            break


if __name__ == "__main__":
    main()
