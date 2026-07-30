from dotenv import load_dotenv
load_dotenv()
import os, json, threading
from fastapi import FastAPI
from fastapi.responses import FileResponse
import uvicorn
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, ContextTypes, filters
from agent import answer_question

LOG_URL = os.environ["LOG_URL"]

async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    question = update.message.text
    raw = answer_question(question)
    try:
        parsed = json.loads(raw)
        answer = parsed.get("answer", parsed)
    except Exception:
        answer = raw
    reply = json.dumps({"answer": answer, "log_url": LOG_URL})
    await update.message.reply_text(reply)

import asyncio

def run_bot():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    app = ApplicationBuilder().token(os.environ["TELEGRAM_TOKEN"]).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))
    app.run_polling(stop_signals=None)
    
web = FastAPI()

@web.get("/health")
def health():
    return {"ok": True}

@web.get("/run.jsonl")
def run_log():
    return FileResponse("logs/run.jsonl", media_type="application/jsonl")

if __name__ == "__main__":
    threading.Thread(target=run_bot, daemon=True).start()
    uvicorn.run(web, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
