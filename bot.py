import asyncio
import sys

# Fix for Python 3.11+ (Render uses 3.13)
if sys.version_info >= (3, 11):
    asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())
    
import logging, asyncio, re, os
import aiosqlite
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import (
    ApplicationBuilder, CommandHandler, ContextTypes,
    MessageHandler, filters, CallbackQueryHandler
)

# -------- CONFIG --------
BOT_TOKEN = os.getenv("BOT_TOKEN")   # <-- secure way
ADMIN_ID = int(os.getenv("ADMIN_ID"))  # you can set this in Render too
PRICE = 20
CONTENT_LINK = "https://www.mediafire.com/file/4afv87x0m2spvdl/PicsArt-Premium.apk/file"
DB_PATH = "orders.db"
QR_IMAGE_PATH = "SAVE_20250525_140613.jpg"   # put the file inside repo

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("pay-bot")

# -------- DB --------
CREATE_SQL = """
CREATE TABLE IF NOT EXISTS orders (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  username TEXT,
  utr TEXT,
  status TEXT DEFAULT 'PENDING',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(CREATE_SQL)
        await db.commit()

async def save_order(user_id, username, utr):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO orders (user_id, username, utr) VALUES (?,?,?)",
            (user_id, username, utr),
        )
        await db.commit()

async def update_order(user_id, status):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE orders SET status=? WHERE user_id=?", (status, user_id))
        await db.commit()

# -------- HANDLERS --------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"👋 Welcome! To PicsArt Premium bot.\n\n"
        f"To get PicsArt Premium Click On /get."
    )

async def get_app(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        f"💳 Pay **₹{PRICE}** using the QR below.\n\n"
        "➡️ After payment, send your 12-digit UTR number here."
    )
    with open(QR_IMAGE_PATH, "rb") as qr:
        await update.message.reply_photo(photo=qr, caption=msg, parse_mode=ParseMode.MARKDOWN)

UTR_REGEX = re.compile(r"^\d{12}$")

async def utr_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    utr_code = update.message.text.strip()
    if not UTR_REGEX.fullmatch(utr_code):
        await update.message.reply_text("❌ Invalid UTR. Please enter exactly 12 digits (numbers only).")
        return

    user = update.effective_user
    await save_order(user.id, user.username or "", utr_code)
    await update.message.reply_text("🕒 UTR saved! Wait for admin approval.")

    keyboard = [
        [
            InlineKeyboardButton("✅ Approve", callback_data=f"approve:{user.id}"),
            InlineKeyboardButton("❌ Reject", callback_data=f"reject:{user.id}")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    admin_msg = (
        f"📥 New Payment Request\n\n"
        f"👤 User: {user.mention_html()} (ID: {user.id})\n"
        f"💳 UTR: <code>{utr_code}</code>"
    )
    await context.bot.send_message(
        chat_id=ADMIN_ID,
        text=admin_msg,
        parse_mode="HTML",
        reply_markup=reply_markup
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.from_user.id != ADMIN_ID:
        await query.answer("⛔ Not authorized", show_alert=True)
        return

    action, user_id = query.data.split(":")
    user_id = int(user_id)

    if action == "approve":
        await update_order(user_id, "APPROVED")
        await context.bot.send_message(
            chat_id=user_id,
            text=f"✅ Payment verified!\nHere is your PicsArt Premium: {CONTENT_LINK}"
        )
        await query.edit_message_text(f"✅ Approved user {user_id}")
    elif action == "reject":
        await update_order(user_id, "REJECTED")
        await context.bot.send_message(
            chat_id=user_id,
            text="❌ Payment rejected. Please contact admin if mistake."
        )
        await query.edit_message_text(f"❌ Rejected user {user_id}")

# -------- MAIN --------
async def main():
    await init_db()
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("get", get_app))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, utr_handler))
    app.add_handler(CallbackQueryHandler
(button_handler))
    logger.info("Bot started")
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(init_db())   # init DB

    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("get", get_app))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, utr_handler))
    app.add_handler(CallbackQueryHandler(button_handler))

    logger.info("Bot started")
    app.run_polling()
    


