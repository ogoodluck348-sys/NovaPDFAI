import asyncio
import os
import json
import logging
import tempfile
import urllib.request
import urllib.error
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton, BotCommand
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
    CallbackQueryHandler,
)

from PyPDF2 import PdfReader, PdfWriter, PdfMerger


# =========================
# CONFIGURATION
# =========================

TOKEN = os.getenv("BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

ADMIN_ID = 8131832776

if not TOKEN:
    raise ValueError("BOT_TOKEN is not set.")

if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY is not set.")

# =========================
# LOGGING
# =========================

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)


# =========================
# CONVERSATION STATES
# =========================

PROTECT_WAIT_PDF = 1
PROTECT_WAIT_PASSWORD = 2
MERGE_WAIT_FILES = 3
EXTRACT_WAIT_PDF = 4
SUMMARY_WAIT_PDF = 5
TEXT_TO_PDF_WAIT_TEXT = 6
TEXT_TO_PDF_WAIT_NAME = 7
MERGE_WAIT_NAME = 8


# =========================
# USER TRACKING
# =========================

USERS_FILE = "users.txt"


def save_user(user_id):
    users = set()

    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, "r") as f:
            users = set(
                line.strip()
                for line in f
                if line.strip()
            )

    users.add(str(user_id))

    with open(USERS_FILE, "w") as f:
        for uid in users:
            f.write(uid + "\n")


def get_user_count():
    if not os.path.exists(USERS_FILE):
        return 0

    with open(USERS_FILE, "r") as f:
        return len([
            line for line in f
            if line.strip()
        ])
# =========================
# MAIN MENU
# =========================

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
            InlineKeyboardButton("📝 Text to PDF", callback_data="texttopdf"),
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

def back_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ Back", callback_data="back")]
    ])

def main_menu_button():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]
    ])



# =========================
# MORE MENU
# =========================

async def more_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query

    if query:
        await query.answer()
        message = query.message
    else:
        message = update.effective_message

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("👑 Admin", callback_data="admin_menu")],
        [InlineKeyboardButton("⬅️ Back", callback_data="more_back_main")]
    ])

    await message.edit_text(
        "➕ More Options\n\nChoose an option:",
        reply_markup=keyboard
    )


async def admin_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if update.effective_user.id != ADMIN_ID:
        await query.answer("⛔ Admin access only.", show_alert=True)
        return

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("👥 Users", callback_data="admin_users")],
        [InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast")],
        [InlineKeyboardButton("⬅️ Back", callback_data="admin_back_more")]
    ])

    await query.message.edit_text(
        "👑 Admin Panel\n\nChoose an option:",
        reply_markup=keyboard
    )


async def admin_users_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if update.effective_user.id != ADMIN_ID:
        await query.answer("⛔ Admin access only.", show_alert=True)
        return

    count = get_user_count()

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ Back", callback_data="admin_back")]
    ])

    await query.message.edit_text(
        f"👥 Total users: {count}",
        reply_markup=keyboard
    )


async def admin_broadcast_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if update.effective_user.id != ADMIN_ID:
        await query.answer("⛔ Admin access only.", show_alert=True)
        return

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ Back", callback_data="admin_back")]
    ])

    await query.message.edit_text(
        "📢 Broadcast\n\n"
        "To broadcast a message, use:\n"
        "/broadcast Your message here",
        reply_markup=keyboard
    )


async def admin_back_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("👥 Users", callback_data="admin_users")],
        [InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast")],
        [InlineKeyboardButton("⬅️ Back", callback_data="admin_back_more")]
    ])

    await query.message.edit_text(
        "👑 Admin Panel\n\nChoose an option:",
        reply_markup=keyboard
    )


async def admin_back_more_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("👑 Admin", callback_data="admin_menu")],
        [InlineKeyboardButton("⬅️ Back", callback_data="more_back_main")]
    ])

    await query.message.edit_text(
        "➕ More Options\n\nChoose an option:",
        reply_markup=keyboard
    )


async def more_back_main_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    await query.message.edit_text(
        "🏠 NovaPDF AI\n\nChoose a tool:",
        reply_markup=main_keyboard()
    )


async def back_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query:
        query = update.callback_query
        await query.answer()

        await query.message.edit_text(
            "🏠 NovaPDF AI\n\nChoose a tool:",
            reply_markup=main_keyboard()
        )
    else:
        await update.effective_message.reply_text(
            "🏠 NovaPDF AI\n\nChoose a tool:",
            reply_markup=main_keyboard()
        )


