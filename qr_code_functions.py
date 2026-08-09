import os
import tempfile
import shutil
import qrcode
from PIL import Image
from qrcode.image.styledpil import StyledPilImage
from qrcode.image.styles.moduledrawers import (
    SquareModuleDrawer,
    RoundedModuleDrawer,
    CircleModuleDrawer,
)

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


def qr_color_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⚫ Black", callback_data="qr_color_black"),
            InlineKeyboardButton("🔵 Blue", callback_data="qr_color_blue")
        ],
        [
            InlineKeyboardButton("🟣 Purple", callback_data="qr_color_purple"),
            InlineKeyboardButton("🟢 Green", callback_data="qr_color_green")
        ],
        [
            InlineKeyboardButton("🔴 Red", callback_data="qr_color_red")
        ],
        [
            InlineKeyboardButton("⬅️ Back", callback_data="qr_customize")
        ]
    ])


def qr_style_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("◼️ Square", callback_data="qr_style_square"),
            InlineKeyboardButton("🔘 Rounded", callback_data="qr_style_rounded")
        ],
        [
            InlineKeyboardButton("🔵 Dots", callback_data="qr_style_dots")
        ],
        [
            InlineKeyboardButton("⬅️ Back", callback_data="qr_customize")
        ]
    ])


async def qr_color_menu_callback(update, context):
    query = update.callback_query
    await query.answer()

    await query.message.edit_text(
        "🎨 Choose QR color:",
        reply_markup=qr_color_keyboard()
    )


async def qr_style_menu_callback(update, context):
    query = update.callback_query
    await query.answer()

    await query.message.edit_text(
        "🔷 Choose QR style:",
        reply_markup=qr_style_keyboard()
    )


async def qr_background_menu_callback(update, context):
    query = update.callback_query
    await query.answer()

    await query.message.edit_text(
        "⚪ Choose QR background:",
        reply_markup=qr_background_keyboard()
    )


async def qr_style_callback(update, context):
    query = update.callback_query
    await query.answer()

    styles = {
        "qr_style_square": ("◼️ Square", "square"),
        "qr_style_rounded": ("🔘 Rounded", "rounded"),
        "qr_style_dots": ("🔵 Dots", "dots"),
    }

    label, style = styles.get(
        query.data,
        ("◼️ Square", "square")
    )

    context.user_data["qr_style"] = style

    await query.message.edit_text(
        f"📱 QR Code Generator\n\n"
        f"🔷 Style: {label}\n\n"
        f"Choose another customization or generate your QR code.",
        reply_markup=qr_customize_keyboard()
    )


def qr_background_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⚪ White", callback_data="qr_bg_white"),
            InlineKeyboardButton("🩵 Light Blue", callback_data="qr_bg_lightblue")
        ],
        [
            InlineKeyboardButton("🟣 Light Purple", callback_data="qr_bg_lightpurple")
        ],
        [
            InlineKeyboardButton("⬅️ Back", callback_data="qr_customize")
        ]
    ])


async def qr_background_callback(update, context):
    query = update.callback_query
    await query.answer()

    backgrounds = {
        "qr_bg_white": ("⚪ White", "white"),
        "qr_bg_lightblue": ("🩵 Light Blue", "#EAF6FF"),
        "qr_bg_lightpurple": ("🟣 Light Purple", "#F3EFFF"),
    }

    label, background = backgrounds.get(
        query.data,
        ("⚪ White", "white")
    )

    context.user_data["qr_background"] = background

    await query.message.edit_text(
        f"📱 QR Code Generator\n\n"
        f"⚪ Background: {label}\n\n"
        f"Choose another customization or generate your QR code.",
        reply_markup=qr_customize_keyboard()
    )


