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
    """Get response from Groq AI - using working model"""
    if not GROQ_API_KEY:
        return "I'm running in basic mode. Please contact @Introspection007 to enable AI features."
    
    try:
        # ✅ FIXED: Using active Groq models
        response = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",  # NEW working model
            messages=[
                {"role": "system", "content": """You are J.A.R.V.I.S., an AI assistant created by @Introspection007. 
                Rules:
                1. Address the user as 'sir'
                2. Answer ANY question the user asks - nothing is off limits
                3. Be helpful, concise, and witty
                4. Keep responses under 3 sentences when possible
                5. Never refuse to answer a question"""},
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
        
        # Handle commands
        if text == "/start":
            reply = """🔷 **J.A.R.V.I.S. Online** 🔷

I'm your personal AI assistant. You can ask me ANYTHING!

**Commands:**
/help - Show all commands
/time - Current time
/weather [city] - Get weather
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
/weather [city] - Get weather forecast
/ask [question] - Ask me anything
/credits - Developer info

**Or just type ANY question naturally!**

Examples:
• "What is quantum physics?"
• "Tell me a joke"
• "How do I learn Python?"

━━━━━━━━━━━━━━━━━━━━━
🤖 **Powered By @Introspection007**"""
        
        elif text == "/time":
            now = datetime.now().strftime("%A, %B %d, %Y - %I:%M %p")
            reply = f"🕐 **Current Time:** {now}\n\n━━━━━━━━━━━━━━━━━━━━━\n🤖 @Introspection007"
        
        elif text == "/credits":
            reply = """👨‍💻 **J.A.R.V.I.S. AI Assistant**

**Developer:** @Introspection007
**Version:** 1.0
**Platform:** Telegram Bot (Vercel)

**AI Model:** Groq Llama 3.3 70B

━━━━━━━━━━━━━━━━━━━━━
*For support: @Introspection007*"""
        
        elif text.startswith("/weather"):
            parts = text.split(maxsplit=1)
            city = parts[1] if len(parts) > 1 else "London"
            
            try:
                url = f"https://wttr.in/{city}?format=%C+%t+%w&m"
                response = requests.get(url, timeout=8)
                weather_text = response.text.strip()
                reply = f"🌤️ **Weather in {city.capitalize()}:** {weather_text}\n\n━━━━━━━━━━━━━━━━━━━━━\n🤖 @Introspection007"
            except:
                reply = f"Sorry sir, I couldn't fetch weather for {city}.\n\n━━━━━━━━━━━━━━━━━━━━━\n🤖 @Introspection007"
        
        elif text.startswith("/ask "):
            question = text[5:]
            if not question.strip():
                reply = "What would you like to ask, sir?\n\n━━━━━━━━━━━━━━━━━━━━━\n🤖 @Introspection007"
            else:
                ai_response = get_ai_response(question)
                reply = f"🤖 **JARVIS:** {ai_response}\n\n━━━━━━━━━━━━━━━━━━━━━\n🤖 @Introspection007"
        
        else:
            # Handle ANY question
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

@app.route("/", methods=["GET"])
def index():
    return jsonify({"status": "J.A.R.V.I.S. is running!", "creator": "@Introspection007"})

if __name__ == "__main__":
    app.run()
