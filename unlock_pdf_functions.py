import tempfile
import os
import shutil
from pathlib import Path

from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ConversationHandler

UNLOCK_WAIT_FILE = 23
UNLOCK_WAIT_PASSWORD = 24
UNLOCK_WAIT_NAME = 25


def main_menu_button():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]
    ])


def unlock_cancel_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ Cancel", callback_data="unlock_cancel")]
    ])


async def remove_unlock_prompt_cancel(update, context):
    message_id = context.user_data.get(
        "unlock_prompt_message_id"
    )

    if not message_id:
        return

    try:
        await context.bot.edit_message_reply_markup(
            chat_id=update.effective_chat.id,
            message_id=message_id,
            reply_markup=None
        )
    except Exception:
        pass


async def unlock_start(update, context):
    query = update.callback_query

    if query:
        await query.answer()
        message = query.message
    else:
        message = update.effective_message

    context.user_data.clear()

    await message.edit_text(
        "🔓 Unlock PDF\n\n"
        "Send the password-protected PDF you want to unlock.",
        reply_markup=unlock_cancel_keyboard()
    )

    context.user_data["unlock_prompt_message_id"] = message.message_id

    return UNLOCK_WAIT_FILE


async def unlock_receive_file(update, context):
    await remove_unlock_prompt_cancel(
        update,
        context
    )

    document = update.effective_message.document

    if not document or not document.file_name:
        prompt = await update.effective_message.reply_text(
            "❌ Invalid file.\n\n"
            "Please send a PDF file.",
            reply_markup=unlock_cancel_keyboard()
        )

        context.user_data["unlock_prompt_message_id"] = (
            prompt.message_id
        )

        return UNLOCK_WAIT_FILE

    if not document.file_name.lower().endswith(".pdf"):
        prompt = await update.effective_message.reply_text(
            "❌ Invalid file.\n\n"
            "Please send a PDF file.",
            reply_markup=unlock_cancel_keyboard()
        )

        context.user_data["unlock_prompt_message_id"] = (
            prompt.message_id
        )

        return UNLOCK_WAIT_FILE

    temp_dir = context.user_data.get("unlock_pdf_path")

    if not temp_dir:
        temp_dir = tempfile.mkdtemp(
            prefix="nova_unlock_"
        )
        context.user_data["unlock_pdf_path"] = temp_dir

    file_path = os.path.join(
        temp_dir,
        document.file_name
    )

    try:
        telegram_file = await document.get_file()
        await telegram_file.download_to_drive(file_path)

        from PyPDF2 import PdfReader

        reader = PdfReader(file_path)

        # Detect whether the PDF is actually encrypted.
        if not reader.is_encrypted:
            shutil.rmtree(
                temp_dir,
                ignore_errors=True
            )

            context.user_data.clear()

            await update.effective_message.reply_text(
                "🔓 This PDF is not password-protected.\n\n"
                "No password is required.",
                reply_markup=main_menu_button()
            )

            return ConversationHandler.END

        context.user_data["unlock_pdf_file"] = file_path

        prompt = await update.effective_message.reply_text(
            "🔑 <b>Enter the PDF password</b>\n\n"
            "Send the password used to protect this PDF.",
            parse_mode="HTML",
            reply_markup=unlock_cancel_keyboard()
        )

        context.user_data["unlock_prompt_message_id"] = (
            prompt.message_id
        )

        return UNLOCK_WAIT_PASSWORD

    except Exception as e:
        logger = getattr(
            context,
            "application",
            None
        )

        if logger:
            try:
                logger.logger.error(
                    f"Unlock PDF validation error: {e}"
                )
            except Exception:
                pass

        prompt = await update.effective_message.reply_text(
            "❌ This doesn't appear to be a valid PDF.\n\n"
            "Please send a valid PDF file.",
            reply_markup=unlock_cancel_keyboard()
        )

        context.user_data["unlock_prompt_message_id"] = (
            prompt.message_id
        )

        if temp_dir and os.path.exists(temp_dir):
            shutil.rmtree(
                temp_dir,
                ignore_errors=True
            )

        context.user_data.pop(
            "unlock_pdf_file",
            None
        )
        context.user_data.pop(
            "unlock_pdf_path",
            None
        )

        return UNLOCK_WAIT_FILE


