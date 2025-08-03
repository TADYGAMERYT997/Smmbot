import logging
import json
import os
import time
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackContext,
    CallbackQueryHandler,
    filters
)

# CONFIGURATION
TELEGRAM_BOT_TOKEN = "8248430563:AAEFh9LuXIwMUchIRC73feFEZwtldpap3I0"
SMM_API_KEY = "9f48a241c91479126bbc655465bf6a34ebcbfc89"
SMM_API_URL = "https://themainsmmprovider.in/api/v2"
SMM_SERVICE_ID = "4383"
FORCE_JOIN_CHANNEL = "@ETHICALxMETHOD"
DB_FILE = "smm_bot_database.json"
OWNER_ID = 5449258093  # Replace with your Telegram numeric ID
REFERRAL_BONUS = 2000
REFERRAL_JOINER_BONUS = 500
DAILY_BONUS = 1000
BONUS_INTERVAL = 86400  # 24 hours

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def load_database():
    if not os.path.exists(DB_FILE):
        return {"users": {}}
    try:
        with open(DB_FILE, 'r') as f:
            return json.load(f)
    except:
        return {"users": {}}

def save_database(db):
    with open(DB_FILE, 'w') as f:
        json.dump(db, f, indent=4)

async def is_user_member_of_channel(context, user_id):
    try:
        member = await context.bot.get_chat_member(chat_id=FORCE_JOIN_CHANNEL, user_id=user_id)
        return member.status in ['member', 'administrator', 'creator']
    except:
        return False

async def send_join_channel_message(update):
    keyboard = [[InlineKeyboardButton("Join Channel", url=f"https://t.me/{FORCE_JOIN_CHANNEL.lstrip('@')}")]]
    await update.message.reply_text("⚠️ Please join our channel to use the bot.", reply_markup=InlineKeyboardMarkup(keyboard))

async def start_command(update, context):
    user = update.effective_user
    user_id_str = str(user.id)
    db = load_database()

    if not await is_user_member_of_channel(context, user.id):
        await send_join_channel_message(update)
        return

    referrer_id = context.args[0] if context.args else None
    if referrer_id in db["users"] and user_id_str not in db["users"]:
        db["users"][referrer_id]["views_balance"] += REFERRAL_BONUS
        db["users"][user_id_str] = {
            "username": user.username,
            "views_balance": REFERRAL_JOINER_BONUS,
            "referred_by": referrer_id,
            "last_bonus_time": 0
        }
        await context.bot.send_message(referrer_id, f"🎉 Someone joined with your link! +{REFERRAL_BONUS} views!")
    elif user_id_str not in db["users"]:
        db["users"][user_id_str] = {
            "username": user.username,
            "views_balance": 0,
            "referred_by": None,
            "last_bonus_time": 0
        }

    save_database(db)

    keyboard = [
        [InlineKeyboardButton("🎯 Get Views", callback_data='order_flow')],
        [InlineKeyboardButton("👥 Invite & Earn", callback_data='referral')],
        [InlineKeyboardButton("💰 My Balance", callback_data='balance')],
        [InlineKeyboardButton("👤 My Referrals", callback_data='my_referrals')],
        [InlineKeyboardButton("🎁 Claim Bonus", callback_data='claim_bonus')]
    ]

    if user.id == OWNER_ID:
        keyboard.append([InlineKeyboardButton("🛠 Admin Panel", callback_data='admin_panel')])

    await update.message.reply_text("👋 Welcome! Use the buttons below:", reply_markup=InlineKeyboardMarkup(keyboard))

# BUTTON CALLBACKS

async def referral_callback(update, context):
    await update.callback_query.answer()
    user_id = str(update.callback_query.from_user.id)
    bot_username = (await context.bot.get_me()).username
    link = f"https://t.me/{bot_username}?start={user_id}"
    await update.callback_query.edit_message_text(f"🔗 Your referral link:\n`{link}`", parse_mode='Markdown')

