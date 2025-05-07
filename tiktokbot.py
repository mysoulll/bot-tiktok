import logging
import asyncio
import os
import pickle
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
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from fake_useragent import UserAgent
import time
import random
from datetime import datetime, timedelta
from urllib.parse import urlparse

# ======================
# KONFIGURASI
# ======================
TOKEN = os.getenv('TELEGRAM_TOKEN')
DATA_FILE = 'user_data.pkl'
MAX_VIEWS_PER_REQUEST = 5000
MAX_REQUESTS_PER_HOUR = 5
VIEW_DELAY = (1, 3)  # Jeda antara view (min, max) detik
PAGE_LOAD_TIMEOUT = 30

# States untuk ConversationHandler
INPUT_PROXY, INPUT_TIKTOK = range(2)

# ======================
# INISIALISASI
# ======================
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Load/save data functions
def load_data():
    try:
        with open(DATA_FILE, 'rb') as f:
            return pickle.load(f)
    except (FileNotFoundError, EOFError):
        return {}

def save_data(data):
    with open(DATA_FILE, 'wb') as f:
        pickle.dump(data, f)

user_data = load_data()
ua = UserAgent()

# Konfigurasi Chrome
chrome_options = Options()
chrome_options.add_argument('--no-sandbox')
chrome_options.add_argument('--disable-dev-shm-usage')
chrome_options.add_argument('--headless')
chrome_options.add_argument('--disable-gpu')
chrome_options.add_argument('--disable-blink-features=AutomationControlled')
chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
chrome_options.add_experimental_option('useAutomationExtension', False)

# ======================
# FUNGSI UTAMA
# ======================
def get_chrome_driver(proxy=None):
    try:
        options = chrome_options.copy()
        if proxy:
            options.add_argument(f'--proxy-server={proxy}')
        options.add_argument(f'user-agent={ua.random}')
        
        service = Service(executable_path='/usr/bin/chromedriver')
        driver = webdriver.Chrome(service=service, options=options)
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        return driver
    except Exception as e:
        logger.error(f"Gagal membuat Chrome driver: {e}")
        raise

def is_valid_tiktok_url(url):
    try:
        result = urlparse(url)
        if not all([result.scheme in ['http', 'https'], 'tiktok.com' in result.netloc]):
            return False
        path = result.path.split('/')
        return len(path) >= 2
    except:
        return False

def is_valid_proxy(proxy):
    try:
        parts = proxy.split(':')
        if len(parts) != 2:
            return False
        ip, port = parts
        return port.isdigit() and 1 <= int(port) <= 65535
    except:
        return False

def extract_proxies(text):
    return [p.strip() for p in text.split() if is_valid_proxy(p.strip())]

def get_user_data(user_id):
    if user_id not in user_data:
        user_data[user_id] = {
            'proxies': [],
            'requests': {
                'count': 0,
                'last_request': datetime.now() - timedelta(hours=1)
            }
        }
        save_data(user_data)
    return user_data[user_id]

def check_rate_limit(user_id):
    user = get_user_data(user_id)
    now = datetime.now()
    
    if now - user['requests']['last_request'] < timedelta(hours=1):
        if user['requests']['count'] >= MAX_REQUESTS_PER_HOUR:
            return False
        user['requests']['count'] += 1
    else:
        user['requests']['count'] = 1
    
    user['requests']['last_request'] = now
    save_data(user_data)
    return True

async def simulate_human_interaction(driver):
    driver.execute_script(f"window.scrollBy(0, {random.randint(50, 150)})")
    await asyncio.sleep(random.uniform(2, 5))

async def increase_views(user_id, url, target_views):
    success = 0
    user = get_user_data(user_id)
    
    for i in range(target_views):
        driver = None
        try:
            proxy = random.choice(user['proxies']) if user['proxies'] else None
            driver = get_chrome_driver(proxy)
            driver.set_page_load_timeout(PAGE_LOAD_TIMEOUT)
            driver.get(url)
            await simulate_human_interaction(driver)
            success += 1
            if i % 10 == 0:
                logger.info(f"Progress: {success}/{target_views}")
        except Exception as e:
            logger.error(f"Error view {i}: {e}")
        finally:
            if driver:
                try:
                    driver.quit()
                except:
                    pass
            await asyncio.sleep(random.uniform(*VIEW_DELAY))
    
    return success

