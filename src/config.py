import os
from dotenv import load_dotenv

# Tự động tìm và nạp file .env ở thư mục gốc
load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# Tạo thư mục temp để chứa các file audio tạm thời nếu chưa có
TEMP_DIR = "temp_audio"
os.makedirs(TEMP_DIR, exist_ok=True)

def validate_config():
    """Kiểm tra xem các biến môi trường quan trọng đã được cấu hình chưa."""
    missing = []
    if not TELEGRAM_BOT_TOKEN:
        missing.append("TELEGRAM_BOT_TOKEN")
    if not GEMINI_API_KEY:
        missing.append("GEMINI_API_KEY")
        
    if missing:
        raise ValueError(f"Thiếu các biến môi trường sau trong file .env: {', '.join(missing)}")
