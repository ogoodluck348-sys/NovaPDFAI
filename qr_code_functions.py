import os
import tempfile
import shutil
import qrcode

from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ConversationHandler


QR_WAIT_TEXT = 26


def qr_cancel_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "❌ Cancel",
                callback_data="qr_cancel"
            )
        ]
    ])


def qr_result_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "🏠 Main Menu",
                callback_data="main_menu"
            )
        ]
    ])


async def qr_start(update, context):
    query = update.callback_query

    if query:
        await query.answer()
        message = query.message
    else:
        message = update.effective_message

    context.user_data.pop("qr_file", None)
    context.user_data.pop("qr_dir", None)

    await message.edit_text(
        "📱 QR Code Generator\n\n"
        "Send the text, link, phone number, email, or any "
        "information you want to put into the QR code.",
        reply_markup=qr_cancel_keyboard()
    )

    context.user_data["qr_prompt_message_id"] = message.message_id

    return QR_WAIT_TEXT


async def qr_receive_text(update, context):
    text = update.effective_message.text

    if not text or not text.strip():
        await update.effective_message.reply_text(
            "❌ Please send some text or information.",
            reply_markup=qr_cancel_keyboard()
        )
        return QR_WAIT_TEXT

    text = text.strip()

    temp_dir = tempfile.mkdtemp(prefix="nova_qr_")
    qr_path = os.path.join(temp_dir, "qr_code.png")

    try:
        qr = qrcode.QRCode(
            version=None,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=10,
            border=4
        )

        qr.add_data(text)
        qr.make(fit=True)

        image = qr.make_image(
            fill_color="black",
            back_color="white"
        )

        image.save(qr_path)

        context.user_data["qr_dir"] = temp_dir
        context.user_data["qr_file"] = qr_path

        await update.effective_message.reply_photo(
            photo=qr_path,
            caption="📱 QR Code generated successfully!",
            reply_markup=qr_result_keyboard()
        )

        return ConversationHandler.END

    except Exception as e:
        shutil.rmtree(temp_dir, ignore_errors=True)

        await update.effective_message.reply_text(
            f"❌ Failed to generate QR code.\n\nError: {e}",
            reply_markup=qr_cancel_keyboard()
        )

        return QR_WAIT_TEXT


async def qr_cancel(update, context):
    query = update.callback_query
    await query.answer()

    temp_dir = context.user_data.get("qr_dir")

    if temp_dir:
        shutil.rmtree(temp_dir, ignore_errors=True)

    context.user_data.clear()

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
