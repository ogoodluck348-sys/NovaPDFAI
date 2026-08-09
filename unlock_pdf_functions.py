import tempfile
import os
import shutil
from pathlib import Path

from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ConversationHandler

UNLOCK_WAIT_FILE = 23
UNLOCK_WAIT_PASSWORD = 24
UNLOCK_WAIT_NAME = 25


def unlock_cancel_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ Cancel", callback_data="unlock_cancel")]
    ])


def unlock_main_menu_keyboard():
    return InlineKeyboardMarkup([
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
            InlineKeyboardButton("➕ More", callback_data="more")
        ]
    ])


async def unlock_start(update, context):
    if update.callback_query:
        await update.callback_query.answer()

    message = update.effective_message

    context.user_data.pop("unlock_pdf_file", None)
    context.user_data.pop("unlock_pdf_path", None)
    context.user_data.pop("unlock_pdf_password", None)
    context.user_data.pop("unlock_pdf_filename", None)

    await message.reply_text(
        "🔓 <b>Unlock PDF</b>\n\n"
        "Send the password-protected PDF you want to unlock.",
        parse_mode="HTML",
        reply_markup=unlock_cancel_keyboard()
    )

    return UNLOCK_WAIT_FILE


async def unlock_receive_file(update, context):
    document = update.message.document

    if not document or not document.file_name.lower().endswith(".pdf"):
        await update.message.reply_text(
            "❌ Please send a PDF file.",
            reply_markup=unlock_cancel_keyboard()
        )
        return UNLOCK_WAIT_FILE

    temp_dir = context.user_data.get("unlock_pdf_path")

    if not temp_dir:
        temp_dir = tempfile.mkdtemp(prefix="nova_unlock_")
        context.user_data["unlock_pdf_path"] = temp_dir

    file_path = os.path.join(temp_dir, document.file_name)

    telegram_file = await document.get_file()
    await telegram_file.download_to_drive(file_path)

    context.user_data["unlock_pdf_file"] = file_path

    await update.message.reply_text(
        "🔑 <b>Enter the PDF password</b>\n\n"
        "Send the password used to protect this PDF.",
        parse_mode="HTML",
        reply_markup=unlock_cancel_keyboard()
    )

    return UNLOCK_WAIT_PASSWORD


async def unlock_receive_password(update, context):
    password = update.message.text

    if not password:
        await update.message.reply_text(
            "❌ Please enter the PDF password.",
            reply_markup=unlock_cancel_keyboard()
        )
        return UNLOCK_WAIT_PASSWORD

    context.user_data["unlock_pdf_password"] = password

    pdf_path = context.user_data.get("unlock_pdf_file")

    if not pdf_path or not os.path.exists(pdf_path):
        await update.message.reply_text(
            "❌ PDF file not found. Please start again.",
            reply_markup=unlock_cancel_keyboard()
        )
        return UNLOCK_WAIT_FILE

    try:
        from PyPDF2 import PdfReader, PdfWriter

        reader = PdfReader(pdf_path)

        if reader.is_encrypted:
            result = reader.decrypt(password)

            if result == 0:
                await update.message.reply_text(
                    "❌ Incorrect password.\n\n"
                    "Please try again.",
                    reply_markup=unlock_cancel_keyboard()
                )
                return UNLOCK_WAIT_PASSWORD

        writer = PdfWriter()

        for page in reader.pages:
            writer.add_page(page)

        unlocked_path = os.path.join(
            context.user_data["unlock_pdf_path"],
            "unlocked.pdf"
        )

        with open(unlocked_path, "wb") as output:
            writer.write(output)

        context.user_data["unlock_pdf_file"] = unlocked_path

        await update.message.reply_text(
            "✅ PDF unlocked successfully!\n\n"
            "Now enter the name for the unlocked PDF.\n\n"
            "Example: <code>My Document</code>",
            parse_mode="HTML",
            reply_markup=unlock_cancel_keyboard()
        )

        return UNLOCK_WAIT_NAME

    except Exception as e:
        await update.message.reply_text(
            f"❌ Could not unlock this PDF.\n\n"
            f"Error: {e}",
            reply_markup=unlock_cancel_keyboard()
        )
        return UNLOCK_WAIT_PASSWORD


async def unlock_receive_name(update, context):
    name = update.message.text.strip()

    if not name:
        await update.message.reply_text(
            "❌ Please enter a filename.",
            reply_markup=unlock_cancel_keyboard()
        )
        return UNLOCK_WAIT_NAME

    safe_name = Path(name).stem

    if not safe_name:
        await update.message.reply_text(
            "❌ Invalid filename. Try another name.",
            reply_markup=unlock_cancel_keyboard()
        )
        return UNLOCK_WAIT_NAME

    output_path = context.user_data.get("unlock_pdf_file")

    if not output_path or not os.path.exists(output_path):
        await update.message.reply_text(
            "❌ Unlocked PDF not found. Please start again.",
            reply_markup=unlock_cancel_keyboard()
        )
        return ConversationHandler.END

    final_path = os.path.join(
        context.user_data["unlock_pdf_path"],
        f"{safe_name}.pdf"
    )

    shutil.copy2(output_path, final_path)

    try:
        await update.message.reply_document(
            document=final_path,
            filename=f"{safe_name}.pdf",
            caption="🔓 PDF unlocked successfully!",
            reply_markup=unlock_main_menu_keyboard()
        )

        shutil.rmtree(
            context.user_data.get("unlock_pdf_path", ""),
            ignore_errors=True
        )

        context.user_data.pop("unlock_pdf_file", None)
        context.user_data.pop("unlock_pdf_path", None)
        context.user_data.pop("unlock_pdf_password", None)
        context.user_data.pop("unlock_pdf_filename", None)

        await update.message.reply_text(
            "🏠 NovaPDF AI\n\nChoose a tool:",
            reply_markup=InlineKeyboardMarkup([
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
                    InlineKeyboardButton("➕ More", callback_data="more")
                ]
            ])
        )

        return ConversationHandler.END

    except Exception as e:
        await update.message.reply_text(
            f"❌ Failed to send the unlocked PDF.\n\nError: {e}",
            reply_markup=unlock_cancel_keyboard()
        )
        return UNLOCK_WAIT_NAME


async def unlock_cancel(update, context):
    query = update.callback_query
    await query.answer()

    temp_dir = context.user_data.get("unlock_pdf_path")

    if temp_dir:
        shutil.rmtree(temp_dir, ignore_errors=True)

    context.user_data.pop("unlock_pdf_file", None)
    context.user_data.pop("unlock_pdf_path", None)
    context.user_data.pop("unlock_pdf_password", None)
    context.user_data.pop("unlock_pdf_filename", None)

    await query.message.edit_text(
        "🏠 NovaPDF AI\n\nChoose a tool:",
        reply_markup=InlineKeyboardMarkup([
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
                InlineKeyboardButton("➕ More", callback_data="more")
            ]
        ])
    )

    return ConversationHandler.END
