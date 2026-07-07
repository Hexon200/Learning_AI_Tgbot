import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
DATABASE_PATH = os.getenv("DATABASE_PATH", str(BASE_DIR / "quiz_bot.sqlite3"))
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

QUIZ_LENGTH = 20
DEFAULT_DIFFICULTY = "mixed"
DEFAULT_MODE = "mixed"
DEFAULT_LANGUAGE = "en"

DIFFICULTIES = ("mixed", "beginner", "intermediate", "advanced")
MODES = ("mixed", "core_ai", "llms", "agents", "coding_ai")

LANGUAGES = ("en", "ru")

LANGUAGE_LABELS = {
    "en": "English",
    "ru": "Русский",
}

MODE_LABELS = {
    "mixed": "Mixed",
    "core_ai": "Core AI",
    "llms": "LLMs",
    "agents": "Agents",
    "coding_ai": "Coding AI",
}

DIFFICULTY_LABELS = {
    "mixed": "Mixed",
    "beginner": "Beginner",
    "intermediate": "Intermediate",
    "advanced": "Advanced",
}
