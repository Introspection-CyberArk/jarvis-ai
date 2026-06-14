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
except Exception as e:
    print(f"❌ Supabase error: {e}")
    supabase = None

# ============ DATABASE FUNCTIONS ============
def get_user_profile(user_id):
    if not supabase:
        return {}
    try:
        result = supabase.table("user_profile").select("*").eq("user_id", user_id).execute()
        return result.data[0] if result.data else {}
    except:
        return {}

def save_user_profile(user_id, data):
    if not supabase:
        return
    try:
        existing = get_user_profile(user_id)
        if existing:
            supabase.table("user_profile").update(data).eq("user_id", user_id).execute()
        else:
            data["user_id"] = user_id
            supabase.table("user_profile").insert(data).execute()
    except Exception as e:
        print(f"Save profile error: {e}")

def save_user_fact(user_id, fact_key, fact_value, context=""):
    if not supabase:
        return
    try:
        supabase.table("user_facts").insert({
            "user_id": user_id,
            "fact_key": fact_key,
            "fact_value": fact_value,
            "context": context,
            "created_at": datetime.now().isoformat()
        }).execute()
    except Exception as e:
        print(f"Save fact error: {e}")

def get_user_facts(user_id):
    if not supabase:
        return {}
    try:
        result = supabase.table("user_facts").select("*").eq("user_id", user_id).execute()
        facts = {}
        for item in result.data:
            facts[item["fact_key"]] = item["fact_value"]
        return facts
    except:
        return {}

def save_user(user_id, username, first_name, last_name):
    if not supabase:
        return
    try:
        existing = supabase.table("users").select("*").eq("user_id", user_id).execute()
        if existing.data:
            supabase.table("users").update({
                "username": username,
                "first_name": first_name,
                "last_name": last_name,
                "last_seen": datetime.now().isoformat()
            }).eq("user_id", user_id).execute()
        else:
            supabase.table("users").insert({
                "user_id": user_id,
                "username": username,
                "first_name": first_name,
                "last_name": last_name,
                "first_seen": datetime.now().isoformat(),
                "last_seen": datetime.now().isoformat()
            }).execute()
    except Exception as e:
        print(f"Save user error: {e}")

def save_conversation(user_id, role, message):
    if not supabase:
        return
    try:
        supabase.table("conversations").insert({
            "user_id": user_id,
            "role": role,
            "message": message[:500],
            "timestamp": datetime.now().isoformat()
        }).execute()
    except Exception as e:
        print(f"Save conversation error: {e}")

def clear_user_memory(user_id):
    if not supabase:
        return
    try:
        supabase.table("conversations").delete().eq("user_id", user_id).execute()
        supabase.table("user_profile").delete().eq("user_id", user_id).execute()
        supabase.table("user_facts").delete().eq("user_id", user_id).execute()
    except Exception as e:
        print(f"Clear memory error: {e}")

def get_stored_name(user_id):
    profile = get_user_profile(user_id)
    return profile.get("preferred_name")

def extract_and_store_information(user_id, message):
    """Extract personal info - FLEXIBLE pattern matching"""
    msg_lower = message.lower().strip()
    
    name_patterns = [
        r'^i am\s+([a-z][a-z\s\-]{1,30})$',
        r'^i\'m\s+([a-z][a-z\s\-]{1,30})$',
        r'^im\s+([a-z][a-z\s\-]{1,30})$',
        r'my name is\s+([a-z][a-z\s\-]{1,30})',
        r'name is\s+([a-z][a-z\s\-]{1,30})',
        r'call me\s+([a-z][a-z\s\-]{1,30})',
    ]
    
    for pattern in name_patterns:
        match = re.search(pattern, msg_lower)
        if match:
            raw_name = match.group(1).strip()
            name = raw_name.title()
            name = name.replace("Spider Man", "Spider-Man")
            
            invalid = ['a', 'an', 'the', 'yeah', 'no', 'ok', 'okay', 'well', 'so', 'then', 'like', 'just']
            if 2 <= len(name) <= 30 and name.lower() not in invalid:
                profile = get_user_profile(user_id)
                if profile.get("preferred_name") != name:
                    profile["preferred_name"] = name
                    save_user_profile(user_id, profile)
                    save_user_fact(user_id, "name", name, "User introduced themselves")
                    print(f"📝 Stored name: {name}")
                    return True
    return False

def send_typing(chat_id):
    try:
        requests.post(f"https://api.telegram.org/bot{TOKEN}/sendChatAction", 
                     json={"chat_id": chat_id, "action": "typing"}, timeout=2)
    except:
        pass

