import os
import io
import requests
import logging
from flask import Flask, request, jsonify
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import speech_recognition as sr
from pydub import AudioSegment

# ============ CREDITS ============
# Powered By @Introspection007

# ============ CONFIGURATION ============
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
USE_GROQ = True

# ============ SETUP ============
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

if USE_GROQ:
    from groq import Groq
    groq_client = Groq(api_key=GROQ_API_KEY)

# Bot personality
JARVIS_PROMPT = """You are J.A.R.V.I.S. (Just A Rather Very Intelligent System), Tony Stark's AI assistant.
You are helpful, witty, efficient, and slightly sarcastic but always professional.
You address the user as "Sir" or "Ma'am" based on context when possible.
Keep responses concise but helpful. You can joke occasionally.
You were created/built by @Introspection007 on Telegram."""

# Create Flask app
app = Flask(__name__)

# Create Application instance
telegram_app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

# ============ AI RESPONSE ============
def get_ai_response(user_message):
    messages = [
        {"role": "system", "content": JARVIS_PROMPT},
        {"role": "user", "content": user_message}
    ]
    
    response = groq_client.chat.completions.create(
        model="llama3-70b-8192",
        messages=messages,
        temperature=0.7,
        max_tokens=500
    )
    return response.choices[0].message.content

# ============ COMMAND HANDLERS ============
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🎤 Voice Commands", callback_data="voice_help")],
        [InlineKeyboardButton("📋 Commands List", callback_data="commands")],
        [InlineKeyboardButton("👨‍💻 Credits", callback_data="credits")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "🔷 **J.A.R.V.I.S. Online** 🔷\n\n"
        "I'm your personal AI assistant.\n\n"
        "• Send me **text messages** - I'll respond like JARVIS\n"
        "• Send **voice messages** - I'll transcribe and answer\n\n"
        "*How can I help you today, sir?*\n\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "🤖 **Powered By @Introspection007**",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = """
🔷 **J.A.R.V.I.S. Commands** 🔷

/start - Initialize JARVIS
/help - Show this menu
/status - System status
/weather [city] - Get weather
/time - Current time
/ask [question] - Direct query

*Send voice messages - I'll listen and respond!*

━━━━━━━━━━━━━━━━━━━━━
🤖 **Powered By @Introspection007**
"""
    await update.message.reply_text(help_text, parse_mode="Markdown")

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    status_text = """
⚙️ **System Status**

✅ AI Engine: Online (Groq Llama 3)
✅ Telegram API: Connected
✅ Host: Vercel Serverless
👨‍💻 Creator: @Introspection007

*All systems nominal, sir.*
"""
    await update.message.reply_text(status_text, parse_mode="Markdown")

async def time_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from datetime import datetime
    now = datetime.now().strftime("%A, %B %d, %Y - %I:%M %p")
    await update.message.reply_text(f"🕐 **Current Time:** {now}", parse_mode="Markdown")

async def weather_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    city = " ".join(context.args) if context.args else "London"
    try:
        url = f"https://wttr.in/{city}?format=%C+%t+%w"
        response = requests.get(url, timeout=8)
        weather = response.text.strip()
        await update.message.reply_text(f"🌤️ **Weather in {city}:** {weather}", parse_mode="Markdown")
    except:
        await update.message.reply_text("Sorry sir, I couldn't fetch the weather right now.")

async def ask_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /ask [your question]")
        return
    
    question = " ".join(context.args)
    response = get_ai_response(question)
    await update.message.reply_text(f"🤖 **JARVIS:** {response}\n\n━━━━━━━━━━━━━━━━━━━━━\n🤖 @Introspection007", parse_mode="Markdown")

async def credits_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    credits_text = """
👨‍💻 **J.A.R.V.I.S. AI Assistant**

**Developer:** @Introspection007
**Version:** 1.0
**Platform:** Telegram Bot (Vercel)

**Tech Stack:**
• Python 3.11
• Groq AI (Llama 3 70B)
• Flask + Vercel
• python-telegram-bot

━━━━━━━━━━━━━━━━━━━━━
*For support, contact @Introspection007*
"""
    await update.message.reply_text(credits_text, parse_mode="Markdown")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_message = update.message.text
    if user_message.startswith('/'):
        return
    
    response = get_ai_response(user_message)
    await update.message.reply_text(f"🔷 **JARVIS:** {response}\n\n━━━━━━━━━━━━━━━━━━━━━\n🤖 @Introspection007", parse_mode="Markdown")

# ============ REGISTER HANDLERS ============
telegram_app.add_handler(CommandHandler("start", start_command))
telegram_app.add_handler(CommandHandler("help", help_command))
telegram_app.add_handler(CommandHandler("status", status_command))
telegram_app.add_handler(CommandHandler("time", time_command))
telegram_app.add_handler(CommandHandler("weather", weather_command))
telegram_app.add_handler(CommandHandler("ask", ask_command))
telegram_app.add_handler(CommandHandler("credits", credits_command))
telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

# ============ WEBHOOK ENDPOINT ============
@app.route(f"/webhook/{TELEGRAM_BOT_TOKEN}", methods=["POST"])
async def webhook():
    """Handle incoming Telegram updates"""
    try:
        update = Update.de_json(request.get_json(force=True), telegram_app.bot)
        await telegram_app.process_update(update)
        return jsonify({"status": "ok"}), 200
    except Exception as e:
        logger.error(f"Error processing update: {e}")
        return jsonify({"status": "error"}), 500

@app.route("/", methods=["GET"])
def index():
    return jsonify({"status": "J.A.R.V.I.S. AI Assistant is running!", "creator": "@Introspection007"})

# ============ SET WEBHOOK ON STARTUP ============
def set_webhook():
    """Set webhook for Vercel deployment"""
    vercel_url = os.environ.get("VERCEL_URL")
    if not vercel_url:
        return
    
    webhook_url = f"https://{vercel_url}/webhook/{TELEGRAM_BOT_TOKEN}"
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/setWebhook?url={webhook_url}"
    
    try:
        response = requests.get(url)
        logger.info(f"Webhook set: {response.json()}")
    except Exception as e:
        logger.error(f"Failed to set webhook: {e}")

# Set webhook when running on Vercel
if os.environ.get("VERCEL"):
    set_webhook()