# =========================
# PROTECT PDF
# =========================

async def protect_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query

    if query:
        await query.answer()
        message = query.message
    else:
        message = update.effective_message

    context.user_data.clear()

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ Back", callback_data="protect_back")]
    ])

    if query:
        await message.edit_text(
            "🔒 Send the PDF you want to protect.",
            reply_markup=keyboard
        )
    else:
        sent = await message.reply_text(
            "🔒 Send the PDF you want to protect.",
            reply_markup=keyboard
        )
        message = sent

    context.user_data["protect_prompt_message_id"] = message.message_id

    return PROTECT_WAIT_PDF


async def protect_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    context.user_data.clear()

    await query.message.edit_text(
        "🏠 NovaPDF AI\n\nChoose a tool:",
        reply_markup=main_keyboard()
    )

    return ConversationHandler.END


async def protect_receive_pdf(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    document = update.effective_message.document

    if not document:
        return PROTECT_WAIT_PDF

    if document.mime_type != "application/pdf":
        await update.effective_message.reply_text(
            "❌ Please send a PDF file."
        )
        return PROTECT_WAIT_PDF

    try:
        temp_dir = tempfile.mkdtemp()

        input_path = os.path.join(
            temp_dir,
            "input.pdf"
        )

        file = await document.get_file()
        await file.download_to_drive(input_path)

        context.user_data["protect_dir"] = temp_dir
        context.user_data["protect_input"] = input_path

        prompt_message_id = context.user_data.get("protect_prompt_message_id")

        # Remove the original Protect prompt so the next message
        # appears directly below the user's PDF.
        if prompt_message_id:
            try:
                await context.bot.delete_message(
                    chat_id=update.effective_chat.id,
                    message_id=prompt_message_id
                )
            except Exception as e:
                logger.warning(f"Could not delete Protect prompt: {e}")

        # Send the password prompt below the user's PDF.
        password_message = await update.effective_message.reply_text(
            "🔑 PDF received.\n\n"
            "Now send the password you want to use.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("❌ Cancel", callback_data="protect_cancel")]
            ])
        )

        context.user_data["protect_password_message_id"] = password_message.message_id

        return PROTECT_WAIT_PASSWORD

    except Exception as e:
        logger.error(f"PDF download error: {e}")

        await update.effective_message.reply_text(
            "❌ Failed to receive the PDF."
        )

        return ConversationHandler.END


async def protect_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    temp_dir = context.user_data.get("protect_dir")

    if temp_dir and os.path.exists(temp_dir):
        try:
            for filename in os.listdir(temp_dir):
                file_path = os.path.join(temp_dir, filename)
                if os.path.isfile(file_path):
                    os.remove(file_path)
            os.rmdir(temp_dir)
        except Exception as e:
            logger.warning(f"Protect cancel cleanup error: {e}")

    context.user_data.clear()

    await query.message.edit_text(
        "🏠 NovaPDF AI\n\nChoose a tool:",
        reply_markup=main_keyboard()
    )

    return ConversationHandler.END


