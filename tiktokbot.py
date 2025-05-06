import logging
import asyncio
import os
import sys
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
# KONFIGURASI UNTUK RAILWAY
# ======================
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')  # Menggunakan environment variable
MAX_VIEWS_PER_REQUEST = 5000
MAX_REQUESTS_PER_HOUR = 5

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

# Database sederhana (untuk production gunakan database eksternal)
user_data_db = {}
ua = UserAgent()

# Konfigurasi Chrome untuk Railway
CHROME_OPTIONS = Options()
CHROME_OPTIONS.add_argument('--no-sandbox')
CHROME_OPTIONS.add_argument('--disable-dev-shm-usage')
CHROME_OPTIONS.add_argument('--headless')
CHROME_OPTIONS.add_argument('--disable-gpu')
CHROME_OPTIONS.add_argument('--disable-blink-features=AutomationControlled')
CHROME_OPTIONS.add_experimental_option("excludeSwitches", ["enable-automation"])
CHROME_OPTIONS.add_experimental_option('useAutomationExtension', False)

# ======================
# FUNGSI UTAMA (OPTIMIZED FOR RAILWAY)
# ======================
def get_chrome_driver(user_id, proxy=None):
    """Create Chrome driver dengan konfigurasi untuk Railway"""
    try:
        chrome_options = CHROME_OPTIONS.copy()
        
        if proxy:
            chrome_options.add_argument(f'--proxy-server={proxy}')
        
        chrome_options.add_argument(f'user-agent={ua.random}')
        
        # Untuk Railway, kita menggunakan Chrome yang sudah terinstall
        service = Service(executable_path='/usr/bin/chromedriver')
        driver = webdriver.Chrome(service=service, options=chrome_options)
        
        # Ubah properti navigator untuk menghindari deteksi
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        return driver
    except Exception as e:
        logger.error(f"Error creating Chrome driver: {e}")
        raise

def is_valid_tiktok_url(url):
    """Validate TikTok URL"""
    try:
        result = urlparse(url)
        return all([result.scheme in ['http', 'https'],
                   'tiktok.com' in result.netloc])
    except:
        return False

def is_valid_proxy(proxy):
    """Validasi format proxy"""
    try:
        parts = proxy.split(':')
        if len(parts) != 2:
            return False
        ip, port = parts
        if not port.isdigit():
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

def check_rate_limit(user_id):
    """Implement rate limiting"""
    if user_id not in user_data_db:
        user_data_db[user_id] = {
            'proxies': [],
            'requests': {
                'count': 0,
                'last_request': datetime.now() - timedelta(hours=1)
            }
        }
        return True
        
    now = datetime.now()
    user_data = user_data_db[user_id]['requests']
    
    if now - user_data['last_request'] < timedelta(hours=1):
        if user_data['count'] >= MAX_REQUESTS_PER_HOUR:
            return False
        user_data['count'] += 1
    else:
        user_data['count'] = 1
        
    user_data['last_request'] = now
    return True

async def increase_tiktok_views(user_id, url, target_views):
    """Fungsi async untuk menambah view"""
    success_count = 0
    driver = None
    
    try:
        if user_id not in user_data_db or not user_data_db[user_id]['proxies']:
            await asyncio.sleep(1)
            return 0
            
        for i in range(target_views):
            try:
                proxy = random.choice(user_data_db[user_id]['proxies'])
                driver = get_chrome_driver(user_id, proxy)
                
                # Buka URL dengan timeout
                driver.set_page_load_timeout(30)
                driver.get(url)
                
                # Simulasi perilaku manusia
                await asyncio.sleep(random.uniform(3, 7))
                driver.execute_script("window.scrollBy(0, %d)" % random.randint(50, 150))
                await asyncio.sleep(random.uniform(2, 5))
                
                success_count += 1
                if i % 10 == 0:
                    logger.info(f"Progress: {success_count}/{target_views}")
                
            except Exception as e:
                logger.error(f"Error on view {i}: {str(e)}")
            finally:
                if driver:
                    try:
                        driver.quit()
                    except:
                        pass
                await asyncio.sleep(random.uniform(1, 3))
    
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}")
    finally:
        return success_count

