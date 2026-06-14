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
    """Extract personal info from ANY message format"""
    msg_lower = message.lower()
    extracted = False
    
    # MORE ROBUST NAME EXTRACTION - works with any capitalization
    # Patterns: "my name is X", "I'm X", "call me X", "name is X", "this is X"
    name_patterns = [
        r'(?:my name is|my name\'s|name\'s|i am|i\'m|call me|this is|im)\s+([A-Za-z][A-Za-z\s]{1,30}?)(?:\.|!|\?|,|$)',
    ]
    
    for pattern in name_patterns:
        match = re.search(pattern, msg_lower)
        if match:
            name = match.group(1).strip()
            # Clean up the name
            name = re.sub(r'\s+', ' ', name)
            name = name.title()
            # Filter out common non-name phrases
            if len(name) < 2 or len(name) > 30:
                continue
            if name.lower() in ['a', 'an', 'the', 'yeah', 'no', 'ok', 'okay', 'well', 'so', 'then', 'like', 'just']:
                continue
            
            profile = get_user_profile(user_id)
            profile["preferred_name"] = name
            save_user_profile(user_id, profile)
            save_user_fact(user_id, "name", name, "User introduced themselves")
            extracted = True
            print(f"📝 Stored name: {name}")
            break
    
    # Age extraction
    age_match = re.search(r'i am (\d+)\s+years? old', msg_lower)
    if not age_match:
        age_match = re.search(r'(\d+)\s+years? old', msg_lower)
    if age_match:
        age = int(age_match.group(1))
        profile = get_user_profile(user_id)
        profile["age"] = age
        save_user_profile(user_id, profile)
        save_user_fact(user_id, "age", str(age), "User shared their age")
        extracted = True
        print(f"📝 Stored age: {age}")
    
    # Location extraction
    location_match = re.search(r'i (?:live|stay) (?:in|at)\s+([A-Za-z\s,]+?)(?:\.|!|\?|$)', msg_lower)
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
    
    # First, extract and store any information from the message
    extract_and_store_information(user_id, user_message)
    
    # Get ALL user data from database
    profile = get_user_profile(user_id)
    facts = get_user_facts(user_id)
    
    # Get the stored name (case insensitive check)
    preferred_name = profile.get("preferred_name")
    
    msg_lower = user_message.lower()
    
    # === DIRECT HANDLERS (No AI needed) ===
    
    # Handle "what's my name" - DIRECT RESPONSE from database
    if any(phrase in msg_lower for phrase in ["what's my name", "what is my name", "tell me my name", "whats my name"]):
        if preferred_name:
            return f"Your name is **{preferred_name}**! I never forget! 😊\n\n━━━━━━━━━━━━━━━━━━━━━\n🤖 **Powered By @Introspection007**"
        else:
            return f"I don't know your name yet. Just tell me *'I am [your name]'* or *'My name is [your name]'*\n\n━━━━━━━━━━━━━━━━━━━━━\n🤖 **Powered By @Introspection007**"
    
    # Handle "do you remember me" - DIRECT RESPONSE
    if any(phrase in msg_lower for phrase in ["do you remember me", "remember my name", "do you know me"]):
        if preferred_name:
            return f"Of course I remember you, **{preferred_name}**! We're having a conversation right now! 😊\n\n━━━━━━━━━━━━━━━━━━━━━\n🤖 **Powered By @Introspection007**"
        else:
            return f"I'd love to remember you! Please tell me your name by saying *'I am [your name]'*\n\n━━━━━━━━━━━━━━━━━━━━━\n🤖 **Powered By @Introspection007**"
    
    # Handle "what do you know about me"
    if "what do you know about me" in msg_lower:
        info = f"📝 **Here's what I remember:**\n\n"
        if profile.get("preferred_name"):
            info += f"👤 Name: {profile['preferred_name']}\n"
        if profile.get("age"):
            info += f"🎂 Age: {profile['age']}\n"
        if profile.get("location"):
            info += f"📍 Location: {profile['location']}\n"
        
        if facts:
            other_facts = []
            for key, value in facts.items():
                if key not in ['name', 'age', 'location']:
                    other_facts.append(f"• {key}: {value}")
            if other_facts:
                info += "\n📋 Other facts:\n" + "\n".join(other_facts[:5])
        
        if len(info) < 50:
            info += "I don't know much about you yet. Tell me about yourself!"
        
        info += "\n━━━━━━━━━━━━━━━━━━━━━\n🤖 **Powered By @Introspection007**"
        return info
    
    # If we have the user's name, don't ask for it again!
    if preferred_name and any(phrase in msg_lower for phrase in ["what's your name", "who are you"]):
        # User asking bot's name - that's fine
        pass
    elif preferred_name and ("name" not in msg_lower):
        # User knows we know their name - no need to ask
        pass
    
    # Build system prompt with user context for AI
    if preferred_name:
        system_prompt = f"""You are J.A.R.V.I.S., an AI assistant created by @Introspection007.

IMPORTANT - THE USER'S NAME IS {preferred_name}.
DO NOT ASK FOR THEIR NAME - YOU ALREADY KNOW IT.
Address them as {preferred_name} in your responses.

Rules:
- Be warm and friendly
- Keep responses concise (2-3 sentences)
- Use their name naturally"""
    else:
        system_prompt = """You are J.A.R.V.I.S., an AI assistant created by @Introspection007.

Rules:
- Be helpful and friendly
- Keep responses concise (2-3 sentences)
- You don't know the user's name yet - ask politely once if appropriate, but don't spam the question"""

    # Get conversation history
    history = get_recent_conversation(user_id, limit=10)
    
    # Build messages
    messages = [{"role": "system", "content": system_prompt}]
    
    for item in history[-10:]:
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
            error_msg = f"Sorry, I'm having trouble. Please try again.\n\n━━━━━━━━━━━━━━━━━━━━━\n🤖 **Powered By @Introspection007**"
            return error_msg
        
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
        
        # Command handlers
        if text == "/start":
            reply = """🔷 **J.A.R.V.I.S. Online** 🔷

I'm your personal AI assistant with memory!

**What I can do:**
• Remember your name and preferences
• Answer any questions
• Continue conversations

**Commands:**
/start - Show this menu
/help - All commands
/whatiknow - What I remember about you
/forget - Reset my memory
/time - Current time
/weather [city] - Get weather

**Try telling me:** *"I am [your name]"* or *"My name is [your name]"*

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
                other_facts = []
                for key, value in facts.items():
                    if key not in ['name', 'age', 'location']:
                        other_facts.append(f"• {key}: {value}")
                if other_facts:
                    info += "\n📋 Other facts:\n" + "\n".join(other_facts[:5])
            
            if len(info) < 50:
                info += "I don't know much about you yet. Tell me about yourself!"
            
            info += "\n━━━━━━━━━━━━━━━━━━━━━\n🤖 **Powered By @Introspection007**"
            reply = info
        
        elif text == "/forget":
            clear_user_memory(user_id)
            reply = f"🗑️ All memories about you have been erased. Starting fresh!\n\n━━━━━━━━━━━━━━━━━━━━━\n🤖 **Powered By @Introspection007**"
        
        elif text == "/help":
            reply = """🔷 **J.A.R.V.I.S. Commands** 🔷

/start - Show welcome menu
/help - Show this menu
/whatiknow - What I remember about you
/forget - Reset my memory
/time - Current time
/weather [city] - Weather forecast

**Memory Features:**
• "I am [name]" - I'll remember your name
• "I am [age] years old" - I'll remember your age
• "I live in [city]" - I'll remember your location

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
        print(f"Error in webhook: {e}")
        return "", 200

@app.route("/", methods=["GET"])
def index():
    return jsonify({
        "status": "J.A.R.V.I.S. is running!",
        "creator": "@Introspection007"
    })

if __name__ == "__main__":
    app.run()
