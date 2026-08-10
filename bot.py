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
from PIL import Image, ImageDraw, ImageFont
from images_to_pdf_functions import *
from unlock_pdf_functions import *
from qr_code_functions import *
from reportlab.pdfgen import canvas
from reportlab.lib.colors import Color
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

DEJAVU_FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
DEJAVU_BOLD_FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

if os.path.exists(DEJAVU_FONT) and os.path.exists(DEJAVU_BOLD_FONT):
    pdfmetrics.registerFont(TTFont("DejaVuSans", DEJAVU_FONT))
    pdfmetrics.registerFont(TTFont("DejaVuSans-Bold", DEJAVU_BOLD_FONT))
else:
    DEJAVU_FONT = None
    DEJAVU_BOLD_FONT = None


# =========================
# CONFIGURATION
# =========================

TOKEN = os.getenv("BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

ADMIN_ID = 8720336056

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
PROTECT_WAIT_NAME = 27
MERGE_WAIT_FILES = 3
EXTRACT_WAIT_PDF = 4
SUMMARY_WAIT_PDF = 5
TEXT_TO_PDF_WAIT_TEXT = 6
TEXT_TO_PDF_WAIT_NAME = 7
TEXT_TO_PDF_WAIT_CUSTOMIZE = 21
MERGE_WAIT_NAME = 8
WATERMARK_WAIT_FILE = 9
WATERMARK_WAIT_TEXT = 10
WATERMARK_WAIT_NAME = 11
WATERMARK_WAIT_COLOR = 12
ROTATE_WAIT_FILE = 13
ROTATE_WAIT_ANGLE = 14
ROTATE_WAIT_NAME = 15
IMAGES_WAIT_FILE = 16
IMAGES_WAIT_FORMAT = 17
COMPRESS_WAIT_FILE = 18
COMPRESS_WAIT_NAME = 19
COMPRESS_WAIT_LEVEL = 20
AI_SUMMARIZER_WAIT_INPUT = 28
AI_SUMMARIZER_WAIT_OUTPUT = 29
AI_SUMMARIZER_WAIT_NAME = 30





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


async def remove_prompt_cancel_button(update, context, key):
    """Remove the Cancel button from a previous prompt message."""
    message_id = context.user_data.get(key)

    if not message_id:
        return

    try:
        await context.bot.edit_message_reply_markup(
            chat_id=update.effective_chat.id,
            message_id=message_id,
            reply_markup=None
        )
    except Exception as e:
        logger.warning(
            f"Could not remove Cancel button from prompt {message_id}: {e}"
        )

    context.user_data.pop(key, None)



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


async def send_invalid_file(
    update: Update,
    message_text: str,
    cancel_callback: str
):
    await update.effective_message.reply_text(
        message_text,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(
                "❌ Cancel",
                callback_data=cancel_callback
            )]
        ])
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
        [InlineKeyboardButton(
            "❌ Cancel",
            callback_data="protect_cancel"
        )]
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
        await send_invalid_file(
            update,
            "❌ Invalid file.\nPlease send a PDF file.",
            "protect_cancel"
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

        # Detect PDFs that are already password-protected.
        reader = PdfReader(input_path)

        if reader.is_encrypted:
            shutil.rmtree(
                temp_dir,
                ignore_errors=True
            )

            context.user_data.clear()

            await update.effective_message.reply_text(
                "🔒 This PDF is already password-protected.\n\n"
                "It cannot be protected again.",
                reply_markup=main_menu_button()
            )

            return ConversationHandler.END

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
            shutil.rmtree(temp_dir, ignore_errors=True)
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
    await remove_prompt_cancel_button(
        update, context, "protect_password_message_id"
    )

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

    context.user_data["protect_password"] = password

    name_message = await update.effective_message.reply_text(
        "🔐 Password saved.\n\n"
        "📝 Now enter the name you want for the protected PDF "
        "(without .pdf).",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(
                "❌ Cancel",
                callback_data="protect_cancel"
            )]
        ])
    )

    context.user_data["protect_name_message_id"] = name_message.message_id

    return PROTECT_WAIT_NAME

async def protect_receive_name(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    await remove_prompt_cancel_button(
        update, context, "protect_name_message_id"
    )

    name = update.effective_message.text.strip()

    if not name:
        await update.effective_message.reply_text(
            "❌ Please enter a valid file name."
        )
        return PROTECT_WAIT_NAME

    name = name.replace("/", "_").replace("\\", "_")

    if not name.lower().endswith(".pdf"):
        name += ".pdf"

    input_path = context.user_data.get("protect_input")
    temp_dir = context.user_data.get("protect_dir")
    password = context.user_data.get("protect_password")

    if not input_path or not temp_dir or not password:
        await update.effective_message.reply_text(
            "❌ Protection session expired. Please start again."
        )
        return ConversationHandler.END

    output_path = os.path.join(temp_dir, name)

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
                filename=name,
                caption="🔐 Your PDF has been password-protected.",
                reply_markup=main_menu_button()
            )


    except Exception as e:
        logger.error(f"Protection error: {e}")

        await update.effective_message.reply_text(
            "❌ Unable to protect this PDF.",
            reply_markup=main_menu_button()
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
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(
                    "❌ Cancel",
                    callback_data="merge_cancel"
                )]
            ])
        )

        context.user_data["merge_prompt_message_id"] = (
            query.message.message_id
        )

    else:
        message = await update.effective_message.reply_text(
            "🔗 Send the PDF files you want to merge.\n\n"
            "Send them one after another.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(
                    "❌ Cancel",
                    callback_data="merge_cancel"
                )]
            ])
        )

        context.user_data["merge_prompt_message_id"] = (
            message.message_id
        )

    return MERGE_WAIT_FILES


async def merge_receive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await remove_prompt_cancel_button(
        update, context, "merge_prompt_message_id"
    )

    document = update.effective_message.document

    if not document:
        return MERGE_WAIT_FILES

    if document.mime_type != "application/pdf":
        await send_invalid_file(
            update,
            "❌ Invalid file.\nPlease send a PDF file.",
            "merge_cancel"
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

        prompt = await update.effective_message.reply_text(
            f"✅ PDF {number} received.\n\n"
            "📄 Send another PDF or type /done when you're finished.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("❌ Cancel", callback_data="merge_cancel")]
            ])
        )

        context.user_data["merge_prompt_message_id"] = prompt.message_id

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
    await remove_prompt_cancel_button(
        update, context, "merge_name_message_id"
    )

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
            "❌ Unable to merge the PDF files.",
            reply_markup=main_menu_button()
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

def text_to_pdf_customize_keyboard(context):
    font = context.user_data.get("text_pdf_font", "Helvetica")
    color = context.user_data.get("text_pdf_color", "black")
    page_numbers = context.user_data.get("text_pdf_page_numbers", False)

    font_names = {
        "Helvetica": "Helvetica",
        "Times-Roman": "Times",
        "Courier": "Courier"
    }

    color_names = {
        "black": "Black",
        "blue": "Blue",
        "red": "Red"
    }

    page_status = "ON" if page_numbers else "OFF"

    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                f"🔤 Font: {font_names.get(font, font)}",
                callback_data="textpdf_font"
            )
        ],
        [
            InlineKeyboardButton(
                f"🎨 Text Color: {color_names.get(color, color)}",
                callback_data="textpdf_color"
            )
        ],
        [
            InlineKeyboardButton(
                f"🔢 Page Numbers: {page_status}",
                callback_data="textpdf_pages"
            )
        ],
        [
            InlineKeyboardButton(
                "✅ Create PDF",
                callback_data="textpdf_create"
            )
        ],
        [
            InlineKeyboardButton(
                "❌ Cancel",
                callback_data="texttopdf_cancel"
            )
        ]
    ])


def text_to_pdf_font_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "Arial",
                callback_data="textpdf_font_helvetica"
            ),
            InlineKeyboardButton(
                "Times New Roman",
                callback_data="textpdf_font_times"
            )
        ],
        [
            InlineKeyboardButton(
                "Courier",
                callback_data="textpdf_font_courier"
            )
        ],
        [
            InlineKeyboardButton(
                "⬅️ Back",
                callback_data="textpdf_customize"
            )
        ]
    ])


def text_to_pdf_color_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "⚫ Black",
                callback_data="textpdf_color_black"
            ),
            InlineKeyboardButton(
                "🔵 Blue",
                callback_data="textpdf_color_blue"
            )
        ],
        [
            InlineKeyboardButton(
                "🔴 Red",
                callback_data="textpdf_color_red"
            )
        ],
        [
            InlineKeyboardButton(
                "⬅️ Back",
                callback_data="textpdf_customize"
            )
        ]
    ])


async def text_to_pdf_cancel(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    query = update.callback_query
    await query.answer()

    context.user_data.clear()

    try:
        await query.message.edit_text(
            "🏠 NovaPDF AI\n\nChoose a tool:",
            reply_markup=main_keyboard()
        )
    except Exception as e:
        logger.warning(
            f"Could not restore main menu after Text-to-PDF cancel: {e}"
        )

    return ConversationHandler.END


async def text_to_pdf_start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    query = update.callback_query

    if query:
        await query.answer()
        message = query.message
    else:
        message = update.effective_message

    context.user_data.clear()

    context.user_data["text_pdf_font"] = "Helvetica"
    context.user_data["text_pdf_color"] = "black"
    context.user_data["text_pdf_page_numbers"] = False

    text = (
        "📝 Send the text you want to convert to PDF.\n\n"
        "You can send a short or long text."
    )

    if query:
        await message.edit_text(
            text,
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        "❌ Cancel",
                        callback_data="texttopdf_cancel"
                    )
                ]
            ])
        )
    else:
        await message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        "❌ Cancel",
                        callback_data="texttopdf_cancel"
                    )
                ]
            ])
        )

    return TEXT_TO_PDF_WAIT_TEXT


