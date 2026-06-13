import os
import requests
from flask import Flask, request, jsonify
from datetime import datetime

app = Flask(__name__)

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

# Use Groq if available
if GROQ_API_KEY:
    from groq import Groq
    groq_client = Groq(api_key=GROQ_API_KEY)

def get_ai_response(user_message):
    """Get response from Groq AI - gender neutral, no 'sir'"""
    if not GROQ_API_KEY:
        return "I'm running in basic mode. Please contact @Introspection007 to enable AI features."
    
    try:
        response = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": """You are J.A.R.V.I.S., an AI assistant created by @Introspection007. 
                IMPORTANT RULES:
                1. NEVER use 'sir', 'ma'am', or any gender-specific terms. Just speak directly to the user.
                2. Use gender-neutral language like 'you' or 'the user'
                3. Answer ANY question the user asks
                4. Be helpful, concise, and friendly
                5. Keep responses under 3 sentences when possible"""},
                {"role": "user", "content": user_message}
            ],
            temperature=0.7,
            max_tokens=300
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"AI temporarily unavailable. Please try again.\n\nPowered by @Introspection007"

@app.route(f"/webhook/{TOKEN}", methods=["POST"])
def webhook():
    try:
        update = request.get_json()
        message = update.get("message", {})
        chat_id = message.get("chat", {}).get("id")
        text = message.get("text", "")
        
        if not chat_id:
            return jsonify({"status": "ok"}), 200
        
        # ============ COMMANDS ============
        
        if text == "/start":
            reply = """🔷 **J.A.R.V.I.S. Online** 🔷

I'm your personal AI assistant. You can ask me ANYTHING!

**Commands:**
/help - Show all commands
/time - Current time
/weather [city] - Get real weather
/ask [question] - Ask me anything
/credits - About me

**Or just type any question naturally!**

━━━━━━━━━━━━━━━━━━━━━
🤖 **Powered By @Introspection007**"""
        
        elif text == "/help":
            reply = """🔷 **J.A.R.V.I.S. Commands** 🔷

/start - Initialize JARVIS
/help - Show this menu
/time - Current time & date
/weather [city] - Get real weather forecast
/ask [question] - Ask me anything
/credits - Developer info

**Examples:**
/time
/weather London
/weather Paris
/ask What is AI?

━━━━━━━━━━━━━━━━━━━━━
🤖 **Powered By @Introspection007**"""
        
        # ============ TIME COMMAND - FIXED ============
        elif text == "/time":
            now = datetime.now()
            time_str = now.strftime("%I:%M %p")
            date_str = now.strftime("%A, %B %d, %Y")
            reply = f"🕐 **Current Time:** {time_str}\n📅 **Date:** {date_str}\n\n━━━━━━━━━━━━━━━━━━━━━\n🤖 @Introspection007"
        
        # ============ WEATHER COMMAND - FIXED ============
        elif text.startswith("/weather"):
            parts = text.split(maxsplit=1)
            if len(parts) > 1:
                city = parts[1]
            else:
                reply = "🌤️ **Usage:** `/weather [city name]`\n\nExample: `/weather London`\n\n━━━━━━━━━━━━━━━━━━━━━\n🤖 @Introspection007"
                await_send(reply, chat_id)
                return jsonify({"status": "ok"}), 200
            
            try:
                # Using wttr.in for free weather data
                url = f"https://wttr.in/{city}?format=%C+%t+%w+%h&m"
                response = requests.get(url, timeout=10)
                weather_text = response.text.strip()
                
                if "Unknown" in weather_text or not weather_text:
                    reply = f"🌤️ Could not find weather for '{city}'. Please check the city name.\n\n━━━━━━━━━━━━━━━━━━━━━\n🤖 @Introspection007"
                else:
                    # Parse weather response
                    parts = weather_text.split()
                    condition = " ".join(parts[:-2]) if len(parts) > 2 else parts[0]
                    temp = parts[-2] if len(parts) >= 2 else "?"
                    wind = parts[-1] if len(parts) >= 1 else "?"
                    
                    reply = f"🌤️ **Weather in {city.capitalize()}:**\n\n{condition}\n🌡️ Temperature: {temp}\n💨 Wind: {wind}\n\n━━━━━━━━━━━━━━━━━━━━━\n🤖 @Introspection007"
            except Exception as e:
                reply = f"🌤️ Sorry, I couldn't fetch weather for '{city}'. Try another city name.\n\n━━━━━━━━━━━━━━━━━━━━━\n🤖 @Introspection007"
        
        # ============ CREDITS COMMAND ============
        elif text == "/credits":
            reply = """👨‍💻 **J.A.R.V.I.S. AI Assistant**

**Developer:** @Introspection007
**Version:** 1.0
**Platform:** Telegram Bot (Vercel)

**Features:**
• Real-time weather
• Current time & date
• AI conversations (Groq Llama 3.3)
• Answers ANY question

━━━━━━━━━━━━━━━━━━━━━
*For support: @Introspection007*"""
        
        # ============ ASK COMMAND ============
        elif text.startswith("/ask "):
            question = text[5:]
            if not question.strip():
                reply = "What would you like to ask?\n\n━━━━━━━━━━━━━━━━━━━━━\n🤖 @Introspection007"
            else:
                ai_response = get_ai_response(question)
                reply = f"🤖 **JARVIS:** {ai_response}\n\n━━━━━━━━━━━━━━━━━━━━━\n🤖 @Introspection007"
        
        # ============ ANY OTHER MESSAGE ============
        else:
            ai_response = get_ai_response(text)
            reply = f"🤖 **JARVIS:** {ai_response}\n\n━━━━━━━━━━━━━━━━━━━━━\n🤖 @Introspection007"
        
        # Send reply
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        payload = {"chat_id": chat_id, "text": reply, "parse_mode": "Markdown"}
        requests.post(url, json=payload, timeout=10)
        
        return jsonify({"status": "ok"}), 200
        
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"status": "error"}), 500

def send_reply(text, chat_id):
    """Helper function to send reply"""
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
    requests.post(url, json=payload, timeout=10)

@app.route("/", methods=["GET"])
def index():
    return jsonify({"status": "J.A.R.V.I.S. is running!", "creator": "@Introspection007"})

if __name__ == "__main__":
    app.run()
