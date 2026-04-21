"""
Seed de puntuaciones diarias y conversaciones para toda la semana.
Simula dias buenos, regulares y malos para ver el historial y el inicio.
"""
from __future__ import annotations
import sys, os, json, uuid
sys.path.insert(0, os.path.dirname(__file__))

import psycopg
from datetime import datetime, timezone, timedelta, date

DSN = "postgresql://postgres:postgres@localhost:5434/rita"
USER_ID = 1
DEVICE_ID = 1

def utc(days_ago=0, hours_ago=0):
    return datetime.now(timezone.utc) - timedelta(days=days_ago, hours=hours_ago)

def d(days_ago=0):
    return (date.today() - timedelta(days=days_ago)).isoformat()

# ─── Puntuaciones diarias ────────────────────────────────────────────────────
# (date_str, global_score, narrative, factors, observed, missed)
SCORES = [
    (d(6), 82, "Buen día. Se mostró animada y comunicativa, hizo check-in a primera hora y mencionó haber descansado bien.",
     ["Checkin puntual", "Estado de ánimo positivo", "Mencionó buen descanso"],
     ["Contacto de bienestar matutino", "Hidratación"], []),

    (d(5), 45, "Día complicado. Comentó que tenía mucho dolor en la rodilla y no había podido dormir bien. Se mostró apagada.",
     ["Dolor reportado", "Mal descanso nocturno", "Estado de ánimo bajo"],
     ["Contacto de bienestar matutino"], ["Comida / Alimentación", "Hidratación"]),

    (d(4), 71, "Día tranquilo. Hizo check-in con normalidad, comentó que la rodilla había mejorado algo. Sin incidencias.",
     ["Mejoría física reportada", "Checkin puntual"],
     ["Contacto de bienestar matutino", "Comida / Alimentación"], []),

    (d(3), 88, "Muy buen día. Habló con entusiasmo de la visita de su nieto y se le notó con energía. Completó todas las rutinas.",
     ["Estado de ánimo muy positivo", "Visita familiar mencionada", "Rutinas completas"],
     ["Contacto de bienestar matutino", "Comida / Alimentación", "Hidratación"], []),

    (d(2), 60, "Día dentro de lo normal. Algo cansada por la noche anterior. Check-in algo tardío pero sin problemas relevantes.",
     ["Checkin con retraso leve", "Cansancio moderado"],
     ["Contacto de bienestar matutino"], ["Hidratación"]),

    (d(1), 51, "Se han registrado varias señales de malestar y el último contacto sigue mostrando síntomas que requieren atención.",
     ["Tensión arterial alta mencionada (145)", "Preocupación por falta de llamada del nieto"],
     ["Contacto de bienestar matutino"], ["Comida / Alimentación"]),

    # Hoy — actividad de mañana (tensión un poco alta, pero animada)
    (d(0), 74, "Buen comienzo de día. Comentó que la tensión estaba algo elevada pero que se encontraba animada. Check-in puntual.",
     ["Check-in puntual", "Tensión ligeramente alta mencionada", "Estado de ánimo positivo"],
     ["Contacto de bienestar matutino"], []),
]

