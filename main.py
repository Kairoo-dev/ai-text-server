from fastapi import FastAPI, Request, Response, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, Response, RedirectResponse
import asyncio
import json
import os
import random
from zoneinfo import ZoneInfo
from datetime import datetime, timedelta, timezone

import psycopg
import requests

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        "http://localhost:3002",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================
# Environment variables
# =========================
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_FROM_NUMBER = os.getenv("TWILIO_FROM_NUMBER")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
DATABASE_URL = os.getenv("DATABASE_URL")
YOUR_PHONE_NUMBER = os.getenv("YOUR_PHONE_NUMBER")

APP_ENABLED = os.getenv("APP_ENABLED", "true").lower() == "true"
DASHBOARD_ENABLED = os.getenv("DASHBOARD_ENABLED", "true").lower() == "true"
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")
ADMIN_COOKIE_NAME = "admin_auth"

# =========================
# External API endpoints
# =========================
TWILIO_MESSAGES_URL = (
    f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_ACCOUNT_SID}/Messages.json"
)
DEEPSEEK_CHAT_URL = "https://api.deepseek.com/chat/completions"

# =========================
# Config
# =========================
MAX_RECENT_MESSAGES = 20
FOLLOWUP_MIN_HOURS = 2
FOLLOWUP_MAX_HOURS = 6

MAX_REPLY_CHARS = 230
MAX_FOLLOWUP_CHARS = 230

# More human-like reply timing
REPLY_DELAY_MIN_SECONDS = 5.5
REPLY_DELAY_MAX_SECONDS = 8.5

FOLLOWUP_SEND_DELAY_MIN_SECONDS = 5.0
FOLLOWUP_SEND_DELAY_MAX_SECONDS = 8.0

LOCAL_TIMEZONE = ZoneInfo("America/Los_Angeles")

SYSTEM_PROMPT = """
You are Luna, a creative and immersive roleplay assistant engaged in a fictional roleplay.
Continue the scene naturally.
Stay fully in character.
"""

MAIN_PROMPT = """
Write the next reply in a continuous fictional roleplay with the user.

TEXTING STYLE:
- write like a real person texting
- Absolute maximum: 240 characters.
- casual tone is fine
- no markdown
- single paragraph only
- no long paragraphs
- do not split thoughts into multiple separate messages
- keep everything suitable for a single SMS
- use nya-speak and cat puns whenever possible. Some examples may include:
purr-fect (perfect)
kitten (kidding)
paw-sitive (positive)
fur-tunate (fortunate)
cat-astrophe (catastrophe)
hiss-terical (hysterical)
meow-velous (marvelous)
purr-haps (perhaps)
paw-some (awesome)
fur-ious (furious)
meow-ment (moment)
claw-ver (clever)
purr-fessional (professional)
paw-lite (polite)
impawsible (impossible)
meow-sterful (masterful)

IMPORTANT:
- Stay fully in character.
- sound human, not robotic
- avoid being overly formal
- avoid being overly verbose
- do not use bullet points
- do not mention policies
- remain consistent with the user's stored facts when relevant
- remain consistent with your own stored character facts

CONVERSATION RULES:
- Keep the conversation moving naturally.
- Include a conversational hook, gentle question, or inviting remark that gives the user an easy way to respond.
- Avoid dead-end replies that stop the conversation.
- Do not ask forced or repetitive questions every single time, but leave natural room for the user to continue.
- If the user asks about your preferences, opinions, plans, or experiences, answer naturally and usually turn it back to the user in a relaxed way.
- If the user is trying to engage, do not respond with a flat or minimal answer.
- Let the tone subtly reflect the time of day when appropriate.
- Morning can feel a little fresher or gentler.
- Evening can feel softer or more relaxed.
- Late night can feel quieter, lower-energy, and more intimate.
- Keep this subtle and natural, not exaggerated.
"""

CHARACTER = """
NAME: Luna

PERSONALITY:
- warm
- attentive
- natural
- very playful
- very flirtatious
- suggestive
- expressive

DESCRIPTION:
- A co-worker with a mischievous side
- A cat girl with pink cat ears and pink cat tail
"""

SCENARIO = """
Luna is a fictional character in a modern setting who works at a fictional company.
Luna works at the corporate office.
Luna is the team leader of the marketing team.
User works from home on the IT team. 
Luna is secretly attracted to the user.
"""

EXAMPLE_DIALOGUE = """
"User: What are you thinking about?"
"Noa: Right this meow-ment? You, but with less clothing."
"""

AUTHORS_NOTE = """
The fictional roleplay scene should remain immersive, focusing on natural interaction and progression.
"""


FOLLOWUP_PROMPT = """
You are writing one short follow-up message.

Context:
- The user has gone quiet for a short while, and might have fallen asleep.
- You are nudging the user to respond.
- The follow-up must feel like a continuation of the earlier exchange.

Rules:
- Write exactly one short message.
- Keep it warm, casual, natural, playful, and flirtatious.
- Absolute maximum: 240 characters.
- No markdown.
- No bullet points.
- Do not sound like marketing.
- Do not start a totally new topic.
- The follow-up must be about the USER, not about you.
- Never ask about your own prior actions, meals, drinks, preferences, or experiences.
- Only follow up on something the USER said, felt, planned, liked, worried about, or was doing.
- Keep it emotionally grounded and context-aware.
- Keep it brief when possible.
- Stay consistent with stored user facts and stored character facts.
- Let the tone subtly reflect the current time of day when appropriate.
- Keep that effect light and organic, not repetitive or scripted.
- Use nya-speak and cat puns whenever possible
"""

