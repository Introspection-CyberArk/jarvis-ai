#!/usr/bin/env python3
"""
Jarvis AI - Telegram Bot with Memory
Powered By @Introspection007
"""

import os
import sys
import logging
import asyncio
import random
import re
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
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

# Models
MODELS = [
    "openrouter/free",
    "openai/gpt-oss-120b:free", 
    "meta-llama/llama-3.3-70b:free"
]

MODEL_STATS = {model: {"success": 0, "fail": 0} for model in MODELS}

SYSTEM_PROMPT = """You are Jarvis AI, a friendly, helpful AI assistant with memory. You remember user details like name, interests, and preferences. 
You adapt your responses based on what you know about the user. Keep conversations natural and engaging. 
You were created by @Introspection007 and you're proud of it!"""

async def get_ai_response(messages, model_override=None, retry_count=0):
    if model_override:
        selected_model = model_override
    else:
        selected_model = random.choice(MODELS)
    
    logger.info(f"Using model: {selected_model}")
    
    try:
        response = await asyncio.to_thread(
            openai.ChatCompletion.create,
            model=selected_model,
            messages=messages,
            max_tokens=800,
            temperature=0.7,
            base_url=OPENROUTER_BASE_URL,
            api_key=OPENROUTER_API_KEY,
            extra_headers={
                "HTTP-Referer": "https://telegram-bot.ai",
                "X-Title": "AI Memory Bot"
            }
        )
        
        ai_response = response.choices[0].message.content
        MODEL_STATS[selected_model]["success"] += 1
        return ai_response, selected_model
        
    except Exception as e:
        logger.error(f"Model {selected_model} failed: {e}")
        MODEL_STATS[selected_model]["fail"] += 1
        
        if retry_count < len(MODELS):
            current_index = MODELS.index(selected_model)
            next_index = (current_index + 1) % len(MODELS)
            return await get_ai_response(messages, model_override=MODELS[next_index], retry_count=retry_count + 1)
        else:
            raise Exception("All models failed")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    
    db.get_or_create_user(user_id, username=user.username, first_name=user.first_name)
    
    welcome = f"""🚀 Welcome {user.first_name}!

I'm Jarvis AI, your intelligent assistant with memory and 3 AI models!

🔥 Features:
• Multi-model AI (3 models with auto-fallback)
• Smart memory storage
• Auto-memory extraction
• Model performance tracking

📋 Commands:
/start - Welcome
/memory - View memories
/add_memory key: value - Add memory
/clear_memory - Clear all
/models - Model stats
/switch model - Switch model
/help - Help

💡 Tell me about yourself and I'll remember!

━━━━━━━━━━━━━━━━━━━━━
⚡ Powered By @Introspection007
━━━━━━━━━━━━━━━━━━━━━"""
    
    await update.message.reply_text(welcome)

async def memory_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    memory = db.get_user_memory(user_id)
    
    if not memory or len(memory) == 0:
        await update.message.reply_text("📭 No memories yet. Use /add_memory or tell me about yourself!")
        return
    
    text = "🧠 Your Memories:\n\n"
    for key, value in memory.items():
        if isinstance(value, list):
            text += f"• {key}: {', '.join(str(v) for v in value)}\n"
        else:
            text += f"• {key}: {value}\n"
    
    text += "\n━━━━━━━━━━━━━━━━━━━━━\n⚡ Powered By @Introspection007"
    await update.message.reply_text(text)

async def add_memory_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if not context.args:
        await update.message.reply_text(
            "⚠️ Usage: /add_memory key: value\n\n"
            "Examples:\n"
            "• /add_memory name: John\n"
            "• /add_memory hobby: Coding\n"
            "• /add_memory favorite_movie: Inception\n"
            "• /add_memory location: New York\n\n"
            "━━━━━━━━━━━━━━━━━━━━━\n⚡ Powered By @Introspection007"
        )
        return
    
    text = ' '.join(context.args)
    
    try:
        if ':' not in text:
            await update.message.reply_text("⚠️ Use: key: value")
            return
        
        key, value = text.split(':', 1)
        key = key.strip()
        value = value.strip()
        
        if not key or not value:
            await update.message.reply_text("⚠️ Key and value cannot be empty")
            return
        
        current = db.get_user_memory(user_id)
        current[key] = value
        db.update_user_memory(user_id, current)
        db.add_memory(user_id, f"{key}: {value}")
        
        await update.message.reply_text(
            f"✅ Memory Added!\n\n"
            f"• {key}: {value}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n⚡ Powered By @Introspection007"
        )
    except Exception as e:
        logger.error(f"Add memory error: {e}")
        await update.message.reply_text("⚠️ Error! Use: /add_memory key: value")

