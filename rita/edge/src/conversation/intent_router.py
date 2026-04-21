from __future__ import annotations

import re

from src.conversation.session import IntentType

# ── Patterns ──────────────────────────────────────────────────────────────────

_PURE_GREETING_RE = re.compile(
    r"^(?:hola(?:\s+rita)?|buenas|hey(?:\s+rita)?"
    r"|buen[oa]s?\s+d[ií]as|buen[oa]s?\s+tardes|buen[oa]s?\s+noches)$",
    re.IGNORECASE,
)
_THANKS_RE = re.compile(r"\bgracias\b|\bte\s+agradezco\b", re.IGNORECASE)
_WHO_RE = re.compile(r"\bc[oó]mo\s+te\s+llamas\b|\bqui[eé]n\s+eres\b", re.IGNORECASE)
_CAPABILITIES_RE = re.compile(
    r"\bqu[eé]\s+puedes\s+hacer\b|\ben\s+qu[eé]\s+me\s+puedes\s+ayudar\b",
    re.IGNORECASE,
)
_HUNGER_RE = re.compile(
    r"\btengo\s+hambre\b|\bquiero\s+comer\b"
    r"|\bqu[eé]\s+(?:puedo|como)\s+comer\b|\btengo\s+sed\b",
    re.IGNORECASE,
)
_RECIPE_CHICKEN_RE = re.compile(
    r"\breceta\b.*\bpollo\b|\bpollo\b.*\breceta\b", re.IGNORECASE
)
_RECIPE_GENERIC_RE = re.compile(
    r"\brecomi[eé]ndame\s+(?:una\s+)?receta\b"
    r"|\bqu[eé]\s+(?:receta|plato)\s+(?:me\s+)?(?:recomiendas|sugieres)\b",
    re.IGNORECASE,
)
_DIZZINESS_RE = re.compile(
    r"\bme\s+(?:siento|encuentro|noto)\s+mareado\b"
    r"|\bestoy\s+(?:muy\s+)?mareado\b|\btengo\s+mareo\b|\bme\s+marea\b",
    re.IGNORECASE,
)
_BACKPAIN_RE = re.compile(
    r"\bdolor\s+(?:de\s+)?espalda\b|\bme\s+duele\s+(?:la\s+)?espalda\b",
    re.IGNORECASE,
)
_TIRED_RE = re.compile(
    r"\bme\s+(?:siento|encuentro)\s+cansado\b"
    r"|\bestoy\s+(?:muy\s+)?cansado\b|\btengo\s+sue\u00f1o\b",
    re.IGNORECASE,
)
_COLD_RE = re.compile(r"\btengo\s+fr[ií]o\b|\bestoy\s+destemplado\b", re.IGNORECASE)
_HEAT_RE = re.compile(r"\btengo\s+calor\b|\bme\s+asfixio\s+de\s+calor\b", re.IGNORECASE)
_SLEEP_BAD_RE = re.compile(
    r"\bno\s+puedo\s+dormir\b|\bhe\s+dormido\s+mal\b|\bdorm[ií]\s+mal\b"
    r"|\bme\s+despierto\s+mucho\b",
    re.IGNORECASE,
)
_WANTS_SLEEP_RE = re.compile(r"\bquiero\s+dormir\b", re.IGNORECASE)
_LONELY_RE = re.compile(r"\bme\s+siento\s+solo\b|\bme\s+encuentro\s+solo\b", re.IGNORECASE)
_BORED_RE = re.compile(r"\bestoy\s+aburrido\b|\bme\s+aburro\b", re.IGNORECASE)
_WHAT_TODAY_RE = re.compile(
    r"\bqu[eé]\s+puedo\s+hacer\s+hoy\b|\bqu[eé]\s+hago\s+hoy\b",
    re.IGNORECASE,
)
_WATER_REMINDER_RE = re.compile(
    r"\brecu[eé]rdame\s+beber\s+agua\b|\brecu[eé]rdame\s+tomar\s+agua\b",
    re.IGNORECASE,
)
_TIME_RE = re.compile(r"\bqu[eé]\s+hora\s+es\b|\bme\s+dices\s+la\s+hora\b", re.IGNORECASE)
_TELL_SOMETHING_RE = re.compile(r"\bcu[eé]ntame\s+algo\b|\bdime\s+algo\b", re.IGNORECASE)
_HUMOR_REQUEST_RE = re.compile(
    r"\bchiste\b|\bbroma\b|\balgo\s+gracioso\b|\bhazme\s+re[ií]r\b",
    re.IGNORECASE,
)
_HUMOR_NOT_SENSE_RE = re.compile(
    r"\bno\s+tiene\s+sentido\b|\bno\s+se\s+entiende\b|\bno\s+tiene\s+gracia\b",
    re.IGNORECASE,
)
_HUMOR_ANOTHER_RE = re.compile(r"\botro\b|\botra\b|\buno\s+m[aá]s\b", re.IGNORECASE)

