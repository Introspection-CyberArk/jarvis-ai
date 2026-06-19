#!/usr/bin/env python3
"""
Jarvis AI - Fast Telegram Bot with Weather & Time
Powered By @Introspection007
"""

import os
import sys
import logging
import asyncio
import random
import json
import aiohttp
from datetime import datetime
import pytz

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import openai
from database import DatabaseManager
from memory_manager import MemoryManager

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Check environment variables
required_vars = ['BOT_TOKEN', 'SUPABASE_URL', 'SUPABASE_KEY']
missing = [v for v in required_vars if not os.getenv(v)]
if missing:
    logger.error(f"Missing: {', '.join(missing)}")
    sys.exit(1)

logger.info("✅ All environment variables are set")

# Weather API Key
WEATHER_API_KEY = os.getenv('WEATHER_API_KEY', '6d41f0ecd281e84165a9b8cf76821a17')
WEATHER_API_URL = "http://api.openweathermap.org/data/2.5/weather"

# Initialize database
try:
    logger.info("📊 Connecting to Supabase...")
    db = DatabaseManager()
    logger.info("✅ Database connected")
except Exception as e:
    logger.error(f"❌ Database error: {e}")
    sys.exit(1)

# Initialize memory manager
try:
    memory_mgr = MemoryManager(db)
    logger.info("✅ Memory Manager ready")
except Exception as e:
    logger.error(f"❌ Memory Manager error: {e}")
    sys.exit(1)

# ===== FREE API CONFIGURATION =====
FREE_API_BASE = "https://aiapiv2.pekpik.com/v1"

# Use your OpenRouter key if available, otherwise use free keys
API_KEYS = [
    "sk-nkYD8biGBouOPNmhVmraOjIZnXnmu7wDsfEGVEoUUCiar83B",
    "sk-Em5LrhWxqFMwzPRVnn3vm2HaZ8ONYaOSHGtobMSA2mjuWQzp",
    "sk-o62L7euyQeAS9NixT4CMdceXmYqCyz4FqFX7ro4bkvgX4iXW",
    "sk-smUQQykGoSnyVBRPpF5WUXRdMMAIga2DAj2bmSfFoFdEM8Km",
]

MODELS_CONFIG = {
    "gpt-5.5": {"key_index": 2, "display": "GPT-5.5"},
    "gpt-5.5-pro": {"key_index": 3, "display": "GPT-5.5 Pro"},
    "claude-opus-4-7": {"key_index": 0, "display": "Claude Opus 4.7"},
    "gemini-2.5-flash": {"key_index": 1, "display": "Gemini 2.5 Flash"},
}

MODELS = ["gpt-5.5", "claude-opus-4-7", "gemini-2.5-flash", "gpt-5.5-pro"]

SYSTEM_PROMPT = """You are Jarvis AI, a fast, friendly AI assistant.
You naturally learn from conversation and remember user details.
You can provide weather and time information when asked.
Keep responses short, warm, and conversational.
You were created by @Introspection007."""

current_model_index = 0

# ===== WEATHER & TIME FUNCTIONS =====

