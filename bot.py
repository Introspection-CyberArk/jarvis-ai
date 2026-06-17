import os
import asyncio
import logging
import random
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

# Get environment variables directly (Railway injects these)
BOT_TOKEN = os.getenv('BOT_TOKEN')
OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN environment variable is not set")
if not OPENROUTER_API_KEY:
    raise ValueError("OPENROUTER_API_KEY environment variable is not set")

# Initialize managers (they'll use env vars directly)
db = DatabaseManager()
memory_mgr = MemoryManager(db)

# Multi-Model Configuration
MODELS = [
    "openrouter/free",
    "openai/gpt-oss-120b:free", 
    "meta-llama/llama-3.3-70b:free"
]

# Model capabilities tracking
MODEL_STATS = {
    model: {
        "success": 0,
        "fail": 0,
        "last_used": None,
        "response_time": []
    } for model in MODELS
}

SYSTEM_PROMPT = """You are a friendly, helpful AI assistant with memory. You remember user details like name, interests, and preferences. 
You adapt your responses based on what you know about the user. Keep conversations natural, engaging, and slightly humorous.
Always be supportive and encouraging. If you don't know something, be honest but offer to help find the answer."""

async def get_ai_response(messages, model_override=None, retry_count=0):
    """Get response from AI with automatic fallback between models"""
    
    if model_override:
        selected_model = model_override
    else:
        available_models = [m for m in MODELS if MODEL_STATS[m]["fail"] < 3]
        if not available_models:
            available_models = MODELS
        
        weights = []
        for model in available_models:
            success = MODEL_STATS[model]["success"]
            fail = MODEL_STATS[model]["fail"]
            total = success + fail
            if total == 0:
                weight = 1.0
            else:
                weight = success / total
            weights.append(weight)
        
        total_weight = sum(weights)
        if total_weight == 0:
            weights = [1.0 / len(available_models) for _ in available_models]
        else:
            weights = [w / total_weight for w in weights]
        
        selected_model = random.choices(available_models, weights=weights, k=1)[0]
    
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
            logger.info(f"Falling back to next model (attempt {retry_count + 1})")
            current_index = MODELS.index(selected_model)
            next_index = (current_index + 1) % len(MODELS)
            return await get_ai_response(messages, model_override=MODELS[next_index], retry_count=retry_count + 1)
        else:
            raise Exception("All models failed")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    user = update.effective_user
    user_id = user.id
    
    profile = db.get_or_create_user(
        user_id, 
        username=user.username, 
        first_name=user.first_name
    )
    
    welcome_message = f"""🚀 *Welcome to your AI Assistant, {user.first_name}!*

I'm a smart AI with *MULTI-MODEL* capabilities! I use 3 different AI models.

*🤖 Models I use:*
• 🟢 OpenRouter Free
• 🔵 OpenAI GPT-OSS 120B Free  
• 🟣 Meta Llama 3.3 70B Free

*🧠 Features:*
• Memory storage
• Auto-fallback models
• Smart load balancing
• Manual memory add with /add_memory

*Commands:*
/memory - View your memories
/add_memory - Add custom memory (key: value)
/clear_memory - Clear all memories
/models - Show model stats
/switch [model] - Force specific model
/help - Show this help

Tell me about yourself! 😊"""
    
    await update.message.reply_text(welcome_message, parse_mode='Markdown')

async def models_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show model statistics"""
    stats_text = "*🤖 Model Performance Statistics*\n\n"
    
    for model, stats in MODEL_STATS.items():
        total = stats["success"] + stats["fail"]
        success_rate = (stats["success"] / total * 100) if total > 0 else 0
        status = "🟢 Online" if stats["fail"] < 3 else "🟡 Degraded" if stats["fail"] < 5 else "🔴 Offline"
        
        stats_text += f"*{model}*\n"
        stats_text += f"├ Status: {status}\n"
        stats_text += f"├ Success: {stats['success']}\n"
        stats_text += f"├ Fail: {stats['fail']}\n"
        stats_text += f"└ Success Rate: {success_rate:.1f}%\n\n"
    
    await update.message.reply_text(stats_text, parse_mode='Markdown')

async def switch_model(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Force a specific model"""
    if not context.args:
        model_list = "\n".join([f"• `{m}`" for m in MODELS])
        await update.message.reply_text(
            f"*Usage:* `/switch [model]`\n\nAvailable models:\n{model_list}\n\nExample: `/switch meta-llama/llama-3.3-70b:free`",
            parse_mode='Markdown'
        )
        return
    
    requested_model = ' '.join(context.args)
    
    if requested_model not in MODELS:
        await update.message.reply_text(f"❌ Model `{requested_model}` not found.", parse_mode='Markdown')
        return
    
    context.user_data['preferred_model'] = requested_model
    await update.message.reply_text(f"✅ Switched to model: `{requested_model}`", parse_mode='Markdown')