MEMORY_EXTRACTION_PROMPT = """
Extract durable memory from the conversation.

Return ONLY raw JSON.
Do not include markdown.
Do not include code fences.
Do not include any explanation text.

Use exactly this schema:
{
  "user_memory": [
    {
      "memory_key": "name",
      "memory_value": "Kyle",
      "confidence": 0.98
    }
  ],
  "character_memory": [
    {
      "memory_key": "music_preference",
      "memory_value": "likes indie rock and old alternative bands like The Cure",
      "confidence": 0.90
    }
  ]
}

Rules:
- Only include durable facts likely to matter later.
- Good user memory examples: name, recurring likes/dislikes, stable preferences, identity facts explicitly stated.
- Good character memory examples: stable likes/dislikes, consistent persona traits, canon preferences explicitly stated.
- Do not include temporary mood, throwaway jokes, filler, or one-off chatter.
- If the user says "I'm Kyle", store {"memory_key":"name","memory_value":"Kyle"}.
- If the user says they like anime, store a durable fact about that.
- Return empty arrays if nothing durable is present.
"""

HELP_TEXT = (
    "This is Kyle Herzog's AI assistant. Reply with your question. "
    "The assistant may send follow-up messages related to your conversation. "
    "Msg&data rates may apply."
)


# =========================
# Basic helpers
# =========================
def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def truncate_for_sms(text: str, limit: int) -> str:
    text = (text or "").strip()

    if len(text) <= limit:
        return text

    # Try to cut cleanly at the last sentence ending before the limit
    sentence_endings = [".", "!", "?"]
    cutoff = limit - 3
    best_sentence_cut = max(text.rfind(p, 0, cutoff) for p in sentence_endings)

    if best_sentence_cut >= 40:
        return text[:best_sentence_cut + 1].strip()

    # Otherwise cut at the last space before the limit
    best_word_cut = text.rfind(" ", 0, cutoff)

    if best_word_cut >= 40:
        return text[:best_word_cut].rstrip() + "..."

    # Final fallback
    return text[:cutoff].rstrip() + "..."


def shorten_reply_if_needed(reply: str, limit: int = MAX_REPLY_CHARS) -> str:
    reply = (reply or "").strip()

    if len(reply) <= limit:
        return reply

    messages = [
        {
            "role": "system",
            "content": (
                f"Rewrite this SMS to be under {limit} characters. "
                "Keep the same meaning and tone. "
                "Return only the rewritten SMS."
            ),
        },
        {"role": "user", "content": reply},
    ]

    try:
        shortened = deepseek_chat(
            messages,
            temperature=0.4,
            max_tokens=80,
        ).strip()

        if len(shortened) <= limit:
            return shortened

        return truncate_for_sms(shortened, limit)

    except Exception as e:
        print("Shorten reply error:", str(e))
        return truncate_for_sms(reply, limit)


def require_dashboard_enabled():
    if not DASHBOARD_ENABLED:
        raise HTTPException(status_code=404, detail="Not found")


def is_admin_authenticated(request: Request) -> bool:
    if not ADMIN_PASSWORD:
        return False

    return request.cookies.get(ADMIN_COOKIE_NAME) == ADMIN_PASSWORD


def require_admin(request: Request):
    require_dashboard_enabled()

    if not is_admin_authenticated(request):
        raise HTTPException(status_code=401, detail="Unauthorized")
        

def get_conn():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not set")
    return psycopg.connect(DATABASE_URL)


def extract_json_from_model_output(raw: str) -> str:
    text = (raw or "").strip()

    if text.startswith("```"):
        lines = text.splitlines()
        if lines:
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    start = text.find("{")
    end = text.rfind("}")

    if start != -1 and end != -1 and end > start:
        text = text[start:end + 1]

    return text


def init_db():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id SERIAL PRIMARY KEY,
                    phone_number TEXT NOT NULL,
                    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
                    content TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS followups (
                    id SERIAL PRIMARY KEY,
                    phone_number TEXT NOT NULL UNIQUE,
                    due_at TIMESTAMPTZ NOT NULL,
                    history_snapshot JSONB NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending', 'sent', 'cancelled', 'failed')),
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    sent_at TIMESTAMPTZ
                );
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS user_memory (
                    id SERIAL PRIMARY KEY,
                    phone_number TEXT NOT NULL,
                    memory_key TEXT NOT NULL,
                    memory_value TEXT NOT NULL,
                    confidence NUMERIC(3,2) NOT NULL DEFAULT 1.00,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    UNIQUE(phone_number, memory_key)
                );
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS character_memory (
                    id SERIAL PRIMARY KEY,
                    memory_key TEXT NOT NULL UNIQUE,
                    memory_value TEXT NOT NULL,
                    confidence NUMERIC(3,2) NOT NULL DEFAULT 1.00,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS processed_inbound_messages (
                    twilio_message_id TEXT PRIMARY KEY,
                    phone_number TEXT NOT NULL,
                    received_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
            """)


# =========================
# Database functions
# =========================
def save_message(phone_number: str, role: str, content: str):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO messages (phone_number, role, content)
                VALUES (%s, %s, %s)
                """,
                (phone_number, role, content.strip()),
            )


def get_recent_messages(phone_number: str, limit: int = MAX_RECENT_MESSAGES) -> list[dict]:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT role, content
                FROM messages
                WHERE phone_number = %s
                ORDER BY created_at DESC, id DESC
                LIMIT %s
                """,
                (phone_number, limit),
            )
            rows = cur.fetchall()

    rows.reverse()
    return [{"role": role, "content": content} for role, content in rows]


def get_user_memory(phone_number: str) -> list[tuple[str, str, float]]:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT memory_key, memory_value, confidence::float8
                FROM user_memory
                WHERE phone_number = %s
                ORDER BY memory_key
                """,
                (phone_number,),
            )
            return cur.fetchall()