_JOKE_SIMPLE_1 = "Claro. Ahí va uno corto: ¿Qué hace una abeja en el gimnasio? ¡Zum-ba!"
_JOKE_SIMPLE_2 = "Vamos con otro más simple: ¿Qué le dice una taza a otra? Te veo el asa."
_JOKE_SIMPLE_3 = "Aquí tienes uno fácil: ¿Cuál es el colmo de un reloj? Estar siempre dando la hora."
_HEADACHE_RE = re.compile(
    r"\bme\s+duele\s+(?:mucho\s+)?la\s+cabeza\b|\btengo\s+dolor\s+de\s+cabeza\b",
    re.IGNORECASE,
)
_STOMACH_PAIN_RE = re.compile(
    r"\bme\s+duele\s+la\s+barriga\b"
    r"|\bme\s+duele\s+el\s+est[oó]mago\b"
    r"|\btengo\s+dolor\s+de\s+barriga\b"
    r"|\btengo\s+dolor\s+de\s+est[oó]mago\b",
    re.IGNORECASE,
)
_GENERAL_UNWELL_RE = re.compile(r"\bme\s+encuentro\s+mal\b|\bestoy\s+mal\b", re.IGNORECASE)
_MAL_EXACT_RE = re.compile(r"^mal$", re.IGNORECASE)
_LEG_PAIN_RE = re.compile(
    r"\bme\s+duele\s+la\s+pierna\b|\bdolor\s+de\s+pierna\b",
    re.IGNORECASE,
)
_NERVOUS_RE = re.compile(r"\bestoy\s+nervioso\b|\bme\s+siento\s+nervioso\b", re.IGNORECASE)
_SAD_RE = re.compile(r"\bestoy\s+triste\b|\bme\s+siento\s+triste\b", re.IGNORECASE)
_FALL_RE = re.compile(r"\bme\s+(?:he\s+)?ca[ií]d[oa]\b|\bme\s+ca[ií]\b", re.IGNORECASE)
_EMERGENCY_RE = re.compile(r"\bayuda\b|\bsocorro\b|\b112\b", re.IGNORECASE)
_CHECKIN_RE = re.compile(
    r"\b(?:estoy|me\s+encuentro|me\s+siento)\s+bien\b|\btodo\s+bien\b|\bcheckin\b",
    re.IGNORECASE,
)
_GENERIC_PAIN_SHORT_RE = re.compile(r"\bme\s+duele(?!\s+(?:la\s+)?(?:cabeza|pierna|espalda|barriga|est[oó]mago))\b", re.IGNORECASE)
_RECOVERY_RE = re.compile(r"\bya\s+estoy\s+mejor\b|\bme\s+encuentro\s+mejor\b|\bye\s+se\s+me\s+ha\s+pasado\b", re.IGNORECASE)
_ACK_AFFIRMATIVE_RE = re.compile(r"^(?:s[ií]|vale|ok|bueno|entendido|de\s+acuerdo)$", re.IGNORECASE)
_ACK_NEGATIVE_RE = re.compile(r"^(?:no|nada)$", re.IGNORECASE)
_NO_PAIN_RE = re.compile(
    r"\bno\s+me\s+duele\s+nada\b"
    r"|\bno\s+me\s+duele\b"
    r"|\bno\s+tengo\s+dolor\b"
    r"|\bno\s+tengo\s+molestias\b"
    r"|\bno\s+me\s+molesta\s+nada\b"
    r"|\bno\s+siento\s+dolor\b",
    re.IGNORECASE,
)


