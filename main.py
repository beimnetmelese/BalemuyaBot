import os
import logging
import requests
from fastapi import FastAPI, Request, HTTPException
from pydantic import BaseModel
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters
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


class SendMessagePayload(BaseModel):
    telegram_id: str
    message: str
    button_text: str
    button_url: str

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

async def handle_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    contact = update.message.contact if update.message else None
    if not contact:
        return

    telegram_id = contact.user_id or (update.effective_user.id if update.effective_user else None)
    phone_number = contact.phone_number

    if not telegram_id or not phone_number:
        await update.message.reply_text("Failed to read your phone number. Please try again.")
        return

    payload = {
        "telegram_id": str(telegram_id),
        "phone_number": phone_number,
    }

    # Best-effort fill for name/username if present
    if update.effective_user:
        if update.effective_user.username:
            payload["username"] = update.effective_user.username
        if update.effective_user.full_name:
            payload["full_name"] = update.effective_user.full_name

    try:
        resp = requests.post(f"{BACKEND_URL}/accounts/", json=payload, timeout=10)
        if resp.status_code in (200, 201):
            await update.message.reply_text("Phone number saved. You can continue in the WebApp.")
        else:
            logging.error(f"Failed to save phone number: {resp.status_code} {resp.text}")
            await update.message.reply_text("Failed to save your phone number. Please try again.")
    except Exception as e:
        logging.error(f"Error saving phone number: {e}")
        await update.message.reply_text("Failed to save your phone number. Please try again.")

# ---------------- Startup / Shutdown ----------------
@app.on_event("startup")
async def startup():
    global telegram_app
    telegram_app = Application.builder().token(TOKEN).build()
    telegram_app.add_handler(CommandHandler("start", start))
    telegram_app.add_handler(MessageHandler(filters.CONTACT, handle_contact))

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


@app.post("/telegram/send")
async def send_message(payload: SendMessagePayload):
    if not telegram_app or not telegram_app.bot:
        raise HTTPException(status_code=503, detail="Bot not initialized")

    keyboard = InlineKeyboardMarkup(
        [[InlineKeyboardButton(payload.button_text, web_app=WebAppInfo(url=payload.button_url))]]
    )
    await telegram_app.bot.send_message(
        chat_id=payload.telegram_id,
        text=payload.message,
        reply_markup=keyboard,
    )
    return {"ok": True}
