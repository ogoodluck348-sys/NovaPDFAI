from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

from pypdf import PdfReader, PdfWriter
import os
import re
import uuid

# ==========================
# BOT TOKEN
# ==========================

TOKEN = "8539424533:AAGq4MdX3Udgiptg-6G-iIrlQoxeOJfTvuI"

# ==========================
# STATES
# ==========================

(
    PROTECT_WAIT_PDF,
    PROTECT_WAIT_PASSWORD,
    MERGE_WAIT_FILES,
    EXTRACT_WAIT_PDF,
) = range(4)

# ==========================
# MENU
# ==========================

keyboard = [
    ["📄 Extract PDF Text", "🔒 Protect PDF"],
    ["🔗 Merge PDF", "🗜 Compress PDF"],
    ["❌ Cancel"]
]

menu = ReplyKeyboardMarkup(
    keyboard,
    resize_keyboard=True
)

# ==========================
# HELPERS
# ==========================

def clean_text(text):
    text = re.sub(r'(?<=[a-z])(?=[A-Z])', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def temp_name(prefix):
    return f"{prefix}_{uuid.uuid4().hex}.pdf"

def delete_file(path):
    if path and os.path.exists(path):
        os.remove(path)

# ==========================
# START
# ==========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    await update.message.reply_text(
        "👋 Welcome to NovaPDF AI\n\n"
        "Your professional PDF assistant.\n\n"
        "Choose an option below.",
        reply_markup=menu
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):

    await update.message.reply_text(
        "/start - Start bot\n"
        "/help - Help\n"
        "/cancel - Cancel current task\n"
        "/done - Finish merging PDFs\n\n"
        "Features\n"
        "📄 Extract PDF Text\n"
        "🔒 Protect PDF\n"
        "🔗 Merge PDF\n"
        "🗜 Compress PDF (coming next)"
    )

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):

    context.user_data.clear()

    await update.message.reply_text(
        "❌ Current operation cancelled.",
        reply_markup=menu
    )

    return ConversationHandler.END
# ==========================
# PROTECT PDF
# ==========================

async def protect_start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    await update.message.reply_text(
        "🔒 Protect PDF\n\n"
        "📄 Please send the PDF you want to protect."
    )

    return PROTECT_WAIT_PDF


async def protect_receive_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not update.message.document:
        await update.message.reply_text(
            "❌ Please send a PDF document."
        )
        return PROTECT_WAIT_PDF

    filename = temp_name("protect")

    file = await update.message.document.get_file()
    await file.download_to_drive(filename)

    context.user_data["protect_pdf"] = filename

    await update.message.reply_text(
        "✅ PDF received.\n\n"
        "🔑 Now send the password you want to use."
    )

    return PROTECT_WAIT_PASSWORD


async def protect_receive_password(update: Update, context: ContextTypes.DEFAULT_TYPE):

    password = update.message.text.strip()

    pdf = context.user_data.get("protect_pdf")

    if not pdf:

        await update.message.reply_text(
            "❌ PDF not found.\nPlease start again."
        )

        return ConversationHandler.END

    waiting = await update.message.reply_text(
        "⏳ Encrypting your PDF...\n"
        "Please wait."
    )

    try:

        reader = PdfReader(pdf)

        writer = PdfWriter()

        for page in reader.pages:
            writer.add_page(page)

        writer.encrypt(password)

        output = temp_name("protected")

        with open(output, "wb") as f:
            writer.write(f)

        await update.message.reply_document(
            document=open(output, "rb"),
            filename="Protected.pdf",
            caption="✅ PDF protected successfully."
        )

        delete_file(pdf)
        delete_file(output)

    except Exception as e:

        await update.message.reply_text(
            f"❌ Failed to protect PDF.\n\n{e}"
        )

    finally:

        try:
            await waiting.delete()
        except:
            pass

        context.user_data.clear()

    return ConversationHandler.END
# ==========================
# MERGE PDF
# ==========================

async def merge_start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    context.user_data["merge_files"] = []

    await update.message.reply_text(
        "🔗 Merge PDF\n\n"
        "📄 Send the first PDF."
    )

    return MERGE_WAIT_FILES