def local_response(user_text: str, intent: IntentType) -> str | None:
    """Return a pre-built response for common cases, or None to delegate to LLM.

        Priority order:
            1. Mild physical/emotional symptoms and daily support — empathetic, instant
            2. Food / recipes
            3. Identity / capabilities / thanks
            4. Pure greetings (only when the entire message is a greeting)

    The caller must handle safety protocols (fall, emergency) before this.
    """
    text = user_text.strip()
    lower = text.lower()

    # 1. Mild physical symptoms — local empathetic responses avoid an LLM round-trip
    if _DIZZINESS_RE.search(text):
        return (
            "Entiendo. Siéntate con calma y bebe un poco de agua si puedes. "
            "¿El mareo empezó de repente o llevas un rato así?"
        )
    if _BACKPAIN_RE.search(lower):
        return (
            "Lo siento, el dolor de espalda es muy molesto. "
            "Prueba a tumbarte un poco o aplicar calor suave. "
            "¿El dolor es muy fuerte o es manejable?"
        )
    if _TIRED_RE.search(lower):
        return (
            "El cansancio es la señal de que el cuerpo necesita descanso. "
            "¿Has podido dormir bien?"
        )
    if _COLD_RE.search(lower):
        return "Abrígate bien con una manta, cariño. ¿Te traigo algo caliente?"
    if _HEAT_RE.search(lower):
        return "Busca un sitio fresco y bebe un poco de agua. ¿Estás mejor así?"
    
    # Check for absence of pain BEFORE generic pain to avoid false positives
    if _NO_PAIN_RE.search(lower):
        return "Me alegra mucho que no sientas molestias. ¿Sigues encontrándote bien?"

    if _GENERIC_PAIN_SHORT_RE.search(lower):
        return "Vaya, lo siento mucho. ¿En qué parte del cuerpo te duele exactamente?"
    if _GENERAL_UNWELL_RE.search(lower) or _MAL_EXACT_RE.search(lower):
        return "Siento que no te encuentres bien. ¿Quieres sentarte un momento conmigo?"
    if _SLEEP_BAD_RE.search(lower):
        return (
            "Dormir mal agota mucho. Esta noche prueba una rutina tranquila y respiración lenta. "
            "Si quieres, te doy una idea sencilla para relajarte."
        )
    if _WANTS_SLEEP_RE.search(lower):
        return (
            "Claro, descansar cuando el cuerpo lo pide es muy buena idea. "
            "Que descanses bien. Llámame si me necesitas."
        )
    if _HEADACHE_RE.search(lower):
        return (
            "Siento que te duela la cabeza. Descansa en un lugar tranquilo e hidrátate un poco. "
            "Si quieres, nos quedamos hablando suave un momento."
        )
    if _STOMACH_PAIN_RE.search(lower):
        return (
            "Siento que te duela la barriga. Descansa un poco, toma agua a sorbitos y evita comidas pesadas. "
            "¿Quieres que estemos un rato tranquilos?"
        )
    if _MAL_EXACT_RE.fullmatch(lower):
        return (
            "Lo siento, estoy contigo. Si quieres, respiramos despacio y me cuentas qué notas ahora."
        )
    if _GENERAL_UNWELL_RE.search(lower):
        return (
            "Siento que te encuentres mal. Vamos con calma y descansamos un momento. "
            "¿Quieres contarme qué te molesta más?"
        )
    if _LEG_PAIN_RE.search(lower):
        return (
            "Vaya, eso molesta mucho. Si puedes, siéntate y eleva un poco la pierna para descansar. "
            "¿El dolor va aflojando?"
        )
    if _NERVOUS_RE.search(lower):
        return (
            "Estoy contigo. Vamos despacio: respira conmigo, inhalar y exhalar suave tres veces. "
            "¿Quieres que te guíe ahora?"
        )
    if _SAD_RE.search(lower):
        return (
            "Gracias por contármelo. A veces hablar un ratito ayuda mucho. "
            "Si te parece, buscamos algo pequeño que te haga sentir mejor ahora."
        )
    if _LONELY_RE.search(lower):
        return (
            "No estás solo, aquí estoy contigo. Podemos charlar un rato o recordar algo bonito. "
            "¿Qué te apetece más?"
        )
    if _BORED_RE.search(lower):
        return (
            "Te entiendo. Podemos hacer algo breve: música suave, estirarte un poco o una charla corta. "
            "¿Cuál prefieres?"
        )
    if _WHAT_TODAY_RE.search(lower):
        return (
            "Hoy podemos hacerlo fácil: un paseo corto en casa, beber agua y hablar con alguien querido. "
            "¿Empezamos por una de esas?"
        )
    if _WATER_REMINDER_RE.search(lower):
        return (
            "Claro. Te lo recuerdo por aquí: toma un vaso de agua ahora y otro dentro de un rato. "
            "Mantenerse hidratado ayuda mucho."
        )
    if _TIME_RE.search(lower):
        return "Ahora no tengo reloj en tiempo real, pero seguimos con calma contigo."
    if _TELL_SOMETHING_RE.search(lower):
        return (
            "Te cuento algo bonito: una conversación tranquila también cuida la salud. "
            "Si quieres, te cuento otra cosa breve."
        )
    if _HUMOR_REQUEST_RE.search(lower):
        if _HUMOR_ANOTHER_RE.search(lower):
            return _JOKE_SIMPLE_2
        return _JOKE_SIMPLE_1

    # 2. Food and recipes
    if _HUNGER_RE.search(lower):
        return (
            "Cuéntame qué tienes en casa y te sugiero algo sencillo. "
            "¿Prefieres algo caliente o frío?"
        )
    if _RECIPE_CHICKEN_RE.search(lower):
        return (
            "Receta fácil de pollo al horno: pon el pollo en una bandeja, "
            "añade aceite, sal, ajo y limón, y hornea a 200 °C unos 45 minutos. "
            "¿Tienes esos ingredientes?"
        )
    if _RECIPE_GENERIC_RE.search(lower):
        return (
            "Una opción sencilla: tortilla de patatas. Fríe patatas en láminas, "
            "mézclala con huevo batido y cuaja en la sartén. "
            "¿Hay algo que no puedas comer?"
        )

    # 3. Identity / capabilities / thanks
    if _WHO_RE.search(lower):
        return "Soy RITA, tu asistente de voz."
    if _CAPABILITIES_RE.search(lower):
        return (
            "Puedo conversar contigo, darte consejos sencillos y acompañarte. "
            "Si hay una urgencia, te guío para pedir ayuda."
        )
    if _RECOVERY_RE.search(lower):
        return "Me alegra muchísimo oír eso, de verdad. ¿Qué te gustaría hacer ahora para aprovechar que estás mejor?"
    if _THANKS_RE.search(lower):
        return "De nada, cariño. Es un placer acompañarte."
    if _ACK_AFFIRMATIVE_RE.fullmatch(lower):
        return "Perfecto, me parece muy bien."
    if _ACK_NEGATIVE_RE.fullmatch(lower):
        return "Entendido. Aquí sigo por si cambias de opinión o necesitas otra cosa."

    # 4. Pure greetings — only when the entire message is a greeting
    if intent == "greeting" and _PURE_GREETING_RE.fullmatch(lower.strip()):
        if re.search(
            r"\bbuen[oa]s?\s+d[ií]as\b|\bbuen[oa]s?\s+tardes\b|\bbuen[oa]s?\s+noches\b",
            lower,
            re.IGNORECASE,
        ):
            return "Hola, me alegra escucharte. ¿Cómo te ayudo hoy?"
        return "Hola, aquí estoy contigo. ¿Qué necesitas?"

    return None