async def protect_receive_password(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    password = update.effective_message.text.strip()

    if not password:
        await update.effective_message.reply_text(
            "❌ Please enter a valid password."
        )
        return PROTECT_WAIT_PASSWORD

    input_path = context.user_data.get("protect_input")
    temp_dir = context.user_data.get("protect_dir")

    if not input_path or not temp_dir:
        await update.effective_message.reply_text(
            "❌ No PDF was found. Please start again."
        )
        return ConversationHandler.END

    output_path = os.path.join(
        temp_dir,
        "protected.pdf"
    )

    try:
        await update.effective_message.reply_text(
            "⏳ Protecting your PDF..."
        )

        reader = PdfReader(input_path)
        writer = PdfWriter()

        for page in reader.pages:
            writer.add_page(page)

        writer.encrypt(password)

        with open(output_path, "wb") as output_file:
            writer.write(output_file)

        with open(output_path, "rb") as pdf_file:
            await update.effective_message.reply_document(
                document=pdf_file,
                caption="🔐 Your PDF has been password-protected.",
                reply_markup=main_menu_button()
            )


    except Exception as e:
        logger.error(f"Protection error: {e}")

        await update.effective_message.reply_text(
            "❌ Unable to protect this PDF."
        )

    finally:
        try:
            for filename in os.listdir(temp_dir):
                os.remove(
                    os.path.join(temp_dir, filename)
                )

            os.rmdir(temp_dir)

        except Exception:
            pass

        context.user_data.clear()

    return ConversationHandler.END
# =========================
# MERGE PDF
# =========================

async def merge_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    context.user_data["merge_files"] = []

    if update.callback_query:
        query = update.callback_query
        await query.answer()

        await query.message.edit_text(
            "🔗 Send the PDF files you want to merge.\n\n"
            "Send them one after another.",
            reply_markup=back_keyboard()
        )
    else:
        message = await update.effective_message.reply_text(
            "🔗 Send the PDF files you want to merge.\n\n"
            "Send them one after another.",
            reply_markup=back_keyboard()
        )
        context.user_data["prompt_message_id"] = message.message_id

    return MERGE_WAIT_FILES


async def merge_receive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    document = update.effective_message.document

    if not document:
        return MERGE_WAIT_FILES

    if document.mime_type != "application/pdf":
        await update.effective_message.reply_text(
            "❌ Please send PDF files only."
        )
        return MERGE_WAIT_FILES

    try:
        temp_dir = context.user_data.get("merge_dir")

        if not temp_dir:
            temp_dir = tempfile.mkdtemp()
            context.user_data["merge_dir"] = temp_dir

        file = await document.get_file()

        files = context.user_data.get("merge_files", [])
        number = len(files) + 1

        input_path = os.path.join(
            temp_dir,
            f"file_{number}.pdf"
        )

        await file.download_to_drive(input_path)

        files.append(input_path)
        context.user_data["merge_files"] = files

        await update.effective_message.reply_text(
            f"✅ PDF {number} received.\n\n"
            "📄 Send another PDF or type /done when you're finished.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("❌ Cancel", callback_data="merge_cancel")]
            ])
        )

        return MERGE_WAIT_FILES

    except Exception as e:
        logger.error(f"Merge receive error: {e}")

        await update.effective_message.reply_text(
            "❌ I couldn't receive that PDF. Please try again."
        )

        return MERGE_WAIT_FILES


async def merge_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    # Clean up temporary merge files
    temp_dir = context.user_data.get("merge_dir")

    if temp_dir and os.path.exists(temp_dir):
        try:
            for filename in os.listdir(temp_dir):
                file_path = os.path.join(temp_dir, filename)
                if os.path.isfile(file_path):
                    os.remove(file_path)
            os.rmdir(temp_dir)
        except Exception as e:
            logger.warning(f"Merge cancel cleanup error: {e}")

    # Clear the merge operation
    context.user_data.clear()

    # Return to Main Menu in the SAME message
    try:
        await query.message.edit_text(
            "🏠 NovaPDF AI\n\nChoose a tool:",
            reply_markup=main_keyboard()
        )
    except Exception as e:
        logger.warning(f"Could not restore Main Menu after merge cancel: {e}")

    return ConversationHandler.END


async def merge_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    files = context.user_data.get("merge_files", [])
    temp_dir = context.user_data.get("merge_dir")

    if not files:
        await update.effective_message.reply_text(
            "❌ You haven't sent any PDF files."
        )
        return ConversationHandler.END

    if len(files) < 2:
        await update.effective_message.reply_text(
            "❌ Please send at least 2 PDF files."
        )
        return MERGE_WAIT_FILES

    await update.effective_message.reply_text(
        "📄 What would you like to name the merged PDF?\n\n"
        "Example: My Documents\n\n"
        "You don't need to type .pdf"
    )

    return MERGE_WAIT_NAME