async def get_weather(city):
    """Get real-time weather for a city"""
    try:
        params = {
            'q': city,
            'appid': WEATHER_API_KEY,
            'units': 'metric',
            'lang': 'en'
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(WEATHER_API_URL, params=params, timeout=5) as response:
                if response.status == 200:
                    data = await response.json()
                    temp = data['main']['temp']
                    feels_like = data['main']['feels_like']
                    description = data['weather'][0]['description']
                    humidity = data['main']['humidity']
                    wind_speed = data['wind']['speed']
                    city_name = data['name']
                    country = data['sys']['country']
                    
                    return {
                        'city': city_name,
                        'country': country,
                        'temp': temp,
                        'feels_like': feels_like,
                        'description': description,
                        'humidity': humidity,
                        'wind_speed': wind_speed
                    }
                return None
    except Exception as e:
        logger.error(f"Weather error: {e}")
        return None

def get_time_info(city=None):
    """Get current time info"""
    now = datetime.now()
    
    # Common timezones mapping
    timezones = {
        'helsinki': 'Europe/Helsinki',
        'london': 'Europe/London',
        'new york': 'America/New_York',
        'los angeles': 'America/Los_Angeles',
        'tokyo': 'Asia/Tokyo',
        'sydney': 'Australia/Sydney',
        'dubai': 'Asia/Dubai',
        'singapore': 'Asia/Singapore',
        'mumbai': 'Asia/Kolkata',
        'paris': 'Europe/Paris',
        'berlin': 'Europe/Berlin',
        'rome': 'Europe/Rome',
        'madrid': 'Europe/Madrid',
        'amsterdam': 'Europe/Amsterdam',
        'moscow': 'Europe/Moscow',
        'beijing': 'Asia/Shanghai',
        'seoul': 'Asia/Seoul',
        'bangkok': 'Asia/Bangkok',
        'jakarta': 'Asia/Jakarta',
        'cairo': 'Africa/Cairo',
        'cape town': 'Africa/Johannesburg',
        'sao paulo': 'America/Sao_Paulo',
        'mexico city': 'America/Mexico_City',
        'chicago': 'America/Chicago',
        'denver': 'America/Denver',
        'phoenix': 'America/Phoenix',
        'san francisco': 'America/Los_Angeles',
        'seattle': 'America/Los_Angeles',
        'vancouver': 'America/Vancouver',
        'toronto': 'America/Toronto'
    }
    
    if city:
        city_lower = city.lower().strip()
        for key, tz in timezones.items():
            if key in city_lower or city_lower in key:
                try:
                    tz_obj = pytz.timezone(tz)
                    city_time = datetime.now(tz_obj)
                    return {
                        'city': city,
                        'time': city_time.strftime('%I:%M %p'),
                        'date': city_time.strftime('%B %d, %Y'),
                        'timezone': tz
                    }
                except:
                    pass
    
    # Default to UTC
    utc_time = datetime.utcnow()
    return {
        'city': 'UTC',
        'time': utc_time.strftime('%I:%M %p'),
        'date': utc_time.strftime('%B %d, %Y'),
        'timezone': 'UTC'
    }

# ===== AI RESPONSE FUNCTION (FAST!) =====

async def get_ai_response(messages, retry_count=0):
    global current_model_index
    
    # Try models with faster timeout
    for attempt in range(len(MODELS)):
        model = MODELS[current_model_index]
        key_index = MODELS_CONFIG[model]["key_index"]
        api_key = API_KEYS[key_index]
        display_name = MODELS_CONFIG[model]["display"]
        
        logger.info(f"🔄 Using {display_name}")
        
        try:
            client = openai.OpenAI(
                base_url=FREE_API_BASE,
                api_key=api_key,
                timeout=10.0  # Faster timeout!
            )
            
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=300,  # Shorter responses = faster
                temperature=0.7
            )
            
            ai_response = response.choices[0].message.content
            logger.info(f"✅ {display_name} responded!")
            current_model_index = (current_model_index + 1) % len(MODELS)
            return ai_response, display_name
            
        except Exception as e:
            logger.error(f"❌ {display_name} failed: {e}")
            current_model_index = (current_model_index + 1) % len(MODELS)
            
            if attempt == len(MODELS) - 1:
                if retry_count < 1:  # Only 1 retry max
                    await asyncio.sleep(1)
                    return await get_ai_response(messages, retry_count + 1)
                else:
                    return "I'm having trouble thinking. Try again! 🙏", "Error"
    
    return "I'm having trouble thinking. Try again! 🙏", "Error"

# ===== BOT COMMANDS =====

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    
    db.get_or_create_user(user_id, username=user.username, first_name=user.first_name)
    
    welcome = f"""👋 Hey {user.first_name}!

I'm Jarvis AI - just chat with me naturally!

💬 Try:
• "What's the weather in Helsinki?"
• "What time is it in London?"
• "My name is..."
• "I love..."

No commands needed - just talk to me! ✨

━━━━━━━━━━━━━━━━━━━━━
⚡ @Introspection007
━━━━━━━━━━━━━━━━━━━━━"""
    
    await update.message.reply_text(welcome)

