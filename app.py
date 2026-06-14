import os
import requests
import json
import re
from flask import Flask, request, jsonify
from datetime import datetime
from supabase import create_client, Client
import asyncio
from functools import lru_cache
import time

app = Flask(__name__)

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
SAMBANOVA_API_KEY = os.environ.get("SAMBANOVA_API_KEY")

# Supabase credentials
SUPABASE_URL = "https://lhtauaweqptozvydrrrt.supabase.co"
SUPABASE_ANON_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImxodGF1YXdlcXB0b3p2eWRycnJ0Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODE0NTQ2NzUsImV4cCI6MjA5NzAzMDY3NX0.HIRRkP5v3Lx-Ae5JfG0A0Yo0t4qMVfVnP0oxKRNTCK4"

# Initialize Supabase
try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
    print("✅ Supabase connected!")
except Exception as e:
    print(f"❌ Supabase error: {e}")
    supabase = None

# Simple cache for recent responses (speeds up repeated questions)
response_cache = {}
CACHE_DURATION = 300  # 5 minutes

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
        print(f"✅ Profile saved for user {user_id}")
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
        print(f"✅ Saved fact: {fact_key} = {fact_value}")
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
            "message": message[:1000],
            "timestamp": datetime.now().isoformat()
        }).execute()
    except Exception as e:
        print(f"Save conversation error: {e}")

def get_recent_conversation(user_id, limit=5):
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
        supabase.table("user_profile").delete().eq("user_id", user_id).execute()
        supabase.table("user_facts").delete().eq("user_id", user_id).execute()
        print(f"✅ Cleared all memory for user {user_id}")
    except Exception as e:
        print(f"Clear memory error: {e}")

def extract_and_store_information(user_id, message):
    """Extract personal info from ANY message format"""
    msg_lower = message.lower()
    extracted = False
    
    # Name extraction
    name_patterns = [
        r'(?:my name is|my name\'s|name\'s|i am|i\'m|call me|this is|im)\s+([A-Za-z][A-Za-z\s\-]{1,30}?)(?:\.|!|\?|,|$)',
    ]
    
    for pattern in name_patterns:
        match = re.search(pattern, msg_lower)
        if match:
            name = match.group(1).strip()
            name = re.sub(r'\s+', ' ', name)
            name = name.title()
            name = name.replace("Spider Man", "Spider-Man")
            
            skip_words = ['a', 'an', 'the', 'yeah', 'no', 'ok', 'okay', 'well', 'so', 'then', 'like', 'just']
            if len(name) >= 2 and len(name) <= 30 and name.lower() not in skip_words:
                profile = get_user_profile(user_id)
                if profile.get("preferred_name") != name:
                    profile["preferred_name"] = name
                    save_user_profile(user_id, profile)
                    save_user_fact(user_id, "name", name, "User introduced themselves")
                    extracted = True
                    print(f"📝 Stored name: {name}")
                break
    return extracted

def get_stored_name(user_id):
    """Helper to get stored name from database"""
    profile = get_user_profile(user_id)
    return profile.get("preferred_name")

def send_typing_indicator(chat_id):
    """Send typing indicator to make bot feel faster"""
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/sendChatAction"
        requests.post(url, json={"chat_id": chat_id, "action": "typing"}, timeout=3)
    except:
        pass

# ============ FAST RESPONSES (No AI needed) ============
def get_fast_response(user_message, stored_name):
    """Check for quick responses that don't need AI"""
    msg_lower = user_message.lower()
    
    # Time command - instant
    if "/time" in msg_lower:
        now = datetime.now()
        return f"🕐 **Time:** {now.strftime('%I:%M %p')}\n📅 **Date:** {now.strftime('%A, %B %d, %Y')}"
    
    # Name questions - instant
    if any(phrase in msg_lower for phrase in ["what's my name", "what is my name", "tell me my name", "whats my name"]):
        if stored_name:
            return f"Your name is **{stored_name}**! 😊"
        else:
            return "I don't know your name yet. Tell me *'I am [your name]'*"
    
    # Remember me questions - instant
    if any(phrase in msg_lower for phrase in ["do you remember me", "remember my name", "do you know my name"]):
        if stored_name:
            return f"Of course I remember you, **{stored_name}**! I never forget! 😊"
        else:
            return "I'd love to remember you! Tell me your name by saying *'I am [your name]'*"
    
    # Greetings - instant
    if msg_lower in ["hi", "hello", "hey", "yo"]:
        if stored_name:
            return f"Hello **{stored_name}**! How can I help you today?"
        return "Hello! How can I help you today?"
    
    return None  # Need AI response

