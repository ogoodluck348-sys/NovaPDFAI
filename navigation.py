from telegram import InlineKeyboardMarkup, InlineKeyboardButton


def main_keyboard():
    keyboard = [
        [
            InlineKeyboardButton("🔗 Merge PDF", callback_data="merge"),
            InlineKeyboardButton("🔒 Protect PDF", callback_data="protect")
        ],
        [
            InlineKeyboardButton("📄 Extract PDF Text", callback_data="extract"),
            InlineKeyboardButton("📝 Summarize PDF", callback_data="summarize")
        ],
        [
            InlineKeyboardButton("💧 Watermark", callback_data="watermark"),
            InlineKeyboardButton("🔄 Rotate PDF", callback_data="rotate")
        ],
        [
            InlineKeyboardButton("🖼️ PDF to Images", callback_data="images"),
            InlineKeyboardButton("📉 Compress PDF", callback_data="compress")
        ],
        [
            InlineKeyboardButton("🖼️ Images → PDF", callback_data="images_to_pdf"),
            InlineKeyboardButton("🔓 Unlock PDF", callback_data="unlock")
        ],
        [
            InlineKeyboardButton("📝 Text to PDF", callback_data="texttopdf"),
            InlineKeyboardButton("📱 QR Code Generator", callback_data="qr_code")
        ],
        [
            InlineKeyboardButton("🧠 AI Explainer", callback_data="ai_summarizer"),
            InlineKeyboardButton("📚 Ask PDF", callback_data="ask_pdf")
        ],
        [
            InlineKeyboardButton("➕ More", callback_data="more")
        ]
    ]

    return InlineKeyboardMarkup(keyboard)



# =========================
# START
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    if user:
        save_user(user.id)

    await update.effective_message.reply_text(
        "👋 Welcome to NovaPDF AI!\n\n"
        "Your all-in-one PDF assistant on Telegram.\n\n"
        "Choose a tool below:",
        reply_markup=main_keyboard()
    )


# =========================
# HELP
# =========================

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text(
        "📚 NovaPDF AI — Commands\n\n"
        "/start — Open the main menu\n"
        "/help — Show commands\n"
        "/cancel — Cancel current operation\n\n"
        "📄 PDF Tools\n"
        "🔗 Merge PDF\n"
        "🔒 Protect PDF\n"
        "📄 Extract PDF Text\n"
        "📝 Summarize PDF with Gemini AI\n"
        "💧 Watermark — Coming soon\n"
        "🔄 Rotate PDF — Coming soon\n"
        "🖼️ PDF to Images — Coming soon\n"
        "📉 Compress PDF — Coming soon\n\n"
        "👑 Admin commands\n"
        "/users — User count\n"
        "/broadcast <message> — Broadcast"
    )
# =========================
# CANCEL
# =========================

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    return ConversationHandler.END


# =========================
# TOOL NAVIGATION
# =========================