async def text_to_pdf_receive(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    await remove_prompt_cancel_button(
        update,
        context,
        "text_pdf_prompt_message_id"
    )

    text = update.effective_message.text

    if not text or not text.strip():
        await update.effective_message.reply_text(
            "❌ Please send some text."
        )
        return TEXT_TO_PDF_WAIT_TEXT

    existing_text = context.user_data.get(
        "pdf_text",
        ""
    )

    if existing_text:
        context.user_data["pdf_text"] = (
            existing_text + "\n" + text
        )
    else:
        context.user_data["pdf_text"] = text

    prompt = await update.effective_message.reply_text(
        "✅ Text received.\n\n"
        "You can send more text if needed.\n"
        "When you are finished, tap **Done**.",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    "✅ Done",
                    callback_data="textpdf_text_done"
                )
            ],
            [
                InlineKeyboardButton(
                    "❌ Cancel",
                    callback_data="texttopdf_cancel"
                )
            ]
        ])
    )

    context.user_data["text_pdf_prompt_message_id"] = (
        prompt.message_id
    )

    return TEXT_TO_PDF_WAIT_TEXT


async def text_to_pdf_text_done(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    query = update.callback_query
    await query.answer()

    text = context.user_data.get(
        "pdf_text",
        ""
    )

    if not text.strip():
        await query.message.edit_text(
            "❌ Please send some text first.",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        "❌ Cancel",
                        callback_data="texttopdf_cancel"
                    )
                ]
            ])
        )
        return TEXT_TO_PDF_WAIT_TEXT

    await query.message.edit_text(
        "📄 What would you like to name your PDF?\n\n"
        "Example: Biology Notes\n\n"
        "You don't need to type .pdf",
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    "❌ Cancel",
                    callback_data="texttopdf_cancel"
                )
            ]
        ])
    )

    context.user_data["text_pdf_prompt_message_id"] = (
        query.message.message_id
    )

    return TEXT_TO_PDF_WAIT_NAME


async def text_to_pdf_name(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    await remove_prompt_cancel_button(
        update,
        context,
        "text_pdf_prompt_message_id"
    )

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

    context.user_data["pdf_name"] = safe_name

    await update.effective_message.reply_text(
        "🎨 Customize your PDF\n\n"
        "Choose what you want to change:",
        reply_markup=text_to_pdf_customize_keyboard(context)
    )

    return TEXT_TO_PDF_WAIT_CUSTOMIZE


async def text_to_pdf_customize(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    query = update.callback_query
    await query.answer()

    await query.message.edit_text(
        "🎨 Customize your PDF\n\n"
        "Choose what you want to change:",
        reply_markup=text_to_pdf_customize_keyboard(context)
    )

    return TEXT_TO_PDF_WAIT_CUSTOMIZE


async def text_to_pdf_font_menu(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    query = update.callback_query
    await query.answer()

    await query.message.edit_text(
        "🔤 Choose a font:",
        reply_markup=text_to_pdf_font_keyboard()
    )

    return TEXT_TO_PDF_WAIT_CUSTOMIZE


async def text_to_pdf_font_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    query = update.callback_query
    await query.answer()

    font_map = {
        "textpdf_font_helvetica": "Helvetica",
        "textpdf_font_times": "Times-Roman",
        "textpdf_font_courier": "Courier"
    }

    context.user_data["text_pdf_font"] = font_map.get(
        query.data,
        "Helvetica"
    )

    await query.message.edit_text(
        "🎨 Customize your PDF\n\n"
        "Choose what you want to change:",
        reply_markup=text_to_pdf_customize_keyboard(context)
    )

    return TEXT_TO_PDF_WAIT_CUSTOMIZE


async def text_to_pdf_color_menu(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    query = update.callback_query
    await query.answer()

    await query.message.edit_text(
        "🎨 Choose a text color:",
        reply_markup=text_to_pdf_color_keyboard()
    )

    return TEXT_TO_PDF_WAIT_CUSTOMIZE


async def text_to_pdf_color_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    query = update.callback_query
    await query.answer()

    color_map = {
        "textpdf_color_black": "black",
        "textpdf_color_blue": "blue",
        "textpdf_color_red": "red"
    }

    context.user_data["text_pdf_color"] = color_map.get(
        query.data,
        "black"
    )

    await query.message.edit_text(
        "🎨 Customize your PDF\n\n"
        "Choose what you want to change:",
        reply_markup=text_to_pdf_customize_keyboard(context)
    )

    return TEXT_TO_PDF_WAIT_CUSTOMIZE


async def text_to_pdf_pages_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    query = update.callback_query
    await query.answer()

    current = context.user_data.get(
        "text_pdf_page_numbers",
        False
    )

    context.user_data["text_pdf_page_numbers"] = not current

    await query.message.edit_text(
        "🎨 Customize your PDF\n\n"
        "Choose what you want to change:",
        reply_markup=text_to_pdf_customize_keyboard(context)
    )

    return TEXT_TO_PDF_WAIT_CUSTOMIZE


async def text_to_pdf_create(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    query = update.callback_query
    await query.answer()

    text = context.user_data.get("pdf_text")
    pdf_name = context.user_data.get("pdf_name", "NovaPDF")

    if not text:
        await query.message.edit_text(
            "❌ Your text could not be found.",
            reply_markup=main_menu_button()
        )
        context.user_data.clear()
        return ConversationHandler.END

    font = context.user_data.get(
        "text_pdf_font",
        "Helvetica"
    )

    color_name = context.user_data.get(
        "text_pdf_color",
        "black"
    )

    page_numbers = context.user_data.get(
        "text_pdf_page_numbers",
        False
    )

    color_map = {
        "black": "black",
        "blue": "blue",
        "red": "red"
    }

    try:
        await query.message.edit_text(
            "⏳ Creating your customized PDF..."
        )

        from reportlab.lib.pagesizes import A4
        from reportlab.platypus import (
            SimpleDocTemplate,
            Paragraph,
            Spacer
        )
        from reportlab.lib.styles import (
            getSampleStyleSheet,
            ParagraphStyle
        )
        from reportlab.lib.enums import TA_LEFT
        from reportlab.lib.units import mm
        from reportlab.lib import colors
        from xml.sax.saxutils import escape

        pdf_path = f"{pdf_name}.pdf"

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
            "NovaPDFBody",
            parent=styles["BodyText"],
            fontName=font,
            fontSize=11,
            leading=16,
            alignment=TA_LEFT,
            textColor=getattr(
                colors,
                color_map.get(color_name, "black")
            ),
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

        def add_page_number(canvas, doc):
            canvas.saveState()

            canvas.setFont(
                "Helvetica",
                9
            )

            canvas.setFillColor(colors.grey)

            canvas.drawCentredString(
                A4[0] / 2,
                10 * mm,
                f"{doc.page}"
            )

            canvas.restoreState()

        if page_numbers:
            doc.build(
                story,
                onFirstPage=add_page_number,
                onLaterPages=add_page_number
            )
        else:
            doc.build(story)

        with open(pdf_path, "rb") as pdf_file:
            await query.message.reply_document(
                document=pdf_file,
                filename=f"{pdf_name}.pdf",
                caption=f"📄 {pdf_name}.pdf created successfully.",
                reply_markup=main_menu_button()
            )

        import os

        if os.path.exists(pdf_path):
            os.remove(pdf_path)

        context.user_data.clear()

        return ConversationHandler.END

    except Exception as e:
        logger.error(
            f"Text to PDF error: {e}"
        )

        await query.message.edit_text(
            "❌ Sorry, I couldn't create the PDF.",
            reply_markup=main_menu_button()
        )

        context.user_data.clear()

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
        [InlineKeyboardButton(
            "❌ Cancel",
            callback_data="extract_back"
        )]
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
    await remove_prompt_cancel_button(
        update, context, "extract_prompt_message_id"
    )

    document = update.effective_message.document

    if not document:
        return EXTRACT_WAIT_PDF

    if document.mime_type != "application/pdf":
        await send_invalid_file(
            update,
            "❌ Invalid file.\nPlease send a PDF file.",
            "extract_back"
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
# =========================
# AI TOPIC SUMMARIZER
# =========================

def ai_summarizer_input_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ Cancel", callback_data="ai_summarizer_cancel")]
    ])


def ai_summarizer_output_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📱 Send as Text", callback_data="ai_summary_text"),
            InlineKeyboardButton("📄 Send as PDF", callback_data="ai_summary_pdf")
        ],
        [
            InlineKeyboardButton("❌ Cancel", callback_data="ai_summarizer_cancel")
        ]
    ])


def ai_summarizer_name_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ Cancel", callback_data="ai_summarizer_cancel")]
    ])


async def ai_summarizer_start(update, context):
    query = update.callback_query

    if query:
        await query.answer()
        message = query.message
        await message.edit_text(
            "🧠 <b>AI Explainer</b>\n\n"
            "Send me any topic, text, notes, or information "
            "you want Nova AI to summarize.\n\n"
            "Example:\n"
            "<i>Explain photosynthesis and its stages</i>",
            parse_mode="HTML",
            reply_markup=ai_summarizer_input_keyboard()
        )
    else:
        message = await update.effective_message.reply_text(
            "🧠 <b>AI Explainer</b>\n\n"
            "Send me any topic, text, notes, or information "
            "you want Nova AI to summarize.\n\n"
            "Example:\n"
            "<i>Explain photosynthesis and its stages</i>",
            parse_mode="HTML",
            reply_markup=ai_summarizer_input_keyboard()
        )

    context.user_data["ai_summarizer_prompt_message_id"] = message.message_id

    return AI_SUMMARIZER_WAIT_INPUT


