from __future__ import annotations

import pytest

from src.config import RitaConfig
from src.conversation.voice_assistant import VoiceAssistant


class _MockLlm:
    def generate(self, _prompt: str) -> str:
        return "Gracias por compartirlo. Continuemos con calma."


class _MessyMockLlm:
    def __init__(self, response: str) -> None:
        self.response = response

    def generate(self, _prompt: str) -> str:
        return self.response


class _FailIfCalledLlm:
    def generate(self, _prompt: str) -> str:
        raise AssertionError("LLM no deberia llamarse en intents simples")


def _assistant() -> VoiceAssistant:
    assistant = VoiceAssistant(config=RitaConfig(), text_mode=True)
    assistant.llm = _MockLlm()
    return assistant


def test_intent_changes_after_risk_when_user_shares_name() -> None:
    assistant = _assistant()

    first = assistant.run_turn("me he caido")
    # El protocolo de caída debe abrirse en lugar del mensaje genérico
    assert assistant.session.incident_type == "fall"
    assert assistant.session.emergency_step >= 1
    assert first.should_exit is False

    second = assistant.run_turn("me llamo david")
    # El protocolo avanza; no repite el primer mensaje
    assert second.rita_text != first.rita_text
    assert assistant.session.last_intent == "personal_info"
    assert assistant.session.user_name == "David"
    # El modo permanece en risk_alert mientras el protocolo está activo
    assert assistant.session.conversation_mode == "risk_alert"


def test_user_name_is_saved_in_session() -> None:
    assistant = _assistant()

    assistant.run_turn("me llamo sofia")

    assert assistant.session.user_name == "Sofia"
    assert assistant.session.last_intent == "personal_info"


def test_risk_alert_does_not_block_conversation_forever() -> None:
    assistant = _assistant()

    assistant.run_turn("me he caido")
    assert assistant.session.conversation_mode == "risk_alert"

    # Completar el protocolo completo (6 respuestas adicionales tras el trigger)
    for _ in range(6):
        assistant.run_turn("ok")

    # El protocolo termina
    assert not assistant.session.fall_incident_is_active()

    # Después del protocolo, la conversación normal puede desescalar el modo
    assistant.run_turn("que tiempo hace hoy")
    assert assistant.session.last_intent == "general_chat"


# ---- Nuevos tests: protocolo de caída ----

def test_fall_incident_activated_by_trigger() -> None:
    assistant = _assistant()

    result = assistant.run_turn("me he caido")

    assert assistant.session.incident_type == "fall"
    assert assistant.session.emergency_step >= 1
    assert result.should_exit is False


def test_fall_location_saved_from_trigger_phrase() -> None:
    assistant = _assistant()

    assistant.run_turn("me he caido en la cocina")

    assert assistant.session.incident_type == "fall"
    assert assistant.session.incident_location == "cocina"


def test_fall_response_not_repeated_on_second_turn() -> None:
    assistant = _assistant()

    first = assistant.run_turn("me he caido")
    second = assistant.run_turn("me duele la rodilla")

    assert first.rita_text != second.rita_text


def test_can_call_false_when_no_phone() -> None:
    assistant = _assistant()

    assistant.run_turn("me he caido")
    assistant.run_turn("no tengo el telefono")

    assert assistant.session.can_call is False


def test_voice_assistant_cleans_fictitious_dialogue_from_llm() -> None:
    assistant = VoiceAssistant(config=RitaConfig(), text_mode=True)
    assistant.llm = _MessyMockLlm("RITA: Buenos días.\nDavid: Hola\nRITA: ¿Cómo estás?")

    result = assistant.run_turn("dime alguna actividad para hacer hoy")

    assert result.rita_text == "Buenos días."


def test_fall_protocol_closes_incident_state_when_finished() -> None:
    assistant = _assistant()

    assistant.run_turn("me he caido")
    for _ in range(6):
        assistant.run_turn("ok")

    assert assistant.session.incident_type is None
    assert assistant.session.incident_location is None
    assert assistant.session.can_call is None
    assert assistant.session.emergency_step == 0


def test_simple_greeting_uses_local_response_without_llm() -> None:
    assistant = VoiceAssistant(config=RitaConfig(), text_mode=True)
    assistant.llm = _FailIfCalledLlm()

    result = assistant.run_turn("buenos dias")

    assert "hola" in result.rita_text.lower()


def test_simple_capabilities_question_uses_local_response_without_llm() -> None:
    assistant = VoiceAssistant(config=RitaConfig(), text_mode=True)
    assistant.llm = _FailIfCalledLlm()

    result = assistant.run_turn("que puedes hacer")

    assert "puedo" in result.rita_text.lower()