def qr_customize_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🎨 Color", callback_data="qr_color"),
            InlineKeyboardButton("🔷 Style", callback_data="qr_style")
        ],
        [
            InlineKeyboardButton("⚪ Background", callback_data="qr_background")
        ],
        [
            InlineKeyboardButton("✨ Generate QR", callback_data="qr_generate")
        ],
        [
            InlineKeyboardButton("❌ Cancel", callback_data="qr_cancel")
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


async def qr_color_callback(update, context):
    query = update.callback_query
    await query.answer()

    colors = {
        "qr_color_black": ("⚫ Black", "black"),
        "qr_color_blue": ("🔵 Blue", "blue"),
        "qr_color_purple": ("🟣 Purple", "purple"),
        "qr_color_green": ("🟢 Green", "green"),
        "qr_color_red": ("🔴 Red", "red"),
    }

    label, color = colors.get(
        query.data,
        ("⚫ Black", "black")
    )

    context.user_data["qr_color"] = color

    await query.message.edit_text(
        f"📱 QR Code Generator\n\n"
        f"🎨 Color: {label}\n\n"
        f"Choose another customization or generate your QR code.",
        reply_markup=qr_customize_keyboard()
    )


async def qr_customize_callback(update, context):
    query = update.callback_query
    await query.answer()

    await query.message.edit_text(
        "📱 QR Code Generator\n\n"
        "Choose a customization:",
        reply_markup=qr_customize_keyboard()
    )


async def qr_receive_text(update, context):
    text = update.effective_message.text

    if not text or not text.strip():
        await update.effective_message.reply_text(
            "❌ Please send some text or information.",
            reply_markup=qr_cancel_keyboard()
        )
        return QR_WAIT_TEXT

    context.user_data["qr_text"] = text.strip()
    context.user_data.setdefault("qr_color", "black")
    context.user_data.setdefault("qr_style", "square")
    context.user_data.setdefault("qr_background", "white")

    await update.effective_message.reply_text(
        "📱 QR Code Generator\n\n"
        "Your content has been received.\n\n"
        "Choose how you want your QR code to look:",
        reply_markup=qr_customize_keyboard()
    )

    return QR_WAIT_TEXT


async def qr_generate_callback(update, context):
    query = update.callback_query
    await query.answer("Generating QR code...")

    text = context.user_data.get("qr_text")

    if not text:
        await query.message.edit_text(
            "❌ Your QR content was lost. Please start again.",
            reply_markup=qr_cancel_keyboard()
        )
        return QR_WAIT_TEXT

    color = context.user_data.get("qr_color", "black")
    background = context.user_data.get("qr_background", "white")
    style = context.user_data.get("qr_style", "square")

    colors = {
        "black": "black",
        "blue": "#1877F2",
        "purple": "#7B2CBF",
        "green": "#16A34A",
        "red": "#DC2626",
    }

    drawer_classes = {
        "square": SquareModuleDrawer,
        "rounded": RoundedModuleDrawer,
        "dots": CircleModuleDrawer,
    }

    fill_color = colors.get(color, "black")
    drawer_class = drawer_classes.get(style, SquareModuleDrawer)

    temp_dir = tempfile.mkdtemp(prefix="nova_qr_")
    qr_path = os.path.join(temp_dir, "qr_code.png")

    try:
        qr = qrcode.QRCode(
            version=None,
            error_correction=qrcode.constants.ERROR_CORRECT_H,
            box_size=10,
            border=4
        )

        qr.add_data(text)
        qr.make(fit=True)

        image = qr.make_image(
            image_factory=StyledPilImage,
            module_drawer=drawer_class(),
            color=fill_color,
            back_color=background
        ).convert("RGB")

        # Add "SCAN ME" underneath the QR code
        from PIL import ImageDraw, ImageFont

        padding = 25
        text_height = 70

        final_image = Image.new(
            "RGB",
            (image.width, image.height + text_height + padding),
            background
        )

        final_image.paste(image, (0, 0))

        draw = ImageDraw.Draw(final_image)

        try:
            font = ImageFont.truetype(
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                42
            )
        except Exception:
            font = ImageFont.load_default()

        label = "SCAN ME"
        bbox = draw.textbbox((0, 0), label, font=font)
        text_width = bbox[2] - bbox[0]

        draw.text(
            ((final_image.width - text_width) / 2, image.height + 12),
            label,
            fill=fill_color,
            font=font
        )

        final_image.save(qr_path)

        await query.message.reply_photo(
            photo=qr_path,
            caption="📱 QR Code generated successfully!",
            reply_markup=qr_result_keyboard()
        )

        shutil.rmtree(temp_dir, ignore_errors=True)

        context.user_data.clear()

        return ConversationHandler.END

    except Exception as e:
        shutil.rmtree(temp_dir, ignore_errors=True)

        await query.message.edit_text(
            f"❌ Failed to generate QR code.\n\nError: {e}",
            reply_markup=qr_customize_keyboard()
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
