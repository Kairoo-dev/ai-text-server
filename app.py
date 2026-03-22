from flask import Flask, request
import requests
import os

app = Flask(__name__)

DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY")

def get_ai_reply(user_message):
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }

    data = {
        "model": "deepseek-chat",
        "messages": [
            {
                "role": "system",
                "content": "You are a helpful assistant. Keep responses short."
            },
            {
                "role": "user",
                "content": user_message
            }
        ]
    }

    r = requests.post(
        "https://api.deepseek.com/v1/chat/completions",
        headers=headers,
        json=data
    )

    return r.json()["choices"][0]["message"]["content"]

@app.route("/")
def home():
    return "Server is running!"

@app.route("/chat")
def chat():
    user_message = request.args.get("msg", "hello")
    reply = get_ai_reply(user_message)
    return reply

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=3000)
