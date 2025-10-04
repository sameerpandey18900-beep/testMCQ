import logging
import os
import json
import secrets
from datetime import datetime, timedelta
import asyncio

import httpx  # Using httpx for asynchronous HTTP requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# --- Configuration ---
# FIX 2: Hardcoded API keys as requested, since environment variables are not accessible.
# WARNING: This is not secure for production. Avoid sharing this code.
TELEGRAM_BOT_TOKEN = "8385743179:AAFGeN6cO1vmrOdmTvu1IRuMTSCLg6KdQAA"
LITESHORT_API_KEY = "3872aef59e2371b1a6db2155cfa6c7a18aa08d64"

LITESHORT_API_URL = "https://liteshort.com/api"
AUTHENTICATION_EXPIRATION_HOURS = 24
FILE_AUTO_DELETE_MINUTES = 20 # How long a file sent to a user will last before deletion
USER_DATA_FILE = "user_data.json"
FILE_LINKS_FILE = "file_links.json" # New file for storing generated links

# --- Logging Setup ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Persistence Helpers ---

def load_json_data(filename: str) -> dict:
    """Loads data from a JSON file."""
    try:
        with open(filename, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_json_data(data: dict, filename: str) -> None:
    """Saves data to a JSON file."""
    with open(filename, 'w') as f:
        json.dump(data, f, indent=4)

# User Data Persistence
def load_user_data() -> dict:
    data = load_json_data(USER_DATA_FILE)
    # Convert timestamp strings back to datetime objects
    for user_info in data.values():
        if user_info.get('auth_timestamp'):
            user_info['auth_timestamp'] = datetime.fromisoformat(user_info['auth_timestamp'])
    return data

def save_user_data(data: dict) -> None:
    # Create a deep copy to avoid modifying the original dict during serialization
    data_to_save = {k: v.copy() for k, v in data.items()}
    for user_info in data_to_save.values():
        if isinstance(user_info.get('auth_timestamp'), datetime):
            user_info['auth_timestamp'] = user_info['auth_timestamp'].isoformat()
    save_json_data(data_to_save, USER_DATA_FILE)

# Load data when the bot starts
user_data = load_user_data()
file_links = load_json_data(FILE_LINKS_FILE)


# --- New asyncio-based deletion scheduler ---
async def schedule_file_deletion(context: ContextTypes.DEFAULT_TYPE, chat_id: int, sent_message_id: int, countdown_message_id: int):
    """
    Waits for a set duration, updates a countdown, and then deletes the messages.
    This replaces the need for JobQueue.
    """
    try:
        # Loop for the duration, updating the message every minute
        for i in range(FILE_AUTO_DELETE_MINUTES, 0, -1):
            await asyncio.sleep(60) # Wait for 1 minute
            minutes_left = i - 1
            if minutes_left > 0:
                countdown_text = f"⏳ This file will be automatically deleted in <b>{minutes_left:02d}:00</b>."
                # Edit message, ignoring error if it was already deleted by the user
                try:
                    await context.bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=countdown_message_id,
                        text=countdown_text,
                        parse_mode=ParseMode.HTML
                    )
                except Exception:
                    # If message is gone, stop the countdown
                    logger.info(f"Countdown message in chat {chat_id} was deleted. Stopping deletion task.")
                    return
            else:
                try:
                    await context.bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=countdown_message_id,
                        text="💥 Deleting file now...",
                        parse_mode=ParseMode.HTML
                    )
                except Exception:
                    pass # Message might be gone, proceed to delete the main file

        logger.info(f"Auto-deleting messages {[sent_message_id, countdown_message_id]} in chat {chat_id}")
        # Delete both the file message and the countdown message
        await context.bot.delete_message(chat_id=chat_id, message_id=sent_message_id)
        await context.bot.delete_message(chat_id=chat_id, message_id=countdown_message_id)
    except Exception as e:
        logger.warning(f"Could not complete the deletion process for chat {chat_id}: {e}")


# --- Helper Functions ---

def is_user_authenticated(user_id: int) -> bool:
    """Checks if a user is currently authenticated and their session is valid."""
    user_id_str = str(user_id)
    if user_id_str not in user_data:
        return False

    user = user_data[user_id_str]
    if not user.get('is_authenticated') or not user.get('auth_timestamp'):
        return False

    expiration_time = user['auth_timestamp'] + timedelta(hours=AUTHENTICATION_EXPIRATION_HOURS)
    
    # FIX 1: Corrected the variable name from 'expiration_.time' to 'expiration_time'.
    # The original code had a typo and was trying to access a '.time' attribute that doesn't exist.
    if datetime.now() > expiration_time:
        user_data.pop(user_id_str, None)
        save_user_data(user_data)
        logger.info(f"User {user_id}'s session has expired.")
        return False

    return True

