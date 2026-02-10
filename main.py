import os
import logging
import requests
from fastapi import FastAPI, Request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import Application, CommandHandler, ContextTypes
from dotenv import load_dotenv

# ---------------- Load environment ----------------
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
BACKEND_URL = os.getenv("BACKEND_URL")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # e.g., https://balemuyabot.onrender.com/telegram/webhook

# ---------------- Logging ----------------
logging.basicConfig(level=logging.INFO)

# ---------------- FastAPI App ----------------
app = FastAPI()
telegram_app: Application = None  # will initialize at startup

# ---------------- Helper Functions ----------------
def get_user_services(telegram_id):
    try:
        resp = requests.get(f"{BACKEND_URL}/services/?provider_telegram_id={telegram_id}")
        return resp.json() if resp.status_code == 200 else []
    except Exception as e:
        logging.error(f"Error fetching services: {e}")
        return []

async def get_user_profile(telegram_id):
    try:
        resp = requests.get(f"{BACKEND_URL}/accounts/{telegram_id}/")
        return resp.json() if resp.status_code == 200 else None
    except Exception as e:
        logging.error(f"Error fetching profile: {e}")
        return None

# ---------------- Telegram Handlers ----------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id

    try:
        requests.post(f"{BACKEND_URL}/accounts/telegram-users/", json={"telegram_id": telegram_id})
    except Exception as e:
        logging.error(f"Failed to register Telegram user: {e}")

    profile = await get_user_profile(telegram_id)

    if not profile:
        keyboard = [
            [InlineKeyboardButton("Register as Customer", web_app=WebAppInfo(url="https://balemuya-frontend-qn6y.vercel.app/register"))],
            [InlineKeyboardButton("Register as Provider", web_app=WebAppInfo(url="https://balemuya-frontend-qn6y.vercel.app/provider"))],
        ]
        await update.message.reply_text(
            "You are not registered 😭",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    services = get_user_services(telegram_id)
    keyboard = [
        [InlineKeyboardButton("Dashboard", web_app=WebAppInfo(url="https://balemuya-frontend-qn6y.vercel.app/"))]
    ]

    if services:
        keyboard.append([InlineKeyboardButton("My Services", web_app=WebAppInfo(url="https://balemuya-frontend-qn6y.vercel.app/provider/dashboard"))])
    else:
        keyboard.append([InlineKeyboardButton("Register as Provider", web_app=WebAppInfo(url="https://balemuya-frontend-qn6y.vercel.app/provider"))])

    await update.message.reply_text(
        f"Hello {profile.get('full_name','Boss')} 😎",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ---------------- Startup / Shutdown ----------------
@app.on_event("startup")
async def startup():
    global telegram_app
    telegram_app = Application.builder().token(TOKEN).build()
    telegram_app.add_handler(CommandHandler("start", start))

    await telegram_app.initialize()
    await telegram_app.start()
    
    # Auto-register webhook on startup
    try:
        resp = requests.post(f"https://api.telegram.org/bot{TOKEN}/setWebhook?url={WEBHOOK_URL}")
        logging.info(f"Webhook registration response: {resp.text}")
    except Exception as e:
        logging.error(f"Failed to register webhook: {e}")

@app.on_event("shutdown")
async def shutdown():
    global telegram_app
    if telegram_app:
        await telegram_app.stop()
        await telegram_app.shutdown()

# ---------------- Webhook Endpoint ----------------
@app.post("/telegram/webhook")
async def telegram_webhook(request: Request):
    global telegram_app
    data = await request.json()
    update = Update.de_json(data, telegram_app.bot)
    await telegram_app.process_update(update)
    return {"ok": True}

# ---------------- Health Check ----------------
@app.get("/")
async def health_check():
    return {"status": "ok"}
