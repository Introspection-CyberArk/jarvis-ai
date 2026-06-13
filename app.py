import os
import json
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

# Use Groq if available
if GROQ_API_KEY:
    from groq import Groq
    groq_client = Groq(api_key=GROQ_API_KEY)

def get_ai_response(user_message):
    """Get response from Groq AI (synchronous)"""
    if not GROQ_API_KEY:
        return "I'm running in basic mode. Please add GROQ_API_KEY to enable AI features.\n\nPowered by @Introspection007"
    
    try:
        response = groq_client.chat.completions.create(
            model="llama3-70b-8192",
            messages=[
                {"role": "system", "content": "You are J.A.R.V.I.S., an AI assistant created by @Introspection007. Be helpful, witty, and address the user as 'sir'."},
                {"role": "user", "content": user_message}
            ],
            temperature=0.7,
            max_tokens=500
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"AI Error: {str(e)}\n\nPowered by @Introspection007"

@app.route(f"/webhook/{TOKEN}", methods=["POST"])
def webhook():
    """Handle incoming Telegram updates (synchronous)"""
    try:
        update = request.get_json()
        
        # Extract message info
        message = update.get("message", {})
        chat_id = message.get("chat", {}).get("id")
        text = message.get("text", "")
        
        if not chat_id:
            return jsonify({"status": "ok"}), 200
        
        # Handle commands
        if text == "/start":
            reply = """🔷 **J.A.R.V.I.S. Online** 🔷

I'm your personal AI assistant.

• Send me **text messages** - I'll respond like JARVIS
• Use /help to see all commands

━━━━━━━━━━━━━━━━━━━━━
🤖 **Powered By @Introspection007**"""
        
        elif text == "/help":
            reply = """🔷 **J.A.R.V.I.S. Commands** 🔷

/start - Initialize JARVIS
/help - Show this menu
/status - System status
/time - Current time
/ask [question] - Ask anything

━━━━━━━━━━━━━━━━━━━━━
🤖 **Powered By @Introspection007**"""
        
        elif text == "/status":
            ai_status = "✅ Online (Groq AI)" if GROQ_API_KEY else "⚠️ Basic mode (Add GROQ_API_KEY)"
            reply = f"""⚙️ **System Status**

✅ Telegram API: Connected
{ai_status}
✅ Host: Vercel Serverless
👨‍💻 Creator: @Introspection007

*All systems nominal, sir.*"""
        
        elif text == "/time":
            from datetime import datetime
            now = datetime.now().strftime("%A, %B %d, %Y - %I:%M %p")
            reply = f"🕐 **Current Time:** {now}\n\n━━━━━━━━━━━━━━━━━━━━━\n🤖 @Introspection007"
        
        elif text == "/credits":
            reply = """👨‍💻 **J.A.R.V.I.S. AI Assistant**

**Developer:** @Introspection007
**Version:** 1.0
**Platform:** Telegram Bot (Vercel)

**Tech Stack:**
• Python 3.11
• Groq AI (Llama 3)
• Flask + Vercel

━━━━━━━━━━━━━━━━━━━━━
*For support: @Introspection007*"""
        
        elif text.startswith("/ask "):
            question = text[5:]
            reply = get_ai_response(question)
            reply += "\n\n━━━━━━━━━━━━━━━━━━━━━\n🤖 @Introspection007"
        
        else:
            # Normal text message - get AI response
            reply = get_ai_response(text)
            reply += "\n\n━━━━━━━━━━━━━━━━━━━━━\n🤖 @Introspection007"
        
        # Send reply
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        payload = {"chat_id": chat_id, "text": reply, "parse_mode": "Markdown"}
        requests.post(url, json=payload, timeout=10)
        
        return jsonify({"status": "ok"}), 200
        
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"status": "error", "error": str(e)}), 500

@app.route("/", methods=["GET"])
def index():
    return jsonify({"status": "J.A.R.V.I.S. is running!", "creator": "@Introspection007"})

if __name__ == "__main__":
    app.run()
