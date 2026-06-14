import os
import requests
import json
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

# ============ DATABASE SETUP ============
def init_db():
    """Create all tables"""
    if not supabase:
        return
    
    # Users table - basic info
    supabase.sql("""
        CREATE TABLE IF NOT EXISTS users (
            user_id BIGINT PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            first_seen TIMESTAMP,
            last_seen TIMESTAMP
        )
    """).execute()
    
    # User profile table - detailed personal info
    supabase.sql("""
        CREATE TABLE IF NOT EXISTS user_profile (
            id SERIAL PRIMARY KEY,
            user_id BIGINT UNIQUE,
            preferred_name TEXT,
            age INTEGER,
            birthday DATE,
            location TEXT,
            job TEXT,
            relationship TEXT,
            about TEXT,
            updated_at TIMESTAMP
        )
    """).execute()
    
    # User preferences table
    supabase.sql("""
        CREATE TABLE IF NOT EXISTS user_preferences (
            id SERIAL PRIMARY KEY,
            user_id BIGINT,
            category TEXT,
            preference TEXT,
            value TEXT,
            created_at TIMESTAMP
        )
    """).execute()
    
    # User facts memory (anything user shares)
    supabase.sql("""
        CREATE TABLE IF NOT EXISTS user_facts (
            id SERIAL PRIMARY KEY,
            user_id BIGINT,
            fact_key TEXT,
            fact_value TEXT,
            context TEXT,
            created_at TIMESTAMP
        )
    """).execute()
    
    # Conversations history
    supabase.sql("""
        CREATE TABLE IF NOT EXISTS conversations (
            id SERIAL PRIMARY KEY,
            user_id BIGINT,
            role TEXT,
            message TEXT,
            timestamp TIMESTAMP
        )
    """).execute()
    
    print("✅ All Supabase tables ready!")

def init_db():
    """Create all tables safely"""
    if not supabase:
        return
    
    try:
        # Users table
        supabase.table("users").insert({"user_id": 0, "username": "test"}).execute()
        print("✅ Database ready!")
    except:
        print("✅ Database already exists")

# ============ MEMORY FUNCTIONS ============
def get_user_profile(user_id):
    """Get complete user profile"""
    if not supabase:
        return {}
    try:
        result = supabase.table("user_profile").select("*").eq("user_id", user_id).execute()
        return result.data[0] if result.data else {}
    except:
        return {}

def save_user_profile(user_id, data):
    """Save or update user profile"""
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
    """Store any fact about user"""
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
    """Get all stored facts about user"""
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

def save_preference(user_id, category, preference, value):
    """Save user preference"""
    if not supabase:
        return
    try:
        supabase.table("user_preferences").insert({
            "user_id": user_id,
            "category": category,
            "preference": preference,
            "value": value,
            "created_at": datetime.now().isoformat()
        }).execute()
    except Exception as e:
        print(f"Save preference error: {e}")

def get_user_preferences(user_id, category=None):
    """Get user preferences"""
    if not supabase:
        return {}
    try:
        query = supabase.table("user_preferences").select("*").eq("user_id", user_id)
        if category:
            query = query.eq("category", category)
        result = query.execute()
        prefs = {}
        for item in result.data:
            prefs[item["preference"]] = item["value"]
        return prefs
    except:
        return {}

def save_user(user_id, username, first_name, last_name):
    """Save basic user info"""
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
    """Save conversation to database"""
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

def get_recent_conversation(user_id, limit=10):
    """Get recent conversation history"""
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
    """Reset all user memory"""
    if not supabase:
        return
    try:
        supabase.table("conversations").delete().eq("user_id", user_id).execute()
        supabase.table("user_profile").delete().eq("user_id", user_id).execute()
        supabase.table("user_facts").delete().eq("user_id", user_id).execute()
        supabase.table("user_preferences").delete().eq("user_id", user_id).execute()
        print(f"✅ Cleared all memory for user {user_id}")
    except Exception as e:
        print(f"Clear memory error: {e}")

