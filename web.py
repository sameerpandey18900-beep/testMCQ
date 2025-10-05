import logging
import os
import json
import secrets
from datetime import datetime, timedelta
import asyncio

import httpx  # Using httpx for asynchronous HTTP requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

# --- Configuration ---
TELEGRAM_BOT_TOKEN = "8379093665:AAFKQKg4K8Zsi0TS5b2p2evmSvbcBNSi_YQ"
LITESHORT_API_KEY = "3872aef59e2371b1a6db2155cfa6c7a18aa08d64"

# --- NEW: Add your Telegram user ID here ---
ADMIN_IDS = [1106151237]  # <--- IMPORTANT: REPLACE 123456789 WITH YOUR NUMERIC TELEGRAM ID

LITESHORT_API_URL = "https://liteshort.com/api"
AUTHENTICATION_EXPIRATION_HOURS = 24
FILE_AUTO_DELETE_MINUTES = 20
USER_DATA_FILE = "user_data.json"
FILE_LINKS_FILE = "file_links.json"
BATCH_FILE_LIMIT = 15

# --- Translations ---
translations = {
    'en': {
        "choose_language": "Please select your language:",
        "auth_required_header": "🔐 <b>Human Verification Required!</b> 🔐",
        "auth_required_body": (
            "To keep things secure, please prove you're not a robot to get your file.\n\n"
            "1️⃣ Click the magical button below.\n"
            "2️⃣ You'll see a quick ad – just wait and click 'Skip'.\n"
            "3️⃣ Poof! You'll be redirected back here to finish.\n\n"
            "Easy peasy! ✨"
        ),
        "auth_button": "✨ Click Here to Authenticate ✨",
        "auth_link_error": "😥 Oh snap! Something went wrong while creating your special authentication link. Please try again.",
        "auth_success_header": "🎉 <b>Authentication Successful!</b> 🎉",
        "auth_success_body": "Welcome aboard, {user_mention}! You're all set to share and receive files.",
        "auth_fail_header": "❌ <b>Authentication Failed!</b> ❌",
        "auth_fail_body": "That token is invalid or has expired. Please use /start to get a fresh link.",
        "already_authenticated": "👍 You're all good! You are already authenticated and ready to go! 🚀",
        "getlink_not_authenticated": "✋ Hold on! You need to be authenticated to use this command. Just type /start to begin!",
        "getlink_reply_prompt": "💡 To generate a link, please reply to the message containing the file with the `/getlink` command.",
        "getlink_no_file": "🤔 Hmm, the message you replied to doesn't seem to have a file I can handle. Please reply to a document, photo, video, or audio file.",
        "getlink_success_header": "✨ <b>Your Sharable Link is Ready!</b> ✨",
        "getlink_success_body": "<b>File:</b> <code>{file_name}</code>\n\nAnyone who clicks this button will need to authenticate before they can receive the file. Share it wisely! 👇",
        "getlink_button": "📂 Get File 📂",
        "help_header": "📖 <b>Bot Commands & Guide</b> 📖",
        "help_body": (
            "Here's how you can use me:\n\n"
            "🔑 /start - Begins the authentication process.\n\n"
            "🔗 /getlink - Reply to a file to get a secure link.\n\n"
            "🗂️ /batch - Start collecting multiple files (up to 15) to create a single link. Send /done when you're finished.\n\n"
            "🙋‍♂️ /help - Shows this helpful message again."
        ),
        "handle_files_not_authenticated": "🔒 Please use /start to authenticate before sending files.",
        "handle_files_received": "👍 File received! Now, simply reply to this file's message with `/getlink` to create a magical, shareable link.",
        "file_invalid_link": "😕 Oops! This file link seems to be invalid or has expired. Please request a new one.",
        "file_access_granted": "✅ Access Granted! 🚀\n\nSending you the file: <b>{file_name}</b>\n\n<i>Please note: For security, this file cannot be forwarded or saved.</i>",
        "file_send_error": "❌ Oh no! An error occurred while sending the file. It might have been removed from Telegram's servers.",
        "file_countdown_text": "⏳ This file is ephemeral! It will self-destruct in <b>{minutes}:00</b>.",
        "file_countdown_update": "⏳ This file will be automatically deleted in <b>{minutes}:00</b>.",
        "file_deleting_now": "💥 Deleting file now...",
        "info_header": "📊 <b>Bot Statistics</b> 📊",
        "info_body": "Total Unique Users: <b>{user_count}</b>",
        "admin_only": "❌ Access Denied! This command is for bot admins only.",
        "batch_start": "✅ <b>Batch Mode Activated</b> ✅\n\nSend me your photos or videos (up to {limit}). I will collect them.\n\nSend /done when you are finished or /cancel to abort.",
        "batch_file_added": "👍 File {count}/{limit} added. Send more, or use /done to get your link.",
        "batch_limit_reached": "⚠️ You've reached the {limit} file limit. Please use /done to generate the link.",
        "batch_no_files": "🤔 You haven't sent any files for this batch. Send some files first, then use /done.",
        "batch_done_header": "✨ <b>Your Batch Link is Ready!</b> ✨",
        "batch_done_body": "Here is the link for your batch of <b>{count}</b> files. Share it wisely! 👇",
        "batch_button": "🗂️ Get {count} Files 🗂️",
        "batch_cancelled": "❌ Batch mode cancelled. Your collected files have been discarded.",
        "batch_invalid_file": "⚠️ In batch mode, you can only send photos and videos.",
    },
    'hi': {
        "choose_language": "कृपया अपनी भाषा चुनें:",
        "auth_required_header": "🔐 <b>मानव सत्यापन आवश्यक!</b> 🔐",
        "auth_required_body": (
            "चीजों को सुरक्षित रखने के लिए, कृपया अपनी फ़ाइल प्राप्त करने के लिए साबित करें कि आप रोबोट नहीं हैं।\n\n"
            "1️⃣ नीचे दिए गए जादुई बटन पर क्लिक करें।\n"
            "2️⃣ आपको एक त्वरित विज्ञापन दिखाई देगा - बस प्रतीक्षा करें और 'Skip' पर क्लिक करें।\n"
            "3️⃣ बूम! आपको प्रक्रिया पूरी करने के लिए यहां वापस भेज दिया जाएगा।\n\n"
            "बहुत आसान! ✨"
        ),
        "auth_button": "✨ प्रमाणित करने के लिए यहां क्लिक करें ✨",
        "auth_link_error": "😥 अरे नहीं! आपका विशेष प्रमाणीकरण लिंक बनाते समय कुछ गलत हो गया। कृपया पुन: प्रयास करें।",
        "auth_success_header": "🎉 <b>प्रमाणीकरण सफल!</b> 🎉",
        "auth_success_body": "आपका स्वागत है, {user_mention}! अब आप फ़ाइलें साझा करने और प्राप्त करने के लिए पूरी तरह तैयार हैं।",
        "auth_fail_header": "❌ <b>प्रमाणीकरण विफल!</b> ❌",
        "auth_fail_body": "वह टोकन अमान्य है या समाप्त हो गया है। कृपया एक नया लिंक प्राप्त करने के लिए /start का उपयोग करें।",
        "already_authenticated": "👍 आप पूरी तरह तैयार हैं! आप पहले से ही प्रमाणित हैं और जाने के लिए तैयार हैं! 🚀",
        "getlink_not_authenticated": "✋ रुकिए! इस कमांड का उपयोग करने के लिए आपको प्रमाणित होना होगा। शुरू करने के लिए बस /start टाइप करें!",
        "getlink_reply_prompt": "💡 एक लिंक उत्पन्न करने के लिए, कृपया फ़ाइल वाले संदेश पर `/getlink` कमांड के साथ उत्तर दें।",
        "getlink_no_file": "🤔 हम्म, जिस संदेश का आपने उत्तर दिया है, उसमें ऐसी कोई फ़ाइल नहीं है जिसे मैं संभाल सकूँ। कृपया एक दस्तावेज़, फ़ोटो, वीडियो, या ऑडियो फ़ाइल का उत्तर दें।",
        "getlink_success_header": "✨ <b>आपका साझा करने योग्य लिंक तैयार है!</b> ✨",
        "getlink_success_body": "<b>फ़ाइल:</b> <code>{file_name}</code>\n\nइस बटन पर क्लिक करने वाले किसी भी व्यक्ति को फ़ाइल प्राप्त करने से पहले प्रमाणित करना होगा। इसे बुद्धिमानी से साझा करें! 👇",
        "getlink_button": "📂 फ़ाइल प्राप्त करें 📂",
        "help_header": "📖 <b>बॉट कमांड और गाइड</b> 📖",
        "help_body": (
            "आप मेरा उपयोग इस प्रकार कर सकते हैं:\n\n"
            "🔑 /start - प्रमाणीकरण प्रक्रिया शुरू करता है।\n\n"
            "🔗 /getlink - एक सुरक्षित लिंक प्राप्त करने के लिए किसी फ़ाइल का उत्तर दें।\n\n"
            "🗂️ /batch - एक ही लिंक बनाने के लिए कई फ़ाइलें (15 तक) इकट्ठा करना शुरू करें। समाप्त होने पर /done भेजें।\n\n"
            "🙋‍♂️ /help - यह सहायक संदेश फिर से दिखाता है।"
        ),
        "handle_files_not_authenticated": "🔒 फ़ाइलें भेजने से पहले प्रमाणित करने के लिए कृपया /start का उपयोग करें।",
        "handle_files_received": "👍 फ़ाइल प्राप्त हुई! अब, एक जादुई, साझा करने योग्य लिंक बनाने के लिए बस इस फ़ाइल के संदेश पर `/getlink` के साथ उत्तर दें।",
        "file_invalid_link": "😕 ओह! यह फ़ाइल लिंक अमान्य या समाप्त हो गया लगता है। कृपया एक नया अनुरोध करें।",
        "file_access_granted": "✅ प्रवेश स्वीकृत! 🚀\n\nआपको फ़ाइल भेजी जा रही है: <b>{file_name}</b>\n\n<i>कृपया ध्यान दें: सुरक्षा कारणों से, यह फ़ाइल फॉरवर्ड या सहेजी नहीं जा सकती है।</i>",
        "file_send_error": "❌ अरे नहीं! फ़ाइल भेजते समय एक त्रुटि हुई। हो सकता है कि इसे टेलीग्राम के सर्वर से हटा दिया गया हो।",
        "file_countdown_text": "⏳ यह फ़ाइल अस्थायी है! यह <b>{minutes}:00</b> में स्वतः नष्ट हो जाएगी।",
        "file_countdown_update": "⏳ यह फ़ाइल <b>{minutes}:00</b> में स्वचालित रूप से हटा दी जाएगी।",
        "file_deleting_now": "💥 अब फ़ाइल हटाई जा रही है...",
        "info_header": "📊 <b>बॉट आँकड़े</b> 📊",
        "info_body": "कुल अद्वितीय उपयोगकर्ता: <b>{user_count}</b>",
        "admin_only": "❌ प्रवेश वर्जित! यह कमांड केवल बॉट एडमिन के लिए है।",
        "batch_start": "✅ <b>बैच मोड सक्रिय</b> ✅\n\nमुझे अपनी तस्वीरें या वीडियो भेजें ({limit} तक)। मैं उन्हें इकट्ठा करूँगा।\n\nजब आप समाप्त कर लें तो /done भेजें या रद्द करने के लिए /cancel भेजें।",
        "batch_file_added": "👍 फ़ाइल {count}/{limit} जोड़ी गई। और भेजें, या अपना लिंक प्राप्त करने के लिए /done का उपयोग करें।",
        "batch_limit_reached": "⚠️ आप {limit} फ़ाइल सीमा तक पहुँच गए हैं। कृपया लिंक उत्पन्न करने के लिए /done का उपयोग करें।",
        "batch_no_files": "🤔 आपने इस बैच के लिए कोई फ़ाइल नहीं भेजी है। पहले कुछ फ़ाइलें भेजें, फिर /done का उपयोग करें।",
        "batch_done_header": "✨ <b>आपका बैच लिंक तैयार है!</b> ✨",
        "batch_done_body": "आपकी <b>{count}</b> फ़ाइलों के बैच का लिंक यहाँ है। इसे बुद्धिमानी से साझा करें! 👇",
        "batch_button": "🗂️ {count} फ़ाइलें प्राप्त करें 🗂️",
        "batch_cancelled": "❌ बैच मोड रद्द कर दिया गया। आपकी एकत्रित फ़ाइलें छोड़ दी गई हैं।",
        "batch_invalid_file": "⚠️ बैच मोड में, आप केवल तस्वीरें और वीडियो भेज सकते हैं।",
    }
}

