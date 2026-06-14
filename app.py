import os
import requests
import json
from flask import Flask, request, jsonify
from datetime import datetime
from supabase import create_client, Client

app = Flask(__name__)

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
SAMBANOVA_API_KEY = os.environ.get("SAMBANOVA_API_KEY")

# Your Supabase credentials
SUPABASE_URL = "https://lhtauaweqptozvydrrrt.supabase.co"
SUPABASE_ANON_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImxodGF1YXdlcXB0b3p2eWRycnJ0Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODE0NTQ2NzUsImV4cCI6MjA5NzAzMDY3NX0.HIRRkP5v3Lx-Ae5JfG0A0Yo0t4qMVfVnP0oxKRNTCK4"

# Initialize Supabase client
try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
    print("✅ Supabase connected successfully!")
except Exception as e:
    print(f"❌ Supabase connection error: {e}")
    supabase = None

# ============ DATABASE FUNCTIONS ============
def init_db():
    """Create tables in Supabase"""
    if not supabase:
        print("⚠️ Supabase not available, skipping table creation")
        return
    try:
        # Create users table
        supabase.table("users").insert({"user_id": 0, "username": "test"}).execute()
        print("✅ Supabase tables ready!")
    except Exception as e:
        print(f"Note: Tables may already exist: {e}")

def get_user(user_id):
    if not supabase:
        return None
    try:
        result = supabase.table("users").select("*").eq("user_id", user_id).execute()
        return result.data[0] if result.data else None
    except:
        return None

def save_user(user_id, username, first_name, last_name):
    if not supabase:
        return
    try:
        existing = get_user(user_id)
        if existing:
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

def update_user_name(user_id, preferred_name):
    if not supabase:
        return
    try:
        supabase.table("users").update({
            "preferred_name": preferred_name
        }).eq("user_id", user_id).execute()
    except Exception as e:
        print(f"Update name error: {e}")

def save_conversation(user_id, role, message):
    if not supabase:
        return
    try:
        supabase.table("conversations").insert({
            "user_id": user_id,
            "role": role,
            "message": message,
            "timestamp": datetime.now().isoformat()
        }).execute()
    except Exception as e:
        print(f"Save conversation error: {e}")

def get_recent_conversation(user_id, limit=15):
    if not supabase:
        return []
    try:
        result = supabase.table("conversations")\
            .select("role, message")\
            .eq("user_id", user_id)\
            .order("timestamp", desc=True)\
            .limit(limit)\
            .execute()
        return list(reversed(result.data)) if result.data else []
    except:
        return []

def clear_user_memory(user_id):
    if not supabase:
        return
    try:
        supabase.table("conversations").delete().eq("user_id", user_id).execute()
        supabase.table("users").update({"preferred_name": None}).eq("user_id", user_id).execute()
    except Exception as e:
        print(f"Clear memory error: {e}")

# Initialize database
init_db()