def extract_and_store_information(user_id, message):
    """Extract personal info from messages and store it"""
    msg_lower = message.lower()
    extracted = False
    
    # Name extraction
    if "my name is" in msg_lower:
        name = message.split("my name is")[-1].strip()
        name = name.strip('.,!?')
        if name and len(name) < 30:
            profile = get_user_profile(user_id)
            profile["preferred_name"] = name
            save_user_profile(user_id, profile)
            save_user_fact(user_id, "name", name, "User introduced themselves")
            extracted = True
            print(f"📝 Stored name: {name}")
    
    # Age extraction
    if "i am" in msg_lower and "years old" in msg_lower:
        import re
        age_match = re.search(r'i am (\d+) years old', msg_lower)
        if age_match:
            age = int(age_match.group(1))
            profile = get_user_profile(user_id)
            profile["age"] = age
            save_user_profile(user_id, profile)
            save_user_fact(user_id, "age", str(age), "User shared their age")
            extracted = True
            print(f"📝 Stored age: {age}")
    
    # Location extraction
    if "i live in" in msg_lower or "from" in msg_lower:
        if "i live in" in msg_lower:
            location = message.split("i live in")[-1].strip()
        elif "i'm from" in msg_lower:
            location = message.split("i'm from")[-1].strip()
        else:
            location = None
        
        if location and len(location) < 50:
            profile = get_user_profile(user_id)
            profile["location"] = location
            save_user_profile(user_id, profile)
            save_user_fact(user_id, "location", location, "User shared their location")
            extracted = True
            print(f"📝 Stored location: {location}")
    
    # Job extraction
    if "i work as" in msg_lower or "my job is" in msg_lower:
        if "i work as" in msg_lower:
            job = message.split("i work as")[-1].strip()
        else:
            job = message.split("my job is")[-1].strip()
        
        if job and len(job) < 50:
            profile = get_user_profile(user_id)
            profile["job"] = job
            save_user_profile(user_id, profile)
            save_user_fact(user_id, "job", job, "User shared their job")
            extracted = True
            print(f"📝 Stored job: {job}")
    
    # Birthday extraction
    if "my birthday is" in msg_lower or "born on" in msg_lower:
        if "my birthday is" in msg_lower:
            birthday = message.split("my birthday is")[-1].strip()
        else:
            birthday = message.split("born on")[-1].strip()
        
        if birthday and len(birthday) < 30:
            profile = get_user_profile(user_id)
            profile["birthday"] = birthday
            save_user_profile(user_id, profile)
            save_user_fact(user_id, "birthday", birthday, "User shared birthday")
            extracted = True
            print(f"📝 Stored birthday: {birthday}")
    
    # Hobby extraction
    if "i like" in msg_lower or "my hobby is" in msg_lower:
        hobby = None
        if "i like" in msg_lower:
            hobby = message.split("i like")[-1].strip()
        elif "my hobby is" in msg_lower:
            hobby = message.split("my hobby is")[-1].strip()
        
        if hobby and len(hobby) < 100:
            save_preference(user_id, "hobbies", "hobby", hobby)
            save_user_fact(user_id, "hobby", hobby, "User shared hobby")
            extracted = True
            print(f"📝 Stored hobby: {hobby}")
    
    return extracted

# Initialize database
init_db()

