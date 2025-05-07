import logging
import asyncio
import os
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
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')  # Menggunakan environment variable
MAX_VIEWS_PER_REQUEST = 5000  # Maksimal view per permintaan
MAX_REQUESTS_PER_HOUR = 5     # Maksimal permintaan per jam
VIEW_DELAY = (1, 3)           # Jeda antara view (min, max) detik
PAGE_LOAD_TIMEOUT = 30        # Timeout loading halaman

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

# Konfigurasi Chrome
CHROME_OPTIONS = Options()
CHROME_OPTIONS.add_argument('--no-sandbox')
CHROME_OPTIONS.add_argument('--disable-dev-shm-usage')
CHROME_OPTIONS.add_argument('--headless')
CHROME_OPTIONS.add_argument('--disable-gpu')
CHROME_OPTIONS.add_argument('--disable-blink-features=AutomationControlled')
CHROME_OPTIONS.add_experimental_option("excludeSwitches", ["enable-automation"])
CHROME_OPTIONS.add_experimental_option('useAutomationExtension', False)

# ======================
# FUNGSI UTAMA
# ======================
def get_chrome_driver(proxy=None):
    """Membuat Chrome driver dengan konfigurasi khusus"""
    try:
        chrome_options = CHROME_OPTIONS.copy()
        
        if proxy:
            chrome_options.add_argument(f'--proxy-server={proxy}')
        
        chrome_options.add_argument(f'user-agent={ua.random}')
        
        # Untuk Railway
        service = Service(executable_path='/usr/bin/chromedriver')
        driver = webdriver.Chrome(service=service, options=chrome_options)
        
        # Ubah properti navigator untuk menghindari deteksi
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        return driver
    except Exception as e:
        logger.error(f"Gagal membuat Chrome driver: {e}")
        raise

def is_valid_tiktok_url(url):
    """Validasi URL TikTok"""
    try:
        result = urlparse(url)
        if not all([result.scheme in ['http', 'https'], 'tiktok.com' in result.netloc]):
            return False
            
        # Validasi tambahan untuk pattern URL TikTok
        path = result.path.split('/')
        if len(path) < 2:
            return False
            
        return True
    except:
        return False

def is_valid_proxy(proxy):
    """Validasi format proxy"""
    try:
        parts = proxy.split(':')
        if len(parts) != 2:
            return False
        ip, port = parts
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

def check_rate_limit(user_id):
    """Implementasi rate limiting"""
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

async def simulate_human_interaction(driver):
    """Simulasi perilaku manusia"""
    # Scroll random
    scroll_amount = random.randint(50, 150)
    driver.execute_script(f"window.scrollBy(0, {scroll_amount})")
    
    # Tunggu dengan variasi waktu
    await asyncio.sleep(random.uniform(2, 5))

async def increase_tiktok_views(user_id, url, target_views):
    """Fungsi utama untuk menambah view"""
    success_count = 0
    driver = None
    
    try:
        if user_id not in user_data_db or not user_data_db[user_id]['proxies']:
            logger.error(f"User {user_id} tidak memiliki proxy")
            return 0
            
        proxies = user_data_db[user_id]['proxies']
        proxy_rotation = len(proxies)
        
        for i in range(target_views):
            try:
                # Rotasi proxy
                proxy = proxies[i % proxy_rotation]
                driver = get_chrome_driver(proxy)
                
                # Atur timeout dan buka URL
                driver.set_page_load_timeout(PAGE_LOAD_TIMEOUT)
                driver.get(url)
                
                # Simulasi interaksi manusia
                await simulate_human_interaction(driver)
                
                success_count += 1
                if i % 10 == 0 or i == target_views - 1:
                    logger.info(f"Progress user {user_id}: {success_count}/{target_views}")
                
            except Exception as e:
                logger.error(f"Error pada view {i}: {str(e)}")
            finally:
                if driver:
                    try:
                        driver.quit()
                    except:
                        pass
                # Jeda acak antara view
                await asyncio.sleep(random.uniform(*VIEW_DELAY))
    
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}")
    finally:
        return success_count