async def memory_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user's stored memory"""
    user_id = update.effective_user.id
    memory = db.get_user_memory(user_id)
    
    if not memory or len(memory) == 0:
        await update.message.reply_text("📭 No memories stored. Use /add_memory or tell me about yourself!")
        return
    
    memory_text = "*🧠 Your Memories:*\n\n"
    for key, value in memory.items():
        if isinstance(value, list):
            memory_text += f"• *{key.capitalize()}:* {', '.join(str(v) for v in value)}\n"
        else:
            memory_text += f"• *{key.capitalize()}:* {value}\n"
    
    await update.message.reply_text(memory_text, parse_mode='Markdown')

async def add_memory_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Add custom memory manually"""
    user_id = update.effective_user.id
    
    if not context.args:
        await update.message.reply_text(
            "⚠️ *Usage:* `/add_memory key: value`\n\n"
            "*Examples:*\n"
            "• `/add_memory name: John`\n"
            "• `/add_memory favorite_movie: Inception`\n"
            "• `/add_memory hobby: Playing guitar`",
            parse_mode='Markdown'
        )
        return
    
    text = ' '.join(context.args)
    
    try:
        if ':' not in text:
            await update.message.reply_text(
                "⚠️ *Invalid format!* Use: `/add_memory key: value`",
                parse_mode='Markdown'
            )
            return
        
        key, value = text.split(':', 1)
        key = key.strip()
        value = value.strip()
        
        if not key or not value:
            await update.message.reply_text("⚠️ *Key and value cannot be empty!*", parse_mode='Markdown')
            return
        
        current_memory = db.get_user_memory(user_id)
        current_memory[key] = value
        db.update_user_memory(user_id, current_memory)
        db.add_memory(user_id, f"{key}: {value}")
        
        await update.message.reply_text(
            f"✅ *Memory added!*\n\n• *{key}* = `{value}`",
            parse_mode='Markdown'
        )
        
    except Exception as e:
        await update.message.reply_text("⚠️ *Error!* Use: `/add_memory key: value`", parse_mode='Markdown')

async def clear_memory_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Clear user's memory"""
    user_id = update.effective_user.id
    
    keyboard = [
        [
            InlineKeyboardButton("✅ Yes", callback_data="clear_yes"),
            InlineKeyboardButton("❌ No", callback_data="clear_no")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "⚠️ *Clear ALL memories?*",
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle callback queries"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    
    if query.data == "clear_yes":
        db.update_user_memory(user_id, {})
        await query.edit_message_text("✅ *Memory cleared!*", parse_mode='Markdown')
    elif query.data == "clear_no":
        await query.edit_message_text("👍 *Canceled.*", parse_mode='Markdown')

async def chat_with_ai(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle user messages"""
    user = update.effective_user
    user_id = user.id
    user_message = update.message.text
    
    db.get_or_create_user(user_id, username=user.username, first_name=user.first_name)
    db.add_chat_history(user_id, 'user', user_message)
    
    user_memory = db.get_user_memory(user_id)
    history = db.get_chat_history(user_id, limit=10)
    
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    
    if user_memory:
        memory_context = "User information I remember:\n"
        for key, value in user_memory.items():
            if isinstance(value, list):
                memory_context += f"- {key}: {', '.join(str(v) for v in value)}\n"
            else:
                memory_context += f"- {key}: {value}\n"
        messages.append({"role": "system", "content": memory_context})
    
    for msg in history:
        messages.append({"role": msg['role'], "content": msg['content']})
    
    messages.append({"role": "user", "content": user_message})
    
    await update.message.chat.send_action(action="typing")
    
    try:
        preferred_model = context.user_data.get('preferred_model')
        ai_response, model_used = await get_ai_response(messages, model_override=preferred_model)
        
        db.add_chat_history(user_id, 'assistant', ai_response)
        memory_mgr.extract_memory_from_conversation(user_id, [
            {'role': 'user', 'content': user_message},
            {'role': 'assistant', 'content': ai_response}
        ])
        
        response_text = f"🤖 *{model_used}*\n\n{ai_response}"
        await update.message.reply_text(response_text, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Error: {e}")
        await update.message.reply_text("⚠️ *AI unavailable. Try again!*", parse_mode='Markdown')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Help command"""
    help_text = """*🤖 AI Assistant Help*

*Commands:*
/start - Initialize bot
/memory - View your memories
/add_memory - Add custom memory (key: value)
/clear_memory - Clear all memories
/models - Show model stats
/switch - Switch AI model
/help - Show this help

*Models:*
• openrouter/free
• openai/gpt-oss-120b:free
• meta-llama/llama-3.3-70b:free

*Examples:*
/add_memory name: John
/add_memory hobby: Coding
/memory - See all memories"""
    
    await update.message.reply_text(help_text, parse_mode='Markdown')

def main():
    """Main function"""
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN not set")
    
    application = Application.builder().token(BOT_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("memory", memory_command))
    application.add_handler(CommandHandler("add_memory", add_memory_command))
    application.add_handler(CommandHandler("clear_memory", clear_memory_command))
    application.add_handler(CommandHandler("models", models_stats))
    application.add_handler(CommandHandler("switch", switch_model))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat_with_ai))
    
    logger.info("🚀 Bot started!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
