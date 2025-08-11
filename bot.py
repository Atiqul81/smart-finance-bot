import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler

# BotFather থেকে পাওয়া তোমার টোকেন এখানে বসাও
BOT_TOKEN = "7836432905:AAFXuh9xQO7VGn95FM6emwvJhAVoqiTlbR4"

# লগিং সেটআপ
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the /start command."""
    user_name = update.effective_user.first_name
    await update.message.reply_text(f'হ্যালো, {user_name}! আমি তোমার ব্যক্তিগত বাজেট ম্যানেজার। খরচের হিসাব রাখতে আমাকে ব্যবহার করো।')

def main():
    """Starts the bot."""
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    # /start কমান্ড হ্যান্ডেলার
    application.add_handler(CommandHandler("start", start_command))

    application.run_polling()

if __name__ == '__main__':
    main()
