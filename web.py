import logging
import os
import json
import secrets
from datetime import datetime, timedelta

import httpx  # Using httpx for asynchronous HTTP requests
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# --- Configuration ---
# It's best practice to load sensitive data from environment variables.
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "7634447028:AAFSw_8NlhYt32WPLwsrCTVPTOJYMxtrX38")
LITESHORT_API_KEY = os.environ.get("LITESHORT_API_KEY", "be1528376cd25a510dce1e3e063ed856e5421250")

LITESHORT_API_URL = "https://liteshort.com/api"
AUTHENTICATION_EXPIRATION_HOURS = 24
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
    """Looks up a file by its unique ID and sends it to the user."""
    file_info = file_links.get(file_unique_id)
    if not file_info:
        await context.bot.send_message(chat_id, "Sorry, this file link is invalid or the file has been removed.")
        logger.warning(f"File not found for unique_id: {file_unique_id} requested by chat_id: {chat_id}")
        return

    file_id = file_info['file_id']
    file_type = file_info['file_type']
    file_name = file_info.get('file_name', 'your file')

    await context.bot.send_message(chat_id, f"✅ Access granted. Sending you the file: <b>{file_name}</b>", parse_mode=ParseMode.HTML)

    try:
        if file_type == 'document':
            await context.bot.send_document(chat_id, document=file_id)
        elif file_type == 'photo':
            await context.bot.send_photo(chat_id, photo=file_id)
        elif file_type == 'video':
            await context.bot.send_video(chat_id, video=file_id)
        elif file_type == 'audio':
            await context.bot.send_audio(chat_id, audio=file_id)
    except Exception as e:
        logger.error(f"Failed to send file {file_id} to {chat_id}: {e}")
        await context.bot.send_message(chat_id, "There was an error sending the file. It might have been deleted.")

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
        await update.message.reply_html(
            "🔐 <b>Please Authenticate to Continue</b>\n\n"
            "To get your file, you need to verify you are a human.\n\n"
            "<b>1.</b> Click the link below.\n"
            "<b>2.</b> Wait for the ad and click 'Skip'.\n"
            "<b>3.</b> You will be redirected back to me to complete authentication.\n\n"
            f"➡️ <b>Your Authentication Link:</b> {short_url}"
        )
        save_user_data(user_data) # Save user data with new token
    else:
        await update.message.reply_text("Sorry, there was an error creating your authentication link.")

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
                f"✅ <b>Authentication Successful!</b>\n\nWelcome, {user.mention_html()}!"
            )
            
            # Check for and fulfill pending file request
            pending_file = user_data[user_id_str].pop('pending_file_request', None)
            if pending_file:
                logger.info(f"Fulfilling pending file request {pending_file} for user {user.id}")
                await send_file_by_id(pending_file, user.id, context)
            
            save_user_data(user_data)
        else:
            await update.message.reply_html("❌ <b>Authentication Failed.</b> Token is invalid or expired.")
        return

    # Scenario 3: User sends /start to check status or begin
    if is_user_authenticated(user.id):
        await update.message.reply_html("👍 You are already authenticated.")
    else:
        await generate_and_send_auth_link(update, context)

async def get_link_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Generates a shareable, authenticated link for a file."""
    user = update.effective_user
    if not is_user_authenticated(user.id):
        await update.message.reply_text("You must be authenticated to use this. Use /start.")
        return

    replied_message = update.message.reply_to_message
    if not replied_message:
        await update.message.reply_text("Please reply to a message with a file to use this command.")
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
        await update.message.reply_text("The replied message does not contain a supported file.")
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
    
    await update.message.reply_html(
        "<b>🔗 Shareable Link Generated</b>\n\n"
        "Anyone who clicks this link will be prompted to authenticate before receiving the file.\n\n"
        f"<code>{link}</code>"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Displays a simple help message."""
    await update.message.reply_html(
        "<b>Bot Help</b>\n\n"
        "<b>Commands:</b>\n"
        "/start - Begin authentication or check your status.\n"
        "/getlink - Reply to a file to create a shareable link.\n"
        "/help - Show this help message.\n"
        "/info - Display bot status.\n\n"
        "Once authenticated, you can send any file to have it processed or use /getlink."
    )

async def info_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Displays information about the bot's current status."""
    current_time = "Friday, October 3, 2025 at 8:41 PM IST"
    current_location = "Kota, Rajasthan, India"
    await update.message.reply_html(
        "<b>🤖 Bot Status</b>\n\n"
        f"<b>📍 Location:</b> {current_location}\n"
        f"<b>⏰ Server Time:</b> {current_time}\n\n"
        "Everything is running smoothly!"
    )

async def handle_files(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles incoming files for general processing."""
    user = update.effective_user
    if not is_user_authenticated(user.id):
        await update.message.reply_text("Please use /start to authenticate.")
        return

    message = update.message
    file_id, file_name, reply_method = None, "your file", message.reply_document
    
    if message.document:
        file_id, file_name, reply_method = message.document.file_id, message.document.file_name, message.reply_document
    elif message.photo:
        file_id, reply_method = message.photo[-1].file_id, message.reply_photo
    elif message.video:
        file_id, file_name, reply_method = message.video.file_id, message.video.file_name, message.reply_video
    elif message.audio:
        file_id, file_name, reply_method = message.audio.file_id, message.audio.file_name, message.reply_audio
    
    if file_id:
        logger.info(f"User {user.id} sent a file: {file_name}")
        await reply_method(file_id, caption="Here is your file, processed successfully!")
    else:
        await message.reply_text("Attachment received.")

def main() -> None:
    """Start the bot."""
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("getlink", get_link_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("info", info_command))
    application.add_handler(MessageHandler(filters.ATTACHMENT, handle_files))

    logger.info("Bot is starting...")
    application.run_polling()

if __name__ == '__main__':
    main()

