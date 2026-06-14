import os
import requests
import re
from flask import Flask, request
from datetime import datetime
from supabase import create_client, Client

app = Flask(__name__)

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
SAMBANOVA_API_KEY = os.environ.get("SAMBANOVA_API_KEY")

SUPABASE_URL = "https://lhtauaweqptozvydrrrt.supabase.co"
SUPABASE_ANON_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImxodGF1YXdlcXB0b3p2eWRycnJ0Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODE0NTQ2NzUsImV4cCI6MjA5NzAzMDY3NX0.HIRRkP5v3Lx-Ae5JfG0A0Yo0t4qMVfVnP0oxKRNTCK4"

try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
    print("✅ Supabase connected!")
except:
    supabase = None
    print("⚠️ Supabase not available")

# ============ SIMPLE MEMORY ============
def get_user_name(user_id):
    if not supabase:
        return None
    try:
        result = supabase.table("user_profile").select("preferred_name").eq("user_id", user_id).execute()
        return result.data[0].get("preferred_name") if result.data else None
    except:
        return None

def save_user_name(user_id, name):
    if not supabase:
        return
    try:
        existing = supabase.table("user_profile").select("*").eq("user_id", user_id).execute()
        if existing.data:
            supabase.table("user_profile").update({"preferred_name": name}).eq("user_id", user_id).execute()
        else:
            supabase.table("user_profile").insert({"user_id": user_id, "preferred_name": name}).execute()
        print(f"✅ Saved name: {name}")
    except:
        pass

def save_user(user_id, username, first_name):
    if not supabase:
        return
    try:
        existing = supabase.table("users").select("*").eq("user_id", user_id).execute()
        if not existing.data:
            supabase.table("users").insert({
                "user_id": user_id,
                "username": username,
                "first_name": first_name,
                "first_seen": datetime.now().isoformat()
            }).execute()
    except:
        pass

def clear_user_memory(user_id):
    if not supabase:
        return
    try:
        supabase.table("user_profile").delete().eq("user_id", user_id).execute()
    except:
        pass

def send_typing(chat_id):
    try:
        requests.post(f"https://api.telegram.org/bot{TOKEN}/sendChatAction", 
                     json={"chat_id": chat_id, "action": "typing"}, timeout=2)
    except:
        pass

def get_ai_response(question):
    """Simple AI response using SambaNova"""
    try:
        url = "https://api.sambanova.ai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {SAMBANOVA_API_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "Meta-Llama-3.1-8B-Instruct",
            "messages": [
                {"role": "system", "content": "You are J.A.R.V.I.S., a helpful AI assistant. Answer questions directly and concisely in 1-2 sentences. Never ask for the user's name."},
                {"role": "user", "content": question}
            ],
            "temperature": 0.7,
            "max_tokens": 150
        }
        response = requests.post(url, json=payload, headers=headers, timeout=5)
        if response.status_code == 200:
            return response.json()["choices"][0]["message"]["content"]
        return None
    except:
        return None

def get_weather(city):
    try:
        resp = requests.get(f"https://wttr.in/{city}?format=%C+%t&m", timeout=5)
        return resp.text.strip()
    except:
        return None