async def clear_memory_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [
            InlineKeyboardButton("✅ Yes", callback_data="clear_yes"),
            InlineKeyboardButton("❌ No", callback_data="clear_no")
        ]
    ]
    await update.message.reply_text(
        "⚠️ Clear ALL memories?\n\nThis action cannot be undone!",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def models_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = "🤖 Model Performance Stats\n\n"
    for model, stats in MODEL_STATS.items():
        total = stats["success"] + stats["fail"]
        rate = (stats["success"] / total * 100) if total > 0 else 0
        status = "🟢 Online" if stats["fail"] < 3 else "🟡 Degraded"
        text += f"{status}\n{model}\n├ Success: {stats['success']}\n├ Fail: {stats['fail']}\n└ Rate: {rate:.0f}%\n\n"
    
    text += "━━━━━━━━━━━━━━━━━━━━━\n⚡ Powered By @Introspection007"
    await update.message.reply_text(text)

async def switch_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        models = "\n".join([f"• {m}" for m in MODELS])
        await update.message.reply_text(
            f"Usage: /switch model\n\nAvailable Models:\n{models}\n\n"
            f"Example: /switch meta-llama/llama-3.3-70b:free\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n⚡ Powered By @Introspection007"
        )
        return
    
    model = ' '.join(context.args)
    if model not in MODELS:
        await update.message.reply_text(f"❌ Model '{model}' not found. Use /models to see available models.")
        return
    
    context.user_data['preferred_model'] = model
    await update.message.reply_text(
        f"✅ Switched to: {model}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n⚡ Powered By @Introspection007"
    )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    
    if query.data == "clear_yes":
        db.update_user_memory(user_id, {})
        await query.edit_message_text(
            "✅ Memory cleared successfully!\n\n"
            "━━━━━━━━━━━━━━━━━━━━━\n⚡ Powered By @Introspection007"
        )
    elif query.data == "clear_no":
        await query.edit_message_text(
            "👍 Memory clear canceled.\n\n"
            "━━━━━━━━━━━━━━━━━━━━━\n⚡ Powered By @Introspection007"
        )

async def chat_with_ai(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    message = update.message.text
    
    db.get_or_create_user(user_id, username=user.username, first_name=user.first_name)
    db.add_chat_history(user_id, 'user', message)
    
    memory = db.get_user_memory(user_id)
    history = db.get_chat_history(user_id, limit=5)
    
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
        preferred = context.user_data.get('preferred_model')
        response, model = await get_ai_response(messages, preferred)
        
        db.add_chat_history(user_id, 'assistant', response)
        
        # Auto-extract memory
        try:
            memory_mgr.extract_memory_from_conversation(user_id, [
                {'role': 'user', 'content': message},
                {'role': 'assistant', 'content': response}
            ])
        except:
            pass
        
        await update.message.reply_text(
            f"🤖 {model}\n\n{response}\n\n━━━━━━━━━━━━━━━━━━━━━\n⚡ Powered By @Introspection007"
        )
        
    except Exception as e:
        logger.error(f"AI error: {e}")
        await update.message.reply_text(
            "⚠️ AI temporarily unavailable. Please try again!\n\n"
            "━━━━━━━━━━━━━━━━━━━━━\n⚡ Powered By @Introspection007"
        )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = """🤖 Jarvis AI Help

📋 Commands:
/start - Welcome message
/memory - View your memories
/add_memory key: value - Add custom memory
/clear_memory - Clear all memories
/models - View model stats
/switch model - Switch AI model
/help - Show this help

🔧 Available Models:
• openrouter/free - Fast, general purpose
• openai/gpt-oss-120b:free - Advanced reasoning
• meta-llama/llama-3.3-70b:free - Latest open source

📝 Examples:
/add_memory name: Alex
/add_memory hobby: Python
/add_memory favorite_movie: Inception

💡 Tips:
• I auto-learn from our conversations
• Use /switch to change AI models
• Check /models for performance stats

━━━━━━━━━━━━━━━━━━━━━
⚡ Powered By @Introspection007
━━━━━━━━━━━━━━━━━━━━━"""
    
    await update.message.reply_text(help_text)

async def credits_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    credits_text = """╔══════════════════════════════════════╗
║         🤖 JARVIS AI              ║
║    Advanced Telegram Bot           ║
╠══════════════════════════════════════╣
║                                     ║
║  🚀 Creator: @Introspection007      ║
║  📅 Version: 1.0                   ║
║  🔥 Status: Active                 ║
║                                     ║
║  ✨ Features:                      ║
║  • Multi-Model AI                  ║
║  • Smart Memory                    ║
║  • Auto-Learning                   ║
║  • Supabase Storage                ║
║                                     ║
║  🤖 Models:                        ║
║  • OpenRouter Free                 ║
║  • OpenAI GPT-OSS 120B            ║
║  • Meta Llama 3.3 70B             ║
║                                     ║
╠══════════════════════════════════════╣
║  ⚡ Powered By @Introspection007    ║
╚══════════════════════════════════════╝"""
    
    await update.message.reply_text(credits_text)

def main():
    token = os.getenv('BOT_TOKEN')
    if not token:
        raise ValueError("BOT_TOKEN not set")
    
    app = Application.builder().token(token).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("memory", memory_command))
    app.add_handler(CommandHandler("add_memory", add_memory_command))
    app.add_handler(CommandHandler("clear_memory", clear_memory_command))
    app.add_handler(CommandHandler("models", models_command))
    app.add_handler(CommandHandler("switch", switch_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("credits", credits_command))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat_with_ai))
    
    logger.info("🚀 Jarvis AI Bot starting...")
    logger.info("⚡ Powered By @Introspection007")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