# --- Logging Setup ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Persistence Helpers ---

def load_json_data(filename: str) -> dict:
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_json_data(data: dict, filename: str) -> None:
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def load_user_data() -> dict:
    data = load_json_data(USER_DATA_FILE)
    for user_info in data.values():
        if user_info.get('auth_timestamp'):
            user_info['auth_timestamp'] = datetime.fromisoformat(user_info['auth_timestamp'])
    return data

def save_user_data(data: dict) -> None:
    data_to_save = {k: v.copy() for k, v in data.items()}
    for user_info in data_to_save.values():
        if isinstance(user_info.get('auth_timestamp'), datetime):
            user_info['auth_timestamp'] = user_info['auth_timestamp'].isoformat()
    save_json_data(data_to_save, USER_DATA_FILE)

user_data = load_user_data()
file_links = load_json_data(FILE_LINKS_FILE)

# --- Helper Functions ---

def get_lang(user_id: int) -> str:
    return user_data.get(str(user_id), {}).get('language', 'en')

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

async def schedule_file_deletion(context: ContextTypes.DEFAULT_TYPE, chat_id: int, sent_message_id: int, countdown_message_id: int):
    lang = get_lang(chat_id)
    try:
        # Countdown logic remains the same
        for i in range(FILE_AUTO_DELETE_MINUTES, 0, -1):
            await asyncio.sleep(60)
            minutes_left = i - 1
            if minutes_left > 0:
                countdown_text = translations[lang]['file_countdown_update'].format(minutes=f"{minutes_left:02d}")
                try:
                    await context.bot.edit_message_text(
                        chat_id=chat_id, message_id=countdown_message_id,
                        text=countdown_text, parse_mode=ParseMode.HTML
                    )
                except Exception:
                    logger.info(f"Countdown message in chat {chat_id} was deleted. Stopping deletion task.")
                    return
            else:
                try:
                    await context.bot.edit_message_text(
                        chat_id=chat_id, message_id=countdown_message_id,
                        text=translations[lang]['file_deleting_now'], parse_mode=ParseMode.HTML
                    )
                except Exception: pass

        logger.info(f"Auto-deleting messages {[sent_message_id, countdown_message_id]} in chat {chat_id}")
        await context.bot.delete_message(chat_id=chat_id, message_id=sent_message_id)
        await context.bot.delete_message(chat_id=chat_id, message_id=countdown_message_id)
    except Exception as e:
        logger.warning(f"Could not complete the deletion process for chat {chat_id}: {e}")