async def merge_receive_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.effective_message.text.strip()

    if not name:
        await update.effective_message.reply_text(
            "❌ Please enter a name for the PDF."
        )
        return MERGE_WAIT_NAME

    if name.lower().endswith(".pdf"):
        name = name[:-4]

    safe_name = "".join(
        c for c in name
        if c.isalnum() or c in " -_()"
    ).strip()

    if not safe_name:
        await update.effective_message.reply_text(
            "❌ Please choose a valid PDF name."
        )
        return MERGE_WAIT_NAME

    files = context.user_data.get("merge_files", [])
    temp_dir = context.user_data.get("merge_dir")

    if len(files) < 2 or not temp_dir:
        await update.effective_message.reply_text(
            "❌ Your PDF files could not be found. Please start the merge again."
        )
        context.user_data.clear()
        return ConversationHandler.END

    output_path = os.path.join(
        temp_dir,
        f"{safe_name}.pdf"
    )

    try:
        await update.effective_message.reply_text(
            "⏳ Merging your PDFs...\n\n"
            "Please wait."
        )

        merger = PdfMerger()

        for pdf_file in files:
            merger.append(pdf_file)

        merger.write(output_path)
        merger.close()

        with open(output_path, "rb") as merged_pdf:
            await update.effective_message.reply_document(
                document=merged_pdf,
                filename=f"{safe_name}.pdf",
                caption=f"✅ {safe_name}.pdf created successfully.",
                reply_markup=main_menu_button()
            )


    except Exception as e:
        logger.error(f"Merge error: {e}")

        await update.effective_message.reply_text(
            "❌ Unable to merge the PDF files."
        )

    finally:
        try:
            if temp_dir and os.path.exists(temp_dir):
                for filename in os.listdir(temp_dir):
                    file_path = os.path.join(temp_dir, filename)

                    if os.path.isfile(file_path):
                        os.remove(file_path)

                os.rmdir(temp_dir)

        except Exception as e:
            logger.error(f"Merge cleanup error: {e}")

        context.user_data.clear()

    return ConversationHandler.END


# =========================
# TEXT TO PDF
# =========================

async def text_to_pdf_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query:
        await update.callback_query.answer()

    await update.effective_message.reply_text(
        "📝 Send the text you want to convert to PDF.\n\n"
        "You can send a short or long text."
    ,
        reply_markup=back_keyboard()
    )
    return TEXT_TO_PDF_WAIT_TEXT


async def text_to_pdf_receive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.effective_message.text

    if not text or not text.strip():
        await update.effective_message.reply_text(
            "❌ Please send some text."
        )
        return TEXT_TO_PDF_WAIT_TEXT

    context.user_data["pdf_text"] = text

    await update.effective_message.reply_text(
        "📄 What would you like to name your PDF?\n\n"
        "Example: Biology Notes\n\n"
        "You don't need to type .pdf"
    )

    return TEXT_TO_PDF_WAIT_NAME


async def text_to_pdf_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.effective_message.text.strip()

    if not name:
        await update.effective_message.reply_text(
            "❌ Please enter a name for the PDF."
        )
        return TEXT_TO_PDF_WAIT_NAME

    if name.lower().endswith(".pdf"):
        name = name[:-4]

    safe_name = "".join(
        c for c in name
        if c.isalnum() or c in " -_()"
    ).strip()

    if not safe_name:
        await update.effective_message.reply_text(
            "❌ Please choose a valid PDF name."
        )
        return TEXT_TO_PDF_WAIT_NAME

    text = context.user_data.get("pdf_text")

    if not text:
        await update.effective_message.reply_text(
            "❌ Your text could not be found. Please start again with /texttopdf."
        )
        return ConversationHandler.END

    try:
        await update.effective_message.reply_text(
            "⏳ Creating your PDF..."
        )

        pdf_path = f"{safe_name}.pdf"

        from reportlab.lib.pagesizes import A4
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.enums import TA_LEFT
        from reportlab.lib.units import mm
        from xml.sax.saxutils import escape

        doc = SimpleDocTemplate(
            pdf_path,
            pagesize=A4,
            rightMargin=20 * mm,
            leftMargin=20 * mm,
            topMargin=20 * mm,
            bottomMargin=20 * mm
        )

        styles = getSampleStyleSheet()

        body_style = ParagraphStyle(
            "BodyText",
            parent=styles["BodyText"],
            fontSize=11,
            leading=16,
            alignment=TA_LEFT,
            spaceAfter=8
        )

        story = []

        for paragraph in text.split("\n"):
            paragraph = paragraph.strip()

            if paragraph:
                story.append(
                    Paragraph(
                        escape(paragraph),
                        body_style
                    )
                )
                story.append(Spacer(1, 4))

        doc.build(story)

        with open(pdf_path, "rb") as pdf_file:
            await update.effective_message.reply_document(
                document=pdf_file,
                filename=f"{safe_name}.pdf",
                caption=f"📄 {safe_name}.pdf",
                reply_markup=main_menu_button()
            )


        import os
        os.remove(pdf_path)

        context.user_data.pop("pdf_text", None)

        return ConversationHandler.END

    except Exception as e:
        logger.error(f"Text to PDF error: {e}")

        await update.effective_message.reply_text(
            "❌ Sorry, I couldn't create the PDF.",
            reply_markup=main_menu_button()
        )

        return ConversationHandler.END

# =========================
# EXTRACT PDF TEXT
# =========================

