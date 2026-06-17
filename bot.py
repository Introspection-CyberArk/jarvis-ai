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
    
    # FIXED: NO parse_mode='Markdown' here!
    await update.message.reply_text(welcome)