async def balance_callback(update, context):
    await update.callback_query.answer()
    db = load_database()
    user_id = str(update.callback_query.from_user.id)
    balance = db["users"].get(user_id, {}).get("views_balance", 0)
    await update.callback_query.edit_message_text(f"💰 Your balance: {balance} views")

async def my_referrals_handler(update, context):
    await update.callback_query.answer()
    user_id = str(update.callback_query.from_user.id)
    db = load_database()
    count = sum(1 for u in db["users"].values() if u.get("referred_by") == user_id)
    await update.callback_query.edit_message_text(f"👤 Referred users: {count}\n🎁 Earned: {count * REFERRAL_BONUS} views")

async def claim_bonus_handler(update, context):
    await update.callback_query.answer()
    user_id = str(update.callback_query.from_user.id)
    db = load_database()
    now = time.time()
    last = db["users"].get(user_id, {}).get("last_bonus_time", 0)
    if now - last >= BONUS_INTERVAL:
        db["users"][user_id]["views_balance"] += DAILY_BONUS
        db["users"][user_id]["last_bonus_time"] = now
        save_database(db)
        await update.callback_query.edit_message_text("🎁 1000 views added! Come back in 24h.")
    else:
        hours_left = int((BONUS_INTERVAL - (now - last)) / 3600)
        await update.callback_query.edit_message_text(f"⏳ Wait {hours_left} hours to claim again.")

# GET VIEWS FLOW

async def order_flow_start(update, context):
    await update.callback_query.answer()
    context.user_data['next_step'] = 'get_view_amount'
    await update.callback_query.edit_message_text("📝 How many views do you want? (Minimum 100)")

async def handle_user_steps(update, context):
    step = context.user_data.get('next_step')
    user_id = str(update.effective_user.id)
    db = load_database()

    if step == 'get_view_amount':
        try:
            amount = int(update.message.text)
            if amount < 100:
                await update.message.reply_text("❌ Minimum order is 100 views.")
                return
        except:
            await update.message.reply_text("❌ Enter a valid number.")
            return

        if db["users"][user_id]["views_balance"] < amount:
            await update.message.reply_text("❌ Not enough views in your balance.")
            context.user_data.clear()
            return

        context.user_data['order_amount'] = amount
        context.user_data['next_step'] = 'get_reel_link'
        await update.message.reply_text("📎 Send your Instagram Reel link:")

    elif step == 'get_reel_link':
        link = update.message.text
        if "instagram.com/reel/" not in link:
            await update.message.reply_text("❌ Invalid reel link.")
            return

        amount = context.user_data['order_amount']
        db["users"][user_id]["views_balance"] -= amount
        save_database(db)

        await update.message.reply_text(f"✅ Sending {amount} views...")
        context.user_data.clear()

        payload = {
            'key': SMM_API_KEY,
            'action': 'add',
            'service': SMM_SERVICE_ID,
            'link': link,
            'quantity': amount
        }

        try:
            res = requests.post(SMM_API_URL, data=payload, timeout=30)
            data = res.json()
            if 'order' in data:
                await update.message.reply_text(f"🚀 Order placed! Order ID: {data['order']}")
            else:
                await update.message.reply_text(f"⚠️ Error: {data.get('error', 'unknown error')}")
                db["users"][user_id]["views_balance"] += amount
                save_database(db)
        except:
            await update.message.reply_text("❌ API Error. Views refunded.")
            db["users"][user_id]["views_balance"] += amount
            save_database(db)

# MAIN BOT SETUP

def main():
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CallbackQueryHandler(balance_callback, pattern='balance'))
    app.add_handler(CallbackQueryHandler(referral_callback, pattern='referral'))
    app.add_handler(CallbackQueryHandler(my_referrals_handler, pattern='my_referrals'))
    app.add_handler(CallbackQueryHandler(claim_bonus_handler, pattern='claim_bonus'))
    app.add_handler(CallbackQueryHandler(order_flow_start, pattern='order_flow'))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_user_steps))
    print("✅ Bot is running...")
    app.run_polling()

if __name__ == '__main__':
    main()