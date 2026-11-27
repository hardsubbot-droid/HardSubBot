import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent

def env_int(name: str, default: int = 0) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
API_ID = env_int("API_ID")
API_HASH = os.getenv("API_HASH", "").strip()
OWNER_ID = env_int("OWNER_ID")
GROUP_ID = env_int("GROUP_ID")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "").strip().rstrip("/")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "").strip()
PORT = env_int("PORT", 8080)

MAX_VIDEO_SIZE = env_int("MAX_VIDEO_SIZE", 2 * 1024 * 1024 * 1024)
MAX_CONCURRENT_JOBS = max(1, env_int("MAX_CONCURRENT_JOBS", 1))
VIDEO_PRESET = os.getenv("VIDEO_PRESET", "medium")
VIDEO_CRF = env_int("VIDEO_CRF", 23)
SUBTITLE_FONT = os.getenv("SUBTITLE_FONT", "Noto Sans Arabic")
SUBTITLE_SIZE = env_int("SUBTITLE_SIZE", 24)
SUBTITLE_MARGIN = env_int("SUBTITLE_MARGIN", 35)

DOWNLOAD_DIR = BASE_DIR / "downloads"
OUTPUT_DIR = BASE_DIR / "output"
TEMP_DIR = BASE_DIR / "temp"
SESSION_DIR = BASE_DIR / "sessions"
FONT_DIR = BASE_DIR / "fonts"

for directory in (DOWNLOAD_DIR, OUTPUT_DIR, TEMP_DIR, SESSION_DIR, FONT_DIR):
    directory.mkdir(parents=True, exist_ok=True)

SESSION_PATH = str(SESSION_DIR / "assistant")