def is_user_authenticated(user_id: int) -> bool:
    user_id_str = str(user_id)
    if user_id_str not in user_data: return False
    user = user_data[user_id_str]
    if not user.get('is_authenticated') or not user.get('auth_timestamp'): return False
    expiration_time = user['auth_timestamp'] + timedelta(hours=AUTHENTICATION_EXPIRATION_HOURS)
    if datetime.now() > expiration_time:
        user_data.pop(user_id_str, None)
        save_user_data(user_data)
        logger.info(f"User {user_id}'s session has expired.")
        return False
    return True

async def generate_short_link(url: str) -> str | None:
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
    lang = get_lang(chat_id)
    file_info = file_links.get(file_unique_id)
    if not file_info:
        await context.bot.send_message(chat_id, translations[lang]['file_invalid_link'])
        logger.warning(f"File not found for unique_id: {file_unique_id} requested by chat_id: {chat_id}")
        return
    
    # Handle both single files (dict) and batches (list)
    files_to_send = file_info if isinstance(file_info, list) else [file_info]

    for single_file_info in files_to_send:
        file_id = single_file_info['file_id']
        file_type = single_file_info['file_type']
        file_name = single_file_info.get('file_name', 'your file')
        
        await context.bot.send_message(
            chat_id, translations[lang]['file_access_granted'].format(file_name=file_name), parse_mode=ParseMode.HTML
        )

        sent_message = None
        try:
            # --- MODIFICATION START ---
            # Added 'has_spoiler=True' for photo and video
            if file_type == 'document':
                sent_message = await context.bot.send_document(chat_id, document=file_id, protect_content=True)
            elif file_type == 'photo':
                sent_message = await context.bot.send_photo(chat_id, photo=file_id, protect_content=True, has_spoiler=True)
            elif file_type == 'video':
                sent_message = await context.bot.send_video(chat_id, video=file_id, protect_content=True, has_spoiler=True)
            elif file_type == 'audio':
                sent_message = await context.bot.send_audio(chat_id, audio=file_id, protect_content=True)
            # --- MODIFICATION END ---
        except Exception as e:
            logger.error(f"Failed to send file {file_id} to {chat_id}: {e}")
            await context.bot.send_message(chat_id, translations[lang]['file_send_error'])
            continue # Try sending next file in batch

        if sent_message:
            delete_in_minutes = FILE_AUTO_DELETE_MINUTES
            initial_countdown_text = translations[lang]['file_countdown_text'].format(minutes=delete_in_minutes)
            countdown_message = await context.bot.send_message(chat_id=chat_id, text=initial_countdown_text, parse_mode=ParseMode.HTML)
            asyncio.create_task(schedule_file_deletion(context, chat_id, sent_message.message_id, countdown_message.message_id))
        
        await asyncio.sleep(1) # Small delay between sending files in a batch