async def ai_summarizer_receive(update, context):
    text = update.effective_message.text

    if not text or not text.strip():
        await update.effective_message.reply_text(
            "❌ Please send a topic or some text to summarize.",
            reply_markup=ai_summarizer_input_keyboard()
        )
        return AI_SUMMARIZER_WAIT_INPUT

    prompt_message_id = context.user_data.get(
        "ai_summarizer_prompt_message_id"
    )

    if prompt_message_id:
        try:
            await context.bot.edit_message_reply_markup(
                chat_id=update.effective_chat.id,
                message_id=prompt_message_id,
                reply_markup=None
            )
        except Exception:
            pass

    context.user_data["ai_summarizer_input"] = text.strip()

    await update.effective_message.reply_text(
        "⏳ <b>Nova AI is preparing your explanation...</b>\n\n"
        "🤖 Please wait.",
        parse_mode="HTML"
    )

    summary = await gemini_summarize(text.strip())

    if not summary:
        context.user_data.clear()

        await update.effective_message.reply_text(
            "❌ Nova AI couldn't generate a summary right now.",
            reply_markup=main_menu_button()
        )

        return ConversationHandler.END

    context.user_data["ai_summarizer_summary"] = summary

    await update.effective_message.reply_text(
        "✅ <b>Summary generated!</b>\n\n"
        "How would you like to receive it?",
        parse_mode="HTML",
        reply_markup=ai_summarizer_output_keyboard()
    )

    return AI_SUMMARIZER_WAIT_OUTPUT


async def ai_summarizer_send_text(update, context):
    query = update.callback_query
    await query.answer()

    summary = context.user_data.get("ai_summarizer_summary")

    if not summary:
        context.user_data.clear()

        await query.message.edit_text(
            "❌ Your summary session expired.",
            reply_markup=main_keyboard()
        )

        return ConversationHandler.END

    await query.message.edit_text("📝 <b>Nova AI Summary</b>", parse_mode="HTML")

    chunk_size = 3500

    for start in range(0, len(summary), chunk_size):
        chunk = summary[start:start + chunk_size].strip()

        if chunk:
            is_last = start + chunk_size >= len(summary)

            await query.message.reply_text(
                chunk,
                reply_markup=main_menu_button() if is_last else None
            )

    context.user_data.clear()

    return ConversationHandler.END


async def ai_summarizer_pdf(update, context):
    query = update.callback_query
    await query.answer()

    if not context.user_data.get("ai_summarizer_summary"):
        context.user_data.clear()

        await query.message.edit_text(
            "❌ Your summary session expired.",
            reply_markup=main_keyboard()
        )

        return ConversationHandler.END

    await query.message.edit_text(
        "📄 <b>PDF output selected.</b>\n\n"
        "📝 Enter the name you want for the PDF.\n\n"
        "Example: Photosynthesis Summary",
        parse_mode="HTML",
        reply_markup=ai_summarizer_name_keyboard()
    )

    context.user_data["ai_summarizer_name_prompt_message_id"] = (
        query.message.message_id
    )

    return AI_SUMMARIZER_WAIT_NAME


async def ai_summarizer_receive_name(update, context):
    prompt_message_id = context.user_data.get(
        "ai_summarizer_name_prompt_message_id"
    )

    if prompt_message_id:
        try:
            await context.bot.edit_message_reply_markup(
                chat_id=update.effective_chat.id,
                message_id=prompt_message_id,
                reply_markup=None
            )
        except Exception:
            pass

    name = update.effective_message.text.strip()

    if not name:
        await update.effective_message.reply_text(
            "❌ Please enter a valid PDF name.",
            reply_markup=ai_summarizer_name_keyboard()
        )
        return AI_SUMMARIZER_WAIT_NAME

    name = name.replace("/", "_").replace("\\", "_")

    if not name.lower().endswith(".pdf"):
        name += ".pdf"

    explanation = context.user_data.get("ai_summarizer_summary")

    if not explanation:
        context.user_data.clear()

        await update.effective_message.reply_text(
            "❌ Your explanation session expired.",
            reply_markup=main_menu_button()
        )

        return ConversationHandler.END

    temp_dir = tempfile.mkdtemp(prefix="nova_ai_explanation_")
    output_path = os.path.join(temp_dir, name)

    try:
        await update.effective_message.reply_text(
            "⏳ Creating your AI explanation PDF..."
        )

        styles = getSampleStyleSheet()

        title_style = styles["Title"].clone("NovaTitle")
        title_style.fontName = "DejaVuSans-Bold" if DEJAVU_BOLD_FONT else "Helvetica-Bold"
        title_style.fontSize = 20
        title_style.leading = 25
        title_style.spaceAfter = 16

        heading_style = styles["Heading2"].clone("NovaHeading")
        heading_style.fontName = "DejaVuSans-Bold" if DEJAVU_BOLD_FONT else "Helvetica-Bold"
        heading_style.fontSize = 14
        heading_style.leading = 19
        heading_style.spaceBefore = 12
        heading_style.spaceAfter = 7

        body_style = styles["BodyText"].clone("NovaBody")
        body_style.fontName = "DejaVuSans" if DEJAVU_FONT else "Helvetica"
        body_style.fontSize = 10.5
        body_style.leading = 16
        body_style.spaceAfter = 8

        bullet_style = styles["BodyText"].clone("NovaBullet")
        bullet_style.fontName = "DejaVuSans" if DEJAVU_FONT else "Helvetica"
        bullet_style.fontSize = 10.5
        bullet_style.leading = 16
        bullet_style.leftIndent = 18
        bullet_style.firstLineIndent = -10
        bullet_style.spaceAfter = 5

        doc = SimpleDocTemplate(
            output_path,
            pagesize=A4,
            rightMargin=45,
            leftMargin=45,
            topMargin=50,
            bottomMargin=50,
            title=name[:-4],
            author="NovaPDF AI"
        )

        story = []

        lines = explanation.splitlines()
        title_added = False

        import html

        for raw_line in lines:
            line = raw_line.strip()

            if not line:
                story.append(Spacer(1, 5))
                continue

            # Remove Markdown heading markers.
            heading_match = re.match(r"^#{1,6}\s+(.*)$", line)

            if heading_match:
                heading = html.escape(heading_match.group(1).strip())

                if not title_added:
                    story.append(
                        Paragraph(heading, title_style)
                    )
                    title_added = True
                else:
                    story.append(
                        Paragraph(heading, heading_style)
                    )

                continue

            # Detect bullet points.
            bullet_match = re.match(
                r"^[-*•]\s+(.*)$",
                line
            )

            if bullet_match:
                content = html.escape(
                    bullet_match.group(1).strip()
                )

                story.append(
                    Paragraph(
                        "• " + content,
                        bullet_style
                    )
                )
                continue

            # Detect numbered lists.
            number_match = re.match(
                r"^(\d+)[.)]\s+(.*)$",
                line
            )

            if number_match:
                number = number_match.group(1)
                content = html.escape(
                    number_match.group(2).strip()
                )

                story.append(
                    Paragraph(
                        f"{number}. {content}",
                        bullet_style
                    )
                )
                continue

            # Convert simple Markdown bold/italic formatting.
            escaped = html.escape(line)

            escaped = re.sub(
                r"\*\*(.+?)\*\*",
                r"<b>\1</b>",
                escaped
            )

            escaped = re.sub(
                r"__(.+?)__",
                r"<b>\1</b>",
                escaped
            )

            escaped = re.sub(
                r"\*(.+?)\*",
                r"<i>\1</i>",
                escaped
            )

            story.append(
                Paragraph(
                    escaped,
                    body_style
                )
            )

        if not title_added:
            story.insert(
                0,
                Paragraph(
                    "NovaPDF AI — AI Explanation",
                    title_style
                )
            )

        def add_page_number(canvas_obj, doc_obj):
            canvas_obj.saveState()

            page_font = "DejaVuSans" if DEJAVU_FONT else "Helvetica"

            canvas_obj.setFont(page_font, 8)
            canvas_obj.drawCentredString(
                A4[0] / 2,
                25,
                f"NovaPDF AI  •  Page {doc_obj.page}"
            )

            canvas_obj.restoreState()

        doc.build(
            story,
            onFirstPage=add_page_number,
            onLaterPages=add_page_number
        )

        with open(output_path, "rb") as pdf_file:
            await update.effective_message.reply_document(
                document=pdf_file,
                filename=name,
                caption="📄 Your Nova AI explanation.",
                reply_markup=main_menu_button()
            )

    except Exception as e:
        logger.error(
            f"AI explanation PDF error: {e}"
        )

        await update.effective_message.reply_text(
            f"❌ PDF error: {type(e).__name__}: {e}",
            reply_markup=main_menu_button()
        )

    finally:
        shutil.rmtree(
            temp_dir,
            ignore_errors=True
        )
        context.user_data.clear()

    return ConversationHandler.END


async def ai_summarizer_cancel(update, context):
    query = update.callback_query
    await query.answer()

    context.user_data.clear()

    await query.message.edit_text(
        "🏠 NovaPDF AI\n\nChoose a tool:",
        reply_markup=main_keyboard()
    )

    return ConversationHandler.END


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
    await remove_prompt_cancel_button(
        update, context, "summary_prompt_message_id"
    )

    document = update.effective_message.document

    if not document:
        return SUMMARY_WAIT_PDF

    if document.mime_type != "application/pdf":
        await send_invalid_file(
            update,
            "❌ Invalid file.\nPlease send a PDF file.",
            "summarize_cancel"
        )
        return SUMMARY_WAIT_PDF

    temp_dir = tempfile.mkdtemp()
    input_path = os.path.join(temp_dir, "input.pdf")

    try:
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
You are NovaPDF AI's AI Explainer.

The user's input may be a topic, question, concept, text, notes, instructions, or general information.

Your task is to produce the best possible explanation of the input. Give a complete, accurate, useful explanation rather than a short summary.

OUTPUT REQUIREMENTS:

1. TITLE
- Begin with a clear, relevant title.
- Do not write labels such as "Summary:" unless the user specifically asks for a summary.

2. STRUCTURE
- Organize the explanation with clear headings and subheadings.
- Use short paragraphs.
- Use numbered lists for processes or sequential steps.
- Use bullet points for grouped facts, characteristics, examples, advantages, disadvantages, or key points.
- Leave clear spacing between sections.
- Do not create unnecessarily long walls of text.