# ======================
# HANDLER TELEGRAM
# ======================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler perintah /start"""
    user_id = update.effective_user.id
    
    # Inisialisasi data user jika belum ada
    if user_id not in user_data_db:
        user_data_db[user_id] = {
            'proxies': [],
            'requests': {
                'count': 0,
                'last_request': datetime.now() - timedelta(hours=1)
            }
        }
    
    # Buat menu dinamis
    keyboard = [
        [InlineKeyboardButton("➕ Tambah Proxy", callback_data='add_proxy')],
        [InlineKeyboardButton("🗑 Hapus Semua Proxy", callback_data='clear_proxy')],
        [InlineKeyboardButton("📋 List Proxy Saya", callback_data='list_proxy')],
    ]
    
    # Tambahkan menu Tambah View hanya jika ada proxy
    if user_data_db[user_id]['proxies']:
        keyboard.insert(2, [InlineKeyboardButton("🎭 Tambah View TikTok", callback_data='add_view')])
    
    keyboard.append([InlineKeyboardButton("ℹ Bantuan", callback_data='help')])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=f"🤖 <b>TikTok View Bot</b>\n\n"
             f"🔧 Proxy tersedia: {len(user_data_db[user_id]['proxies'])}\n"
             f"📊 Request hari ini: {user_data_db[user_id]['requests']['count']}/{MAX_REQUESTS_PER_HOUR}\n\n"
             "Pilih menu di bawah:",
        reply_markup=reply_markup,
        parse_mode='HTML'
    )
    return ConversationHandler.END

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler untuk tombol inline"""
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    
    # Pastikan data user ada
    if user_id not in user_data_db:
        await start(update, context)
        return
    
    if query.data == 'add_proxy':
        await query.edit_message_text(
            text="🔧 <b>Tambah Proxy</b>\n\n"
                 "Kirim proxy dalam format:\n"
                 "<code>ip:port</code>\n\n"
                 "Contoh multiple proxy:\n"
                 "<code>156.228.81.242:3129 156.228.104.58:3129</code>\n\n"
                 "⚠ Pastikan proxy valid dan bekerja",
            parse_mode='HTML'
        )
        return INPUT_PROXY
    
    elif query.data == 'clear_proxy':
        user_data_db[user_id]['proxies'] = []
        await query.edit_message_text(
            text="✅ <b>Semua proxy berhasil dihapus</b>",
            parse_mode='HTML'
        )
        await start(update, context)
    
    elif query.data == 'list_proxy':
        if not user_data_db[user_id]['proxies']:
            await query.edit_message_text(
                text="📋 <b>Daftar Proxy Anda</b>\n\n"
                     "Anda belum menambahkan proxy\n\n"
                     "Gunakan menu '➕ Tambah Proxy' untuk menambahkan",
                parse_mode='HTML'
            )
        else:
            proxy_list = "\n".join([f"🔹 {proxy}" for proxy in user_data_db[user_id]['proxies']])
            keyboard = [
                [InlineKeyboardButton("🔙 Kembali ke Menu", callback_data='back_to_menu')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                text=f"📋 <b>Daftar Proxy Anda</b>\n\n{proxy_list}\n\n"
                     f"Total: {len(user_data_db[user_id]['proxies'])} proxy",
                reply_markup=reply_markup,
                parse_mode='HTML'
            )
    
    elif query.data == 'add_view':
        if not user_data_db[user_id]['proxies']:
            await query.edit_message_text(
                text="⚠ <b>Anda belum menambahkan proxy</b>\n\n"
                     "Silakan tambahkan proxy terlebih dahulu",
                parse_mode='HTML'
            )
            await start(update, context)
        else:
            await query.edit_message_text(
                text="🎭 <b>Tambah View TikTok</b>\n\n"
                     "Kirim link video TikTok dan jumlah view yang diinginkan:\n\n"
                     "Contoh:\n"
                     "<code>https://vm.tiktok.com/abcdef 100</code>\n\n"
                     f"⚠ Maksimal {MAX_VIEWS_PER_REQUEST} view per permintaan",
                parse_mode='HTML'
            )
            return INPUT_TIKTOK
    
    elif query.data == 'help':
        await query.edit_message_text(
            text="ℹ <b>Bantuan Penggunaan</b>\n\n"
                 "1. <b>Tambah Proxy</b>: Tambahkan proxy Anda\n"
                 "2. <b>Tambah View</b>: Tingkatkan view video TikTok\n"
                 "3. <b>List Proxy</b>: Lihat daftar proxy Anda\n\n"
                 "📌 <b>Format Permintaan View:</b>\n"
                 "<code>link_tiktok jumlah_view</code>\n\n"
                 "🔧 <b>Tips:</b>\n"
                 "- Gunakan proxy yang valid dan bekerja\n"
                 "- Jumlah view akan diproses secara bertahap\n"
                 f"- Maksimal {MAX_REQUESTS_PER_HOUR} permintaan per jam",
            parse_mode='HTML'
        )
    
    elif query.data == 'back_to_menu':
        await start(update, context)

async def input_proxy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler untuk input proxy"""
    user_id = update.effective_user.id
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
        return INPUT_PROXY
    
    # Inisialisasi jika belum ada
    if user_id not in user_data_db:
        user_data_db[user_id] = {
            'proxies': [],
            'requests': {
                'count': 0,
                'last_request': datetime.now() - timedelta(hours=1)
            }
        }
    
    # Tambahkan proxy baru (hindari duplikat)
    added_proxies = []
    existing_proxies = []
    
    for proxy in proxies:
        if proxy not in user_data_db[user_id]['proxies']:
            user_data_db[user_id]['proxies'].append(proxy)
            added_proxies.append(proxy)
        else:
            existing_proxies.append(proxy)
    
    # Format pesan balasan
    message = ""
    if added_proxies:
        added_list = "\n".join([f"🔹 {p}" for p in added_proxies])
        message += f"✅ <b>Proxy berhasil ditambahkan:</b>\n{added_list}\n\n"
    
    if existing_proxies:
        message += f"ℹ {len(existing_proxies)} proxy sudah ada sebelumnya\n\n"
    
    message += f"📊 Total proxy Anda sekarang: {len(user_data_db[user_id]['proxies'])}"
    
    await update.message.reply_text(
        message,
        parse_mode='HTML'
    )
    
    # Kembali ke menu utama
    await start(update, context)
    return ConversationHandler.END

