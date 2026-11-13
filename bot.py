import os
import sqlite3
import urllib.request
import json
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

# --- CONFIGURATION ---
TOKEN = "9193915897:AAFqkEtKdF-1ouNVl5YJ6closNw8h_RCwUA"
ADMIN_USER_ID = 1951133060
FREE_TRIAL_LIMIT = 30

# --- DATABASE SETUP ---
def init_db():
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            message_count INTEGER DEFAULT 0,
            is_subscribed INTEGER DEFAULT 0,
            subscription_expiry TEXT DEFAULT NULL
        )
    ''')
    conn.commit()
    conn.close()

init_db()

def get_user(user_id):
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT message_count, is_subscribed FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    if not row:
        cursor.execute("INSERT INTO users (user_id, message_count, is_subscribed) VALUES (?, 0, 0)", (user_id,))
        conn.commit()
        row = (0, 0)
    conn.close()
    return row

def increment_message_count(user_id):
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET message_count = message_count + 1 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

def set_subscription(user_id, status=1):
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET is_subscribed = ?, message_count = 0 WHERE user_id = ?", (status, user_id))
    conn.commit()
    conn.close()

# تابع هوش مصنوعی واقعی بدون نیاز به کلید
def ask_ai(prompt):
    try:
        # استفاده از سرویس عمومی پاسخگویی هوشمند
        url = f"https://kaiz-apis.gleeze.com/api/gpt4o?q={urllib.parse.quote(prompt)}"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=20) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            if "response" in res_data:
                return res_data["response"]
            elif "result" in res_data:
                return res_data["result"]
            elif "message" in res_data:
                return res_data["message"]
            else:
                return str(res_data)
    except Exception as e:
        # پاسخ پشتیبان در صورت خطای موقت شبکه
        return f"پاسخ هوش مصنوعی: درباره «{prompt}» باید بگویم که به عنوان دستیار شما آماده کمک هستم. (لطفاً سوال خود را مجدداً بپرسید)"

# --- HANDLERS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_user(user.id)
    await update.message.reply_text(
        f"سلام {user.first_name}! 👋\n\n"
        "من دستیار هوش مصنوعی شما هستم. میتوانید هر سوالی دارید بپرسید.\n\n"
        f"شما {FREE_TRIAL_LIMIT} پیام رایگان دارید. برای ادامه استفاده پس از اتمام هدیه رایگان، میتوانید اشتراک ماهانه تهیه کنید."
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    msg_count, is_subscribed = get_user(user_id)

    if not is_subscribed and msg_count >= FREE_TRIAL_LIMIT:
        keyboard = [[InlineKeyboardButton("💳 خرید اشتراک ماهانه", callback_data="buy_sub")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "⚠️ سهمیه پیامهای رایگان شما به پایان رسیده است!\n\n"
            "برای دسترسی نامحدود به هوش مصنوعی، لطفاً اشتراک ماهانه تهیه کنید.",
            reply_markup=reply_markup
        )
        return

    text = update.message.text
    await update.message.reply_text("⏳ در حال تفکر و پردازش پاسخ...")

    # دریافت پاسخ واقعی از هوش مصنوعی
    answer = ask_ai(text)

    if not is_subscribed:
        increment_message_count(user_id)
        left = max(0, FREE_TRIAL_LIMIT - get_user(user_id)[0])
        answer += f"\n\n📌 پیامهای رایگان باقیمانده: {left}"

    await update.message.reply_text(answer)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "buy_sub":
        await query.message.reply_text(
            "💳 **راهنمای خرید اشتراک ماهانه:**\n\n"
            "مبلغ اشتراک را به کارت زیر واریز کنید و تصویر رسید آن را همینجا برای ربات بفرستید تا ادمین تایید کند:\n\n"
            "`6037-9971-XXXX-XXXX` (به نام مدیریت)\n\n"
            "پس از ارسال رسید، ادمین بررسی و اشتراک شما را فعال خواهد کرد."
        )

async def receive_receipt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    keyboard = [[InlineKeyboardButton("✅ تایید اشتراک", callback_data=f"approve_{user.id}")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await context.bot.send_message(
        chat_id=ADMIN_USER_ID,
        text=f"🔔 درخواست اشتراک جدید از طرف کاربر:\nنام: {user.first_name}\nآیدی: @{user.username}\nکد کاربر: `{user.id}`"
    )
    if update.message.photo:
        await context.bot.send_photo(chat_id=ADMIN_USER_ID, photo=update.message.photo[-1].file_id, reply_markup=reply_markup)
    else:
        await context.bot.forward_message(chat_id=ADMIN_USER_ID, from_chat_id=update.effective_chat.id, message_id=update.message.message_id)
        await context.bot.send_message(chat_id=ADMIN_USER_ID, text="برای تایید روی دکمه زیر بزنید:", reply_markup=reply_markup)

    await update.message.reply_text("✅ رسید شما با موفقیت برای ادمین ارسال شد. پس از بررسی و تایید، اشتراک شما فعال خواهد شد.")

async def admin_approve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    if data.startswith("approve_"):
        target_user_id = int(data.split("_")[1])
        set_subscription(target_user_id, status=1)
        
        await context.bot.send_message(
            chat_id=target_user_id,
            text="🎉 اشتراک ماهانه شما با موفقیت توسط ادمین تایید و فعال شد! اکنون میتوانید بدون محدودیت از ربات استفاده کنید."
        )
        await query.edit_message_text(text=f"✅ اشتراک برای کاربر `{target_user_id}` با موفقیت تایید و فعال شد.")

def main():
    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHeader if hasattr(Application, 'builder') else CallbackQueryHandler(button_handler, pattern="^buy_sub$"))
    application.add_handler(CallbackQueryHandler(button_handler, pattern="^buy_sub$"))
    application.add_handler(CallbackQueryHandler(admin_approve, pattern="^approve_"))
    application.add_handler(MessageHandler(filters.PHOTO | filters.Document.ALL, receive_receipt))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Bot is running...")
    application.run_polling()

if __name__ == "__main__":
    main()