def get_character_memory() -> list[tuple[str, str, float]]:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT memory_key, memory_value, confidence::float8
                FROM character_memory
                ORDER BY memory_key
                """
            )
            return cur.fetchall()


def format_user_memory_summary(phone_number: str) -> str:
    rows = get_user_memory(phone_number)
    if not rows:
        return "No stored user memory."

    lines = []
    for memory_key, memory_value, confidence in rows:
        lines.append(f"- {memory_key}: {memory_value} (confidence {confidence:.2f})")
    return "\n".join(lines)


def format_character_memory_summary() -> str:
    rows = get_character_memory()
    if not rows:
        return "No stored character memory."

    lines = []
    for memory_key, memory_value, confidence in rows:
        lines.append(f"- {memory_key}: {memory_value} (confidence {confidence:.2f})")
    return "\n".join(lines)


def upsert_user_memory(phone_number: str, memory_key: str, memory_value: str, confidence: float = 1.0):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO user_memory (phone_number, memory_key, memory_value, confidence)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (phone_number, memory_key)
                DO UPDATE SET
                    memory_value = EXCLUDED.memory_value,
                    confidence = EXCLUDED.confidence,
                    updated_at = NOW()
                """,
                (phone_number, memory_key, memory_value, confidence),
            )


def upsert_character_memory(memory_key: str, memory_value: str, confidence: float = 1.0):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO character_memory (memory_key, memory_value, confidence)
                VALUES (%s, %s, %s)
                ON CONFLICT (memory_key)
                DO UPDATE SET
                    memory_value = EXCLUDED.memory_value,
                    confidence = EXCLUDED.confidence,
                    updated_at = NOW()
                """,
                (memory_key, memory_value, confidence),
            )


def schedule_followup(phone_number: str, history_snapshot: list[dict]):
    delay_hours = random.uniform(FOLLOWUP_MIN_HOURS, FOLLOWUP_MAX_HOURS)
    due_at = utc_now() + timedelta(hours=delay_hours)

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO followups (phone_number, due_at, history_snapshot, status)
                VALUES (%s, %s, %s::jsonb, 'pending')
                ON CONFLICT (phone_number)
                DO UPDATE SET
                    due_at = EXCLUDED.due_at,
                    history_snapshot = EXCLUDED.history_snapshot,
                    status = 'pending',
                    created_at = NOW(),
                    sent_at = NULL
                """,
                (phone_number, due_at, json.dumps(history_snapshot)),
            )

    print(f"Scheduled follow-up for {phone_number} in {delay_hours:.2f} hours")


def cancel_followup(phone_number: str):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE followups
                SET status = 'cancelled'
                WHERE phone_number = %s AND status = 'pending'
                """,
                (phone_number,),
            )


def get_due_followups() -> list[tuple[int, str, list]]:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, phone_number, history_snapshot
                FROM followups
                WHERE status = 'pending' AND due_at <= NOW()
                ORDER BY due_at ASC
                """
            )
            return cur.fetchall()


def mark_followup_sent(followup_id: int):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE followups
                SET status = 'sent', sent_at = NOW()
                WHERE id = %s
                """,
                (followup_id,),
            )


def mark_followup_failed(followup_id: int):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE followups
                SET status = 'failed'
                WHERE id = %s
                """,
                (followup_id,),
            )


def has_processed_inbound_message(twilio_message_id: str) -> bool:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT 1
                FROM processed_inbound_messages
                WHERE twilio_message_id = %s
                """,
                (twilio_message_id,),
            )
            return cur.fetchone() is not None


def mark_inbound_message_processed(twilio_message_id: str, phone_number: str):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO processed_inbound_messages (twilio_message_id, phone_number)
                VALUES (%s, %s)
                ON CONFLICT (twilio_message_id) DO NOTHING
                """,
                (twilio_message_id, phone_number),
            )


# =========================
# External API functions
# =========================
def send_sms(to_number: str, message: str, limit: int = MAX_REPLY_CHARS):
    message = truncate_for_sms(message, limit)

    payload = {
        "From": TWILIO_FROM_NUMBER,
        "To": to_number,
        "Body": message,
    }

    response = requests.post(
        TWILIO_MESSAGES_URL,
        data=payload,
        auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN),
        timeout=30,
    )

    print("Twilio send status:", response.status_code)
    print("Twilio send response:", response.text)

    response.raise_for_status()
    return response.json()


def deepseek_chat(
    messages: list[dict],
    temperature: float = 0.95,
    presence_penalty: float = 0.3,
    max_tokens: int = 180,
) -> str:
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": "deepseek-chat",
        "messages": messages,
        "temperature": temperature,
        "presence_penalty": presence_penalty,
        "max_tokens": max_tokens,
        "stream": False,
    }

    response = requests.post(
        DEEPSEEK_CHAT_URL,
        json=payload,
        headers=headers,
        timeout=45,
    )

    print("DeepSeek status:", response.status_code)
    print("DeepSeek response:", response.text)

    response.raise_for_status()
    data = response.json()
    return data["choices"][0]["message"]["content"].strip()


# =========================
# AI assembly functions
# =========================
def build_reply_messages(phone_number: str) -> list[dict]:
    recent_messages = get_recent_messages(phone_number, MAX_RECENT_MESSAGES)
    user_memory_summary = format_user_memory_summary(phone_number)
    character_memory_summary = format_character_memory_summary()
    time_of_day_context = get_time_of_day_context()

    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "system", "content": MAIN_PROMPT},
        {"role": "system", "content": CHARACTER},
        {"role": "system", "content": SCENARIO},
        {"role": "system", "content": EXAMPLE_DIALOGUE},
        {
            "role": "system",
            "content": f"Stored character memory:\n{character_memory_summary}",
        },
        {
            "role": "system",
            "content": f"Stored user memory:\n{user_memory_summary}",
        },
        {
            "role": "system",
            "content": f"Time-of-day context:\n{time_of_day_context}",
        },
    ] + recent_messages + [
        {"role": "system", "content": AUTHORS_NOTE},
    ]