def test_distress_in_greeting_phrase_not_intercepted_locally() -> None:
    """'Hola RITA hoy me encuentro mareado' debe tratarse como malestar con respuesta local empática."""
    assistant = VoiceAssistant(config=RitaConfig(), text_mode=True)
    assistant.llm = _FailIfCalledLlm()  # respuesta local, sin LLM

    result = assistant.run_turn("Hola RITA hoy me encuentro mareado")

    assert assistant.session.last_intent == "distress"
    # La respuesta es empática y habla del mareo, no un saludo genérico
    assert result.rita_text not in {
        "Hola, aquí estoy contigo. ¿Qué necesitas?",
        "Hola, me alegra escucharte. ¿Cómo te ayudo hoy?",
    }
    assert any(word in result.rita_text.lower() for word in ("mareo", "siéntate", "agua", "calma", "repente"))


def test_quiero_comer_uses_local_response_without_llm() -> None:
    assistant = VoiceAssistant(config=RitaConfig(), text_mode=True)
    assistant.llm = _FailIfCalledLlm()

    result = assistant.run_turn("quiero comer")

    assert result.rita_text != ""
    # La respuesta local menciona algo relacionado con comida
    assert any(word in result.rita_text.lower() for word in ("comer", "tienes", "algo", "fr\u00edo", "caliente"))

def test_dizziness_gets_local_empathetic_response() -> None:
    assistant = VoiceAssistant(config=RitaConfig(), text_mode=True)
    assistant.llm = _FailIfCalledLlm()

    result = assistant.run_turn("estoy mareado")

    assert any(word in result.rita_text.lower() for word in ("mareo", "siéntate", "agua", "calma"))


def test_back_pain_gets_local_empathetic_response() -> None:
    assistant = VoiceAssistant(config=RitaConfig(), text_mode=True)
    assistant.llm = _FailIfCalledLlm()

    result = assistant.run_turn("me duele la espalda")

    assert any(word in result.rita_text.lower() for word in ("espalda", "calor", "dolor", "tumbarte"))


@pytest.mark.parametrize(
    ("user_text", "expected_keywords"),
    [
        ("tengo frío", ("abrígate", "manta", "caliente")),
        ("tengo calor", ("fresco", "agua", "descansas")),
        ("no puedo dormir", ("dormir", "respiración", "relajarte")),
        ("he dormido mal", ("dormir", "rutina", "relajarte")),
        ("me siento solo", ("aquí estoy", "no estás solo", "charlar")),
        ("estoy aburrido", ("música", "estirarte", "charla")),
        ("qué puedo hacer hoy", ("hoy", "paseo", "agua")),
        ("recuérdame beber agua", ("recuerdo", "agua", "hidratado")),
        ("qué hora es", ("reloj", "tiempo real", "calma")),
        ("cuéntame algo", ("bonito", "conversación", "breve")),
        ("me duele la cabeza", ("cabeza", "descansa", "hidrátate")),
        ("me duele la pierna", ("pierna", "siéntate", "dolor")),
        ("estoy nervioso", ("respira", "despacio", "guíe")),
        ("estoy triste", ("contármelo", "hablar", "mejor")),
    ],
)
def test_common_local_cases_use_local_response_without_llm(
    user_text: str,
    expected_keywords: tuple[str, ...],
) -> None:
    assistant = VoiceAssistant(config=RitaConfig(), text_mode=True)
    assistant.llm = _FailIfCalledLlm()

    result = assistant.run_turn(user_text)

    lower = result.rita_text.lower()
    assert any(keyword in lower for keyword in expected_keywords)


def test_lonely_phrase_with_greeting_is_not_reduced_to_generic_greeting() -> None:
    assistant = VoiceAssistant(config=RitaConfig(), text_mode=True)
    assistant.llm = _FailIfCalledLlm()

    result = assistant.run_turn("hola rita me siento solo")

    assert result.rita_text not in {
        "Hola, aquí estoy contigo. ¿Qué necesitas?",
        "Hola, me alegra escucharte. ¿Cómo te ayudo hoy?",
    }
    assert any(text in result.rita_text.lower() for text in ("aquí estoy", "no estás solo", "charlar"))


def test_stomach_pain_uses_local_response_without_llm() -> None:
    assistant = VoiceAssistant(config=RitaConfig(), text_mode=True)
    assistant.llm = _FailIfCalledLlm()

    result = assistant.run_turn("me duele la barriga")

    assert any(word in result.rita_text.lower() for word in ("barriga", "descansa", "agua"))


def test_stomach_pain_with_accent_uses_local_response_without_llm() -> None:
    assistant = VoiceAssistant(config=RitaConfig(), text_mode=True)
    assistant.llm = _FailIfCalledLlm()

    result = assistant.run_turn("me duele el estómago")

    assert any(word in result.rita_text.lower() for word in ("barriga", "descansa", "agua"))


