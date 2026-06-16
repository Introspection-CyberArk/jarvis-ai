import os
import requests
import json
import re
from flask import Flask, request
from datetime import datetime, timedelta
import pytz
from timezonefinder import TimezoneFinder
import random
from supabase import create_client, Client

app = Flask(__name__)

# ============ ENVIRONMENT VARIABLES ============
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
OPENWEATHER_API_KEY = os.environ.get("OPENWEATHER_API_KEY")
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

# ============ SUPABASE INIT ============
try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    print("✅ Supabase connected!")
except Exception as e:
    print(f"❌ Supabase error: {e}")
    supabase = None

tf = TimezoneFinder()

# ============ DATABASE FUNCTIONS ============
def init_tables():
    if not supabase:
        return
    try:
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
        supabase.sql("""
            CREATE TABLE IF NOT EXISTS user_profile (
                id SERIAL PRIMARY KEY,
                user_id BIGINT UNIQUE,
                preferred_name TEXT,
                age INTEGER,
                location TEXT,
                updated_at TIMESTAMP
            )
        """).execute()
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
        supabase.sql("""
            CREATE TABLE IF NOT EXISTS conversations (
                id SERIAL PRIMARY KEY,
                user_id BIGINT,
                role TEXT,
                message TEXT,
                timestamp TIMESTAMP
            )
        """).execute()
        print("✅ All tables ready!")
    except Exception as e:
        print(f"Table creation error: {e}")

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

def get_recent_messages(user_id, limit=15):
    if not supabase:
        return []
    try:
        result = supabase.table("conversations")\
            .select("role, message")\
            .eq("user_id", user_id)\
            .order("timestamp", desc=False)\
            .limit(limit)\
            .execute()
        history = []
        for row in result.data:
            history.append({"role": row["role"], "content": row["message"]})
        return history
    except:
        return []

def get_user_name(user_id):
    """Get stored name - ALWAYS check database"""
    profile = get_user_profile(user_id)
    name = profile.get("preferred_name")
    if name:
        print(f"📌 Retrieved name: {name} for user {user_id}")
    else:
        print(f"📌 No name found for user {user_id}")
    return name

def save_user_name(user_id, name):
    """Save user's preferred name"""
    profile = get_user_profile(user_id)
    profile["preferred_name"] = name
    save_user_profile(user_id, profile)
    print(f"✅ Saved name: {name} for user {user_id}")

def clear_user_memory(user_id):
    if not supabase:
        return
    try:
        supabase.table("conversations").delete().eq("user_id", user_id).execute()
        supabase.table("user_profile").delete().eq("user_id", user_id).execute()
        supabase.table("user_facts").delete().eq("user_id", user_id).execute()
        print(f"🗑️ Cleared memory for user {user_id}")
    except:
        pass