# ── Short follow-up helpers ────────────────────────────────────────────────────

_FOLLOWUP_SHORT_RE = re.compile(r"^(?:s[ií]|no|vale|ok)$", re.IGNORECASE)

# Topic labels for routing contextual follow-up responses
_TOPIC_PAIN = "pain"
_TOPIC_SLEEP = "sleep"
_TOPIC_UNWELL = "unwell"
_TOPIC_HUMOR = "humor"


def infer_local_topic(user_text: str) -> str | None:
    """Detect which follow-up topic (if any) the user message opened locally."""
    lower = user_text.strip().lower()
    if (
        _HEADACHE_RE.search(lower)
        or _BACKPAIN_RE.search(lower)
        or _STOMACH_PAIN_RE.search(lower)
        or _LEG_PAIN_RE.search(lower)
    ):
        return _TOPIC_PAIN
    if (
        _TIRED_RE.search(lower)
        or _SLEEP_BAD_RE.search(lower)
        or _WANTS_SLEEP_RE.search(lower)
    ):
        return _TOPIC_SLEEP
    if (
        _DIZZINESS_RE.search(lower)
        or _GENERAL_UNWELL_RE.search(lower)
        or _MAL_EXACT_RE.fullmatch(lower)
    ):
        return _TOPIC_UNWELL
    if _HUMOR_REQUEST_RE.search(lower):
        return _TOPIC_HUMOR
    return None