async def unlock_receive_password(update, context):
    await remove_unlock_prompt_cancel(
        update,
        context
    )

    password = update.effective_message.text

    if not password or not password.strip():
        prompt = await update.effective_message.reply_text(
            "❌ Please enter the PDF password.",
            reply_markup=unlock_cancel_keyboard()
        )

        context.user_data["unlock_prompt_message_id"] = (
            prompt.message_id
        )

        return UNLOCK_WAIT_PASSWORD

    pdf_path = context.user_data.get(
        "unlock_pdf_file"
    )

    if not pdf_path or not os.path.exists(pdf_path):
        prompt = await update.effective_message.reply_text(
            "❌ PDF file not found.\n\n"
            "Please send the PDF again.",
            reply_markup=unlock_cancel_keyboard()
        )

        context.user_data["unlock_prompt_message_id"] = (
            prompt.message_id
        )

        return UNLOCK_WAIT_FILE

    try:
        from PyPDF2 import PdfReader, PdfWriter

        reader = PdfReader(pdf_path)

        if not reader.is_encrypted:
            temp_dir = context.user_data.get(
                "unlock_pdf_path"
            )

            if temp_dir:
                shutil.rmtree(
                    temp_dir,
                    ignore_errors=True
                )

            context.user_data.clear()

            await update.effective_message.reply_text(
                "🔓 This PDF is not password-protected.\n\n"
                "No password is required.",
                reply_markup=main_menu_button()
            )

            return ConversationHandler.END

        result = reader.decrypt(password)

        if result == 0:
            prompt = await update.effective_message.reply_text(
                "❌ Incorrect password.\n\n"
                "Please try again.",
                reply_markup=unlock_cancel_keyboard()
            )

            context.user_data["unlock_prompt_message_id"] = (
                prompt.message_id
            )

            return UNLOCK_WAIT_PASSWORD

        writer = PdfWriter()

        for page in reader.pages:
            writer.add_page(page)

        unlocked_path = os.path.join(
            context.user_data["unlock_pdf_path"],
            "unlocked.pdf"
        )

        with open(
            unlocked_path,
            "wb"
        ) as output:
            writer.write(output)

        context.user_data["unlock_pdf_file"] = unlocked_path

        prompt = await update.effective_message.reply_text(
            "✅ PDF unlocked successfully!\n\n"
            "Now enter the name for the unlocked PDF.\n\n"
            "Example: <code>My Document</code>",
            parse_mode="HTML",
            reply_markup=unlock_cancel_keyboard()
        )

        context.user_data["unlock_prompt_message_id"] = (
            prompt.message_id
        )

        return UNLOCK_WAIT_NAME

    except Exception:
        prompt = await update.effective_message.reply_text(
            "❌ Could not unlock this PDF with that password.\n\n"
            "Please check the password and try again.",
            reply_markup=unlock_cancel_keyboard()
        )

        context.user_data["unlock_prompt_message_id"] = (
            prompt.message_id
        )

        return UNLOCK_WAIT_PASSWORD


async def unlock_receive_name(update, context):
    await remove_unlock_prompt_cancel(
        update,
        context
    )

    name = update.effective_message.text.strip()

    if not name:
        prompt = await update.effective_message.reply_text(
            "❌ Please enter a filename.",
            reply_markup=unlock_cancel_keyboard()
        )

        context.user_data["unlock_prompt_message_id"] = (
            prompt.message_id
        )

        return UNLOCK_WAIT_NAME

    safe_name = "".join(
        c for c in Path(name).stem
        if c.isalnum() or c in " -_()"
    ).strip()

    if not safe_name:
        prompt = await update.effective_message.reply_text(
            "❌ Invalid filename.\n\n"
            "Please enter another name.",
            reply_markup=unlock_cancel_keyboard()
        )

        context.user_data["unlock_prompt_message_id"] = (
            prompt.message_id
        )

        return UNLOCK_WAIT_NAME

    output_path = context.user_data.get(
        "unlock_pdf_file"
    )

    if not output_path or not os.path.exists(output_path):
        prompt = await update.effective_message.reply_text(
            "❌ Unlocked PDF not found.\n\n"
            "Please start again.",
            reply_markup=unlock_cancel_keyboard()
        )

        context.user_data["unlock_prompt_message_id"] = (
            prompt.message_id
        )

        return UNLOCK_WAIT_FILE

    final_path = os.path.join(
        context.user_data["unlock_pdf_path"],
        f"{safe_name}.pdf"
    )

    shutil.copy2(
        output_path,
        final_path
    )

    try:
        await update.effective_message.reply_document(
            document=final_path,
            filename=f"{safe_name}.pdf",
            caption="🔓 PDF unlocked successfully!",
            reply_markup=main_menu_button()
        )

        temp_dir = context.user_data.get(
            "unlock_pdf_path"
        )

        if temp_dir:
            shutil.rmtree(
                temp_dir,
                ignore_errors=True
            )

        context.user_data.clear()

        return ConversationHandler.END

    except Exception:
        prompt = await update.effective_message.reply_text(
            "❌ Failed to send the unlocked PDF.",
            reply_markup=main_menu_button()
        )

        context.user_data["unlock_prompt_message_id"] = (
            prompt.message_id
        )

        return UNLOCK_WAIT_NAME


async def unlock_cancel(update, context):
    query = update.callback_query
    await query.answer()

    temp_dir = context.user_data.get(
        "unlock_pdf_path"
    )

    if temp_dir and os.path.exists(temp_dir):
        shutil.rmtree(
            temp_dir,
            ignore_errors=True
        )

    context.user_data.clear()

    await query.message.edit_text(
        "🏠 NovaPDF AI\n\nChoose a tool:",
        reply_markup=main_menu_button()
    )

    return ConversationHandler.END