async def extract_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query

    if query:
        await query.answer()
        message = query.message
    else:
        message = update.effective_message

    context.user_data.clear()

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ Back", callback_data="extract_back")]
    ])

    if query:
        await message.edit_text(
            "📄 Send the PDF you want me to extract text from.",
            reply_markup=keyboard
        )
    else:
        sent = await message.reply_text(
            "📄 Send the PDF you want me to extract text from.",
            reply_markup=keyboard
        )
        message = sent

    context.user_data["extract_prompt_message_id"] = message.message_id

    return EXTRACT_WAIT_PDF


async def extract_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    context.user_data.clear()

    await query.message.edit_text(
        "🏠 NovaPDF AI\n\nChoose a tool:",
        reply_markup=main_keyboard()
    )

    return ConversationHandler.END


async def extract_receive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    document = update.effective_message.document

    if not document:
        return EXTRACT_WAIT_PDF

    if document.mime_type != "application/pdf":
        await update.effective_message.reply_text(
            "❌ Please send a PDF file."
        )
        return EXTRACT_WAIT_PDF

    temp_dir = tempfile.mkdtemp()
    input_path = os.path.join(temp_dir, "input.pdf")

    try:
        prompt_message_id = context.user_data.get("extract_prompt_message_id")

        if prompt_message_id:
            try:
                await context.bot.delete_message(
                    chat_id=update.effective_chat.id,
                    message_id=prompt_message_id
                )
            except Exception as e:
                logger.warning(f"Could not delete Extract prompt: {e}")

        await update.effective_message.reply_text(
            "⏳ Extracting text from your PDF..."
        )

        file = await document.get_file()
        await file.download_to_drive(input_path)

        reader = PdfReader(input_path)
        extracted_text = ""

        for page in reader.pages:
            text = page.extract_text()

            if text:
                extracted_text += text + "\n\n"

        if not extracted_text.strip():
            await update.effective_message.reply_text(
                "⚠️ I couldn't find readable text in this PDF."
            )
            return ConversationHandler.END

        # Telegram message size is limited,
        # so send long text in smaller sections.
        chunk_size = 3500

        chunks = [
            extracted_text[start:start + chunk_size]
            for start in range(0, len(extracted_text), chunk_size)
        ]

        for i, chunk in enumerate(chunks):
            if i == len(chunks) - 1:
                await update.effective_message.reply_text(
                    chunk,
                    reply_markup=main_menu_button()
                )
            else:
                await update.effective_message.reply_text(chunk)


    except Exception as e:
        logger.error(f"Text extraction error: {e}")

        await update.effective_message.reply_text(
            "❌ Unable to extract text from this PDF.",
            reply_markup=main_menu_button()
        )

    finally:
        try:
            os.remove(input_path)
            os.rmdir(temp_dir)
        except Exception:
            pass

        context.user_data.clear()

    return ConversationHandler.END
# =========================
# GEMINI AI SUMMARIZATION
# =========================

async def summarize_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query

    if query:
        await query.answer()
        message = query.message
    else:
        message = update.effective_message

    context.user_data.clear()

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ Back", callback_data="summary_back")]
    ])

    if query:
        await message.edit_text(
            "📝 Send the PDF you want Nova AI to summarize.",
            reply_markup=keyboard
        )
    else:
        sent = await message.reply_text(
            "📝 Send the PDF you want Nova AI to summarize.",
            reply_markup=keyboard
        )
        message = sent

    context.user_data["summary_prompt_message_id"] = message.message_id

    return SUMMARY_WAIT_PDF


async def summary_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    context.user_data.clear()

    await query.message.edit_text(
        "🏠 NovaPDF AI\n\nChoose a tool:",
        reply_markup=main_keyboard()
    )

    return ConversationHandler.END


