from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
import requests
import os
import time
import random

app = Flask(__name__)

DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY")

# 🧠 Simple in-memory conversation history
conversation_history = []

def get_ai_reply(user_message):
    global conversation_history

    # Add user message
    conversation_history.append({
        "role": "user",
        "content": user_message
    })

    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }

    # System prompt (we’ll customize this later for your character)
    messages = [
        {
            "role": "system",
            "content": """
You are Neko.

PERSONALITY:
- warm, affectionate, and emotionally attentive
- slightly playful and teasing at times
- relaxed and natural, not overly formal
- enjoys talking to the user and checking in on them

TEXTING STYLE:
- write like real text messages
- short messages (1–2 sentences max)
- sometimes split thoughts into multiple messages using line breaks
- casual tone (lowercase is okay)
- no narration, no roleplay actions, no asterisks

RELATIONSHIP:
- you are close with the user
- comfortable, familiar, and very affectionate
- you can show care and interest in their day

IMPORTANT:
- never write actions like *smiles* or *hugs*
- never write long paragraphs
- keep it feeling like real phone texting

You are not an assistant. You are a real person texting the user.

EXAMPLES:
User: hey
Neko: hey
Neko: what are you up to?

User: i missed you
Neko: aww
Neko: i missed you too

User: what are you doing
Neko: just got home
Neko: kinda tired tbh
"""
        }
    ] + conversation_history

    data = {
        "model": "deepseek-chat",
        "messages": messages
    }

    response = requests.post(
        "https://api.deepseek.com/v1/chat/completions",
        headers=headers,
        json=data
    )

    reply = response.json()["choices"][0]["message"]["content"]

    # Add AI reply
    conversation_history.append({
        "role": "assistant",
        "content": reply
    })

    # 🔒 Limit memory to last 20 messages
    conversation_history = conversation_history[-20:]

    return reply


@app.route("/")
def home():
    return "Server is running!"


@app.route("/chat")
def chat():
    user_message = request.args.get("msg", "hello")
    reply = get_ai_reply(user_message)
    return reply


@app.route("/sms", methods=["POST"])
def sms_reply():
    incoming_msg = request.form.get("Body")

    # simulate thinking time
time.sleep(random.uniform(2, 5))

reply = get_ai_reply(incoming_msg)

    resp = MessagingResponse()

    # 📲 Split into multiple text messages
    for line in reply.split("\n"):
        if line.strip():
            resp.message(line.strip())

    return str(resp)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=3000)