async def input_tiktok(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler untuk input TikTok"""
    user_id = update.effective_user.id
    text = update.message.text.strip()
    
    if not check_rate_limit(user_id):
        await update.message.reply_text(
            f"⏳ Anda mencapai limit permintaan ({MAX_REQUESTS_PER_HOUR}/jam). Silakan coba lagi nanti."
        )
        return ConversationHandler.END
    
    parts = text.split()
    if len(parts) != 2:
        await update.message.reply_text(
            "⚠ Format salah. Gunakan:\n"
            "<code>link_tiktok jumlah_view</code>\n\n"
            "Contoh:\n"
            "<code>https://vm.tiktok.com/abcdef 100</code>",
            parse_mode='HTML'
        )
        return INPUT_TIKTOK
    
    url = parts[0]
    try:
        views = int(parts[1])
        
        if views <= 0:
            await update.message.reply_text(
                "⚠ Jumlah view harus lebih dari 0"
            )
            return INPUT_TIKTOK
            
        if views > MAX_VIEWS_PER_REQUEST:
            await update.message.reply_text(
                f"⚠ Maksimal {MAX_VIEWS_PER_REQUEST} view per permintaan"
            )
            return INPUT_TIKTOK
            
        if not is_valid_tiktok_url(url):
            await update.message.reply_text(
                "⚠ Link TikTok tidak valid. Pastikan link dari tiktok.com"
            )
            return INPUT_TIKTOK
            
        # Kirim pesan sedang memproses
        processing_msg = await update.message.reply_text(
            "⏳ <b>Memproses permintaan Anda...</b>\n\n"
            f"🔗 Link: {url}\n"
            f"🎯 Target: {views} view\n"
            f"🔧 Menggunakan {len(user_data_db[user_id]['proxies'])} proxy",
            parse_mode='HTML'
        )
        
        # Jalankan proses menambah view
        start_time = datetime.now()
        success_views = await increase_tiktok_views(user_id, url, views)
        duration = (datetime.now() - start_time).total_seconds()
        
        # Hitung persentase keberhasilan
        success_rate = (success_views / views) * 100 if views > 0 else 0
        
        await context.bot.edit_message_text(
            chat_id=update.effective_chat.id,
            message_id=processing_msg.message_id,
            text=f"✅ <b>Proses Selesai!</b>\n\n"
                 f"🔗 Link: {url}\n"
                 f"🎯 Target: {views} view\n"
                 f"✅ Berhasil: {success_views} view ({success_rate:.1f}%)\n"
                 f"⏱ Durasi: {duration:.1f} detik\n\n"
                 f"📊 Request hari ini: {user_data_db[user_id]['requests']['count']}/{MAX_REQUESTS_PER_HOUR}",
            parse_mode='HTML'
        )
        
    except ValueError:
        await update.message.reply_text(
            "⚠ Jumlah view harus angka"
        )
        return INPUT_TIKTOK
    
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler untuk membatalkan operasi"""
    await update.message.reply_text(
        "Operasi dibatalkan. Ketik /start untuk kembali ke menu utama."
    )
    return ConversationHandler.END

# ======================
# MAIN APPLICATION
# ======================
def main():
    """Jalankan bot"""
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
    logger.info("Bot TikTok View sedang berjalan...")
    application.run_polling()

if __name__ == '__main__':
    main()