# ============ MAIN WEBHOOK ============
@app.route(f"/webhook/{TOKEN}", methods=["POST"])
def webhook():
    try:
        update = request.get_json()
        message = update.get("message", {})
        chat_id = message.get("chat", {}).get("id")
        user_id = message.get("from", {}).get("id")
        username = message.get("from", {}).get("username", "")
        first_name = message.get("from", {}).get("first_name", "")
        text = message.get("text", "")
        
        if not chat_id or not text:
            return "", 200
        
        send_typing(chat_id)
        save_user(user_id, username, first_name)
        
        # Check if user is sharing their name (optional, not required)
        msg_lower = text.lower().strip()
        name_match = re.search(r'(?:my name is|i am|i\'m|im)\s+([a-z][a-z\s\-]{2,20})$', msg_lower)
        if name_match and not get_user_name(user_id):
            name = name_match.group(1).strip().title()
            if len(name) >= 2:
                save_user_name(user_id, name)
        
        stored_name = get_user_name(user_id)
        
        # ============ COMMAND HANDLERS ============
        
        if text == "/start":
            reply = """🔷 **J.A.R.V.I.S.** 🔷

I'm your AI assistant. Ask me anything!

**Commands:**
/start - This menu
/help - All commands
/time - Current time
/weather [city] - Get weather
/whatiknow - What I remember
/forget - Reset memory

**Just type your question!**

━━━━━━━━━━━━━━━━━━━━━
🤖 **Powered By @Introspection007**"""
        
        elif text == "/help":
            reply = """🔷 **Commands** 🔷

/start - Menu
/help - This menu
/time - Current time
/weather [city] - Weather
/whatiknow - What I remember
/forget - Reset memory

Just type anything you want to ask!

━━━━━━━━━━━━━━━━━━━━━
🤖 **Powered By @Introspection007**"""
        
        elif text == "/time":
            now = datetime.now()
            reply = f"🕐 {now.strftime('%I:%M %p')}\n📅 {now.strftime('%A, %B %d, %Y')}\n\n━━━━━━━━━━━━━━━━━━━━━\n🤖 **Powered By @Introspection007**"
        
        elif text == "/whatiknow":
            if stored_name:
                reply = f"📝 I remember your name: **{stored_name}**\n\n━━━━━━━━━━━━━━━━━━━━━\n🤖 **Powered By @Introspection007**"
            else:
                reply = "📝 I don't have any stored info about you yet.\n\n━━━━━━━━━━━━━━━━━━━━━\n🤖 **Powered By @Introspection007**"
        
        elif text == "/forget":
            clear_user_memory(user_id)
            reply = "🗑️ Memory reset!\n\n━━━━━━━━━━━━━━━━━━━━━\n🤖 **Powered By @Introspection007**"
        
        elif text.startswith("/weather"):
            parts = text.split(maxsplit=1)
            city = parts[1] if len(parts) > 1 else "London"
            weather = get_weather(city)
            if weather:
                reply = f"🌤️ **{city.capitalize()}:** {weather}\n\n━━━━━━━━━━━━━━━━━━━━━\n🤖 **Powered By @Introspection007**"
            else:
                reply = f"🌤️ Couldn't get weather for {city}.\n\n━━━━━━━━━━━━━━━━━━━━━\n🤖 **Powered By @Introspection007**"
        
        else:
            # Answer ANY question directly
            ai_answer = get_ai_response(text)
            if ai_answer:
                reply = f"🤖 {ai_answer}\n\n━━━━━━━━━━━━━━━━━━━━━\n🤖 **Powered By @Introspection007**"
            else:
                # Fallback simple responses
                if "time" in msg_lower:
                    now = datetime.now()
                    reply = f"🕐 It's {now.strftime('%I:%M %p')}\n\n━━━━━━━━━━━━━━━━━━━━━\n🤖 **Powered By @Introspection007**"
                elif "weather" in msg_lower:
                    reply = f"🌤️ Use /weather [city] to get weather!\n\n━━━━━━━━━━━━━━━━━━━━━\n🤖 **Powered By @Introspection007**"
                elif "hello" in msg_lower or "hi" in msg_lower:
                    reply = f"Hello! How can I help?\n\n━━━━━━━━━━━━━━━━━━━━━\n🤖 **Powered By @Introspection007**"
                else:
                    reply = f"I'm here! What would you like to know?\n\n━━━━━━━━━━━━━━━━━━━━━\n🤖 **Powered By @Introspection007**"
        
        # Send response
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": chat_id, "text": reply, "parse_mode": "Markdown"}, timeout=5)
        
        return "", 200
        
    except Exception as e:
        print(f"Error: {e}")
        return "", 200

@app.route("/", methods=["GET"])
def index():
    return {"status": "J.A.R.V.I.S. is running!", "creator": "@Introspection007"}

if __name__ == "__main__":
    app.run()