# ============ AI RESPONSE ============
def get_ai_response(user_message, user_id):
    """Get response from OpenRouter AI with full conversation memory"""
    
    if not OPENROUTER_API_KEY:
        print("No OpenRouter API key!")
        return None
    
    try:
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://t.me/Jarvs_Ai_bot",
            "X-Title": "J.A.R.V.I.S. Bot"
        }
        
        user_name = get_user_name(user_id)
        
        system_prompt = """You are J.A.R.V.I.S., a helpful AI assistant created by @Introspection007.
Be friendly, conversational, and answer questions naturally.
Keep responses concise but helpful (1-3 sentences)."""
        
        if user_name:
            system_prompt += f" The user's name is {user_name}. Address them by name occasionally."

        history = get_recent_messages(user_id, limit=15)
        
        messages = [{"role": "system", "content": system_prompt}]
        for msg in history:
            messages.append({"role": msg["role"], "content": msg["content"]})
        messages.append({"role": "user", "content": user_message})
        
        print(f"📨 Sending {len(messages)} messages to AI...")

        payload = {
            "model": "qwen/qwen3-32b:free",
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 250
        }
        
        response = requests.post(url, json=payload, headers=headers, timeout=8)
        
        print(f"📥 OpenRouter response: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            reply = result["choices"][0]["message"]["content"]
            save_conversation(user_id, "user", user_message)
            save_conversation(user_id, "assistant", reply)
            return reply
        else:
            print(f"❌ OpenRouter error: {response.status_code}")
            return None
            
    except requests.exceptions.Timeout:
        print("⏰ OpenRouter timeout")
        return None
    except Exception as e:
        print(f"❌ AI error: {e}")
        return None

# ============ COMMAND FUNCTIONS ============
def get_weather(city):
    if not OPENWEATHER_API_KEY:
        return None
    try:
        url = f"https://api.openweathermap.org/data/2.5/weather?q={city}&appid={OPENWEATHER_API_KEY}&units=metric"
        response = requests.get(url, timeout=6)
        if response.status_code == 200:
            data = response.json()
            return {
                "city": data["name"],
                "temp": round(data["main"]["temp"]),
                "feels_like": round(data["main"]["feels_like"]),
                "humidity": data["main"]["humidity"],
                "description": data["weather"][0]["description"].capitalize(),
                "wind": data["wind"]["speed"]
            }
        return None
    except:
        return None

def get_local_time(city=None):
    try:
        if city and OPENWEATHER_API_KEY:
            geo_url = f"http://api.openweathermap.org/geo/1.0/direct?q={city}&limit=1&appid={OPENWEATHER_API_KEY}"
            response = requests.get(geo_url, timeout=5)
            if response.status_code == 200 and response.json():
                lat = response.json()[0]["lat"]
                lon = response.json()[0]["lon"]
                timezone_str = tf.timezone_at(lat=lat, lng=lon)
                city_name = response.json()[0]["name"]
                if timezone_str:
                    tz = pytz.timezone(timezone_str)
                    now = datetime.now(tz)
                    return {"city": city_name, "time": now.strftime('%I:%M %p'), "date": now.strftime('%A, %B %d, %Y')}
        tz = pytz.timezone("Asia/Kolkata")
        now = datetime.now(tz)
        return {"city": "India", "time": now.strftime('%I:%M %p'), "date": now.strftime('%A, %B %d, %Y')}
    except:
        tz = pytz.timezone("Asia/Kolkata")
        now = datetime.now(tz)
        return {"city": "India", "time": now.strftime('%I:%M %p'), "date": now.strftime('%A, %B %d, %Y')}

# ============ FALLBACK RESPONSES ============
def get_fallback_response(user_message, user_name):
    """Smart fallback responses that use stored name"""
    msg_lower = user_message.lower().strip()
    
    # Check for "remember me" - ALWAYS use stored name if available
    if "remember me" in msg_lower or "do you remember" in msg_lower:
        if user_name:
            return f"Of course I remember you, {user_name}! 😊"
        else:
            return "I don't know your name yet. Tell me 'I am [your name]'!"
    
    # Check for "what's my name" or "my name"
    if "my name" in msg_lower or "what's my name" in msg_lower:
        if user_name:
            return f"Your name is {user_name}! 😊"
        else:
            return "I don't know your name yet. Tell me 'I am [your name]'!"
    
    # Check for "who are you" or "your name"
    if "who are you" in msg_lower or "your name" in msg_lower:
        return "I'm J.A.R.V.I.S., your personal AI assistant created by @Introspection007!"
    
    # Check for "who created you"
    if "who created you" in msg_lower or "who made you" in msg_lower:
        return "I was created by @Introspection007!"
    
    # Check for "joke"
    if "joke" in msg_lower:
        jokes = [
            "Why don't scientists trust atoms? Because they make up everything!",
            "What do you call a fake noodle? An impasta!",
            "Why did the scarecrow win an award? He was outstanding in his field!"
        ]
        return random.choice(jokes)
    
    # Check for "hello" or "hi"
    if msg_lower in ["hello", "hi", "hey", "hola", "sup"]:
        if user_name:
            return f"Hello {user_name}! How can I help you today?"
        else:
            return "Hello! How can I help you today?"
    
    # Default fallback
    if user_name:
        return f"I'm J.A.R.V.I.S.! How can I help you, {user_name}?"
    else:
        return "I'm J.A.R.V.I.S.! Tell me 'I am [your name]' so I can address you properly!"

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
        last_name = message.get("from", {}).get("last_name", "")
        text = message.get("text", "")
        
        if not chat_id or not text:
            return "", 200
        
        # Send typing indicator
        try:
            requests.post(f"https://api.telegram.org/bot{TOKEN}/sendChatAction", 
                         json={"chat_id": chat_id, "action": "typing"}, timeout=2)
        except:
            pass
        
        save_user(user_id, username, first_name, last_name)
        
        # ============ NAME EXTRACTION ============
        msg_lower = text.lower().strip()
        name_extracted = None
        
        # Pattern 1: "I am Spiderman", "I'm Spiderman", "Im Spiderman"
        match = re.search(r'(?:i am|i\'m|im)\s+([A-Za-z][A-Za-z\s\-]{1,20})$', msg_lower)
        if match:
            name_extracted = match.group(1).strip().title()
        
        # Pattern 2: "My name is Spiderman"
        if not name_extracted:
            match = re.search(r'my name is\s+([A-Za-z][A-Za-z\s\-]{1,20})', msg_lower)
            if match:
                name_extracted = match.group(1).strip().title()
        
        # Pattern 3: "Call me Spiderman"
        if not name_extracted:
            match = re.search(r'call me\s+([A-Za-z][A-Za-z\s\-]{1,20})', msg_lower)
            if match:
                name_extracted = match.group(1).strip().title()
        
        # If a name was extracted, save it and respond
        if name_extracted:
            name_extracted = name_extracted.replace("Spider Man", "Spider-Man")
            invalid_names = ['a', 'an', 'the', 'yeah', 'no', 'ok', 'okay', 'well', 'so', 'then', 'like', 'just', 'hello', 'hi', 'hey', 'what', 'who', 'where', 'when', 'why', 'how']
            if name_extracted.lower() not in invalid_names and len(name_extracted) >= 2 and len(name_extracted) <= 30:
                save_user_name(user_id, name_extracted)
                reply = f"🎉 Nice to meet you, {name_extracted}! I'll remember your name."
                return send_response(chat_id, reply)
        
        # ============ GET STORED NAME ============
        user_name = get_user_name(user_id)
        print(f"🔍 User {user_id} has name: {user_name}")
        
        # ============ COMMAND HANDLERS ============
        if text == "/start":
            if user_name:
                reply = f"""🔷 J.A.R.V.I.S. Online 🔷

Welcome back {user_name}!

Commands:
/start - Show menu
/help - All commands
/time - Current time
/time [city] - Time in any city
/weather [city] - Get weather
/whatiknow - What I remember
/forget - Reset memory

Just type anything - I'll chat with you naturally!

━━━━━━━━━━━━━━━━━━━━━
🤖 Powered By @Introspection007"""
            else:
                reply = """🔷 J.A.R.V.I.S. Online 🔷

I'm your personal AI assistant!

Commands:
/start - Show menu
/help - All commands
/time - Current time
/time [city] - Time in any city
/weather [city] - Get weather

Try: "I am [your name]"

━━━━━━━━━━━━━━━━━━━━━
🤖 Powered By @Introspection007"""
        
        elif text == "/help":
            reply = """🔷 J.A.R.V.I.S. Commands 🔷

/time - Current time (India)
/time London - Time in London
/weather London - Weather in London
/whatiknow - What I remember
/forget - Reset my memory
/start - Show menu

Or just chat with me naturally!

━━━━━━━━━━━━━━━━━━━━━
🤖 Powered By @Introspection007"""
        
        elif text == "/whatiknow":
            profile = get_user_profile(user_id)
            info = "📝 What I remember about you:\n\n"
            if user_name:
                info += f"👤 Name: {user_name}\n"
            if profile.get("age"):
                info += f"🎂 Age: {profile['age']}\n"
            if profile.get("location"):
                info += f"📍 Location: {profile['location']}\n"
            if len(info) < 50:
                info += "Tell me about yourself!"
            reply = info + "\n\n━━━━━━━━━━━━━━━━━━━━━\n🤖 Powered By @Introspection007"
        
        elif text == "/forget":
            clear_user_memory(user_id)
            reply = f"🗑️ All memories erased!\n\n━━━━━━━━━━━━━━━━━━━━━\n🤖 Powered By @Introspection007"
        
        elif text.startswith("/time"):
            parts = text.split(maxsplit=1)
            if len(parts) > 1:
                time_data = get_local_time(parts[1])
                if time_data:
                    reply = f"🕐 Time in {time_data['city']}: {time_data['time']}\n📅 Date: {time_data['date']}\n\n━━━━━━━━━━━━━━━━━━━━━\n🤖 Powered By @Introspection007"
                else:
                    reply = f"🕐 Couldn't find time for '{parts[1]}'.\n\n━━━━━━━━━━━━━━━━━━━━━\n🤖 Powered By @Introspection007"
            else:
                time_data = get_local_time()
                reply = f"🕐 Time: {time_data['time']}\n📅 Date: {time_data['date']}\n\n━━━━━━━━━━━━━━━━━━━━━\n🤖 Powered By @Introspection007"
        
        elif text.startswith("/weather"):
            parts = text.split(maxsplit=1)
            if len(parts) < 2:
                reply = "🌤️ Please specify a city.\n\nExample: /weather London\n\n━━━━━━━━━━━━━━━━━━━━━\n🤖 Powered By @Introspection007"
            else:
                weather = get_weather(parts[1])
                if weather:
                    reply = f"""🌤️ Weather in {weather['city']}

🌡️ Temperature: {weather['temp']}°C (feels like {weather['feels_like']}°C)
☁️ Conditions: {weather['description']}
💧 Humidity: {weather['humidity']}%
💨 Wind Speed: {weather['wind']} m/s

━━━━━━━━━━━━━━━━━━━━━
🤖 Powered By @Introspection007"""
                else:
                    reply = f"🌤️ Couldn't find weather for '{parts[1]}'.\n\n━━━━━━━━━━━━━━━━━━━━━\n🤖 Powered By @Introspection007"""
        
        else:
            # Try AI response first
            ai_response = get_ai_response(text, user_id)
            
            if ai_response:
                reply = f"🤖 {ai_response}\n\n━━━━━━━━━━━━━━━━━━━━━\n🤖 Powered By @Introspection007"
            else:
                # Use smart fallback responses
                fallback = get_fallback_response(text, user_name)
                reply = f"🤖 {fallback}\n\n━━━━━━━━━━━━━━━━━━━━━\n🤖 Powered By @Introspection007"
        
        return send_response(chat_id, reply)
        
    except Exception as e:
        print(f"Error: {e}")
        return "", 200

def send_response(chat_id, reply):
    """Send response to Telegram - clean text only"""
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    # Remove Markdown characters
    reply = reply.replace('_', '').replace('*', '').replace('[', '').replace(']', '').replace('(', '').replace(')', '').replace('`', '')
    payload = {"chat_id": chat_id, "text": reply[:4000]}
    requests.post(url, json=payload, timeout=10)
    return "", 200

# Initialize tables on startup
init_tables()

@app.route("/", methods=["GET"])
def index():
    return {"status": "J.A.R.V.I.S. is running!", "creator": "@Introspection007"}

if __name__ == "__main__":
    app.run()