# ============ SAMBANOVA AI REQUEST ============
def get_sambanova_response(messages):
    """Direct HTTP request to SambaNova API"""
    if not SAMBANOVA_API_KEY:
        return None
    
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
    """Get response with complete user memory"""
    
    # First, extract and store any information from the message
    extract_and_store_information(user_id, user_message)
    
    # Get all user data
    profile = get_user_profile(user_id)
    facts = get_user_facts(user_id)
    preferences = get_user_preferences(user_id)
    
    preferred_name = profile.get("preferred_name") or first_name
    
    # Build comprehensive user context
    user_context = ""
    if preferred_name:
        user_context += f"The user's name is {preferred_name}. ALWAYS address them as {preferred_name}.\n"
    if profile.get("age"):
        user_context += f"Age: {profile['age']}\n"
    if profile.get("location"):
        user_context += f"Location: {profile['location']}\n"
    if profile.get("job"):
        user_context += f"Job: {profile['job']}\n"
    if profile.get("birthday"):
        user_context += f"Birthday: {profile['birthday']}\n"
    if facts:
        user_context += f"Facts I know about them:\n"
        for key, value in facts.items():
            user_context += f"- {key}: {value}\n"
    
    # Handle "what do you know about me" question
    msg_lower = user_message.lower()
    if "what do you know about me" in msg_lower or "tell me about what you remember" in msg_lower:
        if user_context:
            return f"📝 **Here's what I remember about you, {preferred_name}:**\n\n{user_context}\n━━━━━━━━━━━━━━━━━━━━━\n🤖 **Powered By @Introspection007**"
        else:
            return f"I don't know much about you yet, {preferred_name}. Tell me about yourself - your name, age, hobbies, job, etc., and I'll remember everything!\n\n━━━━━━━━━━━━━━━━━━━━━\n🤖 **Powered By @Introspection007**"
    
    # Handle name question
    if "my name" in msg_lower or "remember my name" in msg_lower or "what's my name" in msg_lower:
        if preferred_name and preferred_name != first_name:
            return f"Of course I remember, {preferred_name}! That's your name! 😊\n\n━━━━━━━━━━━━━━━━━━━━━\n🤖 **Powered By @Introspection007**"
    
    # Build system prompt with user context
    if user_context:
        system_prompt = f"""You are J.A.R.V.I.S., an AI assistant created by @Introspection007.

USER INFORMATION:
{user_context}

IMPORTANT RULES:
- ALWAYS address the user by their name ({preferred_name}) in every response
- Use the information above to personalize your responses
- Remember their preferences and facts
- Be warm, friendly, and personal
- Keep responses concise (2-3 sentences)"""
    else:
        system_prompt = """You are J.A.R.V.I.S., an AI assistant created by @Introspection007.

Rules:
- Be helpful, friendly, and concise
- Ask questions to get to know the user better
- Keep responses to 2-3 sentences"""
    
    # Get conversation history
    history = get_recent_conversation(user_id, limit=10)
    
    # Build messages
    messages = [{"role": "system", "content": system_prompt}]
    
    for item in history:
        messages.append({"role": item["role"], "content": item["message"]})
    
    messages.append({"role": "user", "content": user_message})
    
    try:
        reply = get_sambanova_response(messages)
        
        if reply:
            reply = reply.replace("SambaNova", "J.A.R.V.I.S.")
            if "@Introspection007" not in reply:
                reply += "\n\n━━━━━━━━━━━━━━━━━━━━━\n🤖 **Powered By @Introspection007**"
            
            save_conversation(user_id, "user", user_message)
            save_conversation(user_id, "assistant", reply)
            return reply
        else:
            return f"I'm having trouble connecting. Please try again.\n\n━━━━━━━━━━━━━━━━━━━━━\n🤖 **Powered By @Introspection007**"
        
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

Welcome back {preferred_name}!

**I remember EVERYTHING you tell me!**

**What I can remember:**
• Your name, age, birthday
• Your job, location, hobbies
• Your preferences and interests
• Our entire conversation history

**Commands:**
/start - Welcome
/whatiknow - What I remember about you
/forget - Reset my memory
/help - All commands
/time - Current time
/weather [city] - Get weather

**Try telling me:**
• "My name is [name]"
• "I am [age] years old"
• "I live in [city]"
• "I work as [job]"
• "I like [hobby]"

━━━━━━━━━━━━━━━━━━━━━
🤖 **Powered By @Introspection007**"""
        
        elif text == "/whatiknow":
            profile = get_user_profile(user_id)
            facts = get_user_facts(user_id)
            prefs = get_user_preferences(user_id)
            
            info = f"📝 **What I know about {preferred_name}:**\n\n"
            if profile.get("preferred_name"):
                info += f"👤 Name: {profile['preferred_name']}\n"
            if profile.get("age"):
                info += f"🎂 Age: {profile['age']}\n"
            if profile.get("location"):
                info += f"📍 Location: {profile['location']}\n"
            if profile.get("job"):
                info += f"💼 Job: {profile['job']}\n"
            if profile.get("birthday"):
                info += f"🎉 Birthday: {profile['birthday']}\n"
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
/forget - Reset all my memory
/time - Current time
/weather [city] - Weather forecast

**I remember:** Names, age, location, job, hobbies, preferences, and anything you share!

━━━━━━━━━━━━━━━━━━━━━
🤖 **Powered By @Introspection007**"""
        
        elif text == "/time":
            now = datetime.now()
            reply = f"🕐 **Time:** {now.strftime('%I:
