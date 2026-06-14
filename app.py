import os
import requests
import json
import re
from flask import Flask, request, jsonify
from datetime import datetime
from supabase import create_client, Client

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

def get_recent_conversation(user_id, limit=10):
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
    """Extract personal info from messages and store it"""
    extracted = False
    
    # Name extraction - FIXED PATTERN
    name_patterns = [
        r'my name is\s+([A-Za-z\s]+?)(?:\.|!|\?|$)',
        r"i'm\s+([A-Za-z\s]+?)(?:\.|!|\?|$)",
        r'call me\s+([A-Za-z\s]+?)(?:\.|!|\?|$)'
    ]
    
    for pattern in name_patterns:
        match = re.search(pattern, message.lower())
        if match:
            name = match.group(1).strip().title()
            if len(name) < 30 and len(name) > 1:
                profile = get_user_profile(user_id)
                profile["preferred_name"] = name
                save_user_profile(user_id, profile)
                save_user_fact(user_id, "name", name, "User introduced themselves")
                extracted = True
                print(f"📝 Stored name: {name}")
                break
    
    # Age extraction
    age_match = re.search(r'i am (\d+)\s+years? old', message.lower())
    if age_match:
        age = int(age_match.group(1))
        profile = get_user_profile(user_id)
        profile["age"] = age
        save_user_profile(user_id, profile)
        save_user_fact(user_id, "age", str(age), "User shared their age")
        extracted = True
        print(f"📝 Stored age: {age}")
    
    # Location extraction
    location_match = re.search(r'i live in\s+([A-Za-z\s,]+?)(?:\.|!|\?|$)', message.lower())
    if location_match:
        location = location_match.group(1).strip().title()
        profile = get_user_profile(user_id)
        profile["location"] = location
        save_user_profile(user_id, profile)
        save_user_fact(user_id, "location", location, "User shared their location")
        extracted = True
        print(f"📝 Stored location: {location}")
    
    return extracted

# ============ SAMBANOVA AI REQUEST ============
def get_ai_response(user_message, user_id):
    """Get response with complete user memory"""
    
    # First, extract and store any information
    extract_and_store_information(user_id, user_message)
    
    # Get all user data
    profile = get_user_profile(user_id)
    facts = get_user_facts(user_id)
    
    preferred_name = profile.get("preferred_name")
    
    # Handle "what's my name" - DIRECT RESPONSE (no AI)
    msg_lower = user_message.lower()
    if "what's my name" in msg_lower or "what is my name" in msg_lower:
        if preferred_name:
            return f"Your name is **{preferred_name}**! I remember everything you tell me, {preferred_name}! 😊\n\n━━━━━━━━━━━━━━━━━━━━━\n🤖 **Powered By @Introspection007**"
        else:
            return f"I don't know your name yet. Please tell me by saying *'My name is [your name]'*\n\n━━━━━━━━━━━━━━━━━━━━━\n🤖 **Powered By @Introspection007**"
    
    # Handle "do you remember me" or "remember my name"
    if "remember my name" in msg_lower or "do you remember" in msg_lower:
        if preferred_name:
            return f"Of course I remember you, {preferred_name}! Your name is {preferred_name} and I never forget!\n\n━━━━━━━━━━━━━━━━━━━━━\n🤖 **Powered By @Introspection007**"
        else:
            return f"I want to remember you! Please tell me your name by saying *'My name is [your name]'*\n\n━━━━━━━━━━━━━━━━━━━━━\n🤖 **Powered By @Introspection007**"
    
    # Build user context for AI
    user_context = ""
    if preferred_name:
        user_context += f"The user's name is {preferred_name}. You MUST call them {preferred_name}.\n"
    if profile.get("age"):
        user_context += f"Their age is {profile['age']}.\n"
    if profile.get("location"):
        user_context += f"They live in {profile['location']}.\n"
    
    # Build system prompt
    if user_context:
        system_prompt = f"""You are J.A.R.V.I.S., an AI assistant created by @Introspection007.

USER INFORMATION:
{user_context}

RULES:
- ALWAYS address the user by their name ({preferred_name}) in every response
- Be warm and friendly
- Keep responses concise (2-3 sentences)
- Never say you don't remember them"""
    else:
        system_prompt = """You are J.A.R.V.I.S., an AI assistant created by @Introspection007.

RULES:
- Be helpful and friendly
- Keep responses concise
- Ask for their name if you don't know it"""
    
    # Get conversation history
    history = get_recent_conversation(user_id, limit=5)
    
    # Build messages
    messages = [{"role": "system", "content": system_prompt}]
    
    for item in history:
        messages.append({"role": item["role"], "content": item["message"]})
    
    messages.append({"role": "user", "content": user_message})
    
    try:
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
        
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            reply = result["choices"][0]["message"]["content"]
            # Remove any SambaNova credit
            reply = re.sub(r'Powered By SambaNova AI \|?', '', reply)
            reply = re.sub(r'SambaNova', 'J.A.R.V.I.S.', reply)
            reply = reply.strip()
            if "@Introspection007" not in reply:
                reply += "\n\n━━━━━━━━━━━━━━━━━━━━━\n🤖 **Powered By @Introspection007**"
            
            save_conversation(user_id, "user", user_message)
            save_conversation(user_id, "assistant", reply)
            return reply
        else:
            return f"Sorry, I'm having trouble. Please try again.\n\n━━━━━━━━━━━━━━━━━━━━━\n🤖 **Powered By @Introspection007**"
        
    except Exception as e:
        print(f"Error: {e}")
        return f"Technical difficulties. Please try again.\n\n━━━━━━━━━━━━━━━━━━━━━\n🤖 **Powered By @Introspection007**"

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
        profile = get_user_profile(user_id)
        preferred_name = profile.get("preferred_name") or first_name or "there"
        
        if text == "/start":
            reply = f"""🔷 **J.A.R.V.I.S. Online** 🔷

Welcome{' back ' + preferred_name if preferred_name else '!'}

**I remember EVERYTHING you tell me!**

**Tell me things like:**
• "My name is Olly"
• "I am 25 years old"
• "I live in London"

**Commands:**
/start - Welcome
/whatiknow - What I remember about you
/forget - Reset my memory
/help - All commands
/time - Current time
/weather [city] - Get weather

━━━━━━━━━━━━━━━━━━━━━
🤖 **Powered By @Introspection007**"""
        
        elif text == "/whatiknow":
            profile = get_user_profile(user_id)
            facts = get_user_facts(user_id)
            
            info = f"📝 **What I remember about you:**\n\n"
            if profile.get("preferred_name"):
                info += f"👤 Name: {profile['preferred_name']}\n"
            if profile.get("age"):
                info += f"🎂 Age: {profile['age']}\n"
            if profile.get("location"):
                info += f"📍 Location: {profile['location']}\n"
            
            if facts:
                info += f"\n📋 Other facts:\n"
                for key, value in list(facts.items())[:5]:
                    info += f"• {key}: {value}\n"
            
            if len(info) < 50:
                info += "I don't know much about you yet. Tell me about yourself!"
            
            info += "\n━━━━━━━━━━━━━━━━━━━━━\n🤖 **Powered By @Introspection007**"
            reply = info
        
        elif text == "/forget":
            clear_user_memory(user_id)
            reply = f"🗑️ All memories about you have been erased, {preferred_name}. Starting fresh!\n\n━━━━━━━━━━━━━━━━━━━━━\n🤖 **Powered By @Introspection007**"
        
        elif text == "/help":
            reply = f"""🔷 **J.A.R.V.I.S. Commands** 🔷

/start - Welcome
/help - This menu
/whatiknow - What I remember about you
/forget - Reset my memory
/time - Current time
/weather [city] - Weather forecast

━━━━━━━━━━━━━━━━━━━━━
🤖 **Powered By @Introspection007**"""
        
        elif text == "/time":
            now = datetime.now()
            reply = f"🕐 **Time:** {now.strftime('%I:%M %p')}\n📅 **Date:** {now.strftime('%A, %B %d, %Y')}\n\n━━━━━━━━━━━━━━━━━━━━━\n🤖 **Powered By @Introspection007**"
        
        elif text.startswith("/weather"):
            parts = text.split(maxsplit=1)
            city = parts[1] if len(parts) > 1 else "London"
            try:
                url = f"https://wttr.in/{city}?format=%C+%t+%w&m"
                response = requests.get(url, timeout=8)
                weather_text = response.text.strip()
                reply = f"🌤️ **Weather in {city.capitalize()}:** {weather_text}\n\n━━━━━━━━━━━━━━━━━━━━━\n🤖 **Powered By @Introspection007**"
            except:
                reply = f"🌤️ Sorry, couldn't fetch weather for {city}.\n\n━━━━━━━━━━━━━━━━━━━━━\n🤖 **Powered By @Introspection007**"
        
        else:
            reply = get_ai_response(text, user_id)
        
        send_url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        payload = {"chat_id": chat_id, "text": reply, "parse_mode": "Markdown"}
        requests.post(send_url, json=payload)
        
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