async def generate_and_send_auth_link(update: Update, context: ContextTypes.DEFAULT_TYPE, message_text: str = None) -> None:
    # This function remains largely the same
    user = update.effective_user
    user_id_str, lang = str(user.id), get_lang(user.id)
    bot_info = await context.bot.get_me()

    auth_token = secrets.token_urlsafe(16)
    if user_id_str not in user_data: user_data[user_id_str] = {}
    user_data[user_id_str].update({'auth_token': auth_token, 'is_authenticated': False, 'auth_timestamp': None})
    
    destination_url = f"https://t.me/{bot_info.username}?start={auth_token}"
    short_url = await generate_short_link(destination_url)

    if short_url:
        logger.info(f"Generated auth link for user {user.id}: {short_url}")
        keyboard = [[InlineKeyboardButton(translations[lang]['auth_button'], url=short_url)]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        text_to_send = message_text or f"{translations[lang]['auth_required_header']}\n\n{translations[lang]['auth_required_body']}"
        
        if update.callback_query:
            await update.callback_query.edit_message_text(text_to_send, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
        else:
            await update.message.reply_html(text_to_send, reply_markup=reply_markup)
        save_user_data(user_data)
    else:
        if update.callback_query:
            await update.callback_query.edit_message_text(translations[lang]['auth_link_error'])
        else:
            await update.message.reply_text(translations[lang]['auth_link_error'])

# --- Command and Message Handlers ---

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user, args = update.effective_user, context.args
    user_id_str, lang = str(user.id), get_lang(user.id)

    # --- MODIFICATION: Handle different deep link payloads (file, batch) ---
    if args and ('file_' in args[0] or 'batch_' in args[0]):
        file_unique_id = args[0] # This can now be 'file_...' or 'batch_...'
        if is_user_authenticated(user.id):
            await send_file_by_id(file_unique_id, user.id, context)
        else:
            logger.info(f"User {user.id} needs auth for content {file_unique_id}.")
            if user_id_str not in user_data: user_data[user_id_str] = {}
            user_data[user_id_str]['pending_file_request'] = file_unique_id
            await generate_and_send_auth_link(update, context)
        return

    if args: # Handle authentication token
        token_received = args[0]
        if user_id_str in user_data and user_data[user_id_str].get('auth_token') == token_received:
            user_data[user_id_str]['is_authenticated'] = True
            user_data[user_id_str]['auth_timestamp'] = datetime.now()
            logger.info(f"User {user.id} successfully authenticated.")
            await update.message.reply_html(f"{translations[lang]['auth_success_header']}\n\n{translations[lang]['auth_success_body'].format(user_mention=user.mention_html())}")
            
            pending_file = user_data[user_id_str].pop('pending_file_request', None)
            if pending_file:
                logger.info(f"Fulfilling pending file request {pending_file} for user {user.id}")
                await send_file_by_id(pending_file, user.id, context)
            save_user_data(user_data)
        else:
            await update.message.reply_html(f"{translations[lang]['auth_fail_header']}\n\n{translations[lang]['auth_fail_body']}")
        return

    if is_user_authenticated(user.id):
        await update.message.reply_html(translations[lang]['already_authenticated'])
    else:
        keyboard = [[InlineKeyboardButton("English 🇬🇧", callback_data='lang_en'), InlineKeyboardButton("हिन्दी 🇮🇳", callback_data='lang_hi')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(translations['en']['choose_language'], reply_markup=reply_markup)

async def language_select_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    user_id_str = str(query.from_user.id)
    lang_code = query.data.split('_')[1]
    
    if user_id_str not in user_data: user_data[user_id_str] = {}
    user_data[user_id_str]['language'] = lang_code
    save_user_data(user_data)
    
    lang = get_lang(query.from_user.id)
    auth_message = f"{translations[lang]['auth_required_header']}\n\n{translations[lang]['auth_required_body']}"
    await generate_and_send_auth_link(update, context, message_text=auth_message)

async def get_link_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # This function is now for single files only
    user, lang = update.effective_user, get_lang(update.effective_user.id)
    if not is_user_authenticated(user.id):
        await update.message.reply_text(translations[lang]['getlink_not_authenticated'])
        return

    replied_message = update.message.reply_to_message
    if not replied_message:
        await update.message.reply_text(translations[lang]['getlink_reply_prompt'])
        return

    file_to_share, file_type, file_name_attr = None, None, 'your file'
    if replied_message.document: file_to_share, file_type, file_name_attr = replied_message.document, 'document', replied_message.document.file_name
    elif replied_message.photo: file_to_share, file_type = replied_message.photo[-1], 'photo'
    elif replied_message.video: file_to_share, file_type, file_name_attr = replied_message.video, 'video', replied_message.video.file_name
    elif replied_message.audio: file_to_share, file_type, file_name_attr = replied_message.audio, 'audio', replied_message.audio.file_name

    if not file_to_share:
        await update.message.reply_text(translations[lang]['getlink_no_file'])
        return
    
    file_id_key = f"file_{file_to_share.file_unique_id}"
    file_links[file_id_key] = {"file_id": file_to_share.file_id, "file_type": file_type, "file_name": file_name_attr}
    save_json_data(file_links, FILE_LINKS_FILE)

    bot_info = await context.bot.get_me()
    link = f"https://t.me/{bot_info.username}?start={file_id_key}"
    keyboard = [[InlineKeyboardButton(translations[lang]['getlink_button'], url=link)]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_html(f"{translations[lang]['getlink_success_header']}\n\n{translations[lang]['getlink_success_body'].format(file_name=file_name_attr)}", reply_markup=reply_markup)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    lang = get_lang(update.effective_user.id)
    await update.message.reply_html(f"{translations[lang]['help_header']}\n\n{translations[lang]['help_body']}")

async def handle_files(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user, lang = update.effective_user, get_lang(update.effective_user.id)
    user_id_str = str(user.id)

    if not is_user_authenticated(user.id):
        await update.message.reply_text(translations[lang]['handle_files_not_authenticated'])
        return
    
    # --- MODIFICATION: Check if user is in batch mode ---
    if user_data.get(user_id_str, {}).get('in_batch_mode', False):
        batch_files = user_data[user_id_str].get('batch_files', [])
        
        if len(batch_files) >= BATCH_FILE_LIMIT:
            await update.message.reply_text(translations[lang]['batch_limit_reached'].format(limit=BATCH_FILE_LIMIT))
            return
            
        file_to_add, file_type, file_name_attr = None, None, 'your file'
        message = update.message
        if message.photo: file_to_add, file_type = message.photo[-1], 'photo'
        elif message.video: file_to_add, file_type, file_name_attr = message.video, 'video', message.video.file_name
        else:
            await update.message.reply_text(translations[lang]['batch_invalid_file'])
            return

        batch_files.append({
            "file_id": file_to_add.file_id,
            "file_type": file_type,
            "file_name": file_name_attr
        })
        user_data[user_id_str]['batch_files'] = batch_files
        save_user_data(user_data)
        
        await update.message.reply_text(translations[lang]['batch_file_added'].format(count=len(batch_files), limit=BATCH_FILE_LIMIT))
    else:
        # Original behavior for single files
        await update.message.reply_text(translations[lang]['handle_files_received'])

# --- NEW: Batch Mode and Info Commands ---

async def batch_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user, lang = update.effective_user, get_lang(update.effective_user.id)
    user_id_str = str(user.id)
    
    if not is_user_authenticated(user.id):
        await update.message.reply_text(translations[lang]['getlink_not_authenticated'])
        return
        
    user_data[user_id_str] = user_data.get(user_id_str, {})
    user_data[user_id_str]['in_batch_mode'] = True
    user_data[user_id_str]['batch_files'] = []
    save_user_data(user_data)
    
    await update.message.reply_html(translations[lang]['batch_start'].format(limit=BATCH_FILE_LIMIT))

async def done_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user, lang = update.effective_user, get_lang(update.effective_user.id)
    user_id_str = str(user.id)

    if not user_data.get(user_id_str, {}).get('in_batch_mode', False):
        return # Ignore if not in batch mode

    batch_files = user_data[user_id_str].get('batch_files', [])
    if not batch_files:
        await update.message.reply_text(translations[lang]['batch_no_files'])
        return
        
    batch_id = f"batch_{secrets.token_urlsafe(8)}"
    file_links[batch_id] = batch_files
    save_json_data(file_links, FILE_LINKS_FILE)
    
    # Clean up user state
    user_data[user_id_str]['in_batch_mode'] = False
    user_data[user_id_str]['batch_files'] = []
    save_user_data(user_data)

    bot_info = await context.bot.get_me()
    link = f"https://t.me/{bot_info.username}?start={batch_id}"
    file_count = len(batch_files)
    keyboard = [[InlineKeyboardButton(translations[lang]['batch_button'].format(count=file_count), url=link)]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_html(
        f"{translations[lang]['batch_done_header']}\n\n{translations[lang]['batch_done_body'].format(count=file_count)}",
        reply_markup=reply_markup
    )

async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user, lang = update.effective_user, get_lang(update.effective_user.id)
    user_id_str = str(user.id)
    
    if user_data.get(user_id_str, {}).get('in_batch_mode', False):
        user_data[user_id_str]['in_batch_mode'] = False
        user_data[user_id_str]['batch_files'] = []
        save_user_data(user_data)
        await update.message.reply_text(translations[lang]['batch_cancelled'])

async def info_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user, lang = update.effective_user, get_lang(update.effective_user.id)
    if not is_admin(user.id):
        await update.message.reply_text(translations[lang]['admin_only'])
        return
        
    user_count = len(user_data)
    await update.message.reply_html(
        f"{translations[lang]['info_header']}\n\n{translations[lang]['info_body'].format(user_count=user_count)}"
    )

def main() -> None:
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CallbackQueryHandler(language_select_callback, pattern='^lang_'))
    application.add_handler(CommandHandler("getlink", get_link_command))
    application.add_handler(CommandHandler("help", help_command))
    
    # --- NEW: Add handlers for new commands ---
    application.add_handler(CommandHandler("info", info_command))
    application.add_handler(CommandHandler("batch", batch_command))
    application.add_handler(CommandHandler("done", done_command))
    application.add_handler(CommandHandler("cancel", cancel_command))
    
    # This handler now needs to check for batch mode
    application.add_handler(MessageHandler(filters.PHOTO | filters.VIDEO | filters.Document.ALL | filters.AUDIO, handle_files))

    logger.info("Bot is starting with new features...")
    application.run_polling()

if __name__ == '__main__':
    main()
