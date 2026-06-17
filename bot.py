#!/usr/bin/env python3
"""
Jarvis AI - Clean Telegram Bot
Powered By @Introspection007
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
required_vars = ['BOT_TOKEN', 'OPENROUTER_API_KEY', 'SUPABASE_URL', 'SUPABASE_KEY']
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

# OpenRouter config
OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# Models (auto-fallback)
MODELS = [
    "openrouter/free",
    "openai/gpt-oss-120b:free", 
    "meta-llama/llama-3.3-70b:free"
]

SYSTEM_PROMPT = """You are Jarvis AI, a friendly, helpful AI assistant. 
You naturally learn about users from conversation and remember their details.
You were created by @Introspection007.
Keep responses warm, natural, and conversational."""

async def get_ai_response(messages, retry_count=0):
    selected_model = random.choice(MODELS)
    logger.info(f"Using model: {selected_model}")
    
    try:
        response = await asyncio.to_thread(
            openai.ChatCompletion.create,
            model=selected_model,
            messages=messages,
            max_tokens=500,
            temperature=0.7,
            base_url=OPENROUTER_BASE_URL,
            api_key=OPENROUTER_API_KEY,
            extra_headers={
                "HTTP-Referer": "https://telegram-bot.ai",
                "X-Title": "Jarvis AI"
            },
            timeout=30
        )
        
        ai_response = response.choices[0].message.content
        logger.info(f"✅ Response received")
        return ai_response
        
    except Exception as e:
        logger.error(f"Model failed: {e}")
        if retry_count < 2:
            return await get_ai_response(messages, retry_count + 1)
        else:
            return "I'm having a little trouble thinking right now. Try again in a moment! 🙏"

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
        response = await get_ai_response(messages)
        
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
        
        await update.message.reply_text(response)
        
    except Exception as e:
        logger.error(f"Error: {e}")
        await update.message.reply_text("⚠️ Oops! Something went wrong. Try again! 🙏")

async def credits_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    credits = """╔══════════════════════════════════════╗
║         🤖 JARVIS AI              ║
╠══════════════════════════════════════╣
║  🚀 Creator: @Introspection007      ║
║  📅 Version: 2.0                   ║
║  🔥 Status: Active                 ║
║                                     ║
║  ✨ Features:                      ║
║  • Auto-learning AI                ║
║  • Natural conversation            ║
║  • Smart memory                    ║
║  • Multi-model support             ║
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
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
