import os
import requests
import sqlite3
from flask import Flask, request, jsonify
from datetime import datetime
from openai import OpenAI

app = Flask(__name__)

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
SAMBANOVA_API_KEY = os.environ.get("SAMBANOVA_API_KEY")

# Initialize SambaNova client (OpenAI-compatible)
sambanova_client = OpenAI(
    base_url="https://api.sambanova.ai/v1",
    api_key=SAMBANOVA_API_KEY
)

# ============ DATABASE SETUP ============
def init_db():
    """Initialize SQLite database"""
    conn = sqlite3.connect('jarvis_memory.db')
    c = conn.cursor()
    
    # Users table - store user info
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        first_name TEXT,
        last_name TEXT,
        preferred_name TEXT,
        first_seen TIMESTAMP,
        last_seen TIMESTAMP
    )''')
    
    # Conversations table - store chat history
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
    """Get user from database"""
    conn = sqlite3.connect('jarvis_memory.db')
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = c.fetchone()
    conn.close()
    return user

def save_user(user_id, username, first_name, last_name):
    """Save or update user"""
    conn = sqlite3.connect('jarvis_memory.db')
    c = conn.cursor()
    c.execute('''INSERT OR REPLACE INTO users 
                 (user_id, username, first_name, last_name, last_seen)
                 VALUES (?, ?, ?, ?, ?)''',
              (user_id, username, first_name, last_name, datetime.now()))
    conn.commit()
    conn.close()

def update_user_name(user_id, preferred_name):
    """Update user's preferred name"""
    conn = sqlite3.connect('jarvis_memory.db')
    c = conn.cursor()
    c.execute("UPDATE users SET preferred_name = ? WHERE user_id = ?", (preferred_name, user_id))
    conn.commit()
    conn.close()

def save_conversation(user_id, role, message):
    """Save conversation to database"""
    conn = sqlite3.connect('jarvis_memory.db')
    c = conn.cursor()
    c.execute("INSERT INTO conversations (user_id, role, message, timestamp) VALUES (?, ?, ?, ?)",
              (user_id, role, message, datetime.now()))
    conn.commit()
    conn.close()

def get_recent_conversation(user_id, limit=15):
    """Get recent conversation history"""
    conn = sqlite3.connect('jarvis_memory.db')
    c = conn.cursor()
    c.execute("SELECT role, message FROM conversations WHERE user_id = ? ORDER BY timestamp DESC LIMIT ?",
              (user_id, limit))
    history = c.fetchall()
    conn.close()
    return list(reversed(history))  # Oldest to newest

def clear_user_memory(user_id):
    """Reset user's conversation history"""
    conn = sqlite3.connect('jarvis_memory.db')
    c = conn.cursor()
    c.execute("DELETE FROM conversations WHERE user_id = ?", (user_id,))
    c.execute("UPDATE users SET preferred_name = NULL WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

# Initialize database on startup
init_db()

# ============ AI RESPONSE WITH MEMORY ============
def get_ai_response(user_message, user_id, first_name):
    """Get response from SambaNova AI with conversation memory"""
    
    # Get user from database
    user = get_user(user_id)
    preferred_name = user[4] if user else None
    
    # Extract name from message if user shares it
    msg_lower = user_message.lower()
    if "my name is" in msg_lower or "call me" in msg_lower:
        if "my name is" in msg_lower:
            name = user_message.split("my name is")[-1].strip()
        else:
            name = user_message.split("call me")[-1].strip()
        
        # Remove any punctuation from name
        name = name.strip('.,!?')
        
        if name and len(name) < 30:
            update_user_name(user_id, name)
            preferred_name = name
            save_conversation(user_id, "user", user_message)
            save_conversation(user_id, "assistant", f"Nice to meet you, {name}! I'll remember your name.")
            return f"🎉 Nice to meet you, **{name}**! I'll remember your name from now on. How can I help you today?\n\n━━━━━━━━━━━━━━━━━━━━━\n⚡ **Powered By SambaNova AI | @Introspection007**"
    
    # Build system prompt with user info
    if preferred_name:
        system_prompt = f"""You are J.A.R.V.I.S., a sophisticated AI assistant created by @Introspection007, powered by SambaNova AI.

IMPORTANT RULES:
- The user's name is {preferred_name}. ALWAYS address them by name in your responses.
- Be warm, friendly, and personal - use their name naturally in conversation.
- Remember everything they tell you during this conversation.
- NEVER say "you haven't told me" if they already shared information.
- Keep responses concise (2-3 sentences) unless more detail is requested.
- Show personality and wit, but stay professional."""

    else:
        system_prompt = """You are J.A.R.V.I.S., a sophisticated AI assistant created by @Introspection007, powered by SambaNova AI.

RULES:
- Be helpful, friendly, and concise.
- If a user shares their name, remember to use it in future responses.
- Show personality but stay professional.
- Keep responses to 2-3 sentences unless more detail is requested."""
    
    # Get recent conversation history
    history = get_recent_conversation(user_id, limit=15)
    
    # Build messages array for SambaNova (OpenAI-compatible)
    messages = [{"role": "system", "content": system_prompt}]
    
    # Add conversation history
    for role, msg in history:
        messages.append({"role": role, "content": msg})
    
    # Add current message
    messages.append({"role": "user", "content": user_message})
    
    try:
        # Call SambaNova API (using Meta-Llama-3.3-70B-Instruct)
        response = sambanova_client.chat.completions.create(
            model="Meta-Llama-3.3-70B-Instruct",  # Fast, powerful, free
            messages=messages,
            temperature=0.7,
            max_tokens=500
        )
        reply = response.choices[0].message.content
        
        # Add credit footer if not already there
        if "@Introspection007" not in reply:
            reply += "\n\n━━━━━━━━━━━━━━━━━━━━━\n⚡ **Powered By SambaNova AI | @Introspection007**"
        
        # Save conversation
        save_conversation(user_id, "user", user_message)
        save_conversation(user_id, "assistant", reply)
        
        return reply
        
    except Exception as e:
        print(f"SambaNova API Error: {e}")
        return f"I'm experiencing some technical difficulties, {preferred_name or 'friend'}. Please try again in a moment.\n\n━━━━━━━━━━━━━━━━━━━━━\n⚡ **Powered By SambaNova AI | @Introspection007**"

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
        
        # Save user info
        save_user(user_id, username, first_name, last_name)
        user = get_user(user_id)
        preferred_name = user[4] if user else None
        display_name = preferred_name or first_name or "there"
        
        # Handle commands
        if text == "/start":
            reply = f"""🔷 **J.A.R.V.I.S. Online** 🔷

Welcome back{' ' + display_name if display_name else ''}!

I'm your personal AI assistant powered by **SambaNova AI** with **persistent memory** - I remember our conversations!

**✨ What I can do:**
• Answer any questions
• Remember your name and preferences
• Continue conversations where we left off
• Learn about you over time

**📋 Commands:**
/start - Welcome message
/forget - Reset my memory of you  
/help - Show all commands
/time - Current time
/weather [city] - Get weather

**💡 Try this:** *"My name is [your name]"* - I'll never forget!

━━━━━━━━━━━━━━━━━━━━━
⚡ **Powered By SambaNova AI | @Introspection007**"""
        
        elif text == "/forget":
            clear_user_memory(user_id)
            reply = f"🗑️ I've forgotten our previous conversations, {display_name}. I'm ready to start fresh with you!\n\n━━━━━━━━━━━━━━━━━━━━━\n⚡ **Powered By SambaNova AI | @Introspection007**"
        
        elif text == "/help":
            reply = f"""🔷 **J.A.R.V.I.S. Commands** 🔷

**Core Commands:**
/start - Welcome message
/help - Show this menu
/forget - Reset my memory

**Utilities:**
/time - Current time
/weather [city] - Get weather forecast

**Memory Features:**
• Tell me *"my name is [name]"* - I'll remember you forever
• I recall our entire conversation history
• I learn your preferences over time

━━━━━━━━━━━━━━━━━━━━━
⚡ **Powered By SambaNova AI | @Introspection007**"""
        
        elif text == "/time":
            now = datetime.now()
            reply = f"🕐 **Current time:** {now.strftime('%I:%M %p')}\n📅 **Date:** {now.strftime('%A, %B %d, %Y')}\n\n━━━━━━━━━━━━━━━━━━━━━\n⚡ **Powered By SambaNova AI | @Introspection007**"
        
        elif text.startswith("/weather"):
            parts = text.split(maxsplit=1)
            city = parts[1] if len(parts) > 1 else "London"
            try:
                url = f"https://wttr.in/{city}?format=%C+%t+%w&m"
                response = requests.get(url, timeout=8)
                weather_text = response.text.strip()
                reply = f"🌤️ **Weather in {city.capitalize()}:** {weather_text}\n\n━━━━━━━━━━━━━━━━━━━━━\n⚡ **Powered By SambaNova AI | @Introspection007**"
            except:
                reply = f"🌤️ Sorry, couldn't fetch weather for {city}. Try another city name.\n\n━━━━━━━━━━━━━━━━━━━━━\n⚡ **Powered By SambaNova AI | @Introspection007**"
        
        else:
            # Get AI response with memory
            reply = get_ai_response(text, user_id, first_name)
        
        # Send reply
        send_url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": reply,
            "parse_mode": "Markdown"
        }
        requests.post(send_url, json=payload)
        
        return "", 200
        
    except Exception as e:
        print(f"Error in webhook: {e}")
        return "", 200

@app.route("/", methods=["GET"])
def index():
    return jsonify({
        "status": "J.A.R.V.I.S. with SambaNova AI + Memory is running!",
        "creator": "@Introspection007",
        "ai_provider": "SambaNova (Meta-Llama-3.3-70B-Instruct)",
        "features": ["Persistent Memory", "User Recognition", "Free AI"]
    })

if __name__ == "__main__":
    app.run()
