from pathlib import Path
import tempfile
import shutil

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, ConversationHandler
from PIL import Image

IMG_PDF_WAIT_IMAGES = 21
IMG_PDF_WAIT_NAME = 22


def images_to_pdf_done_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(
            "✅ Done — Create PDF",
            callback_data="images_to_pdf_done"
        )],
        [InlineKeyboardButton(
            "❌ Cancel",
            callback_data="images_to_pdf_cancel"
        )]
    ])


def images_to_pdf_cancel_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(
            "❌ Cancel",
            callback_data="images_to_pdf_cancel"
        )]
    ])


async def images_to_pdf_start(update, context):
    context.user_data["images_to_pdf_files"] = []
    context.user_data["images_to_pdf_dir"] = tempfile.mkdtemp(
        prefix="nova_images_pdf_"
    )

    query = update.callback_query

    if query:
        await query.answer()
        message = query.message
        await message.edit_text(
            "🖼️ <b>Images → PDF</b>\n\n"
            "Send the images you want to combine into a PDF.\n\n"
            "You can send multiple images.\n"
            "When finished, tap <b>Done — Create PDF</b>.",
            parse_mode="HTML",
            reply_markup=images_to_pdf_done_keyboard()
        )
    else:
        await update.effective_message.reply_text(
            "🖼️ <b>Images → PDF</b>\n\n"
            "Send the images you want to combine into a PDF.\n\n"
            "You can send multiple images.\n"
            "When finished, tap <b>Done — Create PDF</b>.",
            parse_mode="HTML",
            reply_markup=images_to_pdf_done_keyboard()
        )

    return IMG_PDF_WAIT_IMAGES


async def images_to_pdf_receive_image(update, context):
    message = update.effective_message

    directory = context.user_data.get("images_to_pdf_dir")
    files = context.user_data.get("images_to_pdf_files", [])

    if not directory:
        return ConversationHandler.END

    if message.photo:
        telegram_file = await message.photo[-1].get_file()
        extension = ".jpg"
    elif message.document and message.document.mime_type:
        if not message.document.mime_type.startswith("image/"):
            await message.reply_text(
                "❌ Please send an image file.",
                reply_markup=images_to_pdf_done_keyboard()
            )
            return IMG_PDF_WAIT_IMAGES

        telegram_file = await message.document.get_file()
        extension = Path(
            message.document.file_name or ""
        ).suffix.lower() or ".jpg"
    else:
        await message.reply_text(
            "❌ Please send a JPG, JPEG or PNG image.",
            reply_markup=images_to_pdf_done_keyboard()
        )
        return IMG_PDF_WAIT_IMAGES

    number = len(files) + 1
    path = Path(directory) / f"image_{number}{extension}"

    await telegram_file.download_to_drive(str(path))

    files.append(str(path))
    context.user_data["images_to_pdf_files"] = files

    await message.reply_text(
        f"✅ Image {number} received.\n\n"
        f"🖼️ Total images: {number}\n\n"
        "Send another image or tap "
        "<b>Done — Create PDF</b>.",
        parse_mode="HTML",
        reply_markup=images_to_pdf_done_keyboard()
    )

    return IMG_PDF_WAIT_IMAGES


async def images_to_pdf_done(update, context):
    query = update.callback_query
    await query.answer()

    files = context.user_data.get("images_to_pdf_files", [])

    if not files:
        await query.message.edit_text(
            "❌ You haven't sent any images yet.\n\n"
            "Send at least one image.",
            reply_markup=images_to_pdf_done_keyboard()
        )
        return IMG_PDF_WAIT_IMAGES

    await query.message.edit_text(
        "✅ Images received.\n\n"
        "✏️ Enter the name you want for the PDF.\n\n"
        "Example: My Photos",
        reply_markup=images_to_pdf_cancel_keyboard()
    )

    return IMG_PDF_WAIT_NAME


async def images_to_pdf_receive_name(update, context):
    name = update.effective_message.text.strip()

    safe_name = "".join(
        c for c in name
        if c.isalnum() or c in " -_()"
    ).strip()

    if not safe_name:
        await update.effective_message.reply_text(
            "❌ Invalid PDF name. Please try again.",
            reply_markup=images_to_pdf_cancel_keyboard()
        )
        return IMG_PDF_WAIT_NAME

    if not safe_name.lower().endswith(".pdf"):
        safe_name += ".pdf"

    directory = context.user_data.get("images_to_pdf_dir")
    files = context.user_data.get("images_to_pdf_files", [])

    if not directory or not files:
        await update.effective_message.reply_text(
            "❌ Your image session expired. Please start again."
        )
        return ConversationHandler.END

    output_path = Path(directory) / safe_name

    await update.effective_message.reply_text(
        "⏳ Creating your PDF..."
    )

    images = []

    try:
        for file_path in files:
            image = Image.open(file_path).convert("RGB")
            images.append(image)

        images[0].save(
            str(output_path),
            "PDF",
            resolution=100.0,
            save_all=True,
            append_images=images[1:]
        )

        with open(output_path, "rb") as pdf:
            await update.effective_message.reply_document(
                document=pdf,
                filename=safe_name,
                caption=(
                    "🖼️ <b>Images converted successfully!</b>\n\n"
                    f"📄 File: <b>{safe_name}</b>\n"
                    f"🖼️ Images: <b>{len(files)}</b>"
                ),
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton(
                        "🏠 Main Menu",
                        callback_data="main_menu"
                    )]
                ])
            )

    except Exception as e:
        await update.effective_message.reply_text(
            f"❌ Failed to create PDF.\n\n"
            f"Error: {str(e)[:300]}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(
                    "🏠 Main Menu",
                    callback_data="main_menu"
                )]
            ])
        )

    finally:
        for image in images:
            try:
                image.close()
            except Exception:
                pass

        shutil.rmtree(directory, ignore_errors=True)

        context.user_data.pop("images_to_pdf_files", None)
        context.user_data.pop("images_to_pdf_dir", None)

    return ConversationHandler.END


async def images_to_pdf_cancel(update, context):
    query = update.callback_query
    await query.answer()

    directory = context.user_data.get("images_to_pdf_dir")

    if directory:
        shutil.rmtree(directory, ignore_errors=True)

    context.user_data.pop("images_to_pdf_files", None)
    context.user_data.pop("images_to_pdf_dir", None)

    await query.message.edit_text(
        "🏠 NovaPDF AI\n\nChoose a tool:",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]])
    )

    return ConversationHandler.END