3. EXPLANATION
- Define important terms clearly.
- Explain the main idea before going into details.
- Cover the important concepts systematically.
- Include relevant characteristics, types, classifications, causes, effects, functions, mechanisms, processes, applications, advantages, disadvantages, examples, or comparisons when applicable.
- If the input is a question, answer it directly first and then explain it.
- If the topic is broad, cover its major areas rather than giving an overly short response.
- Make difficult ideas easier to understand without removing important technical details.

4. SCIENTIFIC AND TECHNICAL ACCURACY
- Preserve scientific symbols correctly.
- Use Greek letters correctly, such as α, β, γ, Δ, μ, σ, θ, λ, and π.
- Format mathematical formulas clearly.
- Preserve chemical formulas and equations correctly, such as H₂O, CO₂, O₂, NaCl, and C₆H₁₂O₆.
- Preserve units correctly, such as kg, m, s, °C, mol, Pa, and N.
- Do not replace symbols with awkward words when the proper symbol is appropriate.
- Explain important symbols, formulas, and equations when necessary.
- Do not invent formulas or scientific information.

5. READABILITY
- Keep related information together.
- Avoid unnecessary repetition.
- Avoid excessive emojis.
- Use clean formatting that works well when displayed as Telegram text.
- Do not use tables unless they genuinely improve the explanation.
- Do not produce broken Markdown, HTML, or unusual formatting characters.
- Do not place punctuation or symbols randomly on separate lines.
- Make headings visually distinct and easy to scan.

6. ACCURACY
- Do not invent facts.
- Do not knowingly provide unsupported claims.
- If information is uncertain or depends on context, clearly indicate that instead of presenting it as certain.
- Do not mention these instructions, the prompt, the model, internal reasoning, or hidden processes.

7. ACADEMIC TOPICS
- Explain academic subjects at an appropriate university/college level when applicable.
- Include terminology and definitions students are expected to know.
- Explain processes step by step.
- Include examples where useful.
- Make the explanation useful for both learning and revision.

8. GENERAL TOPICS
- Do not assume the user is asking an academic question.
- Explain technology, finance, everyday concepts, science, business, history, language, and other subjects according to the subject itself.
- Adapt the depth and terminology to the topic.

Return ONLY the final explanation.

INPUT:
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
# WATERMARK
# =========================

def watermark_cancel_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ Cancel", callback_data="watermark_cancel")]
    ])


def watermark_color_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⚫ Black", callback_data="wm_color_black"),
            InlineKeyboardButton("⚪ White", callback_data="wm_color_white")
        ],
        [
            InlineKeyboardButton("🔴 Red", callback_data="wm_color_red"),
            InlineKeyboardButton("🔵 Blue", callback_data="wm_color_blue")
        ],
        [
            InlineKeyboardButton("🟢 Green", callback_data="wm_color_green"),
            InlineKeyboardButton("🟡 Yellow", callback_data="wm_color_yellow")
        ],
        [
            InlineKeyboardButton("❌ Cancel", callback_data="watermark_cancel")
        ]
    ])


WATERMARK_COLORS = {
    "black": (0, 0, 0),
    "white": (255, 255, 255),
    "red": (220, 0, 0),
    "blue": (0, 80, 220),
    "green": (0, 150, 70),
    "yellow": (220, 180, 0),
}


async def watermark_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query

    if query:
        await query.answer()
        message = query.message
    else:
        message = update.effective_message

    context.user_data.clear()

    await message.edit_text(
        "💧 Watermark\n\n"
        "Send the PDF or image you want to watermark.\n\n"
        "Supported: PDF, JPG, JPEG, PNG",
        reply_markup=watermark_cancel_keyboard()
    )

    context.user_data["watermark_prompt_message_id"] = message.message_id

    return WATERMARK_WAIT_FILE


async def remove_watermark_cancel_button(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    message_id: int
):
    try:
        await context.bot.edit_message_reply_markup(
            chat_id=chat_id,
            message_id=message_id,
            reply_markup=None
        )
    except Exception as e:
        logger.warning(
            f"Could not remove watermark Cancel button: {e}"
        )


async def watermark_receive_file(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    await remove_prompt_cancel_button(
        update, context, "watermark_prompt_message_id"
    )

    document = update.effective_message.document
    photo = update.effective_message.photo

    if not document and not photo:
        await update.effective_message.reply_text(
            "❌ Please send a PDF or image."
        )
        return WATERMARK_WAIT_FILE

    prompt_message_id = context.user_data.get(
        "watermark_prompt_message_id"
    )

    if prompt_message_id:
        await remove_watermark_cancel_button(
            context,
            update.effective_chat.id,
            prompt_message_id
        )

    temp_dir = tempfile.mkdtemp()

    try:
        if document:
            filename = document.file_name or "input"

            if document.mime_type == "application/pdf":
                extension = ".pdf"

            elif (
                document.mime_type
                and document.mime_type.startswith("image/")
            ):
                extension = (
                    os.path.splitext(filename)[1].lower()
                    or ".jpg"
                )

            else:
                await update.effective_message.reply_text(
                    "❌ Please send a PDF or JPG/PNG image."
                )

                os.rmdir(temp_dir)
                return WATERMARK_WAIT_FILE

            input_path = os.path.join(
                temp_dir,
                "input" + extension
            )

            file = await document.get_file()
            await file.download_to_drive(input_path)

        else:
            input_path = os.path.join(
                temp_dir,
                "input.jpg"
            )

            file = await photo[-1].get_file()
            await file.download_to_drive(input_path)

        context.user_data["watermark_dir"] = temp_dir
        context.user_data["watermark_input"] = input_path

        prompt = await update.effective_message.reply_text(
            "✅ File received.\n\n"
            "✏️ Now send the text you want to use as the watermark.\n\n"
            "Example: Confidential",
            reply_markup=watermark_cancel_keyboard()
        )

        context.user_data["watermark_prompt_message_id"] = (
            prompt.message_id
        )

        return WATERMARK_WAIT_TEXT

    except Exception as e:
        logger.error(
            f"Watermark receive error: {e}"
        )

        try:
            for filename in os.listdir(temp_dir):
                os.remove(os.path.join(temp_dir, filename))
            os.rmdir(temp_dir)
        except Exception:
            pass

        await update.effective_message.reply_text(
            "❌ I couldn't receive that file."
        )

        return WATERMARK_WAIT_FILE


async def watermark_receive_text(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    await remove_prompt_cancel_button(
        update, context, "watermark_prompt_message_id"
    )

    text = update.effective_message.text.strip()

    if not text:
        await update.effective_message.reply_text(
            "❌ Please send watermark text."
        )
        return WATERMARK_WAIT_TEXT

    prompt_message_id = context.user_data.get(
        "watermark_prompt_message_id"
    )

    if prompt_message_id:
        await remove_watermark_cancel_button(
            context,
            update.effective_chat.id,
            prompt_message_id
        )

    context.user_data["watermark_text"] = text

    prompt = await update.effective_message.reply_text(
        "📄 What would you like to name the watermarked file?\n\n"
        "Example: My Document\n\n"
        "You don't need to type .pdf or .jpg",
        reply_markup=watermark_cancel_keyboard()
    )

    context.user_data["watermark_prompt_message_id"] = (
        prompt.message_id
    )

    return WATERMARK_WAIT_NAME


async def watermark_receive_name(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    await remove_prompt_cancel_button(
        update, context, "watermark_prompt_message_id"
    )

    name = update.effective_message.text.strip()

    if not name:
        await update.effective_message.reply_text(
            "❌ Please enter a file name."
        )
        return WATERMARK_WAIT_NAME

    prompt_message_id = context.user_data.get(
        "watermark_prompt_message_id"
    )

    if prompt_message_id:
        await remove_watermark_cancel_button(
            context,
            update.effective_chat.id,
            prompt_message_id
        )

    name = os.path.splitext(name)[0]

    safe_name = "".join(
        c for c in name
        if c.isalnum() or c in " -_()"
    ).strip()

    if not safe_name:
        await update.effective_message.reply_text(
            "❌ Please choose a valid file name.",
            reply_markup=watermark_cancel_keyboard()
        )
        return WATERMARK_WAIT_NAME

    context.user_data["watermark_name"] = safe_name

    prompt = await update.effective_message.reply_text(
        "🎨 Choose the watermark color:",
        reply_markup=watermark_color_keyboard()
    )

    context.user_data["watermark_prompt_message_id"] = (
        prompt.message_id
    )

    return WATERMARK_WAIT_COLOR


async def create_pdf_watermark(
    watermark_path,
    text,
    page_width,
    page_height,
    color
):
    c = canvas.Canvas(
        watermark_path,
        pagesize=(page_width, page_height)
    )

    c.saveState()

    r, g, b = color

    c.setFillColor(
        Color(
            r / 255,
            g / 255,
            b / 255,
            alpha=0.20
        )
    )

    font_size = min(
        max(page_width, page_height) * 0.07,
        65
    )

    c.setFont(
        "Helvetica-Bold",
        font_size
    )

    c.translate(
        page_width / 2,
        page_height / 2
    )

    c.rotate(45)

    text_width = c.stringWidth(
        text,
        "Helvetica-Bold",
        font_size
    )

    c.drawString(
        -text_width / 2,
        0,
        text
    )

    c.restoreState()
    c.save()


def watermark_image(
    input_path,
    output_path,
    text,
    color
):
    image = Image.open(
        input_path
    ).convert("RGBA")

    overlay = Image.new(
        "RGBA",
        image.size,
        (255, 255, 255, 0)
    )

    draw = ImageDraw.Draw(overlay)

    # Large watermark for images
    font_size = max(
        48,
        min(image.size) // 5
    )

    try:
        font = ImageFont.truetype(
            "/system/fonts/Roboto-Bold.ttf",
            font_size
        )
    except Exception:
        try:
            font = ImageFont.truetype(
                "/system/fonts/Roboto-Regular.ttf",
                font_size
            )
        except Exception:
            font = ImageFont.load_default()

    bbox = draw.textbbox(
        (0, 0),
        text,
        font=font
    )

    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]

    x = (image.width - text_width) // 2
    y = (image.height - text_height) // 2

    r, g, b = color

    draw.text(
        (x, y),
        text,
        font=font,
        fill=(r, g, b, 75)
    )

    result = Image.alpha_composite(
        image,
        overlay
    )

    result.convert("RGB").save(
        output_path,
        quality=95
    )


async def watermark_process(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    color
):
    input_path = context.user_data.get(
        "watermark_input"
    )

    temp_dir = context.user_data.get(
        "watermark_dir"
    )

    text = context.user_data.get(
        "watermark_text"
    )

    safe_name = context.user_data.get(
        "watermark_name"
    )

    if not input_path or not temp_dir or not text or not safe_name:
        await update.effective_message.reply_text(
            "❌ Your watermark information could not be found.",
            reply_markup=main_menu_button()
        )

        context.user_data.clear()
        return ConversationHandler.END

    try:
        await update.effective_message.reply_text(
            "⏳ Adding watermark...\n\n"
            "Please wait."
        )

        extension = os.path.splitext(
            input_path
        )[1].lower()

        if extension == ".pdf":

            output_path = os.path.join(
                temp_dir,
                safe_name + ".pdf"
            )

            reader = PdfReader(input_path)
            writer = PdfWriter()

            for index, page in enumerate(reader.pages):

                width = float(
                    page.mediabox.width
                )

                height = float(
                    page.mediabox.height
                )

                watermark_path = os.path.join(
                    temp_dir,
                    f"watermark_{index}.pdf"
                )

                await create_pdf_watermark(
                    watermark_path,
                    text,
                    width,
                    height,
                    color
                )

                watermark_reader = PdfReader(
                    watermark_path
                )

                watermark_page = (
                    watermark_reader.pages[0]
                )

                page.merge_page(
                    watermark_page
                )

                writer.add_page(page)

            with open(
                output_path,
                "wb"
            ) as output_file:
                writer.write(output_file)

            with open(
                output_path,
                "rb"
            ) as pdf_file:

                await update.effective_message.reply_document(
                    document=pdf_file,
                    filename=safe_name + ".pdf",
                    caption="💧 Watermark added successfully.",
                    reply_markup=main_menu_button()
                )

        else:

            output_path = os.path.join(
                temp_dir,
                safe_name + ".jpg"
            )

            await asyncio.to_thread(
                watermark_image,
                input_path,
                output_path,
                text,
                color
            )

            with open(
                output_path,
                "rb"
            ) as image_file:

                await update.effective_message.reply_document(
                    document=image_file,
                    filename=safe_name + ".jpg",
                    caption="💧 Watermark added successfully.",
                    reply_markup=main_menu_button()
                )

    except Exception as e:

        logger.error(
            f"Watermark processing error: {e}"
        )

        await update.effective_message.reply_text(
            "❌ Unable to add the watermark.",
            reply_markup=main_menu_button()
        )

    finally:

        try:
            if temp_dir and os.path.exists(temp_dir):

                for filename in os.listdir(temp_dir):

                    file_path = os.path.join(
                        temp_dir,
                        filename
                    )

                    if os.path.isfile(file_path):
                        os.remove(file_path)

                os.rmdir(temp_dir)

        except Exception:
            pass

        context.user_data.clear()

    return ConversationHandler.END


async def watermark_color_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    query = update.callback_query
    await query.answer()

    color_name = query.data.replace(
        "wm_color_",
        ""
    )

    color = WATERMARK_COLORS.get(
        color_name
    )

    if not color:
        return WATERMARK_WAIT_COLOR

    # Remove Cancel from the color prompt
    await query.message.edit_reply_markup(
        reply_markup=None
    )

    context.user_data["watermark_color"] = color

    await watermark_process(
        update,
        context,
        color
    )

    return ConversationHandler.END


async def watermark_cancel(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    query = update.callback_query
    await query.answer()

    temp_dir = context.user_data.get(
        "watermark_dir"
    )

    if temp_dir and os.path.exists(temp_dir):

        try:
            for filename in os.listdir(temp_dir):

                file_path = os.path.join(
                    temp_dir,
                    filename
                )

                if os.path.isfile(file_path):
                    os.remove(file_path)

            os.rmdir(temp_dir)

        except Exception as e:

            logger.warning(
                f"Watermark cancel cleanup error: {e}"
            )

    context.user_data.clear()

    await query.message.edit_text(
        "🏠 NovaPDF AI\n\nChoose a tool:",
        reply_markup=main_keyboard()
    )

    return ConversationHandler.END



# =========================
# ROTATE PDF
# =========================

def rotate_cancel_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ Cancel", callback_data="rotate_cancel")]
    ])


def rotate_angle_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("↻ 90°", callback_data="rotate_90"),
            InlineKeyboardButton("↻ 180°", callback_data="rotate_180")
        ],
        [
            InlineKeyboardButton("↺ 270°", callback_data="rotate_270")
        ],
        [
            InlineKeyboardButton("❌ Cancel", callback_data="rotate_cancel")
        ]
    ])