# ============ FLASK WEBHOOK ============
@app.route(f"/webhook/{TOKEN}", methods=["POST"])
def webhook():
    try:
        update = request.get_json()
        message = update.get("message", {})
        chat_id = message.get("chat", {}).get("id")
        user_id = message.get("from", {}).get("id")
        username = message.get("from", {}).get("username", "")
        first_name = message.get("from", {}).get("first_name", "")
        last_name = message.get("from", {}).get("last_name", "")
        text = message.get("text", "")
        
        if not chat_id or not text:
            return "", 200
        
        send_typing(chat_id)
        save_user(user_id, username, first_name, last_name)
        
        # Extract name FIRST
        extract_and_store_information(user_id, text)
        stored_name = get_stored_name(user_id)
        
        # ============ COMMANDS ============
        if text == "/start":
            reply = f"""🔷 **J.A.R.V.I.S. Online** 🔷

I'm your AI assistant with memory!

**Commands:**
/start - Menu
/help - All commands
/whatiknow - What I remember
/forget - Reset memory
/time - Current time
/weather [city] - Get weather

**Try:** *"I am Spiderman"*

━━━━━━━━━━━━━━━━━━━━━
🤖 **Powered By @Introspection007**"""
        
        elif text == "/whatiknow":
            profile = get_user_profile(user_id)
            info = "📝 **What I remember:**\n\n"
            if stored_name:
                info += f"👤 Name: {stored_name}\n"
            if profile.get("age"):
                info += f"🎂 Age: {profile['age']}\n"
            if profile.get("location"):
                info += f"📍 Location: {profile['location']}\n"
            if len(info) < 50:
                info += "Tell me about yourself!"
            info += "\n━━━━━━━━━━━━━━━━━━━━━\n🤖 **Powered By @Introspection007**"
            reply = info
        
        elif text == "/forget":
            clear_user_memory(user_id)
            reply = "🗑️ All memories erased. Fresh start!\n\n━━━━━━━━━━━━━━━━━━━━━\n🤖 **Powered By @Introspection007**"
        
        elif text == "/help":
            reply = """🔷 **Commands** 🔷

/start - Menu
/help - This menu
/whatiknow - What I remember
/forget - Reset memory
/time - Current time
/weather [city] - Weather

━━━━━━━━━━━━━━━━━━━━━
🤖 **Powered By @Introspection007**"""
        
        elif text == "/time":
            now = datetime.now()
            reply = f"🕐 {now.strftime('%I:%M %p')}\n📅 {now.strftime('%A, %B %d')}\n\n━━━━━━━━━━━━━━━━━━━━━\n🤖 **Powered By @Introspection007**"
        
        elif text.startswith("/weather"):
            parts = text.split(maxsplit=1)
            city = parts[1] if len(parts) > 1 else "London"
            try:
                resp = requests.get(f"https://wttr.in/{city}?format=%C+%t&m", timeout=5)
                reply = f"🌤️ **{city.capitalize()}:** {resp.text.strip()}\n\n━━━━━━━━━━━━━━━━━━━━━\n🤖 **Powered By @Introspection007**"
            except:
                reply = f"🌤️ Couldn't fetch weather for {city}.\n\n━━━━━━━━━━━━━━━━━━━━━\n🤖 **Powered By @Introspection007**"
        
        else:
            # Handle name-related questions instantly
            msg_lower = text.lower()
            
            if any(phrase in msg_lower for phrase in ["what's my name", "what is my name", "tell me my name"]):
                if stored_name:
                    reply = f"Your name is **{stored_name}**! 😊\n\n━━━━━━━━━━━━━━━━━━━━━\n🤖 **Powered By @Introspection007**"
                else:
                    reply = "I don't know your name yet. Tell me *'I am [your name]'*\n\n━━━━━━━━━━━━━━━━━━━━━\n🤖 **Powered By @Introspection007**"
            
            elif any(phrase in msg_lower for phrase in ["do you remember me", "remember my name"]):
                if stored_name:
                    reply = f"Of course I remember you, **{stored_name}**! 😊\n\n━━━━━━━━━━━━━━━━━━━━━\n🤖 **Powered By @Introspection007**"
                else:
                    reply = "I'd love to remember you! Tell me *'I am [your name]'*\n\n━━━━━━━━━━━━━━━━━━━━━\n🤖 **Powered By @Introspection007**"
            
            elif "i am" in msg_lower or "i'm" in msg_lower or "im " in msg_lower:
                # User is trying to tell their name
                if stored_name:
                    reply = f"I already know you're **{stored_name}**! How can I help?\n\n━━━━━━━━━━━━━━━━━━━━━\n🤖 **Powered By @Introspection007**"
                else:
                    reply = f"Nice to meet you! 😊\n\n━━━━━━━━━━━━━━━━━━━━━\n🤖 **Powered By @Introspection007**"
            
            elif msg_lower in ["hi", "hello", "hey"]:
                if stored_name:
                    reply = f"Hello **{stored_name}**! How can I help?\n\n━━━━━━━━━━━━━━━━━━━━━\n🤖 **Powered By @Introspection007**"
                else:
                    reply = f"Hello! Tell me *'I am [your name]'* to get started.\n\n━━━━━━━━━━━━━━━━━━━━━\n🤖 **Powered By @Introspection007**"
            
            else:
                # Simple AI response
                if stored_name:
                    reply = f"Hey **{stored_name}**! I'm here. What's on your mind?\n\n━━━━━━━━━━━━━━━━━━━━━\n🤖 **Powered By @Introspection007**"
                else:
                    reply = f"I'm listening! Tell me *'I am [your name]'* so I can address you properly.\n\n━━━━━━━━━━━━━━━━━━━━━\n🤖 **Powered By @Introspection007**"
        
        # Send response
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        payload = {"chat_id": chat_id, "text": reply, "parse_mode": "Markdown"}
        requests.post(url, json=payload, timeout=5)
        
        return "", 200
        
    except Exception as e:
        print(f"Error: {e}")
        return "", 200

@app.route("/", methods=["GET"])
def index():
    return {"status": "J.A.R.V.I.S. is running!", "creator": "@Introspection007"}

if __name__ == "__main__":
    app.run()