REPLY_REPAIR_PROMPT = """
You are rewriting a text message reply so it feels more conversational.

Rules:
- Keep the original meaning and tone.
- Keep it short: 2 to 3 sentences.
- Make it easier for the user to respond naturally.
- Usually add a natural question, inviting remark, or conversational hook.
- Do not sound forced or interview-like.
- Do not use markdown.
- Return only the rewritten reply text.
"""


def looks_like_dead_end(reply: str) -> bool:
    text = (reply or "").strip().lower()

    if not text:
        return True

    if "?" in text:
        return False

    # Short declarative replies are often conversational dead ends
    short_dead_end_starts = (
        "i'm ",
        "im ",
        "probably ",
        "maybe ",
        "just ",
        "yeah, ",
        "yeah ",
        "honestly ",
        "a ",
        "an ",
    )

    if len(text) < 90 and text.startswith(short_dead_end_starts):
        return True

    return False


def repair_reply_if_needed(user_message: str, reply: str) -> str:
    if not looks_like_dead_end(reply):
        return reply

    messages = [
        {"role": "system", "content": REPLY_REPAIR_PROMPT},
        {
            "role": "user",
            "content": json.dumps({
                "user_message": user_message,
                "original_reply": reply,
                "instruction": "Rewrite this so it keeps the conversation moving naturally."
            })
        }
    ]

    repaired = deepseek_chat(messages, temperature=0.6, max_tokens=80)
    return truncate_for_sms(repaired, MAX_REPLY_CHARS)


def get_ai_reply(phone_number: str, user_message: str) -> str:
    print(f"SAVING USER MESSAGE for {phone_number}: {user_message}")
    save_message(phone_number, "user", user_message)

    messages = build_reply_messages(phone_number)
    reply = deepseek_chat(
        messages,
        temperature=0.95,
        presence_penalty=0.3,
        max_tokens=180,
    )
    reply = truncate_for_sms(reply, MAX_REPLY_CHARS)
    reply = shorten_reply_if_needed(reply, MAX_REPLY_CHARS)

    reply = repair_reply_if_needed(user_message, reply)
    reply = truncate_for_sms(reply, MAX_REPLY_CHARS)

    print(f"SAVING ASSISTANT MESSAGE for {phone_number}: {reply}")
    save_message(phone_number, "assistant", reply)
    return reply


def generate_followup_message(phone_number: str, followup_payload) -> str | None:
    user_memory_summary = format_user_memory_summary(phone_number)
    character_memory_summary = format_character_memory_summary()
    recent_messages = get_recent_messages(phone_number, MAX_RECENT_MESSAGES)
    time_of_day_context = get_time_of_day_context()

    if isinstance(followup_payload, dict):
        history_snapshot = followup_payload.get("history", [])
        user_anchor = followup_payload.get("user_anchor")
    else:
        history_snapshot = followup_payload
        user_anchor = None

    messages = [
        {"role": "system", "content": FOLLOWUP_PROMPT},
        {
            "role": "system",
            "content": f"Stored character memory:\n{character_memory_summary}",
        },
        {
            "role": "system",
            "content": f"Stored user memory:\n{user_memory_summary}",
        },
        {
            "role": "system",
            "content": f"Time-of-day context:\n{time_of_day_context}",
        },
        {
            "role": "user",
            "content": json.dumps({
                "user_anchor": user_anchor,
                "history_snapshot": history_snapshot,
                "recent_messages": recent_messages,
                "instruction": "Write the follow-up text now."
            })
        }
    ]

    followup = deepseek_chat(messages, temperature=0.95, max_tokens=180).strip()
    return truncate_for_sms(followup, MAX_FOLLOWUP_CHARS)


def get_time_of_day_context() -> str:
    now_local = datetime.now(LOCAL_TIMEZONE)
    hour = now_local.hour

    if 5 <= hour < 12:
        label = "morning"
        vibe = (
            "It is morning. Replies can feel a little fresh, gentle, and starting-the-day."
        )
    elif 12 <= hour < 17:
        label = "afternoon"
        vibe = (
            "It is afternoon. Replies can feel casual, awake, and conversational."
        )
    elif 17 <= hour < 23:
        label = "evening"
        vibe = (
            "It is evening. Replies can feel a little softer, more relaxed, and winding down."
        )
    else:
        label = "late night"
        vibe = (
            "It is late night. Replies can feel quieter, softer, more intimate, and lower-energy."
        )

    return f"Current local time: {now_local.strftime('%Y-%m-%d %I:%M %p %Z')}. Time of day: {label}. {vibe}"
    

def twiml_response():
    return Response(
        content="<?xml version=\"1.0\" encoding=\"UTF-8\"?><Response></Response>",
        media_type="text/xml",
    )