async def rotate_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query

    if query:
        await query.answer()
        message = query.message
    else:
        message = update.effective_message

    context.user_data.clear()

    await message.edit_text(
        "🔄 Rotate PDF\n\n"
        "Send the PDF you want to rotate.",
        reply_markup=rotate_cancel_keyboard()
    )

    context.user_data["rotate_prompt_message_id"] = message.message_id

    return ROTATE_WAIT_FILE


async def remove_rotate_cancel(
    context,
    chat_id,
    message_id
):
    try:
        await context.bot.edit_message_reply_markup(
            chat_id=chat_id,
            message_id=message_id,
            reply_markup=None
        )
    except Exception:
        pass


async def rotate_receive_file(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    await remove_prompt_cancel_button(
        update, context, "rotate_prompt_message_id"
    )

    document = update.effective_message.document

    if not document:
        return ROTATE_WAIT_FILE

    if document.mime_type != "application/pdf":
        await send_invalid_file(
            update,
            "❌ Invalid file.\nPlease send a PDF file.",
            "rotate_cancel"
        )
        return ROTATE_WAIT_FILE

    prompt_message_id = context.user_data.get(
        "rotate_prompt_message_id"
    )

    if prompt_message_id:
        await remove_rotate_cancel(
            context,
            update.effective_chat.id,
            prompt_message_id
        )

    temp_dir = tempfile.mkdtemp()

    try:
        input_path = os.path.join(
            temp_dir,
            "input.pdf"
        )

        file = await document.get_file()
        await file.download_to_drive(input_path)

        context.user_data["rotate_dir"] = temp_dir
        context.user_data["rotate_input"] = input_path

        prompt = await update.effective_message.reply_text(
            "✅ File received.\n\n"
            "🔄 Choose how much you want to rotate the PDF:",
            reply_markup=rotate_angle_keyboard()
        )

        context.user_data["rotate_prompt_message_id"] = (
            prompt.message_id
        )

        return ROTATE_WAIT_ANGLE

    except Exception as e:
        logger.error(f"Rotate receive error: {e}")

        try:
            for filename in os.listdir(temp_dir):
                os.remove(os.path.join(temp_dir, filename))
            os.rmdir(temp_dir)
        except Exception:
            pass

        await update.effective_message.reply_text(
            "❌ I couldn't receive the PDF."
        )

        return ROTATE_WAIT_FILE


async def rotate_angle_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    query = update.callback_query
    await query.answer()

    angle = int(
        query.data.replace(
            "rotate_",
            ""
        )
    )

    await query.message.edit_reply_markup(
        reply_markup=None
    )

    context.user_data["rotate_angle"] = angle

    prompt = await query.message.reply_text(
        "📄 What would you like to name the rotated PDF?\n\n"
        "Example: Rotated Document\n\n"
        "You don't need to type .pdf",
        reply_markup=rotate_cancel_keyboard()
    )

    context.user_data["rotate_prompt_message_id"] = (
        prompt.message_id
    )

    return ROTATE_WAIT_NAME


async def rotate_receive_name(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    await remove_prompt_cancel_button(
        update, context, "rotate_prompt_message_id"
    )

    name = update.effective_message.text.strip()

    if not name:
        await update.effective_message.reply_text(
            "❌ Please enter a PDF name."
        )
        return ROTATE_WAIT_NAME

    prompt_message_id = context.user_data.get(
        "rotate_prompt_message_id"
    )

    if prompt_message_id:
        await remove_rotate_cancel(
            context,
            update.effective_chat.id,
            prompt_message_id
        )

    if name.lower().endswith(".pdf"):
        name = name[:-4]

    safe_name = "".join(
        c for c in name
        if c.isalnum() or c in " -_()"
    ).strip()

    if not safe_name:
        await update.effective_message.reply_text(
            "❌ Please choose a valid PDF name.",
            reply_markup=rotate_cancel_keyboard()
        )
        return ROTATE_WAIT_NAME

    input_path = context.user_data.get("rotate_input")
    temp_dir = context.user_data.get("rotate_dir")
    angle = context.user_data.get("rotate_angle")

    if not input_path or not temp_dir or not angle:
        await update.effective_message.reply_text(
            "❌ Rotation information was lost.",
            reply_markup=main_menu_button()
        )
        context.user_data.clear()
        return ConversationHandler.END

    output_path = os.path.join(
        temp_dir,
        safe_name + ".pdf"
    )

    try:
        await update.effective_message.reply_text(
            "⏳ Rotating your PDF...\n\n"
            "Please wait."
        )

        reader = PdfReader(input_path)
        writer = PdfWriter()

        for page in reader.pages:
            page.rotate(angle)
            writer.add_page(page)

        with open(output_path, "wb") as output_file:
            writer.write(output_file)

        with open(output_path, "rb") as pdf_file:
            await update.effective_message.reply_document(
                document=pdf_file,
                filename=safe_name + ".pdf",
                caption=f"🔄 PDF rotated {angle}° successfully.",
                reply_markup=main_menu_button()
            )

    except Exception as e:
        logger.error(f"Rotate PDF error: {e}")

        await update.effective_message.reply_text(
            "❌ Unable to rotate this PDF.",
            reply_markup=main_menu_button()
        )

    finally:
        try:
            if temp_dir and os.path.exists(temp_dir):
                for filename in os.listdir(temp_dir):
                    file_path = os.path.join(
                        temp_dir,
                        filename
                    )
                    if os.path.isfile(file_path):
                        os.remove(file_path)
                os.rmdir(temp_dir)
        except Exception:
            pass

        context.user_data.clear()

    return ConversationHandler.END


async def rotate_cancel(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    query = update.callback_query
    await query.answer()

    temp_dir = context.user_data.get("rotate_dir")

    if temp_dir and os.path.exists(temp_dir):
        try:
            for filename in os.listdir(temp_dir):
                file_path = os.path.join(
                    temp_dir,
                    filename
                )
                if os.path.isfile(file_path):
                    os.remove(file_path)
            os.rmdir(temp_dir)
        except Exception as e:
            logger.warning(
                f"Rotate cancel cleanup error: {e}"
            )

    context.user_data.clear()

    await query.message.edit_text(
        "🏠 NovaPDF AI\n\nChoose a tool:",
        reply_markup=main_keyboard()
    )

    return ConversationHandler.END



# =========================
# PDF TO IMAGES
# =========================

def images_cancel_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ Cancel", callback_data="images_cancel")]
    ])


def images_format_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🖼️ JPG", callback_data="images_jpg"),
            InlineKeyboardButton("🖼️ PNG", callback_data="images_png")
        ],
        [
            InlineKeyboardButton("❌ Cancel", callback_data="images_cancel")
        ]
    ])


