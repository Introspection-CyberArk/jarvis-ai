import os
import requests
from flask import Flask, request
from datetime import datetime

app = Flask(__name__)

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

def get_groq_response(user_message):
    try:
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "llama3-70b-8192",
            "messages": [
                {"role": "system", "content": "You are J.A.R.V.I.S., a helpful AI assistant created by @Introspection007. Be friendly and concise."},
                {"role": "user", "content": user_message}
            ],
            "temperature": 0.7,
            "max_tokens": 200
        }
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        
        if response.status_code == 200:
            return response.json()["choices"][0]["message"]["content"]
        return None
    except:
        return None

def get_weather(city):
    try:
        url = f"https://wttr.in/{city}?format=%C+%t&m"
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200 and "Unknown" not in resp.text:
            return resp.text.strip()
        return None
    except:
        return None

@app.route(f"/webhook/{TOKEN}", methods=["POST"])
def webhook():
    try:
        update = request.get_json()
        message = update.get("message", {})
        chat_id = message.get("chat", {}).get("id")
        text = message.get("text", "")
        
        if not chat_id or not text:
            return "", 200
        
        # Send typing indicator
        try:
            requests.post(f"https://api.telegram.org/bot{TOKEN}/sendChatAction", 
                         json={"chat_id": chat_id, "action": "typing"}, timeout=2)
        except:
            pass
        
        # Handle commands
        if text == "/start":
            reply = """🔷 **J.A.R.V.I.S. Online** 🔷

I'm your AI assistant powered by Groq!

**Commands:**
/start - Show menu
/help - All commands
/time - Current time
/weather [city] - Get weather

**Just type anything and I'll respond!**

━━━━━━━━━━━━━━━━━━━━━
🤖 **Powered By @Introspection007**"""
        
        elif text == "/help":
            reply = """🔷 **J.A.R.V.I.S. Commands** 🔷

/time - Current time
/weather [city] - Weather forecast
/start - Show menu

━━━━━━━━━━━━━━━━━━━━━
🤖 **Powered By @Introspection007**"""
        
        elif text == "/time":
            now = datetime.now()
            reply = f"🕐 **Time:** {now.strftime('%I:%M %p')}\n📅 **Date:** {now.strftime('%A, %B %d, %Y')}\n\n━━━━━━━━━━━━━━━━━━━━━\n🤖 **Powered By @Introspection007**"
        
        elif text.startswith("/weather"):
            parts = text.split(maxsplit=1)
            city = parts[1] if len(parts) > 1 else "London"
            weather = get_weather(city)
            if weather:
                reply = f"🌤️ **Weather in {city.capitalize()}:** {weather}\n\n━━━━━━━━━━━━━━━━━━━━━\n🤖 **Powered By @Introspection007**"
            else:
                reply = f"🌤️ Couldn't find weather for '{city}'.\n\n━━━━━━━━━━━━━━━━━━━━━\n🤖 **Powered By @Introspection007**"
        
        else:
            ai_response = get_groq_response(text)
            if ai_response:
                reply = f"🤖 {ai_response}\n\n━━━━━━━━━━━━━━━━━━━━━\n🤖 **Powered By @Introspection007**"
            else:
                reply = f"Sorry, I'm having trouble. Please try again.\n\n━━━━━━━━━━━━━━━━━━━━━\n🤖 **Powered By @Introspection007**"
        
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        payload = {"chat_id": chat_id, "text": reply, "parse_mode": "Markdown"}
        requests.post(url, json=payload, timeout=10)
        
        return "", 200
        
    except Exception as e:
        print(f"Error: {e}")
        return "", 200

@app.route("/", methods=["GET"])
def index():
    return {"status": "J.A.R.V.I.S. is running!", "creator": "@Introspection007"}

if __name__ == "__main__":
    app.run()