async def generate_short_link(url: str) -> str | None:
    """Generates a shortened URL using the liteshort.com API asynchronously."""
    params = {'api': LITESHORT_API_KEY, 'url': url, 'format': 'text'}
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(LITESHORT_API_URL, params=params)
            response.raise_for_status()
            return response.text if response.text else None
    except (httpx.RequestError, httpx.HTTPStatusError) as e:
        logger.error(f"Error connecting to Liteshort API: {e}")
        return None

async def send_file_by_id(file_unique_id: str, chat_id: int, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Looks up a file, sends it, and starts a deletion countdown."""
    file_info = file_links.get(file_unique_id)

    if not file_info:
        await context.bot.send_message(chat_id, "😕 Oops! This file link seems to be invalid or has expired. Please request a new one.")
        logger.warning(f"File not found for unique_id: {file_unique_id} requested by chat_id: {chat_id}")
        return

    file_id = file_info['file_id']
    file_type = file_info['file_type']
    file_name = file_info.get('file_name', 'your file')

    await context.bot.send_message(chat_id, f"✅ Access Granted! 🚀\n\nSending you the file: <b>{file_name}</b>", parse_mode=ParseMode.HTML)

    sent_message = None
    try:
        if file_type == 'document':
            sent_message = await context.bot.send_document(chat_id, document=file_id)
        elif file_type == 'photo':
            sent_message = await context.bot.send_photo(chat_id, photo=file_id)
        elif file_type == 'video':
            sent_message = await context.bot.send_video(chat_id, video=file_id)
        elif file_type == 'audio':
            sent_message = await context.bot.send_audio(chat_id, audio=file_id)
    except Exception as e:
        logger.error(f"Failed to send file {file_id} to {chat_id}: {e}")
        await context.bot.send_message(chat_id, "❌ Oh no! An error occurred while sending the file. It might have been removed from Telegram's servers.")
        return

    if sent_message:
        delete_in_minutes = FILE_AUTO_DELETE_MINUTES
        initial_countdown_text = f"⏳ This file is ephemeral! It will self-destruct in <b>{delete_in_minutes:02d}:00</b>."
        countdown_message = await context.bot.send_message(
            chat_id=chat_id,
            text=initial_countdown_text,
            parse_mode=ParseMode.HTML
        )

        # Schedule the deletion task to run in the background
        asyncio.create_task(
            schedule_file_deletion(
                context,
                chat_id,
                sent_message.message_id,
                countdown_message.message_id
            )
        )

async def generate_and_send_auth_link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Generates a new authentication link and sends it to the user."""
    user = update.effective_user
    user_id_str = str(user.id)
    bot_info = await context.bot.get_me()
    
    auth_token = secrets.token_urlsafe(16)
    if user_id_str not in user_data:
        user_data[user_id_str] = {}
    user_data[user_id_str].update({
        'auth_token': auth_token,
        'is_authenticated': False,
        'auth_timestamp': None
    })
    
    destination_url = f"https://t.me/{bot_info.username}?start={auth_token}"
    short_url = await generate_short_link(destination_url)
    
    if short_url:
        logger.info(f"Generated auth link for user {user.id}: {short_url}")
        keyboard = [
            [InlineKeyboardButton("✨ Click Here to Authenticate ✨", url=short_url)]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_html(
            "🔐 <b>Human Verification Required!</b> 🔐\n\n"
            "To keep things secure, please prove you're not a robot to get your file.\n\n"
            "1️⃣ Click the magical button below.\n"
            "2️⃣ You'll see a quick ad – just wait and click 'Skip'.\n"
            "3️⃣ Poof! You'll be redirected back here to finish.\n\n"
            "Easy peasy! ✨",
            reply_markup=reply_markup
        )
        save_user_data(user_data)
    else:
        await update.message.reply_text("😥 Oh snap! Something went wrong while creating your special authentication link. Please try again.")

# --- Command Handlers ---

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles the /start command for all scenarios: new users, auth tokens, and file links."""
    user = update.effective_user
    user_id_str = str(user.id)
    args = context.args

    # Scenario 1: User clicks a file link (e.g., /start file_xyz)
    if args and args[0].startswith('file_'):
        file_unique_id = args[0].split('_', 1)[1]
        if is_user_authenticated(user.id):
            await send_file_by_id(file_unique_id, user.id, context)
        else:
            logger.info(f"User {user.id} needs auth for file {file_unique_id}.")
            if user_id_str not in user_data: user_data[user_id_str] = {}
            user_data[user_id_str]['pending_file_request'] = file_unique_id
            await generate_and_send_auth_link(update, context)
        return

    # Scenario 2: User returns with an authentication token
    if args:
        token_received = args[0]
        if user_id_str in user_data and user_data[user_id_str].get('auth_token') == token_received:
            user_data[user_id_str]['is_authenticated'] = True
            user_data[user_id_str]['auth_timestamp'] = datetime.now()
            logger.info(f"User {user.id} successfully authenticated.")
            await update.message.reply_html(
                f"🎉 <b>Authentication Successful!</b> 🎉\n\nWelcome aboard, {user.mention_html()}! You're all set to share and receive files."
            )
            
            pending_file = user_data[user_id_str].pop('pending_file_request', None)
            if pending_file:
                logger.info(f"Fulfilling pending file request {pending_file} for user {user.id}")
                await send_file_by_id(pending_file, user.id, context)
            
            save_user_data(user_data)
        else:
            await update.message.reply_html("❌ <b>Authentication Failed!</b> ❌\n\nThat token is invalid or has expired. Please use /start to get a fresh link.")
        return

    # Scenario 3: User sends /start to check status or begin
    if is_user_authenticated(user.id):
        await update.message.reply_html("👍 You're all good! You are already authenticated and ready to go! 🚀")
    else:
        await generate_and_send_auth_link(update, context)

async def get_link_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Generates a shareable, authenticated link for a file."""
    user = update.effective_user
    if not is_user_authenticated(user.id):
        await update.message.reply_text("✋ Hold on! You need to be authenticated to use this command. Just type /start to begin!")
        return

    replied_message = update.message.reply_to_message
    if not replied_message:
        await update.message.reply_text("💡 To generate a link, please reply to the message containing the file with the `/getlink` command.")
        return

    file_to_share, file_type = None, None
    if replied_message.document:
        file_to_share, file_type = replied_message.document, 'document'
    elif replied_message.photo:
        file_to_share, file_type = replied_message.photo[-1], 'photo'
    elif replied_message.video:
        file_to_share, file_type = replied_message.video, 'video'
    elif replied_message.audio:
        file_to_share, file_type = replied_message.audio, 'audio'

    if not file_to_share:
        await update.message.reply_text("🤔 Hmm, the message you replied to doesn't seem to have a file I can handle. Please reply to a document, photo, video, or audio file.")
        return

    file_unique_id = file_to_share.file_unique_id
    file_links[file_unique_id] = {
        "file_id": file_to_share.file_id,
        "file_type": file_type,
        "file_name": getattr(file_to_share, 'file_name', f"{file_type}_{file_unique_id}")
    }
    save_json_data(file_links, FILE_LINKS_FILE)

    bot_info = await context.bot.get_me()
    link = f"https://t.me/{bot_info.username}?start=file_{file_unique_id}"

    keyboard = [
        [InlineKeyboardButton("📂 Get File 📂", url=link)]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_html(
        f"✨ <b>Your Sharable Link is Ready!</b> ✨\n\n"
        f"<b>File:</b> <code>{getattr(file_to_share, 'file_name', 'your file')}</code>\n\n"
        f"Anyone who clicks this button will need to authenticate before they can receive the file. Share it wisely! 👇",
        reply_markup=reply_markup
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Displays a simple help message."""
    await update.message.reply_html(
        "📖 <b>Bot Commands & Guide</b> 📖\n\n"
        "Here's how you can use me:\n\n"
        "🔑 /start - Begins the authentication process or checks if your session is still active.\n\n"
        "🔗 /getlink - Reply to any file with this command to generate a secure, shareable link.\n\n"
        "🙋‍♂️ /help - Shows this helpful message again.\n\n"
        "Just send a file, and I'll tell you what to do next! 😉"
    )

async def handle_files(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles incoming files for general processing."""
    user = update.effective_user
    if not is_user_authenticated(user.id):
        await update.message.reply_text("🔒 Please use /start to authenticate before sending files.")
        return

    message = update.message
    file_name = "your file"
    
    if message.document:
        file_name = message.document.file_name
    elif message.video:
        file_name = message.video.file_name
    elif message.audio:
        file_name = message.audio.file_name
        
    logger.info(f"User {user.id} sent a file: {file_name}")
    await message.reply_text("👍 File received! Now, simply reply to this file's message with `/getlink` to create a magical, shareable link.")

def main() -> None:
    """Start the bot."""
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("getlink", get_link_command))
    application.add_handler(CommandHandler("help", help_command))
    # Removed the info command as it wasn't in the help message, you can add it back if needed
    application.add_handler(MessageHandler(filters.ATTACHMENT, handle_files))

    logger.info("Bot is starting...")
    application.run_polling()

if __name__ == '__main__':
    main()