async def chat_with_ai(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    message = update.message.text
    
    db.get_or_create_user(user_id, username=user.username, first_name=user.first_name)
    db.add_chat_history(user_id, 'user', message)
    
    # Check for weather query
    if any(word in message.lower() for word in ['weather', 'temperature', 'forecast', 'rain', 'sunny', 'cloudy', 'humid']):
        # Try to extract city
        import re
        city_match = re.search(r'(?:in|at|for)\s+([A-Za-z\s]+)', message.lower())
        if city_match:
            city = city_match.group(1).strip()
            weather_data = await get_weather(city)
            if weather_data:
                weather_response = f"""🌤️ *Weather in {weather_data['city']}, {weather_data['country']}*

🌡️ Temperature: {weather_data['temp']}°C (feels like {weather_data['feels_like']}°C)
🌥️ Conditions: {weather_data['description'].capitalize()}
💧 Humidity: {weather_data['humidity']}%
💨 Wind: {weather_data['wind_speed']} m/s

━━━━━━━━━━━━━━━━━━━━━
⚡ @Introspection007"""
                await update.message.reply_text(weather_response, parse_mode='Markdown')
                return
    
    # Check for time query
    if any(word in message.lower() for word in ['time', 'clock', 'what time', 'current time']):
        # Try to extract city
        import re
        city_match = re.search(r'(?:in|at|for)\s+([A-Za-z\s]+)', message.lower())
        if city_match:
            city = city_match.group(1).strip()
        else:
            city = None
        
        time_info = get_time_info(city)
        time_response = f"""🕐 *Time in {time_info['city']}*

⏰ {time_info['time']}
📅 {time_info['date']}
🌍 Timezone: {time_info['timezone']}

━━━━━━━━━━━━━━━━━━━━━
⚡ @Introspection007"""
        await update.message.reply_text(time_response, parse_mode='Markdown')
        return
    
    # Regular AI response
    memory = db.get_user_memory(user_id)
    history = db.get_chat_history(user_id, limit=3)  # Less history = faster
    
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    
    if memory:
        ctx = "User info:\n"
        for k, v in memory.items():
            ctx += f"- {k}: {v}\n"
        messages.append({"role": "system", "content": ctx})
    
    for h in history:
        messages.append({"role": h['role'], "content": h['content']})
    
    messages.append({"role": "user", "content": message})
    
    await update.message.chat.send_action(action="typing")
    
    try:
        response, model_used = await get_ai_response(messages)
        db.add_chat_history(user_id, 'assistant', response)
        
        try:
            memory_mgr.extract_memory_from_conversation(user_id, [
                {'role': 'user', 'content': message},
                {'role': 'assistant', 'content': response}
            ])
        except:
            pass
        
        await update.message.reply_text(response)
        
    except Exception as e:
        logger.error(f"Error: {e}")
        await update.message.reply_text("⚠️ Oops! Something went wrong. Try again! 🙏")

async def credits_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    credits = """╔══════════════════════════════════════╗
║         🤖 JARVIS AI              ║
╠══════════════════════════════════════╣
║  🚀 Creator: @Introspection007      ║
║  📅 Version: 3.0                   ║
║  🔥 Status: Active                 ║
║  ⚡ Weather + Time Ready           ║
╠══════════════════════════════════════╣
║  ⚡ Powered By @Introspection007    ║
╚══════════════════════════════════════╝"""
    
    await update.message.reply_text(credits)

def main():
    token = os.getenv('BOT_TOKEN')
    if not token:
        raise ValueError("BOT_TOKEN not set")
    
    app = Application.builder().token(token).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("credits", credits_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat_with_ai))
    
    logger.info("🚀 Jarvis AI Bot starting...")
    logger.info("⚡ Powered By @Introspection007")
    logger.info("🌤️ Weather API: Enabled")
    logger.info("🕐 Time API: Enabled")
    logger.info(f"🤖 Models: {len(MODELS)} loaded")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