# ─── Conversaciones adicionales ──────────────────────────────────────────────
EXTRA_SESSIONS = [
    # Día 6 (bueno) - lunes
    {
        "started_at": utc(days_ago=6, hours_ago=3),
        "last_activity_at": utc(days_ago=6, hours_ago=2),
        "ended_at": utc(days_ago=6, hours_ago=2),
        "status": "ended", "turn_count": 4,
        "session_summary": "Conversación animada. Descansó bien y está con ganas de empezar la semana. Mencionó que quiere llamar a su nieto.",
        "follow_up_suggestion": "Preguntar si llamó a su nieto.",
        "messages": [
            ("user", "Buenos días RITA, hoy me he levantado bastante bien la verdad."),
            ("assistant", "¡Qué alegría oírte así! ¿Has descansado bien esta noche?"),
            ("user", "Sí, dormí del tirón, cosa que no pasa siempre. Creo que voy a llamar a Alejandro hoy."),
            ("assistant", "Perfecto, seguro que le da mucha alegría saber de ti. ¿A qué hora sueles llamarle?"),
            ("user", "Por las tardes, sobre las seis. Antes de cenar."),
            ("assistant", "Muy bien. Que tengas un buen día. Cualquier cosa que necesites, aquí estoy."),
        ],
    },
    # Día 5 (malo) - martes
    {
        "started_at": utc(days_ago=5, hours_ago=4),
        "last_activity_at": utc(days_ago=5, hours_ago=3),
        "ended_at": utc(days_ago=5, hours_ago=3),
        "status": "ended", "turn_count": 5,
        "session_summary": "Día muy duro. Mucho dolor de rodilla, no durmió bien y está desanimada. No ha comido bien tampoco.",
        "follow_up_suggestion": "Verificar si mejoró el dolor y si ha podido comer algo.",
        "messages": [
            ("user", "Ay RITA, qué noche tan mala. La rodilla no me ha dejado dormir nada."),
            ("assistant", "Lo siento mucho. El dolor nocturno es muy difícil de llevar. ¿Has podido tomar tu medicación esta mañana?"),
            ("user", "La tomé pero tarda en hacer efecto. No tengo ganas ni de desayunar."),
            ("assistant", "Entiendo que cuando se está así de cansada no apetece nada. Pero intenta tomar aunque sea algo pequeño, tu cuerpo lo necesita para que la medicación funcione bien."),
            ("user", "Sí tienes razón... Voy a ver si me como una galleta con leche."),
            ("assistant", "Eso está muy bien. Y si el dolor no mejora a lo largo del día, díselo a tu cuidadora o al médico. ¿Tienes su teléfono a mano?"),
            ("user", "Sí, lo tengo apuntado. Gracias RITA."),
            ("assistant", "Cuídate mucho. Estaré aquí si me necesitas."),
        ],
    },
    # Día 3 (muy bueno) - jueves
    {
        "started_at": utc(days_ago=3, hours_ago=5),
        "last_activity_at": utc(days_ago=3, hours_ago=4),
        "ended_at": utc(days_ago=3, hours_ago=4),
        "status": "ended", "turn_count": 4,
        "session_summary": "Día estupendo. Alejandro vino a visitarla y fueron a pasear por el parque. Se le nota con mucha energía y felicidad.",
        "follow_up_suggestion": "Preguntar qué tal le fue la semana y si verá pronto a Alejandro de nuevo.",
        "messages": [
            ("user", "RITA, hoy ha sido un día precioso. Ha venido Alejandro."),
            ("assistant", "¡Qué ilusión! ¿Y qué habéis hecho juntos?"),
            ("user", "Hemos ido al parque a pasear y luego le he hecho las lentejas. Se ha comido dos platos."),
            ("assistant", "¡Qué bien! Nada como cocinar para alguien que quieres. ¿Cómo está él?"),
            ("user", "Muy bien, le va genial en los estudios. Me ha prometido venir más seguido."),
            ("assistant", "Me alegra muchísimo oírte tan contenta. Esos momentos con la familia son los mejores. ¿Cómo está la rodilla hoy?"),
            ("user", "Mucho mejor, el paseo me ha venido bien paradójicamente."),
            ("assistant", "El movimiento suave siempre ayuda. Qué día tan bonito has tenido."),
        ],
    },
    # Hoy
    {
        "started_at": utc(hours_ago=2),
        "last_activity_at": utc(hours_ago=1),
        "ended_at": utc(hours_ago=1),
        "status": "ended", "turn_count": 3,
        "session_summary": "Check-in matutino. Comentó tensión algo elevada (147) pero se encontraba animada. Preguntó si había noticias del nieto.",
        "follow_up_suggestion": "Verificar tensión arterial en la próxima toma y preguntar si ha llamado al nieto.",
        "messages": [
            ("user", "Buenos días RITA. Me he tomado la tensión y estaba un poco alta, 147."),
            ("assistant", "Buenos días. 147 es algo elevada, sí. ¿Has tomado ya la medicación de esta mañana?"),
            ("user", "Sí, ya la he tomado con el desayuno. Creo que ayer me pasé con la sal en la cena."),
            ("assistant", "Puede ser, la sal influye bastante. Bien que te lo hayas tomado. ¿Cómo te encuentras por lo demás?"),
            ("user", "Bien, animada. Estaba pensando en llamar a Alejandro hoy."),
            ("assistant", "Estupendo, seguro que le da alegría. Recuerda tomarte la tensión de nuevo a mediodía para ver si ha bajado."),
        ],
    },
]