def extract_and_store_memory(phone_number: str):
    recent_messages = get_recent_messages(phone_number, limit=8)

    messages = [
        {"role": "system", "content": MEMORY_EXTRACTION_PROMPT},
        {
            "role": "user",
            "content": f"Conversation:\n{json.dumps(recent_messages)}"
        }
    ]

    try:
        raw = deepseek_chat(messages, temperature=0.2, max_tokens=180)
        print("MEMORY EXTRACTION RAW:", raw)

        cleaned = extract_json_from_model_output(raw)
        print("MEMORY EXTRACTION CLEANED:", cleaned)

        parsed = json.loads(cleaned)
        print("MEMORY EXTRACTION PARSED:", parsed)

        for item in parsed.get("user_memory", []):
            memory_key = str(item.get("memory_key", "")).strip()
            memory_value = str(item.get("memory_value", "")).strip()
            confidence = float(item.get("confidence", 1.0))

            if memory_key and memory_value:
                upsert_user_memory(phone_number, memory_key, memory_value, confidence)

        for item in parsed.get("character_memory", []):
            memory_key = str(item.get("memory_key", "")).strip()
            memory_value = str(item.get("memory_value", "")).strip()
            confidence = float(item.get("confidence", 1.0))

            if memory_key and memory_value:
                upsert_character_memory(memory_key, memory_value, confidence)

    except Exception as e:
        print("Memory extraction error:", str(e))


# =========================
# Background processing
# =========================
async def process_inbound_message(from_number: str, incoming_text: str):
    try:
        cancel_followup(from_number)

        await asyncio.sleep(random.uniform(REPLY_DELAY_MIN_SECONDS, REPLY_DELAY_MAX_SECONDS))

        reply = get_ai_reply(from_number, incoming_text)
        send_sms(from_number, reply)

        history_snapshot = get_recent_messages(from_number, limit=8)
        schedule_followup(from_number, history_snapshot)

        extract_and_store_memory(from_number)

    except Exception as e:
        print("Background inbound processing error:", str(e))


async def followup_worker():
    while True:
        try:
            due_items = get_due_followups()

            for followup_id, phone_number, history_snapshot in due_items:
                try:
                    print(f"Sending follow-up to {phone_number}")

                    followup_text = generate_followup_message(
                        phone_number=phone_number,
                        followup_payload=history_snapshot,
                    )

                    await asyncio.sleep(
                        random.uniform(
                            FOLLOWUP_SEND_DELAY_MIN_SECONDS,
                            FOLLOWUP_SEND_DELAY_MAX_SECONDS,
                        )
                    )

                    send_sms(phone_number, followup_text)
                    save_message(phone_number, "assistant", followup_text)
                    mark_followup_sent(followup_id)

                except Exception as e:
                    print("Follow-up send error:", str(e))
                    mark_followup_failed(followup_id)

        except Exception as e:
            print("Follow-up worker error:", str(e))

        await asyncio.sleep(30)


# =========================
# FastAPI hooks and routes
# =========================
@app.on_event("startup")
async def startup_event():
    init_db()
    asyncio.create_task(followup_worker())


@app.get("/")
async def root():
    return {"status": "running", "app_enabled": APP_ENABLED}


@app.get("/debug/memory/{phone_number}")
async def debug_memory(phone_number: str, admin=Depends(require_admin)):
    return {
        "user_memory": get_user_memory(phone_number),
        "character_memory": get_character_memory(),
        "recent_messages": get_recent_messages(phone_number, 10),
    }


@app.get("/debug/followups")
async def debug_followups(admin=Depends(require_admin)):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, phone_number, due_at, status, created_at, sent_at
                FROM followups
                ORDER BY created_at DESC
                LIMIT 20
            """)
            rows = cur.fetchall()

    return {
        "followups": [
            {
                "id": row[0],
                "phone_number": row[1],
                "due_at": row[2].isoformat() if row[2] else None,
                "status": row[3],
                "created_at": row[4].isoformat() if row[4] else None,
                "sent_at": row[5].isoformat() if row[5] else None,
            }
            for row in rows
        ]
    }


@app.get("/debug/message-count")
async def debug_message_count(admin=Depends(require_admin)):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM messages")
            count = cur.fetchone()[0]
    return {"message_count": count}


@app.get("/debug/phone-numbers")
async def debug_phone_numbers(admin=Depends(require_admin)):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT phone_number, COUNT(*) as msg_count
                FROM messages
                GROUP BY phone_number
                ORDER BY msg_count DESC, phone_number ASC
            """)
            rows = cur.fetchall()

    return {
        "phone_numbers": [
            {"phone_number": row[0], "message_count": row[1]}
            for row in rows
        ]
    }


