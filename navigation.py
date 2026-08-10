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
            InlineKeyboardButton("➕ More", callback_data="more")
        ]
    ]

    return InlineKeyboardMarkup(keyboard)