# ======================
# HANDLER TELEGRAM
# ======================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_user_data(update.effective_user.id)
    
    keyboard = [
        [InlineKeyboardButton("➕ Tambah Proxy", callback_data='add_proxy')],
        [InlineKeyboardButton("🗑 Hapus Proxy", callback_data='clear_proxy')],
        [InlineKeyboardButton("📋 List Proxy", callback_data='list_proxy')],
    ]
    
    if user['proxies']:
        keyboard.insert(2, [InlineKeyboardButton("🎭 Tambah View", callback_data='add_view')])
    
    keyboard.append([InlineKeyboardButton("ℹ Bantuan", callback_data='help')])
    
    await update.message.reply_text(
        f"🤖 <b>TikTok View Bot</b>\n\n"
        f"🔧 Proxy: {len(user['proxies'])}\n"
        f"📊 Request: {user['requests']['count']}/{MAX_REQUESTS_PER_HOUR}\n\n"
        "Pilih menu:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )
    return ConversationHandler.END

async def handle_proxy_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_user_data(update.effective_user.id)
    proxies = extract_proxies(update.message.text)
    
    if not proxies:
        await update.message.reply_text(
            "⚠ Format proxy salah. Contoh:\n"
            "<code>123.45.67.89:8080</code>\n"
            "atau multiple:\n"
            "<code>156.228.81.242:3129 156.228.104.58:3129</code>",
            parse_mode='HTML'
        )
        return INPUT_PROXY
    
    added = 0
    for p in proxies:
        if p not in user['proxies']:
            user['proxies'].append(p)
            added += 1
    
    save_data(user_data)
    
    await update.message.reply_text(
        f"✅ {added} proxy ditambahkan!\n"
        f"Total: {len(user['proxies'])}",
        parse_mode='HTML'
    )
    await start(update, context)
    return ConversationHandler.END

async def handle_tiktok_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if not check_rate_limit(user_id):
        await update.message.reply_text(
            f"⏳ Limit tercapai ({MAX_REQUESTS_PER_HOUR}/jam). Coba lagi nanti."
        )
        return ConversationHandler.END
    
    parts = update.message.text.split()
    if len(parts) != 2:
        await update.message.reply_text(
            "⚠ Format: <code>link_tiktok jumlah_view</code>\n"
            "Contoh: <code>https://vm.tiktok.com/abc 100</code>",
            parse_mode='HTML'
        )
        return INPUT_TIKTOK
    
    url, views = parts[0], parts[1]
    
    try:
        views = int(views)
        if views <= 0 or views > MAX_VIEWS_PER_REQUEST:
            await update.message.reply_text(
                f"⚠ Jumlah view 1-{MAX_VIEWS_PER_REQUEST}"
            )
            return INPUT_TIKTOK
            
        if not is_valid_tiktok_url(url):
            await update.message.reply_text(
                "⚠ Link TikTok tidak valid"
            )
            return INPUT_TIKTOK
            
        msg = await update.message.reply_text(
            f"⏳ Memproses {views} view...\n"
            f"🔗 {url}",
            parse_mode='HTML'
        )
        
        success = await increase_views(user_id, url, views)
        duration = (datetime.now() - msg.date).total_seconds()
        
        await msg.edit_text(
            f"✅ <b>Selesai!</b>\n\n"
            f"🔗 {url}\n"
            f"🎯 Target: {views} view\n"
            f"✅ Berhasil: {success} ({success/views*100:.1f}%)\n"
            f"⏱ Durasi: {duration:.1f} detik\n\n"
            f"📊 Request hari ini: {user_data[user_id]['requests']['count']}/{MAX_REQUESTS_PER_HOUR}",
            parse_mode='HTML'
        )
        
    except ValueError:
        await update.message.reply_text("⚠ Jumlah view harus angka")
        return INPUT_TIKTOK
    
    return ConversationHandler.END

async def list_proxies(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user = get_user_data(query.from_user.id)
    
    if not user['proxies']:
        await query.edit_message_text(
            text="📋 <b>Daftar Proxy</b>\n\nBelum ada proxy",
            parse_mode='HTML'
        )
        return
    
    proxy_list = "\n".join([f"🔹 {p}" for p in user['proxies']])
    await query.edit_message_text(
        text=f"📋 <b>Daftar Proxy</b>\n\n{proxy_list}\n\n"
             f"Total: {len(user['proxies'])}",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Kembali", callback_data='back_to_menu')]
        ]),
        parse_mode='HTML'
    )

async def clear_proxies(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user = get_user_data(query.from_user.id)
    user['proxies'] = []
    save_data(user_data)
    
    await query.edit_message_text(
        text="✅ Semua proxy dihapus",
        parse_mode='HTML'
    )
    await start(update, context)

async def show_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        text="ℹ <b>Bantuan Penggunaan</b>\n\n"
             "1. Tambahkan proxy terlebih dahulu\n"
             "2. Pilih 'Tambah View'\n"
             "3. Kirim link TikTok dan jumlah view\n\n"
             "Format:\n<code>https://tiktok.com/... 100</code>\n\n"
             f"🔧 Maksimal {MAX_VIEWS_PER_REQUEST} view/request\n"
             f"📊 Maksimal {MAX_REQUESTS_PER_HOUR} request/jam",
        parse_mode='HTML'
    )

# ======================
# MAIN APPLICATION
# ======================
def main():
    app = ApplicationBuilder().token(TOKEN).build()
    
    # Conversation handler
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            INPUT_PROXY: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_proxy_input)],
            INPUT_TIKTOK: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_tiktok_input)]
        },
        fallbacks=[CommandHandler('cancel', start)]
    )
    
    app.add_handler(conv_handler)
    app.add_handler(CallbackQueryHandler(list_proxies, pattern='^list_proxy$'))
    app.add_handler(CallbackQueryHandler(clear_proxies, pattern='^clear_proxy$'))
    app.add_handler(CallbackQueryHandler(show_help, pattern='^help$'))
    app.add_handler(CallbackQueryHandler(start, pattern='^back_to_menu$'))
    app.add_handler(CallbackQueryHandler(start, pattern='^add_proxy$'))
    app.add_handler(CallbackQueryHandler(start, pattern='^add_view$'))
    
    logger.info("Bot running...")
    app.run_polling()

if __name__ == '__main__':
    main()
