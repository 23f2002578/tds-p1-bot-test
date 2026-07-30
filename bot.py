from dotenv import load_dotenv
load_dotenv()
import os, json
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
        answer = raw  # fallback

    reply = json.dumps({"answer": answer, "log_url": LOG_URL})
    await update.message.reply_text(reply)

app = ApplicationBuilder().token(os.environ["TELEGRAM_TOKEN"]).build()
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))
print("Bot is running... waiting for messages")
app.run_polling()