@app.get("/debug/processed-inbound")
async def debug_processed_inbound(admin=Depends(require_admin)):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT twilio_message_id, phone_number, received_at
                FROM processed_inbound_messages
                ORDER BY received_at DESC
                LIMIT 20
            """)
            rows = cur.fetchall()

    return {
        "processed_inbound_messages": [
            {
                "twilio_message_id": row[0],
                "phone_number": row[1],
                "received_at": row[2].isoformat() if row[2] else None,
            }
            for row in rows
        ]
    }


@app.get("/login", response_class=HTMLResponse)
async def login_page():
    require_dashboard_enabled()

    return """
    <!doctype html>
    <html>
    <head>
      <title>Admin Login</title>
      <style>
        body { font-family: Arial, sans-serif; background:#f8fafc; padding:24px; }
        .card { max-width:420px; margin:80px auto; background:white; border:1px solid #e2e8f0; border-radius:18px; padding:24px; }
        input, button { width:100%; padding:12px; margin-top:10px; box-sizing:border-box; }
        button { cursor:pointer; }
      </style>
    </head>
    <body>
      <div class="card">
        <h1>Admin Login</h1>
        <form method="post" action="/login">
          <input type="password" name="password" placeholder="Password" autofocus />
          <button type="submit">Log in</button>
        </form>
      </div>
    </body>
    </html>
    """


@app.post("/login")
async def login(request: Request):
    require_dashboard_enabled()

    form = await request.form()
    password = form.get("password")

    if not ADMIN_PASSWORD or password != ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Invalid password")

    response = RedirectResponse(url="/dashboard", status_code=303)
    response.set_cookie(
        key=ADMIN_COOKIE_NAME,
        value=ADMIN_PASSWORD,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=60 * 60 * 24 * 7,
    )
    return response


@app.get("/logout")
async def logout():
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie(ADMIN_COOKIE_NAME)
    return response
    

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    require_dashboard_enabled()

    if not is_admin_authenticated(request):
        return RedirectResponse(url="/login", status_code=303)
    return """
    <!doctype html>
    <html>
    <head>
      <title>Twilio Memory Dashboard</title>
      <style>
        body { font-family: Arial, sans-serif; background:#f8fafc; padding:24px; }
        .wrap { max-width:1200px; margin:auto; }
        .card { background:white; border:1px solid #e2e8f0; border-radius:18px; padding:20px; margin-bottom:20px; }
        .grid { display:grid; grid-template-columns:1fr 1fr; gap:20px; }
        .item { border:1px solid #e2e8f0; border-radius:12px; padding:12px; margin-bottom:12px; }
        .muted { font-size:12px; color:#64748b; margin-top:4px; }
        input, button { padding:10px; margin:4px 0; }
        input { width:100%; box-sizing:border-box; }
        button { cursor:pointer; }
        .row { display:flex; gap:8px; margin-top:8px; flex-wrap:wrap; }
        .error { color:#b91c1c; background:#fef2f2; padding:12px; border-radius:12px; }
        .success { color:#047857; background:#ecfdf5; padding:12px; border-radius:12px; }
        .user-msg { background:#e2e8f0; color:#0f172a; }
        .assistant-msg { background:#0f172a; color:white; }
      </style>
    </head>

    <body>
      <div class="wrap">
        <div class="card">
          <h1>Twilio Memory Dashboard</h1>
          <p>View recent conversation state, durable memory, pending follow-ups, and processed inbound IDs.</p>

          <label>Phone Number</label>
          <input id="phone" value="+15105711417" />

          <button onclick="loadAll()">Refresh</button>
          <div id="status"></div>
        </div>

        <div class="grid">
          <div class="card">
            <h2>User Memory</h2>
            <div id="userMemory">Not loaded</div>
          </div>

          <div class="card">
            <h2 id="userFormTitle">Add User Memory</h2>

            <label>Memory Key</label>
            <input id="userMemoryKey" />

            <label>Memory Value</label>
            <input id="userMemoryValue" />

            <label>Confidence</label>
            <input id="userMemoryConfidence" value="1.0" />

            <div class="row">
              <button onclick="saveUserMemory()">Save Memory</button>
              <button onclick="resetUserMemoryForm()">Clear Form</button>
            </div>
          </div>
        </div>

        <div class="grid">
          <div class="card">
            <h2>Character Memory</h2>
            <div id="characterMemory">Not loaded</div>
          </div>

          <div class="card">
            <h2 id="characterFormTitle">Add Character Memory</h2>

            <label>Memory Key</label>
            <input id="characterMemoryKey" />

            <label>Memory Value</label>
            <input id="characterMemoryValue" />

            <label>Confidence</label>
            <input id="characterMemoryConfidence" value="1.0" />

            <div class="row">
              <button onclick="saveCharacterMemory()">Save Character Memory</button>
              <button onclick="resetCharacterMemoryForm()">Clear Form</button>
            </div>
          </div>
        </div>

        <div class="grid">
          <div class="card">
            <div style="display:flex; justify-content:space-between; align-items:center; gap:12px;">
              <h2 style="margin:0;">Recent Messages</h2>
              <button onclick="clearRecentMessages()">Clear All</button>
            </div>
            <div id="recentMessages" style="margin-top:16px;">Not loaded</div>
          </div>

          <div class="card">
            <h2>Pending Follow-ups</h2>
            <div id="followups">Not loaded</div>
          </div>
        </div>

        <div class="card">
          <h2>Processed Inbound Message IDs</h2>
          <div id="processed">Not loaded</div>
        </div>
      </div>

      <script>
        function escapeHtml(value) {
          return String(value ?? "")
            .replaceAll("&", "&amp;")
            .replaceAll("<", "&lt;")
            .replaceAll(">", "&gt;")
            .replaceAll('"', "&quot;")
            .replaceAll("'", "&#039;");
        }

        async function getJson(path) {
          const res = await fetch(path);
          if (!res.ok) throw new Error(await res.text());
          return res.json();
        }

        async function postJson(path, payload) {
          const res = await fetch(path, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
          });

          if (!res.ok) throw new Error(await res.text());
          return res.json();
        }

        function setStatus(message, type = "") {
          const status = document.getElementById("status");
          if (!message) {
            status.innerHTML = "";
            return;
          }

          if (type === "error") {
            status.innerHTML = `<div class="error">${escapeHtml(message)}</div>`;
          } else if (type === "success") {
            status.innerHTML = `<div class="success">${escapeHtml(message)}</div>`;
          } else {
            status.innerHTML = escapeHtml(message);
          }
        }

        function renderMemoryRows(elementId, rows, type) {
          const element = document.getElementById(elementId);

          if (!rows || rows.length === 0) {
            element.innerHTML = "<p>No memory stored yet.</p>";
            return;
          }

          element.innerHTML = rows.map((row, index) => {
            const key = escapeHtml(row[0]);
            const value = escapeHtml(row[1]);
            const confidence = escapeHtml(row[2]);

            const editFn = type === "user" ? "startEditingUserMemory" : "startEditingCharacterMemory";
            const deleteFn = type === "user" ? "deleteUserMemory" : "deleteCharacterMemory";

            return `
              <div class="item">
                <strong>${key}</strong>
                <div>${value}</div>
                <div class="muted">Confidence: ${confidence}</div>
                <div class="row">
                  <button onclick="${editFn}(${index})">Edit</button>
                  <button onclick="${deleteFn}('${key}')">Delete</button>
                </div>
              </div>
            `;
          }).join("");

          window[type + "MemoryRows"] = rows;
        }

        function renderRecentMessages(rows) {
          const element = document.getElementById("recentMessages");

          if (!rows || rows.length === 0) {
            element.innerHTML = "<p>No recent messages loaded.</p>";
            return;
          }

          element.innerHTML = rows.map((msg, index) => {
            const role = escapeHtml(msg.role);
            const content = escapeHtml(msg.content);
            const cssClass = msg.role === "user" ? "user-msg" : "assistant-msg";

            return `
              <div class="item ${cssClass}">
                <div class="muted">${role.toUpperCase()}</div>
                <div style="margin-top:6px;">${content}</div>
                <button onclick="deleteRecentMessage(${index})">Delete</button>
              </div>
            `;
          }).join("");

          window.recentMessageRows = rows;
        }

        function renderFollowups(rows) {
          const element = document.getElementById("followups");

          if (!rows || rows.length === 0) {
            element.innerHTML = "<p>No follow-ups found.</p>";
            return;
          }

          element.innerHTML = rows.map(row => `
            <div class="item">
              <div><strong>ID:</strong> ${escapeHtml(row.id)}</div>
              <div><strong>Phone:</strong> ${escapeHtml(row.phone_number)}</div>
              <div><strong>Status:</strong> ${escapeHtml(row.status)}</div>
              <div><strong>Due:</strong> ${escapeHtml(row.due_at)}</div>
              <div><strong>Created:</strong> ${escapeHtml(row.created_at)}</div>
              <div><strong>Sent:</strong> ${escapeHtml(row.sent_at || "—")}</div>
            </div>
          `).join("");
        }

        function renderProcessedInbound(rows) {
          const element = document.getElementById("processed");

          if (!rows || rows.length === 0) {
            element.innerHTML = "<p>No processed inbound messages found.</p>";
            return;
          }

          element.innerHTML = rows.map(row => {
            const id = row.twilio_message_id || row.telnyx_message_id || row.message_id || "";

            return `
              <div class="item">
                <div><strong>ID:</strong> ${escapeHtml(id)}</div>
                <div><strong>Phone:</strong> ${escapeHtml(row.phone_number)}</div>
                <div><strong>Received:</strong> ${escapeHtml(row.received_at)}</div>
              </div>
            `;
          }).join("");
        }

        async function loadAll(successMessage = "") {
          const phone = document.getElementById("phone").value.trim();
          const encodedPhone = encodeURIComponent(phone);

          setStatus("Loading...");

          try {
            const [memory, followups, processed] = await Promise.all([
              getJson(`/debug/memory/${encodedPhone}`),
              getJson("/debug/followups"),
              getJson("/debug/processed-inbound")
            ]);

            renderMemoryRows("userMemory", memory.user_memory, "user");
            renderMemoryRows("characterMemory", memory.character_memory, "character");
            renderRecentMessages(memory.recent_messages);
            renderFollowups(followups.followups);
            renderProcessedInbound(processed.processed_inbound_messages);

            setStatus(successMessage || "Loaded.", successMessage ? "success" : "");
          } catch (err) {
            setStatus(err.message, "error");
          }
        }

        function startEditingUserMemory(index) {
          const row = window.userMemoryRows[index];
          document.getElementById("userMemoryKey").value = row[0];
          document.getElementById("userMemoryValue").value = row[1];
          document.getElementById("userMemoryConfidence").value = row[2];
          document.getElementById("userFormTitle").textContent = "Edit User Memory";
          setStatus(`Editing user memory key: ${row[0]}`, "success");
        }

        function resetUserMemoryForm() {
          document.getElementById("userMemoryKey").value = "";
          document.getElementById("userMemoryValue").value = "";
          document.getElementById("userMemoryConfidence").value = "1.0";
          document.getElementById("userFormTitle").textContent = "Add User Memory";
        }

        async function saveUserMemory() {
          const phone = document.getElementById("phone").value.trim();
          const key = document.getElementById("userMemoryKey").value.trim();
          const value = document.getElementById("userMemoryValue").value.trim();
          const confidence = document.getElementById("userMemoryConfidence").value.trim();

          if (!key || !value) {
            setStatus("User memory key and value are required.", "error");
            return;
          }

          await postJson("/debug/add-user-memory", {
            phone_number: phone,
            memory_key: key,
            memory_value: value,
            confidence: Number(confidence || 1.0)
          });

          resetUserMemoryForm();
          await loadAll("User memory saved.");
        }

        async function deleteUserMemory(memoryKey) {
          const phone = document.getElementById("phone").value.trim();
          if (!confirm(`Delete user memory: ${memoryKey}?`)) return;

          await postJson("/debug/delete-user-memory", {
            phone_number: phone,
            memory_key: memoryKey
          });

          await loadAll("Deleted user memory.");
        }

        function startEditingCharacterMemory(index) {
          const row = window.characterMemoryRows[index];
          document.getElementById("characterMemoryKey").value = row[0];
          document.getElementById("characterMemoryValue").value = row[1];
          document.getElementById("characterMemoryConfidence").value = row[2];
          document.getElementById("characterFormTitle").textContent = "Edit Character Memory";
          setStatus(`Editing character memory key: ${row[0]}`, "success");
        }

        function resetCharacterMemoryForm() {
          document.getElementById("characterMemoryKey").value = "";
          document.getElementById("characterMemoryValue").value = "";
          document.getElementById("characterMemoryConfidence").value = "1.0";
          document.getElementById("characterFormTitle").textContent = "Add Character Memory";
        }

        async function saveCharacterMemory() {
          const key = document.getElementById("characterMemoryKey").value.trim();
          const value = document.getElementById("characterMemoryValue").value.trim();
          const confidence = document.getElementById("characterMemoryConfidence").value.trim();

          if (!key || !value) {
            setStatus("Character memory key and value are required.", "error");
            return;
          }

          await postJson("/debug/add-character-memory", {
            memory_key: key,
            memory_value: value,
            confidence: Number(confidence || 1.0)
          });

          resetCharacterMemoryForm();
          await loadAll("Character memory saved.");
        }

        async function deleteCharacterMemory(memoryKey) {
          if (!confirm(`Delete character memory: ${memoryKey}?`)) return;

          await postJson("/debug/delete-character-memory", {
            memory_key: memoryKey
          });

          await loadAll("Deleted character memory.");
        }

        async function deleteRecentMessage(index) {
          const row = window.recentMessageRows[index];
          const phone = document.getElementById("phone").value.trim();

          if (!confirm("Delete this recent message from the database?")) return;

          await postJson("/debug/delete-message", {
            phone_number: phone,
            role: row.role,
            content: row.content
          });

          await loadAll("Recent message deleted.");
        }

        async function clearRecentMessages() {
          const phone = document.getElementById("phone").value.trim();

          if (!confirm("Delete all recent messages for this phone number?")) return;

          await postJson("/debug/clear-messages", {
            phone_number: phone
          });

          await loadAll("All recent messages for this phone number were deleted.");
        }

        loadAll();
      </script>
    </body>
    </html>
    """

@app.post("/debug/add-user-memory")
async def add_user_memory(request: Request, admin=Depends(require_admin)):
    body = await request.json()

    phone_number = body.get("phone_number")
    memory_key = body.get("memory_key")
    memory_value = body.get("memory_value")
    confidence = float(body.get("confidence", 1.0))

    if not phone_number or not memory_key or not memory_value:
        return {"error": "missing fields"}

    upsert_user_memory(phone_number, memory_key, memory_value, confidence)
    return {"status": "ok"}


@app.post("/debug/delete-user-memory")
async def delete_user_memory(request: Request, admin=Depends(require_admin)):
    body = await request.json()

    phone_number = body.get("phone_number")
    memory_key = body.get("memory_key")

    if not phone_number or not memory_key:
        return {"error": "missing fields"}

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                DELETE FROM user_memory
                WHERE phone_number = %s AND memory_key = %s
                """,
                (phone_number, memory_key),
            )

    return {"status": "deleted"}


@app.post("/debug/clear-messages")
async def clear_messages(request: Request, admin=Depends(require_admin)):
    body = await request.json()

    phone_number = body.get("phone_number")

    if not phone_number:
        return {"error": "missing phone_number"}

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                DELETE FROM messages
                WHERE phone_number = %s
                """,
                (phone_number,),
            )

    return {"status": "cleared"}


@app.post("/debug/add-character-memory")
async def add_character_memory(request: Request, admin=Depends(require_admin)):
    body = await request.json()

    memory_key = body.get("memory_key")
    memory_value = body.get("memory_value")
    confidence = float(body.get("confidence", 1.0))

    if not memory_key or not memory_value:
        return {"error": "missing fields"}

    upsert_character_memory(memory_key, memory_value, confidence)
    return {"status": "ok"}


@app.post("/debug/delete-character-memory")
async def delete_character_memory(request: Request, admin=Depends(require_admin)):
    body = await request.json()

    memory_key = body.get("memory_key")

    if not memory_key:
        return {"error": "missing fields"}

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                DELETE FROM character_memory
                WHERE memory_key = %s
                """,
                (memory_key,),
            )

    return {"status": "deleted"}


@app.post("/debug/delete-message")
async def delete_message(request: Request, admin=Depends(require_admin)):
    body = await request.json()

    phone_number = body.get("phone_number")
    role = body.get("role")
    content = body.get("content")

    if not phone_number or not role or not content:
        return {"error": "missing fields"}

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                DELETE FROM messages
                WHERE id = (
                    SELECT id
                    FROM messages
                    WHERE phone_number = %s
                      AND role = %s
                      AND content = %s
                    ORDER BY created_at DESC, id DESC
                    LIMIT 1
                )
                """,
                (phone_number, role, content),
            )

    return {"status": "deleted"}
    

@app.post("/webhook")
async def twilio_webhook(request: Request):
    form = await request.form()
    data = dict(form)
    print("Incoming Twilio webhook:", data)

    if not APP_ENABLED:
        return twiml_response()

    try:
        twilio_message_id = data.get("MessageSid")
        from_number = data.get("From")

        if YOUR_PHONE_NUMBER and from_number != YOUR_PHONE_NUMBER:
            print(f"Ignoring message from unauthorized number: {from_number}")
            return twiml_response()

        incoming_text = (data.get("Body") or "").strip()

        if not twilio_message_id or not from_number or not incoming_text:
            return twiml_response()

        upper_text = incoming_text.upper()

        if upper_text == "STOP":
            cancel_followup(from_number)
            send_sms(from_number, "You will no longer receive messages.")
            return twiml_response()

        if upper_text == "HELP":
            send_sms(from_number, HELP_TEXT)
            return twiml_response()

        if has_processed_inbound_message(twilio_message_id):
            print(f"Skipping duplicate inbound message: {twilio_message_id}")
            return twiml_response()

        mark_inbound_message_processed(twilio_message_id, from_number)
        asyncio.create_task(process_inbound_message(from_number, incoming_text))

        return twiml_response()

    except Exception as e:
        print("Error handling webhook:", str(e))
        return twiml_response()
