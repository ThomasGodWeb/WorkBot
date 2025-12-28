import os
import sys
from dotenv import load_dotenv

load_dotenv()

# Токен бота из переменных окружения
BOT_TOKEN = os.getenv('BOT_TOKEN', '')

# Проверка токена
if not BOT_TOKEN or BOT_TOKEN.startswith('ваш_') or 'BotFather' in BOT_TOKEN:
    print("[ERROR] Ne ukazan token bota v fayle .env")
    print("[INFO] Poluchite token u @BotFather v Telegram i ukazhite ego v .env fayle:")
    print("   BOT_TOKEN=vash_token_zdes")
    sys.exit(1)

# ID администраторов (можно добавить несколько через запятую в .env)
ADMIN_IDS_STR = os.getenv('ADMIN_IDS', '')
ADMIN_IDS = []
if ADMIN_IDS_STR:
    for admin_id in ADMIN_IDS_STR.split(','):
        admin_id = admin_id.strip()
        if admin_id and admin_id.isdigit():
            ADMIN_IDS.append(int(admin_id))

# Проверка администраторов
if not ADMIN_IDS or (len(ADMIN_IDS_STR) > 0 and any(x in ADMIN_IDS_STR.lower() for x in ['ваш', 'your', 'telegram_id', 'example'])):
    print("[WARNING] Ne ukazany ID administratorov v fayle .env")
    print("[INFO] Ukazhite vash Telegram ID v .env fayle:")
    print("   ADMIN_IDS=vash_telegram_id")
    print("   Chtoby uznat svoi ID, napishite botu @userinfobot")
    if not ADMIN_IDS:
        print("\n[ERROR] Bot ne mozhet rabotat bez administratorov. Zavershenie raboty.")
        sys.exit(1)

# Путь к базе данных
DATABASE_PATH = 'bot_database.db'