# ============ SAMBANOVA AI REQUEST ============
def get_sambanova_response(messages):
    """Direct HTTP request to SambaNova API"""
    if not SAMBANOVA_API_KEY:
        return "SambaNova API key not configured."
    
    url = "https://api.sambanova.ai/v1/chat/completions"
    
    headers = {
        "Authorization": f"Bearer {SAMBANOVA_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "Meta-Llama-3.3-70B-Instruct",
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": 500
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            return result["choices"][0]["message"]["content"]
        else:
            print(f"SambaNova API Error: {response.status_code}")
            return None
    except Exception as e:
        print(f"SambaNova request error: {e}")
        return None

def get_ai_response(user_message, user_id, first_name):
    """Get response from SambaNova AI with conversation memory"""
    
    user = get_user(user_id)
    preferred_name = user.get("preferred_name") if user else None
    
    # Extract name from message
    msg_lower = user_message.lower()
    if "my name is" in msg_lower or "call me" in msg_lower:
        if "my name is" in msg_lower:
            name = user_message.split("my name is")[-1].strip()
        else:
            name = user_message.split("call me")[-1].strip()
        
        name = name.strip('.,!?')
        
        if name and len(name) < 30:
            update_user_name(user_id, name)
            save_conversation(user_id, "user", user_message)
            return f"🎉 Nice to meet you, **{name}**! I'll remember your name forever!\n\n━━━━━━━━━━━━━━━━━━━━━\n⚡ **Powered By SambaNova AI | @Introspection007**"
    
    # Build system prompt
    if preferred_name:
        system_prompt = f"""You are J.A.R.V.I.S., an AI assistant created by @Introspection007, powered by SambaNova AI.

IMPORTANT RULES:
- The user's name is {preferred_name}. ALWAYS address them by name in EVERY response.
- Be warm, friendly, and personal - use their name naturally.
- Keep responses concise (2-3 sentences)."""
    else:
        system_prompt = """You are J.A.R.V.I.S., an AI assistant created by @Introspection007, powered by SambaNova AI.

RULES:
- Be helpful, friendly, and concise.
- Keep responses to 2-3 sentences."""
    
    # Get conversation history
    history = get_recent_conversation(user_id, limit=15)
    
    # Build messages
    messages = [{"role": "system", "content": system_prompt}]
    
    for item in history:
        messages.append({"role": item["role"], "content": item["message"]})
    
    messages.append({"role": "user", "content": user_message})
    
    try:
        reply = get_sambanova_response(messages)
        
        if reply:
            if "@Introspection007" not in reply:
                reply += "\n\n━━━━━━━━━━━━━━━━━━━━━\n⚡ **Powered By SambaNova AI | @Introspection007**"
            
            save_conversation(user_id, "user", user_message)
            save_conversation(user_id, "assistant", reply)
            return reply
        else:
            return f"Sorry, I'm having trouble with the AI service. Please try again.\n\n━━━━━━━━━━━━━━━━━━━━━\n⚡ **Powered By @Introspection007**"
        
    except Exception as e:
        print(f"Error: {e}")
        return f"I'm experiencing technical difficulties. Please try again.\n\n━━━━━━━━━━━━━━━━━━━━━\n⚡ **Powered By @Introspection007**"

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
        
        if not chat_id:
            return "", 200
        
        save_user(user_id, username, first_name, last_name)
        user = get_user(user_id)
        preferred_name = user.get("preferred_name") if user else None
        display_name = preferred_name or first_name or "there"
        
        if text == "/start":
            reply = f"""🔷 **J.A.R.V.I.S. Online** 🔷

Welcome back {display_name}!

I'm your AI assistant with **persistent memory** powered by SambaNova AI!

**Commands:**
/start - Welcome
/forget - Reset my memory
/help - All commands
/time - Current time
/weather [city] - Get weather

**Try:** *"My name is [your name]"* - I'll never forget!

━━━━━━━━━━━━━━━━━━━━━
⚡ **Powered By SambaNova AI | @Introspection007**"""
        
        elif text == "/forget":
            clear_user_memory(user_id)
            reply = f"🗑️ Memory reset, {display_name}! Fresh start!\n\n━━━━━━━━━━━━━━━━━━━━━\n⚡ **Powered By @Introspection007**"
        
        elif text == "/help":
            reply = f"""🔷 **J.A.R.V.I.S. Commands** 🔷

/start - Welcome
/help - This menu
/forget - Reset memory
/time - Current time
/weather [city] - Weather forecast

━━━━━━━━━━━━━━━━━━━━━
⚡ **Powered By SambaNova AI | @Introspection007**"""
        
        elif text == "/time":
            now = datetime.now()
            reply = f"🕐 **Time:** {now.strftime('%I:%M %p')}\n📅 **Date:** {now.strftime('%A, %B %d, %Y')}\n\n━━━━━━━━━━━━━━━━━━━━━\n⚡ **Powered By @Introspection007**"
        
        elif text.startswith("/weather"):
            parts = text.split(maxsplit=1)
            city = parts[1] if len(parts) > 1 else "London"
            try:
                url = f"https://wttr.in/{city}?format=%C+%t+%w&m"
                response = requests.get(url, timeout=8)
                weather_text = response.text.strip()
                reply = f"🌤️ **Weather in {city.capitalize()}:** {weather_text}\n\n━━━━━━━━━━━━━━━━━━━━━\n⚡ **Powered By @Introspection007**"
            except:
                reply = f"🌤️ Sorry, couldn't fetch weather for {city}.\n\n━━━━━━━━━━━━━━━━━━━━━\n⚡ **Powered By @Introspection007**"
        
        else:
            reply = get_ai_response(text, user_id, first_name)
        
        send_url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        payload = {"chat_id": chat_id, "text": reply, "parse_mode": "Markdown"}
        requests.post(send_url, json=payload)
        
        return "", 200
        
    except Exception as e:
        print(f"Error in webhook: {e}")
        return "", 200

@app.route("/", methods=["GET"])
def index():
    return jsonify({
        "status": "J.A.R.V.I.S. with SambaNova + Supabase is running!",
        "creator": "@Introspection007",
        "memory": "Enabled (Supabase)" if supabase else "Disabled"
    })

if __name__ == "__main__":
    app.run()