EXTRA_EVENTS = [
    # Día 6 (bueno)
    ("checkin", "low", {}, utc(days_ago=6, hours_ago=8)),
    ("user_speech", "low", {"text": "Buenos días, hoy me he levantado bien"}, utc(days_ago=6, hours_ago=3)),
    # Día 5 (malo)
    ("checkin", "low", {}, utc(days_ago=5, hours_ago=9)),
    ("user_speech", "medium", {"text": "La rodilla no me ha dejado dormir, tengo dolor"}, utc(days_ago=5, hours_ago=4)),
    # Día 4 (normal)
    ("checkin", "low", {}, utc(days_ago=4, hours_ago=8)),
    ("user_speech", "low", {"text": "La rodilla ha mejorado un poco"}, utc(days_ago=4, hours_ago=3)),
    # Día 3 (muy bueno)
    ("checkin", "low", {}, utc(days_ago=3, hours_ago=8)),
    ("user_speech", "low", {"text": "Ha venido mi nieto, estoy muy contenta"}, utc(days_ago=3, hours_ago=5)),
    # Día 2 (normal-bajo)
    ("checkin", "low", {}, utc(days_ago=2, hours_ago=10)),
    ("user_speech", "low", {"text": "Estoy algo cansada hoy"}, utc(days_ago=2, hours_ago=3)),
    # Hoy
    ("checkin", "low", {}, utc(hours_ago=3)),
    ("user_speech", "low", {"text": "Buenos días, la tensión algo alta pero me encuentro bien"}, utc(hours_ago=2)),
]


