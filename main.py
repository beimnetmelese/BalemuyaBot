import os
import logging
import requests
from fastapi import FastAPI, Request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import Application, CommandHandler, ContextTypes
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
BACKEND_URL = os.getenv("BACKEND_URL")

logging.basicConfig(level=logging.INFO)

app = FastAPI()
telegram_app = Application.builder().token(TOKEN).build()


@app.on_event("startup")
async def on_startup() -> None:
    await telegram_app.initialize()
    await telegram_app.start()


@app.on_event("shutdown")
async def on_shutdown() -> None:
    await telegram_app.stop()
    await telegram_app.shutdown()

# ---------------- API Calls ----------------

def get_user_services(telegram_id):
    try:
        resp = requests.get(f"{BACKEND_URL}/services/?provider_telegram_id={telegram_id}")
        return resp.json() if resp.status_code == 200 else []
    except Exception as e:
        logging.error(e)
        return []

async def get_user_profile(telegram_id):
    try:
        resp = requests.get(f"{BACKEND_URL}/accounts/{telegram_id}/")
        return resp.json() if resp.status_code == 200 else None
    except Exception as e:
        logging.error(e)
        return None

# ---------------- Telegram Handlers ----------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id

    try:
        requests.post(f"{BACKEND_URL}/accounts/telegram-users/", json={"telegram_id": telegram_id})
    except:
        pass

    profile = await get_user_profile(telegram_id)

    if not profile:
        keyboard = [
            [InlineKeyboardButton("Register as Customer", web_app=WebAppInfo(url="https://balemuya-frontend-qn6y.vercel.app/register"))],
            [InlineKeyboardButton("Register as Provider", web_app=WebAppInfo(url="https://balemuya-frontend-qn6y.vercel.app/provider"))],
        ]
        await update.message.reply_text("You are not registered 😭", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    services = get_user_services(telegram_id)
    keyboard = [[InlineKeyboardButton("Dashboard", web_app=WebAppInfo(url="https://balemuya-frontend-qn6y.vercel.app/"))]]

    if services:
        keyboard.append([InlineKeyboardButton("My Services", web_app=WebAppInfo(url="https://balemuya-frontend-qn6y.vercel.app/provider/dashboard"))])
    else:
        keyboard.append([InlineKeyboardButton("Register as Provider", web_app=WebAppInfo(url="https://balemuya-frontend-qn6y.vercel.app/provider"))])

    await update.message.reply_text(f"Hello {profile.get('full_name','Boss')} 😎", reply_markup=InlineKeyboardMarkup(keyboard))

telegram_app.add_handler(CommandHandler("start", start))

# ---------------- Webhook Endpoint ----------------

@app.post("/telegram/webhook")
async def telegram_webhook(request: Request):
    data = await request.json()
    update = Update.de_json(data, telegram_app.bot)
    await telegram_app.process_update(update)
    return {"ok": True}