async def images_start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    query = update.callback_query

    if query:
        await query.answer()
        message = query.message
    else:
        message = update.effective_message

    context.user_data.clear()

    await message.edit_text(
        "🖼️ PDF to Images\n\n"
        "Send the PDF you want to convert into images.",
        reply_markup=images_cancel_keyboard()
    )

    context.user_data["images_prompt_message_id"] = (
        message.message_id
    )

    return IMAGES_WAIT_FILE


async def remove_images_cancel(
    context,
    chat_id,
    message_id
):
    try:
        await context.bot.edit_message_reply_markup(
            chat_id=chat_id,
            message_id=message_id,
            reply_markup=None
        )
    except Exception:
        pass


async def images_receive_file(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    await remove_prompt_cancel_button(
        update, context, "images_prompt_message_id"
    )

    document = update.effective_message.document

    if not document:
        return IMAGES_WAIT_FILE

    if document.mime_type != "application/pdf":
        await send_invalid_file(
            update,
            "❌ Invalid file.\nPlease send a PDF file.",
            "images_cancel"
        )
        return IMAGES_WAIT_FILE

    prompt_message_id = context.user_data.get(
        "images_prompt_message_id"
    )

    if prompt_message_id:
        await remove_images_cancel(
            context,
            update.effective_chat.id,
            prompt_message_id
        )

    temp_dir = tempfile.mkdtemp()

    try:
        input_path = os.path.join(
            temp_dir,
            "input.pdf"
        )

        file = await document.get_file()
        await file.download_to_drive(input_path)

        context.user_data["images_dir"] = temp_dir
        context.user_data["images_input"] = input_path

        prompt = await update.effective_message.reply_text(
            "✅ File received.\n\n"
            "🖼️ Choose the image format:",
            reply_markup=images_format_keyboard()
        )

        context.user_data["images_prompt_message_id"] = (
            prompt.message_id
        )

        return IMAGES_WAIT_FORMAT

    except Exception as e:
        logger.error(f"PDF image receive error: {e}")

        try:
            for filename in os.listdir(temp_dir):
                os.remove(
                    os.path.join(
                        temp_dir,
                        filename
                    )
                )
            os.rmdir(temp_dir)
        except Exception:
            pass

        await update.effective_message.reply_text(
            "❌ I couldn't receive the PDF."
        )

        return IMAGES_WAIT_FILE


async def images_format_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    query = update.callback_query
    await query.answer()

    if query.data == "images_jpg":
        image_format = "jpg"
    elif query.data == "images_png":
        image_format = "png"
    else:
        return IMAGES_WAIT_FORMAT

    context.user_data["images_format"] = image_format

    try:
        await query.message.edit_reply_markup(
            reply_markup=None
        )
    except Exception:
        pass

    input_path = context.user_data.get("images_input")
    temp_dir = context.user_data.get("images_dir")

    if not input_path or not temp_dir:
        await query.message.reply_text(
            "❌ The PDF could not be found.",
            reply_markup=main_menu_button()
        )

        context.user_data.clear()

        return ConversationHandler.END

    try:
        await query.message.reply_text(
            "⏳ Converting your PDF to images...\n\n"
            "Please wait."
        )

        output_prefix = os.path.join(
            temp_dir,
            "page"
        )

        if image_format == "jpg":
            command = [
                "pdftoppm",
                "-jpeg",
                "-r",
                "150",
                input_path,
                output_prefix
            ]
        else:
            command = [
                "pdftoppm",
                "-png",
                "-r",
                "150",
                input_path,
                output_prefix
            ]

        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            logger.error(
                f"pdftoppm error: {stderr.decode(errors='ignore')}"
            )

            await query.message.reply_text(
                "❌ Unable to convert this PDF.",
                reply_markup=main_menu_button()
            )

            return ConversationHandler.END

        extension = "jpg" if image_format == "jpg" else "png"

        image_files = sorted(
            [
                os.path.join(temp_dir, filename)
                for filename in os.listdir(temp_dir)
                if filename.lower().endswith(
                    "." + extension
                )
            ]
        )

        if not image_files:
            await query.message.reply_text(
                "❌ No pages could be converted.",
                reply_markup=main_menu_button()
            )

            return ConversationHandler.END

        total = len(image_files)

        for index, image_path in enumerate(image_files, start=1):

            caption = f"🖼️ Page {index} of {total}"

            is_last = index == total

            with open(image_path, "rb") as image_file:

                await query.message.reply_photo(
                    photo=image_file,
                    caption=caption
                )

        await query.message.reply_text(
            f"✅ Conversion complete!\n\n"
            f"🖼️ Pages converted: {total}\n"
            f"📁 Format: {extension.upper()}",
            reply_markup=main_menu_button()
        )

    except Exception as e:
        logger.error(
            f"PDF to images error: {e}"
        )

        await query.message.reply_text(
            "❌ An error occurred while converting the PDF.",
            reply_markup=main_menu_button()
        )

    finally:
        try:
            if temp_dir and os.path.exists(temp_dir):
                for filename in os.listdir(temp_dir):
                    file_path = os.path.join(
                        temp_dir,
                        filename
                    )

                    if os.path.isfile(file_path):
                        os.remove(file_path)

                os.rmdir(temp_dir)

        except Exception:
            pass

        context.user_data.clear()

    return ConversationHandler.END


async def images_cancel(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    query = update.callback_query
    await query.answer()

    temp_dir = context.user_data.get(
        "images_dir"
    )

    if temp_dir and os.path.exists(temp_dir):
        try:
            for filename in os.listdir(temp_dir):
                file_path = os.path.join(
                    temp_dir,
                    filename
                )

                if os.path.isfile(file_path):
                    os.remove(file_path)

            os.rmdir(temp_dir)

        except Exception as e:
            logger.warning(
                f"Images cancel cleanup error: {e}"
            )

    context.user_data.clear()

    await query.message.edit_text(
        "🏠 NovaPDF AI\n\nChoose a tool:",
        reply_markup=main_keyboard()
    )

    return ConversationHandler.END



# =========================
# COMPRESS PDF
# =========================

def compress_cancel_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ Cancel", callback_data="compress_cancel")]
    ])


def compress_level_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🟢 Low", callback_data="compress_low")],
        [InlineKeyboardButton("🟡 Medium", callback_data="compress_medium")],
        [InlineKeyboardButton("🔴 High", callback_data="compress_high")],
        [InlineKeyboardButton("❌ Cancel", callback_data="compress_cancel")]
    ])


async def compress_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query

    if query:
        await query.answer()
        message = query.message
    else:
        message = update.effective_message

    context.user_data.clear()

    await message.edit_text(
        "📉 Compress PDF\n\n"
        "Send the PDF you want to compress.",
        reply_markup=compress_cancel_keyboard()
    )

    context.user_data["compress_prompt_message_id"] = message.message_id

    return COMPRESS_WAIT_FILE