async def summarize_receive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    document = update.effective_message.document

    if not document:
        return SUMMARY_WAIT_PDF

    if document.mime_type != "application/pdf":
        await update.effective_message.reply_text(
            "❌ Please send a PDF file."
        )
        return SUMMARY_WAIT_PDF

    temp_dir = tempfile.mkdtemp()
    input_path = os.path.join(temp_dir, "input.pdf")

    try:
        prompt_message_id = context.user_data.get("summary_prompt_message_id")

        if prompt_message_id:
            try:
                await context.bot.delete_message(
                    chat_id=update.effective_chat.id,
                    message_id=prompt_message_id
                )
            except Exception as e:
                logger.warning(f"Could not delete Summarize prompt: {e}")

        await update.effective_message.reply_text(
            "⏳ Processing your PDF...\n\n"
            "🤖 Nova AI is preparing your summary."
        )

        file = await document.get_file()
        await file.download_to_drive(input_path)

        reader = PdfReader(input_path)
        extracted_text = ""

        for page in reader.pages:
            text = page.extract_text()

            if text:
                extracted_text += text + "\n\n"

        if not extracted_text.strip():
            await update.effective_message.reply_text(
                "⚠️ I couldn't extract readable text from this PDF.",
                reply_markup=main_menu_button()
            )
            return ConversationHandler.END

        # Prevent extremely large API requests.
        text_for_gemini = extracted_text[:30000]

        summary = await gemini_summarize(text_for_gemini)

        if not summary:
            await update.effective_message.reply_text(
                "❌ Nova AI couldn't generate a summary at the moment.",
                reply_markup=main_menu_button()
            )
            return ConversationHandler.END

        # Telegram messages have a size limit.
        if not summary:
            await update.effective_message.reply_text(
                "❌ Nova AI couldn't generate a summary.",
                reply_markup=main_menu_button()
            )
            return ConversationHandler.END

        # Telegram messages have a size limit.
        chunk_size = 3500

        await update.effective_message.reply_text("📝 Nova AI Summary")

        for start in range(0, len(summary), chunk_size):
            chunk = summary[start:start + chunk_size].strip()

            if chunk:
                is_last = start + chunk_size >= len(summary)
                await update.effective_message.reply_text(
                    chunk,
                    reply_markup=main_menu_button() if is_last else None
                )


    except Exception as e:
        logger.error(f"Gemini summarization error: {e}")

        await update.effective_message.reply_text(
            "❌ An error occurred while generating the summary.",
            reply_markup=main_menu_button()
        )

    finally:
        try:
            os.remove(input_path)
            os.rmdir(temp_dir)
        except Exception:
            pass

        context.user_data.clear()

    return ConversationHandler.END


async def gemini_summarize(text):
    prompt = f"""
You are NovaPDF AI's document summarization engine.

Create a clear, accurate, well-organized summary of the document below.

STRICT RULES:
- Return ONLY the final summary.
- Do NOT reveal reasoning, thinking, planning, drafting, checking, or self-correction.
- Do NOT mention the user, AI, model, prompt, or these instructions.
- Do NOT include phrases such as "I will", "I need to", "The user wants", "Check:", "Critique:", "Correction:", "Self-Correction", "Draft", "Planning", "Reasoning", or "Analysis".
- Use clear headings and bullet points.
- Organize related information together.
- Preserve important names, dates, definitions, facts, examples, figures, formulas, and key terms.
- Do not invent information.
- Do not add information that is not supported by the document.
- Remove unnecessary repetition.
- For academic documents, make the summary useful for exam revision.
- Explain important concepts briefly rather than merely listing keywords.
- Return a polished final summary only.

DOCUMENT:
{text}
"""

    try:
        import urllib.request
        import urllib.error
        import json

        url = (
            "https://generativelanguage.googleapis.com/v1beta/"
            "models/gemma-4-26b-a4b-it:generateContent?key="
            + GEMINI_API_KEY
        )

        data = json.dumps({
            "contents": [
                {
                    "parts": [
                        {
                            "text": prompt
                        }
                    ]
                }
            ]
        }).encode("utf-8")

        request = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST"
        )

        response = await asyncio.to_thread(
            urllib.request.urlopen,
            request,
            timeout=120
        )

        result = json.loads(response.read().decode("utf-8"))

        candidates = result.get("candidates", [])

        if not candidates:
            logger.error(f"Gemma returned no candidates: {result}")
            return None

        parts = candidates[0].get("content", {}).get("parts", [])

        # Use the actual answer and ignore thought/reasoning parts.
        answer_parts = [
            part.get("text", "")
            for part in parts
            if not part.get("thought", False)
        ]

        summary = "\n".join(answer_parts).strip()

        if not summary:
            return None

        return summary

    except Exception as e:
        logger.error(f"Gemini summary error: {e}")
        return None
# =========================
# COMING SOON FEATURES
# =========================