# ============ SAMBANOVA AI REQUEST (with timeout) ============
def get_ai_response_fast(user_message, user_id, stored_name):
    """Get AI response with timeout fallback"""
    
    # Build minimal system prompt
    if stored_name:
        system_prompt = f"""You are J.A.R.V.I.S., AI assistant. User's name is {stored_name}. Address them as {stored_name}. Be concise (1-2 sentences)."""
    else:
        system_prompt = "You are J.A.R.V.I.S., AI assistant. Be helpful and very concise (1-2 sentences)."

    # Get only last 3 messages for context (faster)
    history = get_recent_conversation(user_id, limit=3)
    
    messages = [{"role": "system", "content": system_prompt}]
    for item in history:
        messages.append({"role": item["role"], "content": item["message"][:200]})
    messages.append({"role": "user", "content": user_message[:200]})
    
    try:
        url = "https://api.sambanova.ai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {SAMBANOVA_API_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "Meta-Llama-3.1-8B-Instruct",  # FASTER model
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 150,  # Shorter responses = faster
            "stream": False
        }
        
        # 8 second timeout
        response = requests.post(url, json=payload, headers=headers, timeout=8)
        
        if response.status_code == 200:
            result = response.json()
            reply = result["choices"][0]["message"]["content"]
            reply = re.sub(r'Powered By SambaNova AI \|?', '', reply)
            reply = re.sub(r'SambaNova', 'J.A.R.V.I.S.', reply)
            reply = reply.strip()
            return reply
        else:
            return None
        
    except requests.Timeout:
        print("AI timeout - using fallback")
        return None
    except Exception as e:
        print(f"AI error: {e}")
        return None

# ============ FLASK WEBHOOK ============
@app.route(f"/webhook/{TOKEN}", methods=["POST"])
def webhook():
    try:
        start_time = time.time()
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
        
        # Send typing indicator immediately
        send_typing_indicator(chat_id)
        
        save_user(user_id, username, first_name, last_name)
        extract_and_store_information(user_id, text)
        stored_name = get_stored_name(user_id)
        
        # ============ COMMAND HANDLERS ============
        if text == "/start":
            reply = """🔷 **J.A.R.V.I.S. Online** 🔷

I'm your personal AI assistant with memory!

**Commands:**
/start - Show menu
/help - All commands
/whatiknow - What I remember
/forget - Reset memory
/time - Current time
/weather [city] - Get weather

**Try:** *"I am [your name]"*

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
                url = f"https://wttr.in/{city}?format=%C+%t&m"
                response = requests.get(url, timeout=5)
                weather_text = response.text.strip()
                reply = f"🌤️ **{city.capitalize()}:** {weather_text}\n\n━━━━━━━━━━━━━━━━━━━━━\n🤖 **Powered By @Introspection007**"
            except:
                reply = f"🌤️ Couldn't fetch weather for {city}.\n\n━━━━━━━━━━━━━━━━━━━━━\n🤖 **Powered By @Introspection007**"
        
        else:
            # First, try fast response (no AI)
            fast_reply = get_fast_response(text, stored_name)
            
            if fast_reply:
                reply = fast_reply + "\n\n━━━━━━━━━━━━━━━━━━━━━\n🤖 **Powered By @Introspection007**"
            else:
                # Try AI with timeout
                ai_reply = get_ai_response_fast(text, user_id, stored_name)
                
                if ai_reply:
                    reply = ai_reply
                    if "@Introspection007" not in reply:
                        reply += "\n\n━━━━━━━━━━━━━━━━━━━━━\n🤖 **Powered By @Introspection007**"
                    save_conversation(user_id, "user", text)
                    save_conversation(user_id, "assistant", reply)
                else:
                    # Fallback response
                    if stored_name:
                        reply = f"I'm processing your request, {stored_name}. Please try again in a moment.\n\n━━━━━━━━━━━━━━━━━━━━━\n🤖 **Powered By @Introspection007**"
                    else:
                        reply = f"I'm a bit busy right now. Please try again in a moment.\n\n━━━━━━━━━━━━━━━━━━━━━\n🤖 **Powered By @Introspection007**"
        
        # Send response
        send_url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        payload = {"chat_id": chat_id, "text": reply, "parse_mode": "Markdown"}
        requests.post(send_url, json=payload, timeout=5)
        
        elapsed = time.time() - start_time
        print(f"⏱️ Response time: {elapsed:.2f}s")
        
        return "", 200
        
    except Exception as e:
        print(f"Error: {e}")
        return "", 200

@app.route("/", methods=["GET"])
def index():
    return jsonify({
        "status": "J.A.R.V.I.S. is running!",
        "creator": "@Introspection007"
    })

if __name__ == "__main__":
    app.run()
