import os
import requests
from flask import Flask, request
from datetime import datetime
import random

app = Flask(__name__)

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
SAMBANOVA_API_KEY = os.environ.get("SAMBANOVA_API_KEY")

# ============ AI RESPONSES WITH FALLBACK ============

def get_groq_response(user_message):
    """Get response from Groq AI"""
    try:
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "llama-3.3-70b-versatile",
            "messages": [
                {"role": "system", "content": "You are J.A.R.V.I.S., a helpful AI assistant created by @Introspection007. Be friendly, warm, and answer questions directly. Keep responses short and natural."},
                {"role": "user", "content": user_message}
            ],
            "temperature": 0.7,
            "max_tokens": 150
        }
        response = requests.post(url, json=payload, headers=headers, timeout=8)
        
        if response.status_code == 200:
            return response.json()["choices"][0]["message"]["content"]
        return None
    except Exception as e:
        print(f"Groq error: {e}")
        return None

def get_sambanova_response(user_message):
    """Get response from SambaNova AI"""
    try:
        url = "https://api.sambanova.ai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {SAMBANOVA_API_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "Meta-Llama-3.1-8B-Instruct",
            "messages": [
                {"role": "system", "content": "You are J.A.R.V.I.S., a helpful AI assistant created by @Introspection007. Be friendly, warm, and answer questions directly. Keep responses short and natural."},
                {"role": "user", "content": user_message}
            ],
            "temperature": 0.7,
            "max_tokens": 150
        }
        response = requests.post(url, json=payload, headers=headers, timeout=8)
        
        if response.status_code == 200:
            return response.json()["choices"][0]["message"]["content"]
        return None
    except Exception as e:
        print(f"SambaNova error: {e}")
        return None

def get_ai_response(user_message):
    """Try Groq first, then SambaNova as fallback"""
    
    # Try Groq first
    if GROQ_API_KEY:
        response = get_groq_response(user_message)
        if response:
            return response
    
    # Fallback to SambaNova
    if SAMBANOVA_API_KEY:
        response = get_sambanova_response(user_message)
        if response:
            return response
    
    # Ultimate fallback
    return get_fallback_response(user_message)

def get_fallback_response(user_message):
    """Local fallback responses when both AIs fail"""
    msg = user_message.lower()
    
    if "time" in msg:
        now = datetime.now()
        return f"It's {now.strftime('%I:%M %p')} on {now.strftime('%A, %B %d')}"
    
    if "hello" in msg or "hi" in msg or "hey" in msg:
        return "Hello! How can I help you today?"
    
    if "how are you" in msg:
        return "I'm doing great! Ready to help you."
    
    if "your name" in msg or "who are you" in msg:
        return "I'm J.A.R.V.I.S., your personal AI assistant."
    
    if "joke" in msg:
        jokes = [
            "Why don't scientists trust atoms? Because they make up everything!",
            "What do you call a fake noodle? An impasta!",
            "Why did the scarecrow win an award? He was outstanding in his field!"
        ]
        return random.choice(jokes)
    
    return "I'm here to help! What would you like to know?"

def get_weather(city):
    try:
        url = f"https://wttr.in/{city}?format=%C+%t&m"
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200 and "Unknown" not in resp.text:
            return resp.text.strip()
        return None
    except:
        return None

# ============ WEBHOOK ============
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

I'm your personal AI assistant!

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

**You can also just ask me anything!**

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
                reply = f"🌤️ Couldn't find weather for '{city}'. Try another city.\n\n━━━━━━━━━━━━━━━━━━━━━\n🤖 **Powered By @Introspection007**"
        
        else:
            # Get AI response
            ai_response = get_ai_response(text)
            reply = f"🤖 {ai_response}\n\n━━━━━━━━━━━━━━━━━━━━━\n🤖 **Powered By @Introspection007**"
        
        # Send response
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        payload = {"chat_id": chat_id, "text": reply, "parse_mode": "Markdown"}
        requests.post(url, json=payload, timeout=10)
        
        return "", 200
        
    except Exception as e:
        print(f"Error: {e}")
        return "", 200

@app.route("/", methods=["GET"])
def index():
    return {
        "status": "J.A.R.V.I.S. is running!",
        "creator": "@Introspection007"
    }

if __name__ == "__main__":
    app.run()
