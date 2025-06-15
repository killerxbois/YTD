from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
import yt_dlp
import os
import json
from datetime import datetime
from threading import Thread
from http.server import BaseHTTPRequestHandler, HTTPServer

BOT_TOKEN = "7586091566:AAGw_jZYta7aDK71sG-ZVYdBBfvb9h9S5Sk"
ADMIN_ID = 7586091566
user_links = {}
usage_log = "usage_log.json"
download_count = "count.log"

# Fake server for Render
class FakeServer(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is Running on Render!")

def run_fake_server():
    server = HTTPServer(('0.0.0.0', 10000), FakeServer)
    server.serve_forever()

Thread(target=run_fake_server).start()

# Usage log functions
def load_usage():
    if os.path.exists(usage_log):
        with open(usage_log, "r") as f:
            return json.load(f)
    return {}

def save_usage(data):
    with open(usage_log, "w") as f:
        json.dump(data, f)

def increment_count():
    count = 0
    if os.path.exists(download_count):
        with open(download_count, "r") as f:
            count = int(f.read().strip())
    count += 1
    with open(download_count, "w") as f:
        f.write(str(count))
    return count

# Bot handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🎉 Welcome to YTD BOT Pro!\nSend any YouTube link to choose Audio or Video download.")

async def handle_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    today = datetime.now().strftime("%Y-%m-%d")
    usage = load_usage()
    if user_id not in usage:
        usage[user_id] = {}
    if usage[user_id].get(today, 0) >= 10:
        await update.message.reply_text("🚫 Daily limit reached (10 downloads/day). Try again tomorrow.")
        return

    url = update.message.text.strip()
    if "youtube.com" not in url and "youtu.be" not in url:
        await update.message.reply_text("❌ Please send a valid YouTube link.")
        return

    user_links[update.effective_chat.id] = url

    buttons = [
        [InlineKeyboardButton("🎵 Audio (MP3)", callback_data="audio")],
        [InlineKeyboardButton("🎥 Video (MP4)", callback_data="video")]
    ]
    await update.message.reply_text("Choose format to download:", reply_markup=InlineKeyboardMarkup(buttons))

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    chat_id = query.message.chat_id
    user_id = str(query.from_user.id)
    today = datetime.now().strftime("%Y-%m-%d")
    usage = load_usage()

    if user_id not in usage:
        usage[user_id] = {}
    usage[user_id][today] = usage[user_id].get(today, 0) + 1
    save_usage(usage)

    url = user_links.get(chat_id)
    if not url:
        await query.edit_message_text("❌ Link expired. Send again.")
        return

    choice = query.data
    await query.edit_message_text("⏳ Downloading... Please wait.")
    os.makedirs("downloads", exist_ok=True)

    try:
        if choice == "audio":
            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': 'downloads/%(title)s.%(ext)s',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
                'cookiefile': 'cookies.txt',
                'quiet': True
            }
            ext = "mp3"
        else:
            ydl_opts = {
                'format': 'bestvideo+bestaudio/best',
                'outtmpl': 'downloads/%(title)s.%(ext)s',
                'merge_output_format': 'mp4',
                'cookiefile': 'cookies.txt',
                'quiet': True
            }
            ext = "mp4"

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info).replace(".webm", f".{ext}").replace(".mkv", f".{ext}")
            if choice == "audio":
                filename = filename.replace(".mp4", ".mp3")

        await context.bot.send_chat_action(chat_id=chat_id, action="upload_document")
        with open(filename, 'rb') as file:
            if choice == "audio":
                await context.bot.send_audio(chat_id=chat_id, audio=file, title=info.get('title', 'Audio'))
            else:
                await context.bot.send_video(chat_id=chat_id, video=file, caption=info.get('title', 'Video'))

        os.remove(filename)
        increment_count()

    except Exception as e:
        await context.bot.send_message(chat_id=chat_id, text=f"❌ Error: {str(e)}")

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    count = 0
    if os.path.exists(download_count):
        with open(download_count, "r") as f:
            count = f.read().strip()
    await update.message.reply_text(f"📊 Total downloads: {count}")

# Run the bot
app = ApplicationBuilder().token(BOT_TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("stats", stats))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_link))
app.add_handler(CallbackQueryHandler(button_handler))

if __name__ == '__main__':
    app.run_polling()