def test_exact_mal_uses_local_response_without_llm() -> None:
    assistant = VoiceAssistant(config=RitaConfig(), text_mode=True)
    assistant.llm = _FailIfCalledLlm()

    result = assistant.run_turn("mal")

    assert any(word in result.rita_text.lower() for word in ("contigo", "respiramos", "notas"))


def test_llm_reply_without_terminal_punctuation_gets_period() -> None:
    assistant = VoiceAssistant(config=RitaConfig(), text_mode=True)
    assistant.llm = _MessyMockLlm("RITA: Te recomiendo descansar")

    result = assistant.run_turn("háblame de algo tranquilo")

    assert result.rita_text == "Te recomiendo descansar."


def test_headache_with_mucho_uses_local_response_without_llm() -> None:
    assistant = VoiceAssistant(config=RitaConfig(), text_mode=True)
    assistant.llm = _FailIfCalledLlm()

    result = assistant.run_turn("me duele mucho la cabeza")

    assert any(word in result.rita_text.lower() for word in ("cabeza", "descansa", "tranquilo", "hidrátat"))


def test_quiero_dormir_uses_local_response_without_llm() -> None:
    assistant = VoiceAssistant(config=RitaConfig(), text_mode=True)
    assistant.llm = _FailIfCalledLlm()

    result = assistant.run_turn("quiero dormir")

    assert any(word in result.rita_text.lower() for word in ("descansar", "duermas", "necesitas"))


def test_si_followup_after_pain_uses_local_response_without_llm() -> None:
    assistant = VoiceAssistant(config=RitaConfig(), text_mode=True)
    assistant.llm = _FailIfCalledLlm()

    # Primer turno: dolor → respuesta local, guarda topic=pain
    assistant.run_turn("me duele la cabeza")
    assert assistant.session.last_local_topic == "pain"

    # Seguimiento corto afirmativo → debe resolverse localmente sin LLM
    result = assistant.run_turn("sí")

    assert any(word in result.rita_text.lower() for word in ("descansa", "agua", "dolor"))
    assert assistant.session.last_local_topic is None


def test_no_followup_after_pain_uses_local_response_without_llm() -> None:
    assistant = VoiceAssistant(config=RitaConfig(), text_mode=True)
    assistant.llm = _FailIfCalledLlm()

    # Primer turno: dolor de espalda → topic=pain
    assistant.run_turn("me duele la espalda")
    assert assistant.session.last_local_topic == "pain"

    # Seguimiento negativo → respuesta local sin LLM
    result = assistant.run_turn("no")

    assert any(word in result.rita_text.lower() for word in ("acuerdo", "dolor", "ayuda"))
    assert assistant.session.last_local_topic is None


def test_truncated_response_agua_fres_normalized() -> None:
    assistant = VoiceAssistant(config=RitaConfig(), text_mode=True)

    result = assistant._normalize_reply_punctuation("agua fres")

    # Debe añadirse puntuación final (el fragmento no puede quedar sin cerrar)
    assert result.endswith(".")


def test_fall_incident_closes_when_user_says_estoy_bien() -> None:
    assistant = _assistant()

    assistant.run_turn("me he caido")
    result = assistant.run_turn("estoy bien")

    assert assistant.session.incident_type is None
    assert assistant.session.conversation_mode == "normal"
    assert "me alegra que estés bien" in result.rita_text.lower()


def test_fall_incident_closes_and_transitions_to_joke() -> None:
    assistant = _assistant()

    assistant.run_turn("me he caido")
    result = assistant.run_turn("cuéntame un chiste")

    assert assistant.session.incident_type is None
    assert assistant.session.conversation_mode == "normal"
    assert "te cuento un chiste" in result.rita_text.lower()
    assert "zum-ba" in result.rita_text.lower()


def test_humor_request_uses_local_simple_joke_without_llm() -> None:
    assistant = VoiceAssistant(config=RitaConfig(), text_mode=True)
    assistant.llm = _FailIfCalledLlm()

    result = assistant.run_turn("hazme reír")

    assert "abeja" in result.rita_text.lower()
    assert "zum-ba" in result.rita_text.lower()


def test_humor_not_sense_returns_different_simpler_joke() -> None:
    assistant = VoiceAssistant(config=RitaConfig(), text_mode=True)
    assistant.llm = _FailIfCalledLlm()

    first = assistant.run_turn("cuéntame un chiste")
    second = assistant.run_turn("no tiene sentido")

    assert first.rita_text != second.rita_text
    assert "más claro" in second.rita_text.lower()
    assert "taza" in second.rita_text.lower()