async def merge_receive(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not update.message.document:
        await update.message.reply_text(
            "❌ Please send a PDF document."
        )
        return MERGE_WAIT_FILES

    filename = temp_name("merge")

    file = await update.message.document.get_file()
    await file.download_to_drive(filename)

    context.user_data["merge_files"].append(filename)

    count = len(context.user_data["merge_files"])

    await update.message.reply_text(
        f"✅ PDF {count} received.\n\n"
        "Send another PDF or type /done when you are finished."
    )

    return MERGE_WAIT_FILES


async def merge_done(update: Update, context: ContextTypes.DEFAULT_TYPE):

    files = context.user_data.get("merge_files", [])

    if len(files) < 2:
        await update.message.reply_text(
            "❌ Please send at least two PDF files."
        )
        return MERGE_WAIT_FILES

    waiting = await update.message.reply_text(
        "⏳ Merging your PDF files...\n"
        "Please wait."
    )

    try:

        writer = PdfWriter()

        for pdf in files:

            reader = PdfReader(pdf)

            for page in reader.pages:
                writer.add_page(page)

        output = temp_name("merged")

        with open(output, "wb") as f:
            writer.write(f)

        await update.message.reply_document(
            document=open(output, "rb"),
            filename="Merged.pdf",
            caption="✅ Your PDFs have been merged successfully."
        )

    except Exception as e:

        await update.message.reply_text(
            f"❌ Merge failed.\n\n{e}"
        )

    finally:

        for pdf in files:
            delete_file(pdf)

        if "output" in locals():
            delete_file(output)

        context.user_data.clear()

        try:
            await waiting.delete()
        except:
            pass

    return ConversationHandler.END
# ==========================
# EXTRACT PDF
# ==========================

async def extract_start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    await update.message.reply_text(
        "📄 Please send the PDF you want to extract text from."
    )

    return EXTRACT_WAIT_PDF


async def extract_receive(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not update.message.document:
        await update.message.reply_text(
            "❌ Please send a PDF."
        )
        return EXTRACT_WAIT_PDF

    waiting = await update.message.reply_text(
        "⏳ Extracting text from your PDF...\nPlease wait."
    )

    filename = temp_name("extract")

    file = await update.message.document.get_file()
    await file.download_to_drive(filename)

    try:

        reader = PdfReader(filename)

        text = ""

        for page in reader.pages:
            text += page.extract_text() or ""

        text = clean_text(text)

        if not text:

            await update.message.reply_text(
                "❌ No readable text found."
            )

        else:

            for i in range(0, len(text), 3500):

                await update.message.reply_text(
                    text[i:i+3500]
                )

    except Exception as e:

        await update.message.reply_text(
            f"❌ Extraction failed.\n\n{e}"
        )

    finally:

        delete_file(filename)

        try:
            await waiting.delete()
        except:
            pass

    return ConversationHandler.END


# ==========================
# MAIN
# ==========================

def main():

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("cancel", cancel))
    app.add_handler(CommandHandler("done", merge_done))

    protect_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^🔒 Protect PDF$"), protect_start)
        ],
        states={
            PROTECT_WAIT_PDF: [
                MessageHandler(filters.Document.PDF, protect_receive_pdf)
            ],
            PROTECT_WAIT_PASSWORD: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, protect_receive_password)
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel)
        ],
    )

    merge_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^🔗 Merge PDF$"), merge_start)
        ],
        states={
            MERGE_WAIT_FILES: [
                MessageHandler(filters.Document.PDF, merge_receive),
                CommandHandler("done", merge_done),
            ]
        },
        fallbacks=[
            CommandHandler("cancel", cancel)
        ],
    )

    extract_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^📄 Extract PDF Text$"), extract_start)
        ],
        states={
            EXTRACT_WAIT_PDF: [
                MessageHandler(filters.Document.PDF, extract_receive)
            ]
        },
        fallbacks=[
            CommandHandler("cancel", cancel)
        ],
    )

    app.add_handler(protect_handler)
    app.add_handler(merge_handler)
    app.add_handler(extract_handler)

    print("✅ NovaPDF AI is running...")

    app.run_polling()


if __name__ == "__main__":
    main()
