import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
    ConversationHandler
)
import pickle
import os
from datetime import datetime, timedelta

# ======================
# KONFIGURASI
# ======================
TOKEN = os.getenv('TELEGRAM_TOKEN')
DATA_FILE = 'user_data.pkl'  # File untuk menyimpan data persisten
MAX_REQUESTS_PER_HOUR = 5

# ======================
# INISIALISASI
# ======================
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Load data dari file jika ada
def load_data():
    try:
        with open(DATA_FILE, 'rb') as f:
            return pickle.load(f)
    except (FileNotFoundError, EOFError):
        return {}

# Save data ke file
def save_data(data):
    with open(DATA_FILE, 'wb') as f:
        pickle.dump(data, f)

# Inisialisasi data
user_data = load_data()

# ======================
# FUNGSI UTILITAS
# ======================
def is_valid_proxy(proxy):
    """Validasi format proxy ip:port"""
    try:
        if not proxy or ':' not in proxy:
            return False
        ip, port = proxy.split(':')
        if not port.isdigit() or int(port) < 1 or int(port) > 65535:
            return False
        return True
    except:
        return False

def extract_proxies(text):
    """Ekstrak multiple proxies dari text"""
    proxies = []
    for item in text.split():
        proxy = item.strip()
        if is_valid_proxy(proxy):
            proxies.append(proxy)
    return proxies

def get_user_data(user_id):
    """Dapatkan atau inisialisasi data user"""
    if user_id not in user_data:
        user_data[user_id] = {
            'proxies': [],
            'requests': {
                'count': 0,
                'last_request': datetime.now() - timedelta(hours=1)
            }
        }
        save_data(user_data)  # Simpan perubahan
    return user_data[user_id]

# ======================
# HANDLER TELEGRAM
# ======================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user_data(user_id)
    
    keyboard = [
        [InlineKeyboardButton("➕ Tambah Proxy", callback_data='add_proxy')],
        [InlineKeyboardButton("🗑 Hapus Proxy", callback_data='clear_proxy')],
        [InlineKeyboardButton("📋 List Proxy", callback_data='list_proxy')],
    ]
    
    if user['proxies']:
        keyboard.insert(2, [InlineKeyboardButton("🎭 Tambah View", callback_data='add_view')])
    
    keyboard.append([InlineKeyboardButton("ℹ Bantuan", callback_data='help')])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=f"🤖 <b>TikTok View Bot</b>\n\n"
             f"🔧 Proxy tersedia: {len(user['proxies'])}\n"
             f"📊 Request hari ini: {user['requests']['count']}/{MAX_REQUESTS_PER_HOUR}\n\n"
             "Pilih menu di bawah:",
        reply_markup=reply_markup,
        parse_mode='HTML'
    )

async def handle_proxy_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user_data(user_id)
    text = update.message.text.strip()
    
    proxies = extract_proxies(text)
    if not proxies:
        await update.message.reply_text(
            "⚠ Format proxy tidak valid. Contoh:\n"
            "<code>123.45.67.89:8080</code>\n"
            "atau multiple proxies:\n"
            "<code>156.228.81.242:3129 156.228.104.58:3129</code>",
            parse_mode='HTML'
        )
        return
    
    added = 0
    for proxy in proxies:
        if proxy not in user['proxies']:
            user['proxies'].append(proxy)
            added += 1
    
    save_data(user_data)  # Simpan perubahan
    
    if added > 0:
        await update.message.reply_text(
            f"✅ {added} proxy berhasil ditambahkan!\n"
            f"Total proxy Anda sekarang: {len(user['proxies'])}",
            parse_mode='HTML'
        )
    else:
        await update.message.reply_text(
            "ℹ Semua proxy yang dimasukkan sudah ada",
            parse_mode='HTML'
        )
    
    await start(update, context)

async def list_proxies(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    user = get_user_data(user_id)
    
    if not user['proxies']:
        await query.edit_message_text(
            text="📋 <b>Daftar Proxy Anda</b>\n\n"
                 "Anda belum menambahkan proxy",
            parse_mode='HTML'
        )
        return
    
    proxy_list = "\n".join([f"🔹 {proxy}" for proxy in user['proxies']])
    keyboard = [[InlineKeyboardButton("🔙 Kembali", callback_data='back_to_menu')]]
    
    await query.edit_message_text(
        text=f"📋 <b>Daftar Proxy Anda</b>\n\n{proxy_list}\n\n"
             f"Total: {len(user['proxies'])} proxy",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )

async def clear_proxies(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    user = get_user_data(user_id)
    
    user['proxies'] = []
    save_data(user_data)
    
    await query.edit_message_text(
        text="✅ Semua proxy berhasil dihapus",
        parse_mode='HTML'
    )
    await start(update, context)

# ======================
# MAIN APPLICATION
# ======================
def main():
    # Buat aplikasi Telegram
    application = ApplicationBuilder().token(TOKEN).build()
    
    # Setup handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(list_proxies, pattern='^list_proxy$'))
    application.add_handler(CallbackQueryHandler(clear_proxies, pattern='^clear_proxy$'))
    application.add_handler(CallbackQueryHandler(start, pattern='^back_to_menu$'))
    
    # Handler untuk input proxy
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        handle_proxy_input
    ))
    
    logger.info("Bot starting...")
    application.run_polling()

if __name__ == '__main__':
    main()
