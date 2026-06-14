import os
import requests
import sqlite3
import json
from flask import Flask, request, jsonify
from datetime import datetime

app = Flask(__name__)

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
SAMBANOVA_API_KEY = os.environ.get("SAMBANOVA_API_KEY")

# ============ DATABASE SETUP ============
def init_db():
    """Initialize SQLite database"""
    conn = sqlite3.connect('jarvis_memory.db')
    c = conn.cursor()
    
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        first_name TEXT,
        last_name TEXT,
        preferred_name TEXT,
        first_seen TIMESTAMP,
        last_seen TIMESTAMP
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS conversations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        role TEXT,
        message TEXT,
        timestamp TIMESTAMP
    )''')
    
    conn.commit()
    conn.close()
    print("✅ Database initialized!")

def get_user(user_id):
    conn = sqlite3.connect('jarvis_memory.db')
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = c.fetchone()
    conn.close()
    return user

def save_user(user_id, username, first_name, last_name):
    conn = sqlite3.connect('jarvis_memory.db')
    c = conn.cursor()
    c.execute('''INSERT OR REPLACE INTO users 
                 (user_id, username, first_name, last_name, last_seen)
                 VALUES (?, ?, ?, ?, ?)''',
              (user_id, username, first_name, last_name, datetime.now()))
    conn.commit()
    conn.close()

def update_user_name(user_id, preferred_name):
    conn = sqlite3.connect('jarvis_memory.db')
    c = conn.cursor()
    c.execute("UPDATE users SET preferred_name = ? WHERE user_id = ?", (preferred_name, user_id))
    conn.commit()
    conn.close()

def save_conversation(user_id, role, message):
    conn = sqlite3.connect('jarvis_memory.db')
    c = conn.cursor()
    c.execute("INSERT INTO conversations (user_id, role, message, timestamp) VALUES (?, ?, ?, ?)",
              (user_id, role, message, datetime.now()))
    conn.commit()
    conn.close()

def get_recent_conversation(user_id, limit=15):
    conn = sqlite3.connect('jarvis_memory.db')
    c = conn.cursor()
    c.execute("SELECT role, message FROM conversations WHERE user_id = ? ORDER BY timestamp DESC LIMIT ?",
              (user_id, limit))
    history = c.fetchall()
    conn.close()
    return list(reversed(history))

def clear_user_memory(user_id):
    conn = sqlite3.connect('jarvis_memory.db')
    c = conn.cursor()
    c.execute("DELETE FROM conversations WHERE user_id = ?", (user_id,))
    c.execute("UPDATE users SET preferred_name = NULL WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

init_db()

# ============ SAMBANOVA AI REQUEST (NO openai package!) ============
def get_sambanova_response(messages):
    """Direct HTTP request to SambaNova API"""
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
        return result["choices"][0]["message"]["content"]
    else:
        print(f"SambaNova API Error: {response.status_code} - {response.text}")
        return None

def get_ai_response(user_message, user_id, first_name):
    """Get response from SambaNova AI with conversation memory"""
    
    user = get_user(user_id)
    preferred_name = user[4] if user else None
    
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
            preferred_name = name
            save_conversation(user_id, "user", user_message)
            return f"🎉 Nice to meet you, **{name}**! I'll remember your name from now on. How can I help you today?\n\n━━━━━━━━━━━━━━━━━━━━━\n⚡ **Powered By SambaNova AI | @Introspection007**"
    
    # Build system prompt
    if preferred_name:
        system_prompt = f"""You are J.A.R.V.I.S., an AI assistant created by @Introspection007, powered by SambaNova AI.

RULES:
- The user's name is {preferred_name}. ALWAYS address them by name.
- Be warm, friendly, and personal.
- Keep responses concise (2-3 sentences).
- Never say "you haven't told me" if they already shared information."""
    else:
        system_prompt = """You are J.A.R.V.I.S., an AI assistant created by @Introspection007, powered by SambaNova AI.

RULES:
- Be helpful, friendly, and concise.
- Keep responses to 2-3 sentences.
- If a user shares their name, remember to use it."""
    
    # Get conversation history
    history = get_recent_conversation(user_id, limit=15)
    
    # Build messages
    messages = [{"role": "system", "content": system_prompt}]
    
    for role, msg in history:
        messages.append({"role": role, "content": msg})
    
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
            return f"Sorry {preferred_name or 'friend'}, I'm having trouble connecting to AI. Please try again.\n\n━━━━━━━━━━━━━━━━━━━━━\n⚡ **Powered By @Introspection007**"
        
    except Exception as e:
        print(f"Error: {e}")
        return f"I'm experiencing technical difficulties. Please try again in a moment.\n\n━━━━━━━━━━━━━━━━━━━━━\n⚡ **Powered By @Introspection007**"

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
        preferred_name = user[4] if user else None
        display_name = preferred_name or first_name or "there"
        
        if text == "/start":
            reply = f"""🔷 **J.A.R.V.I.S. Online** 🔷

Welcome back {display_name}!

I'm your AI assistant powered by **SambaNova AI** with **persistent memory**!

**Commands:**
/start - Welcome
/forget - Reset my memory
/help - All commands
/time - Current time
/weather [city] - Get weather

**Try:** *"My name is [your name]"* - I'll remember forever!

━━━━━━━━━━━━━━━━━━━━━
⚡ **Powered By SambaNova AI | @Introspection007**"""
        
        elif text == "/forget":
            clear_user_memory(user_id)
            reply = f"🗑️ I've forgotten our previous conversations, {display_name}. Fresh start!\n\n━━━━━━━━━━━━━━━━━━━━━\n⚡ **Powered By @Introspection007**"
        
        elif text == "/help":
            reply = f"""🔷 **J.A.R.V.I.S. Commands** 🔷

/start - Welcome message
/help - This menu
/forget - Reset my memory
/time - Current time
/weather [city] - Weather forecast

**Memory:** I remember your name and conversation history!

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
                reply = f"🌤️ Couldn't fetch weather for {city}.\n\n━━━━━━━━━━━━━━━━━━━━━\n⚡ **Powered By @Introspection007**"
        
        else:
            reply = get_ai_response(text, user_id, first_name)
        
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
        "status": "J.A.R.V.I.S. with SambaNova AI is running!",
        "creator": "@Introspection007"
    })

if __name__ == "__main__":
    app.run()