async def compress_receive_file(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    await remove_prompt_cancel_button(
        update, context, "compress_prompt_message_id"
    )

    document = update.effective_message.document

    if not document:
        return COMPRESS_WAIT_FILE

    if document.mime_type != "application/pdf":
        await send_invalid_file(
            update,
            "❌ Invalid file.\nPlease send a PDF file.",
            "compress_cancel"
        )
        return COMPRESS_WAIT_FILE

    temp_dir = tempfile.mkdtemp()

    try:
        input_path = os.path.join(temp_dir, "input.pdf")

        file = await document.get_file()
        await file.download_to_drive(input_path)

        context.user_data["compress_dir"] = temp_dir
        context.user_data["compress_input"] = input_path

        prompt_message_id = context.user_data.get(
            "compress_prompt_message_id"
        )

        if prompt_message_id:
            try:
                await context.bot.edit_message_reply_markup(
                    chat_id=update.effective_chat.id,
                    message_id=prompt_message_id,
                    reply_markup=None
                )
            except Exception:
                pass

        prompt = await update.effective_message.reply_text(
            "✅ File received.\n\n"
            "✏️ Now enter the name you want for the compressed PDF.\n\n"
            "Example: My Compressed PDF",
            reply_markup=compress_cancel_keyboard()
        )

        context.user_data["compress_prompt_message_id"] = prompt.message_id

        return COMPRESS_WAIT_NAME

    except Exception as e:
        logger.error(f"Compression file receive error: {e}")

        try:
            for filename in os.listdir(temp_dir):
                os.remove(os.path.join(temp_dir, filename))
            os.rmdir(temp_dir)
        except Exception:
            pass

        await update.effective_message.reply_text(
            "❌ I couldn't receive the PDF."
        )

        return COMPRESS_WAIT_FILE


async def compress_receive_name(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    await remove_prompt_cancel_button(
        update, context, "compress_prompt_message_id"
    )

    name = update.effective_message.text.strip()

    if not name:
        await update.effective_message.reply_text(
            "❌ Please enter a valid PDF name.",
            reply_markup=compress_cancel_keyboard()
        )
        return COMPRESS_WAIT_NAME

    # Remove characters that are unsafe in filenames.
    safe_name = "".join(
        c for c in name
        if c.isalnum() or c in " -_()"
    ).strip()

    if not safe_name:
        await update.effective_message.reply_text(
            "❌ Invalid PDF name. Please try another name.",
            reply_markup=compress_cancel_keyboard()
        )
        return COMPRESS_WAIT_NAME

    if not safe_name.lower().endswith(".pdf"):
        safe_name += ".pdf"

    context.user_data["compress_filename"] = safe_name

    prompt_message_id = context.user_data.get(
        "compress_prompt_message_id"
    )

    if prompt_message_id:
        try:
            await context.bot.edit_message_reply_markup(
                chat_id=update.effective_chat.id,
                message_id=prompt_message_id,
                reply_markup=None
            )
        except Exception:
            pass

    prompt = await update.effective_message.reply_text(
        "📄 File name: " + safe_name + "\n\n"
        "📉 Now choose compression level:\n\n"
        "🟢 Low — best quality\n"
        "🟡 Medium — balanced\n"
        "🔴 High — smallest file",
        reply_markup=compress_level_keyboard()
    )

    context.user_data["compress_prompt_message_id"] = prompt.message_id

    return COMPRESS_WAIT_LEVEL


async def compress_level_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    query = update.callback_query
    await query.answer()

    levels = {
        "compress_low": ("/printer", "Low"),
        "compress_medium": ("/ebook", "Medium"),
        "compress_high": ("/screen", "High"),
    }

    setting = levels.get(query.data)

    if not setting:
        return COMPRESS_WAIT_LEVEL

    pdf_setting, level_name = setting

    input_path = context.user_data.get("compress_input")
    temp_dir = context.user_data.get("compress_dir")

    if not input_path or not temp_dir:
        await query.message.edit_text(
            "❌ The PDF could not be found.",
            reply_markup=main_menu_button()
        )
        context.user_data.clear()
        return ConversationHandler.END

    try:
        await query.message.edit_text(
            f"⏳ Compressing your PDF...\n\n"
            f"📉 Level: {level_name}\n"
            f"Please wait."
        )

        output_path = os.path.join(
            temp_dir,
            "compressed.pdf"
        )

        command = [
            "gs",
            "-sDEVICE=pdfwrite",
            "-dCompatibilityLevel=1.4",
            "-dPDFSETTINGS=" + pdf_setting,
            "-dNOPAUSE",
            "-dQUIET",
            "-dBATCH",
            "-sOutputFile=" + output_path,
            input_path
        ]

        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        stdout, stderr = await process.communicate()

        if process.returncode != 0 or not os.path.exists(output_path):
            logger.error(
                f"Ghostscript error: "
                f"{stderr.decode(errors='ignore')}"
            )

            await query.message.edit_text(
                "❌ Unable to compress this PDF.",
                reply_markup=main_menu_button()
            )

            return ConversationHandler.END

        original_size = os.path.getsize(input_path)
        compressed_size = os.path.getsize(output_path)

        if original_size > 0:
            saved_percent = (
                (original_size - compressed_size)
                / original_size
            ) * 100
        else:
            saved_percent = 0

        def format_size(size):
            if size >= 1024 * 1024:
                return f"{size / (1024 * 1024):.2f} MB"
            return f"{size / 1024:.1f} KB"

        # If compression made the file larger, return the original.
        final_path = output_path
        final_size = compressed_size

        if compressed_size >= original_size:
            final_path = input_path
            final_size = original_size
            saved_percent = 0

        await query.message.edit_text(
            "📤 Sending your compressed PDF..."
        )

        with open(final_path, "rb") as pdf_file:
            await query.message.reply_document(
                document=pdf_file,
                filename=context.user_data.get("compress_filename", "compressed.pdf"),
                caption=(
                    "✅ Compression complete!\n\n"
                    f"📦 Original: {format_size(original_size)}\n"
                    f"📉 Compressed: {format_size(final_size)}\n"
                    f"💾 Saved: {saved_percent:.1f}%\n"
                    f"⚙️ Level: {level_name}"
                ),
                reply_markup=main_menu_button()
            )

    except Exception as e:
        logger.error(f"PDF compression error: {e}")

        await query.message.edit_text(
            "❌ An error occurred while compressing the PDF.",
            reply_markup=main_menu_button()
        )

    finally:
        try:
            if temp_dir and os.path.exists(temp_dir):
                for filename in os.listdir(temp_dir):
                    file_path = os.path.join(temp_dir, filename)

                    if os.path.isfile(file_path):
                        os.remove(file_path)

                os.rmdir(temp_dir)
        except Exception:
            pass

        context.user_data.clear()

    return ConversationHandler.END


async def compress_cancel(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    query = update.callback_query
    await query.answer()

    temp_dir = context.user_data.get("compress_dir")

    if temp_dir and os.path.exists(temp_dir):
        try:
            for filename in os.listdir(temp_dir):
                file_path = os.path.join(temp_dir, filename)

                if os.path.isfile(file_path):
                    os.remove(file_path)

            os.rmdir(temp_dir)
        except Exception as e:
            logger.warning(
                f"Compression cancel cleanup error: {e}"
            )

    context.user_data.clear()

    await query.message.edit_text(
        "🏠 NovaPDF AI\n\nChoose a tool:",
        reply_markup=main_keyboard()
    )

    return ConversationHandler.END


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
        f"👥 Total: {total}",
        reply_markup=main_menu_button()
    )

async def inline_main_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    # Clear any active operation
    context.user_data.clear()

    # Remove the Main Menu button from the result message
    # after it has been tapped.
    try:
        await query.message.edit_reply_markup(reply_markup=None)
    except Exception as e:
        logger.warning(f"Could not remove Main Menu button: {e}")

    # Send the full Main Menu as a new message.
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

async def summarize_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    context.user_data.clear()

    await query.message.edit_text(
        "🏠 NovaPDF AI\n\nChoose a tool:",
        reply_markup=main_keyboard()
    )

    return ConversationHandler.END


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
                    protect_cancel,
                    pattern="^protect_cancel$"
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
            PROTECT_WAIT_NAME: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    protect_receive_name
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

    # Unlock PDF
    unlock_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(unlock_start, pattern="^unlock$"),
        ],
        states={
            UNLOCK_WAIT_FILE: [
                MessageHandler(
                    filters.Document.ALL,
                    unlock_receive_file
                ),
                CallbackQueryHandler(
                    unlock_cancel,
                    pattern="^unlock_cancel$"
                )
            ],
            UNLOCK_WAIT_PASSWORD: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    unlock_receive_password
                ),
                CallbackQueryHandler(
                    unlock_cancel,
                    pattern="^unlock_cancel$"
                )
            ],
            UNLOCK_WAIT_NAME: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    unlock_receive_name
                ),
                CallbackQueryHandler(
                    unlock_cancel,
                    pattern="^unlock_cancel$"
                )
            ]
        },
        fallbacks=[
            CallbackQueryHandler(
                unlock_cancel,
                pattern="^unlock_cancel$"
            ),
            CallbackQueryHandler(
                inline_back_handler,
                pattern="^back$"
            ),
            CommandHandler(
                "cancel",
                cancel
            )
        ]
    )

    app.add_handler(unlock_handler)

    # AI Topic Summarizer
    ai_summarizer_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(
                ai_summarizer_start,
                pattern="^ai_summarizer$"
            )
        ],
        states={
            AI_SUMMARIZER_WAIT_INPUT: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    ai_summarizer_receive
                ),
                CallbackQueryHandler(
                    ai_summarizer_cancel,
                    pattern="^ai_summarizer_cancel$"
                )
            ],
            AI_SUMMARIZER_WAIT_OUTPUT: [
                CallbackQueryHandler(
                    ai_summarizer_send_text,
                    pattern="^ai_summary_text$"
                ),
                CallbackQueryHandler(
                    ai_summarizer_pdf,
                    pattern="^ai_summary_pdf$"
                ),
                CallbackQueryHandler(
                    ai_summarizer_cancel,
                    pattern="^ai_summarizer_cancel$"
                )
            ],
            AI_SUMMARIZER_WAIT_NAME: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    ai_summarizer_receive_name
                ),
                CallbackQueryHandler(
                    ai_summarizer_cancel,
                    pattern="^ai_summarizer_cancel$"
                )
            ]
        },
        fallbacks=[
            CallbackQueryHandler(
                ai_summarizer_cancel,
                pattern="^ai_summarizer_cancel$"
            ),
            CommandHandler(
                "cancel",
                cancel
            )
        ]
    )

    app.add_handler(ai_summarizer_handler)

    # QR Code Generator
    qr_code_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(
                qr_start,
                pattern="^qr_code$"
            )
        ],
        states={
            QR_WAIT_TEXT: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    qr_receive_text
                ),
                CallbackQueryHandler(
                    qr_color_callback,
                    pattern="^qr_color_(black|blue|purple|green|red)$"
                ),
                CallbackQueryHandler(
                    qr_customize_callback,
                    pattern="^qr_customize$"
                ),
                CallbackQueryHandler(
                    qr_style_callback,
                    pattern="^qr_style_(square|rounded|dots)$"
                ),
                CallbackQueryHandler(
                    qr_background_callback,
                    pattern="^qr_bg_(white|lightblue|lightpurple)$"
                ),
                CallbackQueryHandler(
                    qr_color_menu_callback,
                    pattern="^qr_color$"
                ),
                CallbackQueryHandler(
                    qr_style_menu_callback,
                    pattern="^qr_style$"
                ),
                CallbackQueryHandler(
                    qr_background_menu_callback,
                    pattern="^qr_background$"
                ),
                CallbackQueryHandler(
                    qr_generate_callback,
                    pattern="^qr_generate$"
                ),
                CallbackQueryHandler(
                    qr_cancel,
                    pattern="^qr_cancel$"
                )
            ]
        },
        fallbacks=[
            CallbackQueryHandler(
                qr_cancel,
                pattern="^qr_cancel$"
            ),
            CallbackQueryHandler(
                inline_back_handler,
                pattern="^back$"
            ),
            CommandHandler(
                "cancel",
                cancel
            )
        ]
    )

    app.add_handler(qr_code_handler)

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
                    filters.Document.ALL,
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
                    filters.Document.ALL,
                    extract_receive
                ),
                CallbackQueryHandler(
                    extract_back,
                    pattern="^extract_back$"
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
                    filters.Document.ALL,
                    summarize_receive
                ),
                CallbackQueryHandler(
                    summarize_cancel,
                    pattern="^summarize_cancel$"
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


    # Watermark
    watermark_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(
                watermark_start,
                pattern="^watermark$"
            ),
            MessageHandler(
                filters.Regex("^💧 Watermark$"),
                watermark_start
            )
        ],
        states={
            WATERMARK_WAIT_FILE: [
                MessageHandler(
                    filters.Document.ALL,
                    watermark_receive_file
                ),
                MessageHandler(
                    filters.PHOTO,
                    watermark_receive_file
                ),
                CallbackQueryHandler(
                    watermark_cancel,
                    pattern="^watermark_cancel$"
                )
            ],

            WATERMARK_WAIT_TEXT: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    watermark_receive_text
                ),
                CallbackQueryHandler(
                    watermark_cancel,
                    pattern="^watermark_cancel$"
                )
            ],

            WATERMARK_WAIT_NAME: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    watermark_receive_name
                ),
                CallbackQueryHandler(
                    watermark_cancel,
                    pattern="^watermark_cancel$"
                )
            ],

            WATERMARK_WAIT_COLOR: [
                CallbackQueryHandler(
                    watermark_color_callback,
                    pattern="^wm_color_"
                ),
                CallbackQueryHandler(
                    watermark_cancel,
                    pattern="^watermark_cancel$"
                )
            ]
        },

        fallbacks=[
            CallbackQueryHandler(
                watermark_cancel,
                pattern="^watermark_cancel$"
            ),
            CallbackQueryHandler(
                inline_back_handler,
                pattern="^back$"
            ),
            CommandHandler(
                "cancel",
                cancel
            )
        ]
    )

    app.add_handler(watermark_handler)

    # Rotate PDF
    rotate_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(
                rotate_start,
                pattern="^rotate$"
            ),
            MessageHandler(
                filters.Regex("^🔄 Rotate PDF$"),
                rotate_start
            )
        ],
        states={
            ROTATE_WAIT_FILE: [
                MessageHandler(
                    filters.Document.ALL,
                    rotate_receive_file
                ),
                CallbackQueryHandler(
                    rotate_cancel,
                    pattern="^rotate_cancel$"
                )
            ],

            ROTATE_WAIT_ANGLE: [
                CallbackQueryHandler(
                    rotate_angle_callback,
                    pattern="^rotate_(90|180|270)$"
                ),
                CallbackQueryHandler(
                    rotate_cancel,
                    pattern="^rotate_cancel$"
                )
            ],

            ROTATE_WAIT_NAME: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    rotate_receive_name
                ),
                CallbackQueryHandler(
                    rotate_cancel,
                    pattern="^rotate_cancel$"
                )
            ]
        },

        fallbacks=[
            CallbackQueryHandler(
                rotate_cancel,
                pattern="^rotate_cancel$"
            ),
            CallbackQueryHandler(
                inline_back_handler,
                pattern="^back$"
            ),
            CommandHandler(
                "cancel",
                cancel
            )
        ]
    )

    app.add_handler(rotate_handler)

    # PDF to Images
    images_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(
                images_start,
                pattern="^images$"
            ),
            MessageHandler(
                filters.Regex("^🖼️ PDF to Images$"),
                images_start
            )
        ],

        states={
            IMAGES_WAIT_FILE: [
                MessageHandler(
                    filters.Document.ALL,
                    images_receive_file
                ),
                CallbackQueryHandler(
                    images_cancel,
                    pattern="^images_cancel$"
                )
            ],

            IMAGES_WAIT_FORMAT: [
                CallbackQueryHandler(
                    images_format_callback,
                    pattern="^images_(jpg|png)$"
                ),
                CallbackQueryHandler(
                    images_cancel,
                    pattern="^images_cancel$"
                )
            ]
        },

        fallbacks=[
            CallbackQueryHandler(
                images_cancel,
                pattern="^images_cancel$"
            ),
            CallbackQueryHandler(
                inline_back_handler,
                pattern="^back$"
            ),
            CommandHandler(
                "cancel",
                cancel
            )
        ]
    )

    app.add_handler(images_handler)

    # Images to PDF
    images_to_pdf_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(
                images_to_pdf_start,
                pattern="^images_to_pdf$"
            ),
            MessageHandler(
                filters.Regex("^🖼️ Images → PDF$"),
                images_to_pdf_start
            )
        ],

        states={
            IMG_PDF_WAIT_IMAGES: [
                MessageHandler(
                    filters.PHOTO | filters.Document.IMAGE,
                    images_to_pdf_receive_image
                ),
                CallbackQueryHandler(
                    images_to_pdf_done,
                    pattern="^images_to_pdf_done$"
                ),
                CallbackQueryHandler(
                    images_to_pdf_cancel,
                    pattern="^images_to_pdf_cancel$"
                )
            ],

            IMG_PDF_WAIT_NAME: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    images_to_pdf_receive_name
                ),
                CallbackQueryHandler(
                    images_to_pdf_cancel,
                    pattern="^images_to_pdf_cancel$"
                )
            ]
        },

        fallbacks=[
            CallbackQueryHandler(
                images_to_pdf_cancel,
                pattern="^images_to_pdf_cancel$"
            ),
            CallbackQueryHandler(
                inline_back_handler,
                pattern="^back$"
            ),
            CommandHandler(
                "cancel",
                cancel
            )
        ]
    )

    app.add_handler(images_to_pdf_handler)

    # Compress PDF
    compress_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(
                compress_start,
                pattern="^compress$"
            ),
            MessageHandler(
                filters.Regex("^📉 Compress PDF$"),
                compress_start
            )
        ],

        states={
            COMPRESS_WAIT_FILE: [
                MessageHandler(
                    filters.Document.ALL,
                    compress_receive_file
                ),
                CallbackQueryHandler(
                    compress_cancel,
                    pattern="^compress_cancel$"
                )
            ],

            COMPRESS_WAIT_NAME: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    compress_receive_name
                ),
                CallbackQueryHandler(
                    compress_cancel,
                    pattern="^compress_cancel$"
                )
            ],

            COMPRESS_WAIT_LEVEL: [
                CallbackQueryHandler(
                    compress_level_callback,
                    pattern="^compress_(low|medium|high)$"
                ),
                CallbackQueryHandler(
                    compress_cancel,
                    pattern="^compress_cancel$"
                )
            ]
        },

        fallbacks=[
            CallbackQueryHandler(
                compress_cancel,
                pattern="^compress_cancel$"
            ),
            CallbackQueryHandler(
                inline_back_handler,
                pattern="^back$"
            ),
            CommandHandler(
                "cancel",
                cancel
            )
        ]
    )

    app.add_handler(compress_handler)

    # Text to PDF
    text_to_pdf_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(
                text_to_pdf_start,
                pattern="^texttopdf$"
            ),
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
                ),
                CallbackQueryHandler(
                    text_to_pdf_text_done,
                    pattern="^textpdf_text_done$"
                ),
                CallbackQueryHandler(
                    text_to_pdf_cancel,
                    pattern="^texttopdf_cancel$"
                )
            ],

            TEXT_TO_PDF_WAIT_NAME: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    text_to_pdf_name
                ),
                CallbackQueryHandler(
                    text_to_pdf_cancel,
                    pattern="^texttopdf_cancel$"
                )
            ],

            TEXT_TO_PDF_WAIT_CUSTOMIZE: [
                CallbackQueryHandler(
                    text_to_pdf_font_menu,
                    pattern="^textpdf_font$"
                ),
                CallbackQueryHandler(
                    text_to_pdf_font_callback,
                    pattern="^textpdf_font_(helvetica|times|courier)$"
                ),
                CallbackQueryHandler(
                    text_to_pdf_color_menu,
                    pattern="^textpdf_color$"
                ),
                CallbackQueryHandler(
                    text_to_pdf_color_callback,
                    pattern="^textpdf_color_(black|blue|red)$"
                ),
                CallbackQueryHandler(
                    text_to_pdf_pages_callback,
                    pattern="^textpdf_pages$"
                ),
                CallbackQueryHandler(
                    text_to_pdf_create,
                    pattern="^textpdf_create$"
                ),
                CallbackQueryHandler(
                    text_to_pdf_customize,
                    pattern="^textpdf_customize$"
                ),
                CallbackQueryHandler(
                    text_to_pdf_cancel,
                    pattern="^texttopdf_cancel$"
                )
            ]
        },
        fallbacks=[
            CallbackQueryHandler(
                text_to_pdf_cancel,
                pattern="^texttopdf_cancel$"
            ),
            CallbackQueryHandler(
                inline_back_handler,
                pattern="^back$"
            ),
            CommandHandler(
                "cancel",
                cancel
            )
        ]
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
            pattern="^(rotate|images|compress)$"
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