def followup_response(user_text: str, last_topic: str | None) -> str | None:
    """Return a local response for short yes/no follow-up inputs based on context.

    Only activates when last_topic is set (a previous local response opened a
    health-related topic) and user_text is a short affirmative or negative reply.
    """
    if last_topic is None:
        return None
    lower = user_text.strip().lower()

    if last_topic == _TOPIC_HUMOR:
        if _HUMOR_NOT_SENSE_RE.search(lower):
            return (
                "Tienes razón, voy con uno más claro: "
                f"{_JOKE_SIMPLE_2}"
            )
        if _HUMOR_ANOTHER_RE.search(lower):
            return _JOKE_SIMPLE_3

    if not _FOLLOWUP_SHORT_RE.fullmatch(lower):
        return None

    affirmative = lower in ("sí", "si", "vale", "ok")

    if last_topic == _TOPIC_PAIN:
        if affirmative:
            return "Entiendo. Descansa con calma y bebe un poco de agua. Si el dolor sigue fuerte, avísame."
        return "De acuerdo. Si el dolor sigue o empeora, dímelo y buscamos ayuda juntos."

    if last_topic == _TOPIC_SLEEP:
        if affirmative:
            return "Bien. Descansa cuanto necesites, el sueño es muy importante para recuperarse."
        return "Vaya, lo siento. Prueba a respirar despacio antes de dormir; aquí estaré si me necesitas."

    if last_topic == _TOPIC_UNWELL:
        if affirmative:
            return "Me alegra mucho escucharlo. Sigue con calma y dime si necesitas cualquier cosa."
        return "Entiendo, estoy aquí contigo. Cuéntame qué notas si te apetece y lo miramos juntos."

    return None


def detect_backend_event_type(user_text: str, intent: IntentType) -> str | None:
    """Detect event_type to send to backend for relevant user intents."""
    text = user_text.strip().lower()

    if _FALL_RE.search(text):
        return "fall"
    if intent == "emergency" or _EMERGENCY_RE.search(text):
        return "emergency"
    if intent == "distress":
        return "distress"
    if _CHECKIN_RE.search(text):
        return "checkin"
    return None
