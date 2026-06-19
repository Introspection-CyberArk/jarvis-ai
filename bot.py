#!/usr/bin/env python3
"""
Jarvis AI - Clean Telegram Bot  
Powered By @Introspection007
Using Free LLM API Keys
"""

import os
import sys
import logging
import asyncio
import random
from datetime import datetime

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
# REMOVED: OPENROUTER_API_KEY - now using free keys!
missing = [v for v in required_vars if not os.getenv(v)]
if missing:
    logger.error(f"Missing: {', '.join(missing)}")
    sys.exit(1)

logger.info("✅ All environment variables are set")

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
# Base URL for free API
FREE_API_BASE = "https://aiapiv2.pekpik.com/v1"

# FREE API KEYS - Rotate through them for reliability
API_KEYS = [
    "sk-nkYD8biGBouOPNmhVmraOjIZnXnmu7wDsfEGVEoUUCiar83B",  # Claude Opus 4.7
    "sk-Em5LrhWxqFMwzPRVnn3vm2HaZ8ONYaOSHGtobMSA2mjuWQzp",  # Gemini 2.5 Flash
    "sk-o62L7euyQeAS9NixT4CMdceXmYqCyz4FqFX7ro4bkvgX4iXW",  # GPT-5.5
    "sk-smUQQykGoSnyVBRPpF5WUXRdMMAIga2DAj2bmSfFoFdEM8Km",  # GPT-5.5 Pro
    "sk-7qfO6iJV5eqbPCRTaLzuSOxx9i2V5hui3Nau9u8Bx3LZXv2l",  # DeepSeek V4 Pro
    "sk-gKcFDVChRkaSw8bvUIUCPaG35q0MadLVXZ4wG2eWhzSH1LXB",  # DeepSeek V4 Flash
    "sk-i2PNvzfVeDeoWT4HsOYVLNW8gh8Jm1jLCHHwComj1vOHM3k5",  # Kimi K2.5
    "sk-NmdYyEW4MtXEL3EnPloFNf79IDcdF8j7qWTdstjH6psLMI6b",  # Grok 4.3
]

# Available Models with their keys
MODELS_CONFIG = {
    "gpt-5.5": {"key_index": 2, "display": "GPT-5.5"},
    "gpt-5.5-pro": {"key_index": 3, "display": "GPT-5.5 Pro"},
    "claude-opus-4-7": {"key_index": 0, "display": "Claude Opus 4.7"},
    "gemini-2.5-flash": {"key_index": 1, "display": "Gemini 2.5 Flash"},
    "deepseek-v4-pro": {"key_index": 4, "display": "DeepSeek V4 Pro"},
    "deepseek-v4-flash": {"key_index": 5, "display": "DeepSeek V4 Flash"},
    "kimi-k2.5": {"key_index": 6, "display": "Kimi K2.5"},
    "x-ai/grok-4.3": {"key_index": 7, "display": "Grok 4.3"},
}

# List of models to try (in order of preference)
MODELS = [
    "gpt-5.5",
    "claude-opus-4-7", 
    "gemini-2.5-flash",
    "deepseek-v4-pro",
    "gpt-5.5-pro",
    "kimi-k2.5",
    "x-ai/grok-4.3",
    "deepseek-v4-flash",
]

SYSTEM_PROMPT = """You are Jarvis AI, a friendly, helpful AI assistant. 
You naturally learn about users from conversation and remember their details.
You were created by @Introspection007.
Keep responses warm, natural, and conversational."""

# Track which key/model is working
current_key_index = 0
current_model_index = 0

async def get_ai_response(messages, retry_count=0):
    global current_key_index, current_model_index
    
    # Try models in sequence
    for attempt in range(len(MODELS)):
        model = MODELS[current_model_index]
        key_index = MODELS_CONFIG[model]["key_index"]
        api_key = API_KEYS[key_index]
        display_name = MODELS_CONFIG[model]["display"]
        
        logger.info(f"🔄 Trying {display_name} (Attempt {attempt + 1}/{len(MODELS)})")
        
        try:
            # Create client with free API
            client = openai.OpenAI(
                base_url=FREE_API_BASE,
                api_key=api_key,
                timeout=30.0
            )
            
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=500,
                temperature=0.7
            )
            
            ai_response = response.choices[0].message.content
            logger.info(f"✅ {display_name} responded successfully!")
            
            # Rotate to next model for next request (load balancing)
            current_model_index = (current_model_index + 1) % len(MODELS)
            
            return ai_response, display_name
            
        except Exception as e:
            logger.error(f"❌ {display_name} failed: {e}")
            # Try next model
            current_model_index = (current_model_index + 1) % len(MODELS)
            
            # If we've tried all models, wait a bit and retry
            if attempt == len(MODELS) - 1:
                if retry_count < 2:
                    logger.info(f"🔄 All models failed. Retrying... ({retry_count + 1}/2)")
                    await asyncio.sleep(2)
                    return await get_ai_response(messages, retry_count + 1)
                else:
                    return "⚠️ All AI models are currently busy. Please try again in a moment! 🙏", "Error"
    
    return "⚠️ All AI models are currently busy. Please try again in a moment! 🙏", "Error"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    
    db.get_or_create_user(user_id, username=user.username, first_name=user.first_name)
    
    welcome = f"""👋 Hey {user.first_name}!

I'm Jarvis AI - just chat with me naturally and I'll remember what you tell me!

💬 Try saying things like:
• "My name is..."
• "I love..."
• "I work as..."
• "My favorite..."

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
    
    # Get user memory
    memory = db.get_user_memory(user_id)
    history = db.get_chat_history(user_id, limit=5)
    
    # Build messages
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    
    if memory:
        ctx = "User info I know:\n"
        for k, v in memory.items():
            ctx += f"- {k}: {v}\n"
        messages.append({"role": "system", "content": ctx})
    
    for h in history:
        messages.append({"role": h['role'], "content": h['content']})
    
    messages.append({"role": "user", "content": message})
    
    await update.message.chat.send_action(action="typing")
    
    try:
        # Get AI response
        response, model_used = await get_ai_response(messages)
        
        # Store in history
        db.add_chat_history(user_id, 'assistant', response)
        
        # Auto-learn from conversation
        try:
            memory_mgr.extract_memory_from_conversation(user_id, [
                {'role': 'user', 'content': message},
                {'role': 'assistant', 'content': response}
            ])
        except:
            pass
        
        # Send response with model info (optional - remove if you want cleaner)
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
║  💰 Free API: 90+ Models           ║
║                                     ║
║  ✨ Features:                      ║
║  • Auto-learning AI                ║
║  • Natural conversation            ║
║  • Smart memory                    ║
║  • Multi-model fallback            ║
║  • GPT-5.5, Claude, Gemini, Grok  ║
╠══════════════════════════════════════╣
║  ⚡ Powered By @Introspection007    ║
╚══════════════════════════════════════╝"""
    
    await update.message.reply_text(credits)

def main():
    token = os.getenv('BOT_TOKEN')
    if not token:
        raise ValueError("BOT_TOKEN not set")
    
    app = Application.builder().token(token).build()
    
    # Only 2 commands - clean and minimal!
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("credits", credits_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat_with_ai))
    
    logger.info("🚀 Jarvis AI Bot starting...")
    logger.info("⚡ Powered By @Introspection007")
    logger.info(f"📡 Using free API: {FREE_API_BASE}")
    logger.info(f"🤖 Available models: {', '.join(MODELS)}")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