def seed():
    conn = psycopg.connect(DSN)
    cur = conn.cursor()

    print("=== Limpiando datos anteriores ===")
    cur.execute("DELETE FROM daily_scores WHERE user_id = %s", (USER_ID,))
    cur.execute("DELETE FROM conversation_memories WHERE user_id = %s", (USER_ID,))
    cur.execute("""
        DELETE FROM conversation_messages WHERE session_id IN
        (SELECT id FROM conversation_sessions WHERE user_id = %s)
    """, (USER_ID,))
    cur.execute("DELETE FROM conversation_sessions WHERE user_id = %s", (USER_ID,))
    cur.execute("DELETE FROM events WHERE user_id = %s AND source = 'edge'", (USER_ID,))

    print("=== Insertando puntuaciones diarias ===")
    for (date_str, score, narrative, factors, observed, missed) in SCORES:
        cur.execute("""
            INSERT INTO daily_scores
              (user_id, date, global_score, mood_score, activity_score, routine_score,
               autonomy_score, baseline_similarity, main_factors, narrative_summary,
               interpretation, observed_routines, missed_or_late_routines,
               created_at, updated_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s, now(), now())
        """, (
            USER_ID, date_str, score,
            min(100, score + 5), max(0, min(100, score - 5)), score, score, score,
            json.dumps(factors), narrative,
            "Datos suficientes para el informe." if score > 0 else "Sin datos suficientes.",
            json.dumps(observed), json.dumps(missed),
        ))
    print(f"  {len(SCORES)} puntuaciones insertadas")

    print("=== Insertando sesiones y mensajes ===")
    all_sessions = [
        {
            "started_at": utc(days_ago=3, hours_ago=2),
            "last_activity_at": utc(days_ago=3, hours_ago=1),
            "ended_at": utc(days_ago=3, hours_ago=1),
            "status": "ended", "turn_count": 4,
            "session_summary": "La persona comentó que había dormido mal por el dolor de rodilla y que se sentía cansada. Mencionó que no había desayunado bien.",
            "follow_up_suggestion": "Preguntar cómo ha ido la rodilla y si ha podido descansar mejor.",
            "messages": [
                ("user", "Buenos días RITA. Hoy me he levantado un poco cansada, la verdad."),
                ("assistant", "Buenos días. ¿Qué tal ha ido la noche? ¿Has podido descansar bien?"),
                ("user", "No mucho, me ha dolido la rodilla izquierda bastante. Ya sabes, los huesos a esta edad..."),
                ("assistant", "Entiendo, el dolor nocturno es muy molesto. ¿Has podido tomar algo para el dolor?"),
                ("user", "Sí, tomé una pastilla por la mañana. También creo que no desayuné bien, solo un café."),
                ("assistant", "Es importante desayunar bien. ¿Podrías tomar algo más ahora? Un poco de fruta o una tostada te vendría muy bien."),
                ("user", "Tienes razón, voy a ver qué hay en la nevera. Gracias RITA."),
                ("assistant", "Claro que sí. Cuídate mucho. Aquí estoy."),
            ],
        },
        {
            "started_at": utc(days_ago=1, hours_ago=3),
            "last_activity_at": utc(days_ago=1, hours_ago=2),
            "ended_at": utc(days_ago=1, hours_ago=2),
            "status": "ended", "turn_count": 5,
            "session_summary": "Buena conversación. La persona habló sobre su nieto que viene a visitarla el fin de semana. Está animada y con ganas. Mencionó que le gustan las novelas de misterio.",
            "follow_up_suggestion": "Preguntar qué tal fue la visita del nieto.",
            "messages": [
                ("user", "RITA, ¿sabes qué? Mi nieto viene este fin de semana. Me hace mucha ilusión."),
                ("assistant", "¡Qué alegría! ¿Cuánto tiempo lleva sin venir a verte?"),
                ("user", "Casi dos meses. Está estudiando en Madrid. Se llama Alejandro, tiene 19 años."),
                ("assistant", "Seguro que tiene muchas cosas que contarte. ¿Tenéis algo planeado?"),
                ("user", "Creo que iremos a pasear por el parque. Y le voy a hacer su guiso favorito, el de lentejas."),
                ("assistant", "Suena perfecto. ¿Y tú cómo estás hoy? ¿Mejor de la rodilla?"),
                ("user", "Hoy está más tranquila, gracias. Estaba leyendo una novela de misterio, me encantan."),
                ("assistant", "¡Me alegra mucho oírte así de animada! Las novelas de misterio son fantásticas. ¿De qué autora es?"),
                ("user", "Agatha Christie. Siempre vuelvo a ella."),
                ("assistant", "Una clásica infalible. Disfruta de la lectura y de la visita de Alejandro."),
            ],
        },
        {
            "started_at": utc(hours_ago=2),
            "last_activity_at": utc(hours_ago=1),
            "ended_at": None,
            "status": "active", "turn_count": 3,
            "session_summary": None,
            "follow_up_suggestion": None,
            "messages": [
                ("user", "RITA, buenos días. ¿Qué tiempo va a hacer hoy?"),
                ("assistant", "Buenos días. No tengo acceso al tiempo en tiempo real, pero puedes mirarlo por la ventana. ¿Cómo te encuentras tú hoy?"),
                ("user", "Bien bien. Un poco de tensión, me la tomé antes y estaba un poco alta, 145. Pero ya he desayunado."),
                ("assistant", "Bien que te la hayas tomado. 145 es algo alta. ¿Lo tienes anotado para contárselo al médico el martes?"),
                ("user", "Sí, se lo digo. Oye, el nieto no me ha llamado todavía hoy..."),
                ("assistant", "Seguro que te llama pronto. Los jóvenes a veces se lían con los horarios. ¿Quieres que te recuerde llamarle tú a la hora de comer?"),
            ],
        },
    ]

    for s in all_sessions + EXTRA_SESSIONS:
        cur.execute("""
            INSERT INTO conversation_sessions
              (user_id, status, turn_count, session_summary, follow_up_suggestion,
               started_at, last_activity_at, ended_at, summary_turn_index)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,0) RETURNING id
        """, (USER_ID, s["status"], s["turn_count"], s["session_summary"],
              s["follow_up_suggestion"], s["started_at"], s["last_activity_at"], s["ended_at"]))
        sid = cur.fetchone()[0]
        for idx, (role, content) in enumerate(s["messages"]):
            mood = "sad" if (role == "user" and any(w in content for w in ["dolor","cansada","mala","malestar"])) else None
            risk = "low" if mood == "sad" else None
            cur.execute("""
                INSERT INTO conversation_messages
                  (session_id, user_id, role, content, turn_index, mood, risk_level,
                   requested_help, routine_change_detected)
                VALUES (%s,%s,%s,%s,%s,%s,%s,false,false)
            """, (sid, USER_ID, role, content, idx, mood, risk))

    print("=== Insertando memorias ===")
    MEMORIES = [
        ("person", "high", "Se llama Demo Senior y vive sola. Tiene un nieto llamado Alejandro, de 19 años, que estudia en Madrid."),
        ("person", "high", "Le encanta la lectura, especialmente las novelas de misterio de Agatha Christie."),
        ("health", "high", "Sufre dolores crónicos en la rodilla izquierda, especialmente por la noche."),
        ("health", "high", "Tiene tendencia a la tensión arterial alta. Valor reciente: 145."),
        ("health", "medium", "A veces no desayuna bien, sobre todo cuando está cansada o con dolor."),
        ("preference", "high", "Le gusta pasear por el parque. Disfruta cocinando guisos tradicionales como lentejas."),
        ("routine", "high", "Tiene cita médica el martes. Toma medicación para el dolor según necesidad."),
        ("emotional", "high", "Se muestra animada y positiva cuando habla de su nieto o de sus lecturas."),
        ("emotional", "medium", "Cuando no descansa bien tiende a encontrarse más cansada y con menos apetito."),
        ("life_event", "high", "Su nieto Alejandro la visitó el jueves pasado — paseo por el parque y lentejas caseras."),
    ]
    for (t, c, content) in MEMORIES:
        cur.execute("""
            INSERT INTO conversation_memories
              (user_id, memory_type, content, confidence, is_active,
               first_mentioned_at, last_confirmed_at, mention_count)
            VALUES (%s,%s,%s,%s,true,now(),now(),1)
        """, (USER_ID, t, content, c))

    print("=== Insertando eventos ===")
    for (etype, severity, payload, created_at) in EXTRA_EVENTS:
        cur.execute("""
            INSERT INTO events
              (trace_id, device_id, user_id, event_type, severity, source, payload_json, created_at)
            VALUES (%s,%s,%s,%s,%s,'edge',%s,%s)
        """, (str(uuid.uuid4()), DEVICE_ID, USER_ID, etype, severity, json.dumps(payload), created_at))

    conn.commit()
    conn.close()
    print("\n=== Seed completado ===")
    print("Puntuaciones por día:")
    for (d_str, score, *_) in SCORES:
        bar = "█" * (score // 10)
        print(f"  {d_str}  {score:3d}  {bar}")

if __name__ == "__main__":
    seed()