# ======================
# HANDLER TELEGRAM
# ======================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if user_id not in user_data_db:
        user_data_db[user_id] = {
            'proxies': [],
            'requests': {
                'count': 0,
                'last_request': datetime.now() - timedelta(hours=1)
            }
        }
    
    keyboard = [
        [InlineKeyboardButton("➕ Tambah Proxy", callback_data='add_proxy')],
        [InlineKeyboardButton("🗑 Hapus Semua Proxy", callback_data='clear_proxy')],
        [InlineKeyboardButton("📋 List Proxy Saya", callback_data='list_proxy')],
        [InlineKeyboardButton("🎭 Tambah View TikTok", callback_data='add_view')],
        [InlineKeyboardButton("ℹ Bantuan", callback_data='help')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="🤖 <b>TikTok View Bot</b>\n\nPilih menu di bawah:",
        reply_markup=reply_markup,
        parse_mode='HTML'
    )
    return ConversationHandler.END

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    
    if query.data == 'add_proxy':
        await query.edit_message_text(
            text="🔧 <b>Tambah Proxy</b>\n\n"
                 "Anda bisa memasukkan:\n"
                 "- Satu proxy: <code>123.45.67.89:8080</code>\n"
                 "- Multiple proxies dipisahkan spasi/baris baru:\n"
                 "<code>156.228.81.242:3129 156.228.104.58:3129</code>",
            parse_mode='HTML'
        )
        return INPUT_PROXY
    
    elif query.data == 'clear_proxy':
        if user_id in user_data_db:
            user_data_db[user_id]['proxies'] = []
        await query.edit_message_text(
            text="✅ <b>Semua proxy berhasil dihapus</b>",
            parse_mode='HTML'
        )
    
    elif query.data == 'list_proxy':
        if user_id not in user_data_db or not user_data_db[user_id]['proxies']:
            await query.edit_message_text(
                text="📋 <b>Daftar Proxy Anda</b>\n\n"
                     "Anda belum menambahkan proxy",
                parse_mode='HTML'
            )
        else:
            proxy_list = "\n".join([f"🔹 {proxy}" for proxy in user_data_db[user_id]['proxies']])
            await query.edit_message_text(
                text=f"📋 <b>Daftar Proxy Anda</b>\n\n{proxy_list}\n\n"
                     f"Total: {len(user_data_db[user_id]['proxies'])} proxy",
                parse_mode='HTML'
            )
    
    elif query.data == 'add_view':
        if user_id not in user_data_db or not user_data_db[user_id]['proxies']:
            await query.edit_message_text(
                text="⚠ <b>Anda belum menambahkan proxy</b>\n\n"
                     "Silakan tambahkan proxy terlebih dahulu sebelum menambah view",
                parse_mode='HTML'
            )
        else:
            await query.edit_message_text(
                text="🎭 <b>Tambah View TikTok</b>\n\n"
                     "Masukkan link TikTok dan jumlah view yang diinginkan:\n\n"
                     "Contoh:\n"
                     "<code>https://vm.tiktok.com/abcdef 1000</code>",
                parse_mode='HTML'
            )
            return INPUT_TIKTOK
    
    elif query.data == 'help':
        await query.edit_message_text(
            text="ℹ <b>Bantuan Penggunaan Bot</b>\n\n"
                 "1. <b>Tambah Proxy</b>: Tambahkan proxy Anda (bisa multiple)\n"
                 "2. <b>Hapus Proxy</b>: Kosongkan daftar proxy\n"
                 "3. <b>List Proxy</b>: Lihat daftar proxy yang sudah ditambahkan\n"
                 "4. <b>Tambah View</b>: Masukkan link TikTok dan jumlah view\n\n"
                 f"📌 <i>Maksimal {MAX_VIEWS_PER_REQUEST} view per permintaan</i>\n"
                 f"📌 <i>Maksimal {MAX_REQUESTS_PER_HOUR} permintaan per jam</i>",
            parse_mode='HTML'
        )
    
    return ConversationHandler.END

async def input_proxy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()
    
    proxies = extract_proxies(text)
    if not proxies:
        await update.message.reply_text(
            "⚠ Tidak ada proxy valid yang ditemukan. Format harus:\n"
            "<code>ip:port</code>\n\n"
            "Contoh multiple proxy:\n"
            "<code>156.228.81.242:3129 156.228.104.58:3129 156.233.73.28:3129</code>",
            parse_mode='HTML'
        )
        return INPUT_PROXY
    
    if user_id not in user_data_db:
        user_data_db[user_id] = {
            'proxies': [],
            'requests': {
                'count': 0,
                'last_request': datetime.now() - timedelta(hours=1)
            }
        }
    
    added = 0
    existing = 0
    for proxy in proxies:
        if proxy not in user_data_db[user_id]['proxies']:
            user_data_db[user_id]['proxies'].append(proxy)
            added += 1
        else:
            existing += 1
    
    message = f"✅ <b>Proxy berhasil ditambahkan</b>\n\n"
    if added > 0:
        message += f"🔹 Ditambahkan: {added} proxy\n"
    if existing > 0:
        message += f"🔹 Sudah ada: {existing} proxy\n"
    message += f"\nTotal proxy Anda sekarang: {len(user_data_db[user_id]['proxies'])}"
    
    await update.message.reply_text(
        message,
        parse_mode='HTML'
    )
    
    return ConversationHandler.END

async def input_tiktok(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text
    
    if not check_rate_limit(user_id):
        await update.message.reply_text(
            f"⏳ Anda mencapai limit permintaan ({MAX_REQUESTS_PER_HOUR}/jam). Silakan coba lagi nanti."
        )
        return ConversationHandler.END
    
    parts = text.split()
    if len(parts) != 2:
        await update.message.reply_text(
            "⚠ Format salah. Gunakan format:\n"
            "<code>https://tiktok.com/... 1000</code>",
            parse_mode='HTML'
        )
        return INPUT_TIKTOK
    
    url = parts[0]
    try:
        views = int(parts[1])
        
        if views > MAX_VIEWS_PER_REQUEST:
            await update.message.reply_text(
                f"⚠ Maksimal {MAX_VIEWS_PER_REQUEST} view per permintaan"
            )
            return ConversationHandler.END
            
        if not is_valid_tiktok_url(url):
            await update.message.reply_text(
                "⚠ Link TikTok tidak valid"
            )
            return INPUT_TIKTOK
            
        processing_msg = await update.message.reply_text(
            "⏳ Memproses permintaan Anda..."
        )
        
        success_views = await increase_tiktok_views(user_id, url, views)
        
        await context.bot.edit_message_text(
            chat_id=update.effective_chat.id,
            message_id=processing_msg.message_id,
            text=f"✅ <b>Proses selesai!</b>\n\n"
                 f"🔗 Link: {url}\n"
                 f"🎯 Target view: {views}\n"
                 f"✅ Berhasil ditambahkan: {success_views}\n"
                 f"🔧 Proxy digunakan: {len(user_data_db[user_id]['proxies'])}\n\n"
                 f"📊 Total request Anda hari ini: {user_data_db[user_id]['requests']['count']}/{MAX_REQUESTS_PER_HOUR}",
            parse_mode='HTML'
        )
        
    except ValueError:
        await update.message.reply_text(
            "⚠ Jumlah view harus angka"
        )
        return INPUT_TIKTOK
    
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Operasi dibatalkan. Ketik /start untuk kembali ke menu utama."
    )
    return ConversationHandler.END

# ======================
# MAIN APPLICATION
# ======================
def main():
    # Buat aplikasi Telegram
    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    
    # Setup ConversationHandler
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            INPUT_PROXY: [MessageHandler(filters.TEXT & ~filters.COMMAND, input_proxy)],
            INPUT_TIKTOK: [MessageHandler(filters.TEXT & ~filters.COMMAND, input_tiktok)]
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )
    
    application.add_handler(conv_handler)
    application.add_handler(CallbackQueryHandler(button_handler))
    
    # Jalankan bot
    logger.info("Bot starting on Railway...")
    application.run_polling()

if __name__ == '__main__':
    main()