async def coming_soon(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text(
        "🚧 Coming Soon!\n\n"
        "This feature is currently under development "
        "and will be available in a future update.",
        reply_markup=main_menu_button()
    )
# =========================
# ADMIN FEATURES
# =========================

async def users_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    count = get_user_count()

    await update.effective_message.reply_text(
        f"👥 Total users: {count}"
    )


async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    if not context.args:
        await update.effective_message.reply_text(
            "📢 Usage:\n/broadcast Your message here"
        )
        return

    message = " ".join(context.args)

    if not os.path.exists(USERS_FILE):
        await update.effective_message.reply_text(
            "👥 No users found."
        )
        return

    with open(USERS_FILE, "r") as f:
        user_ids = [
            line.strip()
            for line in f
            if line.strip()
        ]

    sent = 0
    failed = 0

    await update.effective_message.reply_text(
        f"📢 Broadcasting to {len(user_ids)} users..."
    )

    for user_id in user_ids:
        try:
            await context.bot.send_message(
                chat_id=int(user_id),
                text=message
            )

            sent += 1

        except Exception as e:
            failed += 1

            logger.warning(
                f"Broadcast failed for {user_id}: {e}"
            )

    total = len(user_ids)

    await update.effective_message.reply_text(
        f"📢 Broadcast complete!\n\n"
        f"✅ Sent: {sent}\n"
        f"❌ Failed: {failed}\n"
        f"👥 Total: {total}"
    )

async def inline_main_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    # Clear any active operation
    context.user_data.clear()

    # Always SEND a new menu.
    # This works for PDF/document messages, images and normal text messages.
    await query.message.reply_text(
        "🏠 NovaPDF AI\n\nChoose a tool:",
        reply_markup=main_keyboard()
    )

    return ConversationHandler.END

async def inline_back_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    # Cancel the active operation
    context.user_data.clear()

    # Restore Main Menu in the SAME message
    try:
        await query.message.edit_text(
            "🏠 NovaPDF AI\n\nChoose a tool:",
            reply_markup=main_keyboard()
        )
    except Exception as e:
        logger.warning(f"Could not restore Main Menu: {e}")

    return ConversationHandler.END


# =========================
# BUTTON HANDLER
# =========================

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.effective_message.text

    if text == "➕ More":
        await more_menu(update, context)

    elif text == "⬅️ Back":
        context.user_data.clear()
        await back_menu(update, context)
        return

    elif text == "📋 Commands":
        await help_command(update, context)

    elif text == "👑 Admin":
        if update.effective_user.id == ADMIN_ID:
            await update.effective_message.reply_text(
                "👑 Admin Panel\n\n"
                "/users — View user count\n"
                "/broadcast <message> — Broadcast a message"
            )
        else:
            await update.effective_message.reply_text(
                "⛔ Admin access only."
            )

    elif text in [
        "💧 Watermark",
        "🔄 Rotate PDF",
        "🖼️ PDF to Images",
        "📉 Compress PDF"
    ]:
        await coming_soon(update, context)
# =========================
# COMING SOON CALLBACK HANDLER
# =========================

async def coming_soon_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    await coming_soon(update, context)

# =========================
# MAIN APPLICATION
# =========================

def main():
    app = Application.builder().token(TOKEN).build()

    # Commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("cancel", cancel))

    # Admin commands
    app.add_handler(CommandHandler("users", users_command))
    app.add_handler(CommandHandler("broadcast", broadcast_command))

    # Global Back button — must be registered before tool conversations
    app.add_handler(
        MessageHandler(
            filters.Regex("^⬅️ Back$"),
            back_menu
        ),
        group=0
    )

    # Protect PDF
    protect_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(protect_start, pattern="^protect$"),
            MessageHandler(
                filters.Regex("^🔒 Protect PDF$"),
                protect_start
            )
        ],
        states={
            PROTECT_WAIT_PDF: [
                MessageHandler(
                    filters.Document.PDF,
                    protect_receive_pdf
                ),
                CallbackQueryHandler(
                    protect_back,
                    pattern="^protect_back$"
                )
            ],
            PROTECT_WAIT_PASSWORD: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    protect_receive_password
                ),
                CallbackQueryHandler(
                    protect_cancel,
                    pattern="^protect_cancel$"
                )
            ],
        },
        fallbacks=[
            CallbackQueryHandler(inline_back_handler, pattern="^back$"),
            CommandHandler("cancel", cancel)
        ],
    )

    # Merge PDF
    merge_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(merge_start, pattern="^merge$"),
            MessageHandler(
                filters.Regex("^🔗 Merge PDF$"),
                merge_start
            )
        ],
        states={
            MERGE_WAIT_FILES: [
                MessageHandler(
                    filters.Document.PDF,
                    merge_receive
                ),
                CommandHandler("done", merge_done),
                CallbackQueryHandler(
                    merge_cancel,
                    pattern="^merge_cancel$"
                )
            ],
            MERGE_WAIT_NAME: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    merge_receive_name
                )
            ]
        },
        fallbacks=[
            CallbackQueryHandler(inline_back_handler, pattern="^back$"),
            CommandHandler("cancel", cancel)
        ],
    )

    # Extract PDF text
    extract_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(extract_start, pattern="^extract$"),
            MessageHandler(
                filters.Regex("^📄 Extract PDF Text$"),
                extract_start
            )
        ],
        states={
            EXTRACT_WAIT_PDF: [
                MessageHandler(
                    filters.Document.PDF,
                    extract_receive
                )
            ]
        },
        fallbacks=[
            CallbackQueryHandler(extract_back, pattern="^extract_back$"),
            CommandHandler("cancel", cancel)
        ],
    )

    # Gemini summary
    summary_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(summarize_start, pattern="^summarize$"),
            MessageHandler(
                filters.Regex("^📝 Summarize PDF$"),
                summarize_start
            )
        ],
        states={
            SUMMARY_WAIT_PDF: [
                MessageHandler(
                    filters.Document.PDF,
                    summarize_receive
                )
            ]
        },
        fallbacks=[
            CallbackQueryHandler(summary_back, pattern="^summary_back$"),
            CommandHandler("cancel", cancel)
        ],
    )

    # Register handlers
    app.add_handler(protect_handler)
    app.add_handler(merge_handler)
    app.add_handler(extract_handler)
    app.add_handler(summary_handler)
    # Text to PDF
    text_to_pdf_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(text_to_pdf_start, pattern="^texttopdf$"),
            MessageHandler(
                filters.Regex("^📝 Text to PDF$"),
                text_to_pdf_start
            ),
            CommandHandler(
                "texttopdf",
                text_to_pdf_start
            )
        ],
        states={
    TEXT_TO_PDF_WAIT_TEXT: [
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            text_to_pdf_receive
        )
    ],
    TEXT_TO_PDF_WAIT_NAME: [
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            text_to_pdf_name
        )
    ]
},
        fallbacks=[]
    )

    # Register Text to PDF handler
    app.add_handler(text_to_pdf_handler)

    # Inline menu callbacks
    app.add_handler(
        CallbackQueryHandler(
            inline_main_menu_handler,
            pattern="^main_menu$"
        )
    )


    # More menu inline button
    app.add_handler(
        CallbackQueryHandler(
            more_menu,
            pattern="^more$"
        )
    )

    app.add_handler(
        CallbackQueryHandler(
            admin_menu,
            pattern="^admin_menu$"
        )
    )

    # Text to PDF inline button
    app.add_handler(
        CallbackQueryHandler(
            text_to_pdf_start,
            pattern="^texttopdf$"
        )
    )

    # Admin inline buttons
    app.add_handler(
        CallbackQueryHandler(
            admin_users_callback,
            pattern="^admin_users$"
        )
    )

    app.add_handler(
        CallbackQueryHandler(
            admin_broadcast_callback,
            pattern="^admin_broadcast$"
        )
    )

    # More/Admin navigation callbacks
    app.add_handler(
        CallbackQueryHandler(
            admin_back_callback,
            pattern="^admin_back$"
        )
    )

    app.add_handler(
        CallbackQueryHandler(
            admin_back_more_callback,
            pattern="^admin_back_more$"
        )
    )

    app.add_handler(
        CallbackQueryHandler(
            more_back_main_callback,
            pattern="^more_back_main$"
        )
    )

    # Coming Soon inline buttons
    app.add_handler(
        CallbackQueryHandler(
            coming_soon_callback,
            pattern="^(watermark|rotate|images|compress)$"
        )
    )

    # Menu buttons
    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            button_handler
        )
    )

    print("✅ NovaPDF AI is running...")


    # Render Web Service compatibility
    # Keep a lightweight HTTP server running while Telegram polling runs.
    import threading
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class RenderHealthHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"NovaPDF AI is running.")

        def log_message(self, format, *args):
            pass

    port = int(os.environ.get("PORT", 10000))

    health_server = HTTPServer(("0.0.0.0", port), RenderHealthHandler)

    threading.Thread(
        target=health_server.serve_forever,
        daemon=True
    ).start()

    logger.info(f"Render health server running on port {port}")

    app.run_polling()


# =========================
# START BOT
# =========================

if __name__ == "__main__":
    main()
