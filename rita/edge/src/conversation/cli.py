from __future__ import annotations

from src.config import load_config
from src.conversation.voice_assistant import VoiceAssistant


def main() -> None:
    config = load_config()
    try:
        assistant = VoiceAssistant(config=config, text_mode=False)
    except Exception as exc:
        print(f"No se pudo iniciar el modo voz: {exc}")
        return

    print("RITA (voz) inicializada. Habla cuando estes lista/o.")
    assistant.greet()

    while True:
        try:
            print("Escuchando...")
            user_text = assistant.listen_user()
            if not user_text:
                print("No te he entendido. Intenta de nuevo.")
                continue

            print(f"Tu: {user_text}")
            result = assistant.run_turn(user_text)
            print(f"RITA: {result.rita_text}")
            if result.should_exit:
                break
        except KeyboardInterrupt:
            print("\nSesion finalizada por teclado.")
            break
        except Exception as exc:
            print(f"Error en turno de voz: {exc}")


if __name__ == "__main__":
    main()
