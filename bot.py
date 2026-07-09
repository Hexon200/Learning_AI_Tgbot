import html
import json
import logging
import sys

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.request import HTTPXRequest
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters

from config import (
    DIFFICULTIES,
    MODES,
    QUIZ_LENGTH,
    TELEGRAM_BOT_TOKEN,
    LANGUAGES,
    LANGUAGE_LABELS,
)
from database import (
    cancel_active_session,
    complete_session,
    create_session,
    ensure_user,
    get_active_session,
    get_question,
    get_settings,
    get_db,
    init_db,
    is_bookmarked,
    record_answer,
    toggle_bookmark,
    update_setting,
    subscribe_user,
    unsubscribe_user,
    is_subscribed,
    get_all_subscribers,
)
from quiz_engine import (
    LEARNING_PATHS,
    available_question_count,
    get_question_for_session,
    leaderboard,
    select_questions,
    session_summary,
    user_stats,
    weak_study_list,
)


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


# Simple i18n dictionary for English and Russian. Add keys as needed.
TRANSLATIONS = {
    "start_welcome": {
        "en": "Welcome to the AI and LLM Quiz Bot.\n\nPractice practical concepts across transformers, RAG, agents, evaluation, safety, local models, multimodal AI, and coding agents.",
        "ru": "Добро пожаловать в викторину по AI и LLM.\n\nПрактикуйтесь в трансформерах, RAG, агентах, оценке, безопасности, локальных моделях, мультимодальном AI и кодирующих агентах.",
    },
    "help_text": {
        "en": "Commands:\n/start - open the main menu\n/stats - see your score, streak, and topic mastery\n/settings - choose difficulty and question mode\n/news - get daily AI news digest\n/subscribe - subscribe to daily news broadcasts\n/unsubscribe - unsubscribe from daily news\n/cancel - stop the active quiz\n/help - show this help",
        "ru": "Команды:\n/start - открыть главное меню\n/stats - посмотреть очки, серию и освоение тем\n/settings - выбрать сложность и режим вопросов\n/news - получить дайджест новостей ИИ\n/subscribe - подписаться на рассылку новостей\n/unsubscribe - отписаться от рассылки новостей\n/cancel - остановить текущую викторину\n/help - показать справку",
    },
    "cancelled": {"en": "Cancelled the active quiz.", "ru": "Активная викторина отменена."},
    "choose_learning_path": {"en": "Choose a learning path.", "ru": "Выберите учебный путь."},
    "no_active_weak": {"en": "No active weak questions yet. Start a quiz and missed questions will appear here.", "ru": "Пока нет слабых вопросов. Пройдите викторину, и пропущенные вопросы появятся здесь."},
    "low_pool_prompt": {"en": "Only {count} questions match this setting{path_label}.\n\nUse Mixed difficulty or Mixed mode?", "ru": "Только {count} вопросов соответствует этим настройкам{path_label}.\n\nИспользовать смешанную сложность или смешанный режим?"},
    "path_context": {"en": " in {path}", "ru": " в «{path}»"},
    "correct": {"en": "Correct", "ru": "Правильно"},
    "incorrect": {"en": "Incorrect", "ru": "Неправильно"},
    "your_answer": {"en": "Your answer:", "ru": "Ваш ответ:"},
    "correct_answer": {"en": "Correct answer:", "ru": "Правильный ответ:"},
    "explain_more": {"en": "Explain more", "ru": "Объяснить подробнее"},
    "why_not": {"en": "Why not the others?", "ru": "Почему не другие?"},
    "bookmark_question": {"en": "Bookmark question", "ru": "Добавить в закладки"},
    "next_question": {"en": "Next Question", "ru": "Следующий вопрос"},
    "see_results": {"en": "See Results", "ru": "Посмотреть результаты"},
    "settings_title": {"en": "Settings", "ru": "Настройки"},
    "language_label": {"en": "Language", "ru": "Язык"},
    "main_menu": {"en": "Main menu", "ru": "Главное меню"},
    "start_quiz": {"en": "Start 20-question quiz", "ru": "Начать викторину из 20 вопросов"},
    "review_wrong": {"en": "Review wrong answers", "ru": "Повторить неверные ответы"},
    "stats": {"en": "Stats", "ru": "Статистика"},
    "news": {"en": "📰 AI News Digest", "ru": "📰 Новости ИИ"},
    "fetching_news": {"en": "📰 Fetching today's AI news...", "ru": "📰 Загружаю сегодняшние новости ИИ..."},
    "leaderboard": {"en": "Leaderboard", "ru": "Таблица лидеров"},
    "learning_paths": {"en": "Learning paths", "ru": "Учебные пути"},
    "export_weak": {"en": "Export weak topics", "ru": "Экспорт слабых тем"},
    "start_another_quiz": {"en": "Start another quiz", "ru": "Начать другую викторину"},
    "cancel_button": {"en": "Cancel", "ru": "Отмена"},
    "difficulty_label": {"en": "Difficulty", "ru": "Сложность"},
    "question_mode_label": {"en": "Question mode", "ru": "Режим вопросов"},
    "use_mixed_difficulty": {"en": "Use Mixed difficulty", "ru": "Использовать смешанную сложность"},
    "use_mixed_mode": {"en": "Use Mixed mode", "ru": "Использовать смешанный режим"},
    "language_prompt": {
        "en": "Choose your language to start.",
        "ru": "Выберите язык, чтобы начать.",
    },
    "language_updated": {"en": "Language updated.", "ru": "Язык обновлен."},
    "question_header": {"en": "Question {number}/{total}", "ru": "Вопрос {number}/{total}"},
    "topic_label": {"en": "Topic", "ru": "Тема"},
    "stats_answered": {"en": "Answered", "ru": "Ответов"},
    "stats_correct": {"en": "Correct", "ru": "Правильно"},
    "stats_accuracy": {"en": "Accuracy", "ru": "Точность"},
    "active_weak_questions": {"en": "Active weak questions", "ru": "Активных слабых вопросов"},
    "current_streak": {"en": "Current streak", "ru": "Текущая серия"},
    "longest_streak": {"en": "Longest streak", "ru": "Лучшая серия"},
    "topic_mastery": {"en": "Topic mastery", "ru": "Освоение тем"},
    "no_topic_data": {"en": "No topic data yet.", "ru": "Пока нет данных по темам."},
    "quiz_complete": {"en": "Quiz complete", "ru": "Викторина завершена"},
    "score": {"en": "Score", "ru": "Счет"},
    "percentage": {"en": "Percentage", "ru": "Процент"},
    "weak_topics": {"en": "Weak topics", "ru": "Слабые темы"},
    "questions_missed": {"en": "Questions missed", "ru": "Вопросы с ошибками"},
    "suggested_next_focus": {"en": "Suggested next focus", "ru": "Следующий фокус"},
    "none": {"en": "None", "ru": "Нет"},
    "keep_mixing": {
        "en": "Keep mixing topics to maintain breadth.",
        "ru": "Продолжайте смешивать темы, чтобы сохранять широту знаний.",
    },
    "stale_question": {
        "en": "This question is no longer current.",
        "ru": "Этот вопрос уже неактуален.",
    },
    "unknown_learning_path": {"en": "Unknown learning path.", "ru": "Неизвестный учебный путь."},
    "unknown_action": {"en": "Unknown action.", "ru": "Неизвестное действие."},
    "generic_error": {
        "en": "Something went wrong. Please try /start again.",
        "ru": "Что-то пошло не так. Попробуйте снова через /start.",
    },
    "bookmarked": {"en": "Bookmarked.", "ru": "Добавлено в закладки."},
    "bookmark_removed": {"en": "Bookmark removed.", "ru": "Закладка удалена."},
    "no_bookmarks": {"en": "You have no bookmarked questions yet.", "ru": "У вас пока нет закладок."},
    "bookmarked_menu": {"en": "Review bookmarks", "ru": "Повторить закладки"},
    "never_answered_header": {"en": "Never answered by learning path", "ru": "Непройденные вопросы по учебным путям"},
    "no_scores": {"en": "No scores yet.", "ru": "Пока нет результатов."},
    "leaderboard_user": {"en": "User", "ru": "Пользователь"},
    "leaderboard_line": {
        "en": "{name}: {correct} correct, best streak {streak}",
        "ru": "{name}: правильно {correct}, лучшая серия {streak}",
    },
    "buttons_only": {
        "en": "Use the buttons below to continue, or send /start to choose a language again.",
        "ru": "Используйте кнопки ниже, чтобы продолжить, или отправьте /start, чтобы снова выбрать язык.",
    },
    "choose_lesson": {
        "en": "Choose a lesson:",
        "ru": "Выберите урок:",
    },
    "back_learning_paths": {
        "en": "⬅️ Back to learning paths",
        "ru": "⬅️ Назад к учебным путям",
    },
    "lesson_not_available": {
        "en": "This lesson will be available soon! Please select Lesson 1.",
        "ru": "Этот урок будет доступен позже! Пожалуйста, выберите Урок 1.",
    },
}


DIFFICULTY_LABELS_I18N = {
    "mixed": {"en": "Mixed", "ru": "Смешанная"},
    "beginner": {"en": "Beginner", "ru": "Начальный"},
    "intermediate": {"en": "Intermediate", "ru": "Средний"},
    "advanced": {"en": "Advanced", "ru": "Продвинутый"},
}

MODE_LABELS_I18N = {
    "mixed": {"en": "Mixed", "ru": "Смешанный"},
    "core_ai": {"en": "Core AI", "ru": "Основы AI"},
    "llms": {"en": "LLMs", "ru": "LLM"},
    "agents": {"en": "Agents", "ru": "Агенты"},
    "coding_ai": {"en": "Coding AI", "ru": "AI для кода"},
}

TOPIC_LABELS_I18N = {
    "AI agents": {"en": "AI agents", "ru": "AI-агенты"},
    "AI history": {"en": "AI history", "ru": "История AI"},
    "RAG": {"en": "RAG", "ru": "RAG"},
    "RLHF": {"en": "RLHF", "ru": "RLHF"},
    "attention": {"en": "attention", "ru": "внимание"},
    "benchmarks": {"en": "benchmarks", "ru": "бенчмарки"},
    "coding agents": {"en": "coding agents", "ru": "агенты для кода"},
    "context windows": {"en": "context windows", "ru": "контекстные окна"},
    "embeddings": {"en": "embeddings", "ru": "эмбеддинги"},
    "fine-tuning": {"en": "fine-tuning", "ru": "дообучение"},
    "hallucinations": {"en": "hallucinations", "ru": "галлюцинации"},
    "local LLMs": {"en": "local LLMs", "ru": "локальные LLM"},
    "model evaluation": {"en": "model evaluation", "ru": "оценка моделей"},
    "multimodal models": {"en": "multimodal models", "ru": "мультимодальные модели"},
    "open-source models": {"en": "open-source models", "ru": "open-source модели"},
    "pretraining": {"en": "pretraining", "ru": "предобучение"},
    "safety": {"en": "safety", "ru": "безопасность"},
    "tool use": {"en": "tool use", "ru": "использование инструментов"},
    "transformers": {"en": "transformers", "ru": "трансформеры"},
    "vector databases": {"en": "vector databases", "ru": "векторные базы данных"},
}

LEARNING_PATH_LABELS_I18N = {
    "transformer_basics": {"en": "Transformer Basics", "ru": "Основы трансформеров"},
    "rag_basics": {"en": "RAG Basics", "ru": "Основы RAG"},
    "ai_agents_basics": {"en": "AI Agents Basics", "ru": "Основы AI-агентов"},
    "coding_agents": {"en": "Coding Agents", "ru": "Агенты для кода"},
    "model_evaluation": {"en": "Model Evaluation", "ru": "Оценка моделей"},
    "local_llms": {"en": "Local LLMs", "ru": "Локальные LLM"},
    "deep_learning": {"en": "Deep Learning", "ru": "Глубокое обучение"},
    "deep_learning_lesson_1": {"en": "Deep Learning - Lesson 1", "ru": "Глубокое обучение - Урок 1"},
    "deep_learning_lesson_2": {"en": "Deep Learning - Lesson 2", "ru": "Глубокое обучение - Урок 2"},
    "deep_learning_lesson_3": {"en": "Deep Learning - Lesson 3", "ru": "Глубокое обучение - Урок 3"},
    "deep_learning_lesson_4": {"en": "Deep Learning - Lesson 4", "ru": "Глубокое обучение - Урок 4"},
    "deep_learning_lesson_5": {"en": "Deep Learning - Lesson 5", "ru": "Глубокое обучение - Урок 5"},
    "deep_learning_lesson_6": {"en": "Deep Learning - Lesson 6", "ru": "Глубокое обучение - Урок 6"},
    "deep_learning_lesson_7": {"en": "Deep Learning - Lesson 7", "ru": "Глубокое обучение - Урок 7"},
    "deep_learning_lesson_8": {"en": "Deep Learning - Lesson 8", "ru": "Глубокое обучение - Урок 8"},
    "deep_learning_lesson_9": {"en": "Deep Learning - Lesson 9", "ru": "Глубокое обучение - Урок 9"},
    "rag_lesson_1": {"en": "RAG Basics - Lesson 1", "ru": "Основы RAG - Урок 1"},
    "rag_lesson_2": {"en": "RAG Basics - Lesson 2", "ru": "Основы RAG - Урок 2"},
    "rag_lesson_3": {"en": "RAG Basics - Lesson 3", "ru": "Основы RAG - Урок 3"},
}


def t(key: str, lang: str, **kwargs) -> str:
    entry = TRANSLATIONS.get(key, {})
    text = entry.get(lang) or entry.get("en") or key
    try:
        return text.format(**kwargs)
    except Exception:
        return text


def _label(labels: dict[str, dict[str, str]], key: str, lang: str) -> str:
    entry = labels.get(key, {})
    return entry.get(lang) or entry.get("en") or key


def difficulty_label(value: str, lang: str) -> str:
    return _label(DIFFICULTY_LABELS_I18N, value, lang)


def mode_label(value: str, lang: str) -> str:
    return _label(MODE_LABELS_I18N, value, lang)


def topic_label(value: str, lang: str) -> str:
    return _label(TOPIC_LABELS_I18N, value, lang)


def learning_path_label(value: str, lang: str) -> str:
    return _label(LEARNING_PATH_LABELS_I18N, value, lang)


def _get_lang_from_update(update: Update) -> str:
    try:
        if update.callback_query and update.callback_query.from_user:
            uid = update.callback_query.from_user.id
        elif update.message and update.effective_user:
            uid = update.effective_user.id
        else:
            return "en"
        settings = get_settings(uid)
        return settings.get("language", "en")
    except Exception:
        return "en"


SAFE_TEXT_LIMIT = 3900


def split_message(text: str, limit: int = SAFE_TEXT_LIMIT) -> list[str]:
    if len(text) <= limit:
        return [text]
    chunks: list[str] = []
    remaining = text
    while len(remaining) > limit:
        split_at = remaining.rfind("\n", 0, limit)
        if split_at < limit // 2:
            split_at = remaining.rfind(" ", 0, limit)
        if split_at < limit // 2:
            split_at = limit
        chunks.append(remaining[:split_at].strip())
        remaining = remaining[split_at:].strip()
    if remaining:
        chunks.append(remaining)
    return chunks


def language_keyboard(prefix: str = "choose_lang") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton(LANGUAGE_LABELS[lang], callback_data=f"{prefix}:{lang}") for lang in LANGUAGES]]
    )


async def reply_long(message, text: str, reply_markup: InlineKeyboardMarkup | None = None, parse_mode: str | None = None) -> None:
    chunks = split_message(text)
    for idx, chunk in enumerate(chunks):
        await message.reply_text(
            chunk,
            reply_markup=reply_markup if idx == len(chunks) - 1 else None,
            parse_mode=parse_mode,
        )


def main_menu_for_lang(lang: str) -> InlineKeyboardMarkup:
    test_yourself_label = "📝 Test Yourself" if lang == "en" else "📝 Проверить себя"
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(t("start_quiz", lang), callback_data="start_quiz")],
            [InlineKeyboardButton(test_yourself_label, callback_data="test_yourself")],
            [
                InlineKeyboardButton(t("review_wrong", lang), callback_data="review"),
                InlineKeyboardButton(t("bookmarked_menu", lang), callback_data="bookmarks"),
            ],
            [
                InlineKeyboardButton(t("stats", lang), callback_data="stats"),
                InlineKeyboardButton(t("settings_title", lang), callback_data="settings"),
            ],
            [
                InlineKeyboardButton(t("news", lang), callback_data="news"),
                InlineKeyboardButton(t("leaderboard", lang), callback_data="leaderboard"),
            ],
            [InlineKeyboardButton(t("learning_paths", lang), callback_data="learning_paths")],
        ]
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user:
        ensure_user(update.effective_user)
    text = f"{t('language_prompt', 'en')}\n{t('language_prompt', 'ru')}"
    if update.message:
        await update.message.reply_text(text, reply_markup=language_keyboard())
    elif update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=language_keyboard())


async def show_main_menu(update: Update, telegram_id: int) -> None:
    lang = get_settings(telegram_id).get("language", "en")
    await send_or_edit(update, t("start_welcome", lang), main_menu_for_lang(lang))


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user:
        ensure_user(update.effective_user)
    lang = _get_lang_from_update(update)
    await reply_long(update.message, t("help_text", lang), main_menu_for_lang(lang))


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user:
        ensure_user(update.effective_user)
        cancel_active_session(update.effective_user.id)
    lang = _get_lang_from_update(update)
    await reply_long(update.message, t("cancelled", lang), main_menu_for_lang(lang))


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    ensure_user(update.effective_user)
    lang = _get_lang_from_update(update)
    text = format_stats(update.effective_user.id, lang)
    await reply_long(update.message, text, stats_keyboard(lang))


async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    ensure_user(update.effective_user)
    lang = _get_lang_from_update(update)
    await reply_long(update.message, format_settings(update.effective_user.id, lang), settings_keyboard(update.effective_user.id))


tutor_sessions = {}
interview_sessions = {}

SYSTEM_DESIGN_CHALLENGES = [
    {
        "en": "Design a real-time, high-throughput Retrieval-Augmented Generation (RAG) system for a global enterprise. The system must index 1 million new documents daily, update vector embeddings within 5 seconds of ingest, and handle peak query volume of 1,000 queries per second (QPS) with an end-to-end latency budget of under 200ms.",
        "ru": "Спроектируйте высокопроизводительную RAG-систему (генерация с дополненным поиском) для крупного предприятия. Система должна ежедневно индексировать 1 миллион новых документов, обновлять векторные эмбеддинги в течение 5 секунд после импорта и обрабатывать пиковый объем запросов в 1000 QPS с задержкой не более 200 мс."
    },
    {
        "en": "Design a scalable LLM gateway and routing layer for an organization. The gateway must handle load balancing across multiple provider endpoints (OpenAI, Anthropic, local clusters), enforce rate-limits and token-quota buckets per team, dynamically fallback on high-latency or failures, and cache semantically similar queries to reduce API costs.",
        "ru": "Спроектируйте масштабируемый шлюз LLM и слой маршрутизации для организации. Шлюз должен распределять нагрузку между провайдерами (OpenAI, Anthropic, локальные кластеры), ограничивать лимиты запросов и токенов для команд, автоматически переключаться при сбоях и кэшировать семантически похожие запросы для снижения затрат."
    },
    {
        "en": "Design an autonomous multi-agent coding assistant framework. The system must support long-running tasks (up to 30 minutes), coordinate multiple specialized agents (planner, coder, reviewer), maintain task memory states across execution turns, safely execute generated code in sandboxed environments, and handle tools that can dynamically fail or time out.",
        "ru": "Спроектируйте автономную среду для многоагентного помощника по написанию кода. Система должна поддерживать длительные задачи (до 30 минут), координировать специализированных агентов (планировщик, кодер, ревьюер), сохранять память о задачах, безопасно выполнять код в песочнице и обрабатывать сбои инструментов."
    },
    {
        "en": "Design a distributed vector database indexing engine. The system needs to support billion-scale vector sets, maintain real-time indexing capabilities for inserts, support hybrid search (combining sparse keyword search with dense vector search), and run efficiently in-memory on high-RAM cloud instances without exhausting budget bounds.",
        "ru": "Спроектируйте распределенный движок индексирования для векторной базы данных. Система должна поддерживать миллиардные наборы векторов, индексацию в реальном времени, гибридный поиск (разреженные ключевые слова + плотные векторы) и эффективно работать в памяти без превышения бюджета."
    }
]


# Keywords to identify AI-related posts on Hacker News
EXACT_KEYWORDS = {"ai", "llm", "rag", "dpo", "gpu", "lora", "rlhf", "vllm"}
SUBSTRING_KEYWORDS = {
    "llama", "deep learning", "machine learning", "transformers", "embeddings", 
    "agent", "quantization", "qlora", "claude", "gpt", "openai", "gemini",
    "mistral", "cohere", "diffusion", "stable diffusion", "midjourney",
    "model", "models", "deepseek", "anthropic", "neural", "speech", "voice",
    "vision", "robot", "robots", "robotics", "dataset", "datasets", "training",
    "inference"
}

def is_ai_related(title: str) -> bool:
    import re
    # Clean non-alphanumeric except hyphens, replace hyphens with spaces
    clean_title = re.sub(r'[^a-zA-Z0-9\s-]', ' ', title.lower()).replace("-", " ")
    words = set(clean_title.split())
    
    # 1. Exact match check for short acronyms
    if words.intersection(EXACT_KEYWORDS):
        return True
        
    # 2. Substring match check for longer terms
    for kw in SUBSTRING_KEYWORDS:
        if " " in kw:
            if kw in clean_title:
                return True
        else:
            if any(kw in w for w in words):
                return True
                
    return False

async def fetch_hacker_news() -> list[dict]:
    import httpx
    news_items = []
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            res = await client.get("https://hacker-news.firebaseio.com/v0/topstories.json")
            if res.status_code == 200:
                story_ids = res.json()[:30]  # Check top 30 stories
                for sid in story_ids:
                    item_res = await client.get(f"https://hacker-news.firebaseio.com/v0/item/{sid}.json")
                    if item_res.status_code == 200:
                        item = item_res.json()
                        title = item.get("title", "")
                        url = item.get("url") or f"https://news.ycombinator.com/item?id={sid}"
                        score = item.get("score", 0)
                        
                        if is_ai_related(title):
                            news_items.append({
                                "title": title,
                                "url": url,
                                "score": score,
                                "source": "Hacker News"
                            })
    except Exception as e:
        logger.warning(f"Hacker News fetch failed: {e}")
    news_items.sort(key=lambda x: x["score"], reverse=True)
    return news_items[:3]

async def fetch_venturebeat() -> list[dict]:
    import httpx
    import xml.etree.ElementTree as ET
    news_items = []
    try:
        url = "https://venturebeat.com/category/ai/feed/"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        async with httpx.AsyncClient(timeout=10.0) as client:
            res = await client.get(url, headers=headers, follow_redirects=True)
            if res.status_code == 200:
                root = ET.fromstring(res.text)
                channel = root.find('channel')
                if channel is not None:
                    items = channel.findall('item')
                    for item in items[:10]: # Look at top 10 articles
                        title_node = item.find('title')
                        link_node = item.find('link')
                        
                        title = title_node.text if title_node is not None else ""
                        href = link_node.text if link_node is not None else "https://venturebeat.com/category/ai/"
                        
                        news_items.append({
                            "title": title,
                            "url": href,
                            "score": 100,  # Default score for sorting
                            "source": "VentureBeat"
                        })
    except Exception as e:
        logger.warning(f"VentureBeat fetch failed: {e}")
    return news_items[:3]

async def fetch_reddit_rss(subreddit: str) -> list[dict]:
    import httpx
    import xml.etree.ElementTree as ET
    news_items = []
    try:
        url = f"https://www.reddit.com/r/{subreddit}/hot/.rss"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        async with httpx.AsyncClient(timeout=15.0) as client:
            res = await client.get(url, headers=headers)
            if res.status_code == 200:
                root = ET.fromstring(res.text)
                ns = {'atom': 'http://www.w3.org/2005/Atom'}
                entries = root.findall('atom:entry', ns)
                
                for entry in entries:
                    title_node = entry.find('atom:title', ns)
                    link_node = entry.find('atom:link', ns)
                    
                    title = title_node.text if title_node is not None else ""
                    href = link_node.attrib.get('href') if link_node is not None else f"https://www.reddit.com/r/{subreddit}/"
                    
                    # Skip pinned posts
                    if any(term in title.lower() for term in ["discussion", "pinned", "weekly", "welcome"]):
                        continue
                        
                    news_items.append({
                        "title": title,
                        "url": href,
                        "score": 100,
                        "source": f"r/{subreddit}"
                    })
    except Exception as e:
        logger.warning(f"Reddit r/{subreddit} RSS fetch failed: {e}")
    return news_items[:3]

async def fetch_techcrunch() -> list[dict]:
    import httpx
    import xml.etree.ElementTree as ET
    news_items = []
    try:
        url = "https://techcrunch.com/category/artificial-intelligence/feed/"
        headers = {"User-Agent": "Mozilla/5.0"}
        async with httpx.AsyncClient(timeout=10.0) as client:
            res = await client.get(url, headers=headers, follow_redirects=True)
            if res.status_code == 200:
                root = ET.fromstring(res.text)
                channel = root.find('channel')
                if channel is not None:
                    items = channel.findall('item')
                    for item in items[:10]:
                        title = item.find('title').text
                        link = item.find('link').text
                        news_items.append({
                            "title": title,
                            "url": link,
                            "score": 100,
                            "source": "TechCrunch"
                        })
    except Exception as e:
        logger.warning(f"TechCrunch fetch failed: {e}")
    return news_items[:3]

async def fetch_v2ex() -> list[dict]:
    import httpx
    import xml.etree.ElementTree as ET
    news_items = []
    try:
        url = "https://www.v2ex.com/feed/go/ai.xml"
        headers = {"User-Agent": "Mozilla/5.0"}
        async with httpx.AsyncClient(timeout=10.0) as client:
            res = await client.get(url, headers=headers, follow_redirects=True)
            if res.status_code == 200:
                root = ET.fromstring(res.text)
                ns = {'atom': 'http://www.w3.org/2005/Atom'}
                entries = root.findall('atom:entry', ns)
                for entry in entries[:10]:
                    title = entry.find('atom:title', ns).text
                    link = entry.find('atom:link', ns).attrib.get('href')
                    news_items.append({
                        "title": title,
                        "url": link,
                        "score": 100,
                        "source": "V2EX AI"
                    })
    except Exception as e:
        logger.warning(f"V2EX fetch failed: {e}")
    return news_items[:3]

async def fetch_arxiv(category: str) -> list[dict]:
    import httpx
    import xml.etree.ElementTree as ET
    news_items = []
    try:
        url = f"https://export.arxiv.org/rss/{category}"
        headers = {"User-Agent": "Mozilla/5.0"}
        async with httpx.AsyncClient(timeout=15.0) as client:
            res = await client.get(url, headers=headers, follow_redirects=True)
            if res.status_code == 200:
                root = ET.fromstring(res.text)
                channel = root.find('channel')
                if channel is not None:
                    items = root.findall('.//{http://purl.org/rss/1.0/}item') or channel.findall('item')
                    for item in items[:10]:
                        title = item.find('{http://purl.org/rss/1.0/}title') or item.find('title')
                        link = item.find('{http://purl.org/rss/1.0/}link') or item.find('link')
                        title_text = title.text if title is not None else ""
                        link_text = link.text if link is not None else ""
                        
                        news_items.append({
                            "title": title_text,
                            "url": link_text,
                            "score": 100,
                            "source": f"ArXiv {category}"
                        })
    except Exception as e:
        logger.warning(f"ArXiv {category} fetch failed: {e}")
    return news_items[:3]

async def generate_evening_digest(lang: str = "en") -> str:
    import asyncio
    from deep_translator import GoogleTranslator
    from datetime import datetime, timezone
    
    tc_task = fetch_techcrunch()
    v2_task = fetch_v2ex()
    ax_ai_task = fetch_arxiv("cs.AI")
    ax_lg_task = fetch_arxiv("cs.LG")
    
    tc, v2, ax_ai, ax_lg = await asyncio.gather(tc_task, v2_task, ax_ai_task, ax_lg_task)
    all_items = tc + v2 + ax_ai + ax_lg
    
    if not all_items:
        return "⚠️ No trending monthly AI news found." if lang == "en" else "⚠️ Не найдено главных трендовых обновлений за этот месяц."
        
    digest_lines = []
    title_label = "📰 <b>Monthly AI News Digest (Top Updates)</b>" if lang == "en" else "📰 <b>Ежемесячный дайджест новостей ИИ (Главное за месяц)</b>"
    digest_lines.append(title_label)
    digest_lines.append(f"Date: {datetime.now(timezone.utc).strftime('%Y-%m-%d')}\n")
    
    for i, item in enumerate(all_items[:10], start=1):
        title = item["title"]
        source = item["source"]
        url = item["url"]
        
        if lang == "ru":
            try:
                translator = GoogleTranslator(source="en", target="ru")
                title = translator.translate(title)
            except Exception:
                pass
                
        title_safe = html.escape(title)
        digest_lines.append(f"{i}. <b>{title_safe}</b>")
        digest_lines.append(f"   Source: <a href=\"{url}\">{source}</a>\n")
        
    return "\n".join(digest_lines)

async def generate_news_digest(lang: str = "en") -> str:
    import asyncio
    from deep_translator import GoogleTranslator
    from datetime import datetime, timezone
    
    hn_task = fetch_hacker_news()
    vb_task = fetch_venturebeat()
    llama_task = fetch_reddit_rss("LocalLLaMA")
    ml_task = fetch_reddit_rss("MachineLearning")
    
    hn_items, vb_items, llama_items, ml_items = await asyncio.gather(hn_task, vb_task, llama_task, ml_task)
    all_items = hn_items + vb_items + llama_items + ml_items
    
    if not all_items:
        return "⚠️ No trending AI news found in the last 24 hours." if lang == "en" else "⚠️ Не найдено трендовых новостей ИИ за последние 24 часа."
        
    digest_lines = []
    title_label = "📰 <b>Daily AI News Digest</b>" if lang == "en" else "📰 <b>Ежедневный дайджест новостей ИИ</b>"
    digest_lines.append(title_label)
    digest_lines.append(f"Date: {datetime.now(timezone.utc).strftime('%Y-%m-%d')}\n")
    
    # Take top 10 items
    for i, item in enumerate(all_items[:10], start=1):
        title = item["title"]
        source = item["source"]
        url = item["url"]
        
        if lang == "ru":
            try:
                translator = GoogleTranslator(source="en", target="ru")
                title = translator.translate(title)
            except Exception:
                pass
                
        title_safe = html.escape(title)
        digest_lines.append(f"{i}. <b>{title_safe}</b>")
        digest_lines.append(f"   Source: <a href=\"{url}\">{source}</a>\n")
        
    return "\n".join(digest_lines)

async def handle_news(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    telegram_id = query.from_user.id
    lang = get_settings(telegram_id).get("language", "en")
    
    await query.answer("📰 Loading news digest...")
    await query.edit_message_text(text=t("fetching_news", lang), parse_mode=ParseMode.HTML)
    
    try:
        digest = await generate_news_digest(lang)
        
        back_label = "⬅️ Back / Назад" if lang == "en" else "⬅️ Назад"
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(back_label, callback_data="menu")]
        ])
        
        await query.edit_message_text(digest, reply_markup=keyboard, parse_mode=ParseMode.HTML, disable_web_page_preview=True)
    except Exception as e:
        logger.exception("News Digest generation failed")
        back_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("⬅️ Back / Назад" if lang == "en" else "⬅️ Назад", callback_data="menu")]
        ])
        await query.edit_message_text(
            "⚠️ Failed to load news digest." if lang == "en" else "⚠️ Не удалось загрузить дайджест новостей.",
            reply_markup=back_keyboard,
            parse_mode=ParseMode.HTML
        )

async def news_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    ensure_user(update.effective_user)
    telegram_id = update.effective_user.id
    lang = get_settings(telegram_id).get("language", "en")
    
    status_msg = await update.message.reply_text("📰 Loading news digest...")
    try:
        digest = await generate_news_digest(lang)
        await status_msg.edit_text(digest, parse_mode=ParseMode.HTML, disable_web_page_preview=True)
    except Exception as e:
        logger.exception("News digest command failed")
        await status_msg.edit_text("⚠️ Failed to load news digest." if lang == "en" else "⚠️ Не удалось загрузить дайджест новостей.")


async def handle_test_yourself(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    import random
    query = update.callback_query
    telegram_id = query.from_user.id
    lang = get_settings(telegram_id).get("language", "en")
    await query.answer()
    
    # Pick a random System Design Challenge
    challenge = random.choice(SYSTEM_DESIGN_CHALLENGES)
    challenge_text = challenge[lang]
    
    interview_sessions[telegram_id] = {
        "challenge": challenge_text,
        "history": [
            {"role": "system", "content": (
                "You are a distinguished Principal AI Engineer and System Design Interviewer. "
                "The candidate is designing a solution for the following challenge:\n"
                f"Challenge: {challenge_text}\n\n"
                "As an interviewer, evaluate their response constructively but critically. Analyze their choices "
                "of data store, LLMs, pipelines, networks, scalability strategies, bottleneck mitigation, and latency. "
                "Ask 1-2 probing follow-up questions, and assign a rating/score out of 100 with clear justifications. "
                "Keep your reply well-structured, professional, educational, and under 300 words. "
                "Respond in English if the user is writing in English, otherwise respond in Russian."
            )}
        ]
    }
    
    welcome_text = (
        "📝 <b>System Design Interview Mode</b>\n\n"
        "<b>Your Challenge:</b>\n"
        f"{challenge_text}\n\n"
        "Describe your architectural solution below (mention your stack, data flows, and optimization choices). "
        "The AI Interviewer will evaluate your design, identify bottlenecks, and score your proposal.\n"
        "<i>(Please wait up to 10 seconds for the evaluation after sending your answer)</i>"
        if lang == "en" else
        "📝 <b>Режим Системного Интервью</b>\n\n"
        "<b>Ваша задача:</b>\n"
        f"{challenge_text}\n\n"
        "Опишите ваше архитектурное решение ниже (укажите используемый стек, потоки данных и оптимизации). "
        "ИИ-Интервьюер оценит вашу архитектуру, найдет узкие места и выставит оценку вашему проекту.\n"
        "<i>(Пожалуйста, подождите до 10 секунд для получения оценки после отправки вопроса)</i>"
    )
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ Exit Interview / Выйти" if lang == "en" else "❌ Выйти", callback_data="exit_interview")]
    ])
    
    await query.edit_message_text(welcome_text, reply_markup=keyboard, parse_mode=ParseMode.HTML)


async def handle_interview_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    import httpx
    telegram_id = update.effective_user.id
    lang = get_settings(telegram_id).get("language", "en")
    session = interview_sessions.get(telegram_id)
    if not session:
        return
        
    user_text = update.message.text
    session["history"].append({"role": "user", "content": user_text})
    
    # Send typing status
    await context.bot.send_chat_action(chat_id=telegram_id, action="typing")
    
    try:
        url = "https://text.pollinations.ai/"
        payload = {
            "messages": session["history"],
            "model": "openai"
        }
        async with httpx.AsyncClient(timeout=40.0) as client:
            res = await client.post(url, json=payload)
            if res.status_code == 200:
                ai_response = res.text
                
                # Clean pollinations ad footer if present
                for ad_marker in ["Support Pollinations.AI", "🌸 Ad 🌸", "Powered by Pollinations.AI"]:
                    if ad_marker in ai_response:
                        ai_response = ai_response.split(ad_marker)[0].strip()
                
                # Strip trailing Markdown dividers and whitespace
                while ai_response.endswith("---") or ai_response.endswith("\n") or ai_response.endswith(" "):
                    if ai_response.endswith("---"):
                        ai_response = ai_response[:-3].strip()
                    else:
                        ai_response = ai_response.strip()
            else:
                ai_response = "⚠️ Failed to get evaluation. Please try again." if lang == "en" else "⚠️ Не удалось получить оценку. Пожалуйста, попробуйте еще раз."
    except Exception as e:
        logger.error(f"Pollinations AI request failed in interview: {e}")
        ai_response = "⚠️ An error occurred while evaluating your design." if lang == "en" else "⚠️ Произошла ошибка при оценке вашей архитектуры."
        
    session["history"].append({"role": "assistant", "content": ai_response})
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Another Challenge / Другая задача" if lang == "en" else "🔄 Другая задача", callback_data="test_yourself")],
        [InlineKeyboardButton("❌ Exit Interview / Выйти" if lang == "en" else "❌ Выйти", callback_data="exit_interview")]
    ])
    
    try:
        await update.message.reply_text(ai_response, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)
    except Exception:
        # Fallback to plain text if Markdown format triggers Telegram parsing errors
        await update.message.reply_text(ai_response, reply_markup=keyboard, disable_web_page_preview=True)


async def handle_ask_tutor(update: Update, context: ContextTypes.DEFAULT_TYPE, question_id: int, selected_index: int) -> None:
    query = update.callback_query
    telegram_id = query.from_user.id
    lang = get_settings(telegram_id).get("language", "en")
    
    question = get_question(question_id)
    if not question:
        await query.answer("⚠️ Question not found / Вопрос не найден.", show_alert=True)
        return
        
    try:
        from quiz_engine import localize_question
        question = localize_question(question, lang)
    except Exception:
        pass
        
    await query.answer()
    
    # Initialize the tutor chat session history
    tutor_sessions[telegram_id] = {
        "question_id": question_id,
        "selected_index": selected_index,
        "history": [
            {"role": "system", "content": (
                "You are an expert AI and LLM tutor. You are helping a developer study for a certification/quiz. "
                "Here is the question they are currently studying:\n"
                f"Question: {question['question']}\n"
                f"Options:\n" + "\n".join(f"- {opt}" for opt in question['options']) + "\n"
                f"Correct Answer: {question['options'][question['answer_index']]}\n"
                f"Explanation: {question['explanation']}\n\n"
                "Provide clear, concise, and highly educational answers. Focus on code examples, deep concepts, "
                "and comparisons where appropriate. Keep answers under 200 words if possible. Answer in English "
                "if the user's question is in English, otherwise answer in Russian."
            )}
        ]
    }
    
    welcome_text = (
        "🤖 <b>AI Tutor Chat Mode</b>\n\n"
        "Ask me any questions about this topic! I will explain concepts, show code examples, and clarify details.\n"
        "<i>(Please wait up to 10 seconds for a response after sending a question)</i>\n\n"
        "Type your question below, or click <b>Cancel</b> to return to the quiz."
        if lang == "en" else
        "🤖 <b>Чат с ИИ-Тьютором</b>\n\n"
        "Задайте мне любые вопросы по этой теме! Я объясню концепции, покажу примеры кода и отвечу на ваши вопросы.\n"
        "<i>(Пожалуйста, подождите до 10 секунд для получения ответа после отправки вопроса)</i>\n\n"
        "Напишите ваш вопрос ниже или нажмите <b>Отмена</b>, чтобы вернуться к викторине."
    )
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ Cancel / Отмена" if lang == "en" else "❌ Отмена", callback_data=f"cancel_tutor:{question_id}:{selected_index}")]
    ])
    
    await query.edit_message_text(welcome_text, reply_markup=keyboard, parse_mode=ParseMode.HTML)


async def handle_tutor_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    import httpx
    telegram_id = update.effective_user.id
    lang = get_settings(telegram_id).get("language", "en")
    session = tutor_sessions.get(telegram_id)
    if not session:
        return
        
    user_text = update.message.text
    session["history"].append({"role": "user", "content": user_text})
    
    # Send typing status indicator
    await context.bot.send_chat_action(chat_id=telegram_id, action="typing")
    
    try:
        url = "https://text.pollinations.ai/"
        payload = {
            "messages": session["history"],
            "model": "openai"
        }
        async with httpx.AsyncClient(timeout=35.0) as client:
            res = await client.post(url, json=payload)
            if res.status_code == 200:
                ai_response = res.text
                
                # Clean pollinations ad footer if present
                for ad_marker in ["Support Pollinations.AI", "🌸 Ad 🌸", "Powered by Pollinations.AI"]:
                    if ad_marker in ai_response:
                        ai_response = ai_response.split(ad_marker)[0].strip()
                
                # Strip trailing Markdown dividers and whitespace
                while ai_response.endswith("---") or ai_response.endswith("\n") or ai_response.endswith(" "):
                    if ai_response.endswith("---"):
                        ai_response = ai_response[:-3].strip()
                    else:
                        ai_response = ai_response.strip()
            else:
                ai_response = "⚠️ Failed to get a response from the AI tutor. Please try again." if lang == "en" else "⚠️ Не удалось получить ответ от ИИ-тьютора. Пожалуйста, попробуйте еще раз."
    except Exception as e:
        logger.error(f"Pollinations AI request failed: {e}")
        ai_response = "⚠️ An error occurred while contacting the AI tutor." if lang == "en" else "⚠️ Произошла ошибка при связи с ИИ-тьютором."
        
    session["history"].append({"role": "assistant", "content": ai_response})
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ Cancel / Отмена" if lang == "en" else "❌ Отмена", callback_data=f"cancel_tutor:{session['question_id']}:{session['selected_index']}")]
    ])
    
    try:
        await update.message.reply_text(ai_response, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)
    except Exception:
        # Fallback to plain text if Markdown format triggers Telegram parsing errors
        await update.message.reply_text(ai_response, reply_markup=keyboard, disable_web_page_preview=True)


async def subscribe_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    ensure_user(update.effective_user)
    telegram_id = update.effective_user.id
    lang = get_settings(telegram_id).get("language", "en")
    
    try:
        if is_subscribed(telegram_id):
            msg = "You are already subscribed to the AI News Digest!" if lang == "en" else "Вы уже подписаны на дайджест новостей ИИ!"
        else:
            subscribe_user(telegram_id)
            msg = (
                "🎉 You have successfully subscribed to the AI News Digest!\n\n"
                "You will receive:\n"
                "• 1:00 PM: Daily AI news digest (Hacker News, VentureBeat, Reddit)\n"
                "• 8:00 PM: General most important updates of the month (TechCrunch, V2EX, ArXiv)"
                if lang == "en" else
                "🎉 Вы успешно подписались на дайджест новостей ИИ!\n\n"
                "Вы будете получать:\n"
                "• 13:00: Ежедневный дайджест (Hacker News, VentureBeat, Reddit)\n"
                "• 20:00: Главные обновления месяца (TechCrunch, V2EX, ArXiv)"
            )
        await update.message.reply_text(msg)
    except Exception as e:
        logger.exception("Subscribe command failed")
        await update.message.reply_text("⚠️ An error occurred / Произошла ошибка.")


async def unsubscribe_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    ensure_user(update.effective_user)
    telegram_id = update.effective_user.id
    lang = get_settings(telegram_id).get("language", "en")
    
    try:
        if not is_subscribed(telegram_id):
            msg = "You are not subscribed to the AI News Digest." if lang == "en" else "Вы не подписаны на дайджест новостей ИИ."
        else:
            unsubscribe_user(telegram_id)
            msg = "You have unsubscribed from the AI News Digest." if lang == "en" else "Вы отписались от дайджеста новостей ИИ."
        await update.message.reply_text(msg)
    except Exception as e:
        logger.exception("Unsubscribe command failed")
        await update.message.reply_text("⚠️ An error occurred / Произошла ошибка.")


async def broadcast_news(application, digest_type: str):
    subscribers = get_all_subscribers()
    if not subscribers:
        logger.info("No subscribers to broadcast news to.")
        return
        
    logger.info(f"Broadcasting {digest_type} news to {len(subscribers)} subscribers")
    
    try:
        digest_en = None
        digest_ru = None
        
        for telegram_id in subscribers:
            lang = get_settings(telegram_id).get("language", "en")
            
            if lang == "ru":
                if not digest_ru:
                    if digest_type == "daily":
                        digest_ru = await generate_news_digest("ru")
                    else:
                        digest_ru = await generate_evening_digest("ru")
                text = digest_ru
            else:
                if not digest_en:
                    if digest_type == "daily":
                        digest_en = await generate_news_digest("en")
                    else:
                        digest_en = await generate_evening_digest("en")
                text = digest_en
                
            try:
                await application.bot.send_message(
                    chat_id=telegram_id,
                    text=text,
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=True
                )
            except Exception as e:
                logger.warning(f"Failed to send news to subscriber {telegram_id}: {e}")
    except Exception as e:
        logger.error(f"Error during news broadcast: {e}", exc_info=True)


async def subscription_scheduler(application):
    import datetime
    import asyncio
    logger.info("Subscription scheduler started")
    last_sent_day = None
    last_sent_hour = None
    
    while True:
        try:
            now = datetime.datetime.now(datetime.timezone.utc)
            # User local time is UTC+5
            local_tz = datetime.timezone(datetime.timedelta(hours=5))
            now_local = now.astimezone(local_tz)
            
            current_day = now_local.date()
            current_hour = now_local.hour
            current_minute = now_local.minute
            
            if current_minute == 0:
                if (last_sent_day != current_day) or (last_sent_hour != current_hour):
                    if current_hour == 13:
                        logger.info("Triggering 1:00 PM daily news broadcast")
                        await broadcast_news(application, "daily")
                        last_sent_day = current_day
                        last_sent_hour = current_hour
                    elif current_hour == 20:
                        logger.info("Triggering 8:00 PM monthly news broadcast")
                        await broadcast_news(application, "monthly")
                        last_sent_day = current_day
                        last_sent_hour = current_hour
                        
        except Exception as e:
            logger.error(f"Error in subscription scheduler loop: {e}", exc_info=True)
            
        await asyncio.sleep(30)


def answer_keyboard(question: dict, lang: str = "en") -> InlineKeyboardMarkup:
    letters = ["A", "B", "C", "D", "E", "F"]
    buttons = []
    for idx in range(len(question["options"])):
        letter = letters[idx] if idx < len(letters) else str(idx + 1)
        buttons.append(InlineKeyboardButton(letter, callback_data=f"ans:{question['id']}:{idx}"))
    
    rows = []
    # Place buttons in rows of 2 for clean layout
    for i in range(0, len(buttons), 2):
        rows.append(buttons[i:i+2])
        
    rows.append([InlineKeyboardButton(t("cancel_button", lang), callback_data="cancel")])
    return InlineKeyboardMarkup(rows)


def after_answer_keyboard(question_id: int, selected_index: int, has_next: bool = True, is_bookmarked: bool = False, lang: str = "en", show_glossary: bool = False) -> InlineKeyboardMarkup:
    bookmark_label = f"✅ {t('bookmark_question', lang)}" if is_bookmarked else t("bookmark_question", lang)
    deep_dive_label = "🔍 Deep Dive" if lang == "en" else "🔍 Подробнее"
    tutor_label = "💬 Ask AI Tutor" if lang == "en" else "💬 Спросить ИИ-Тьютора"
    first_row = [
        InlineKeyboardButton(t("why_not", lang), callback_data=f"why:{question_id}"),
    ]
    if show_glossary:
        define_label = "❓ Define Terms" if lang == "en" else "❓ Термины"
        first_row.append(InlineKeyboardButton(define_label, callback_data=f"def_terms:{question_id}"))
    rows = [
        first_row,
        [
            InlineKeyboardButton(bookmark_label, callback_data=f"bookmark:{question_id}:{selected_index}"),
            InlineKeyboardButton(deep_dive_label, callback_data=f"deep_dive:{question_id}:{selected_index}")
        ],
        [
            InlineKeyboardButton(tutor_label, callback_data=f"ask_tutor:{question_id}:{selected_index}")
        ],
    ]
    rows.append([InlineKeyboardButton(t("next_question", lang) if has_next else t("see_results", lang), callback_data="next")])
    return InlineKeyboardMarkup(rows)


def stats_keyboard(lang: str = "en") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(t("export_weak", lang), callback_data="export_weak")],
            [InlineKeyboardButton(t("start_another_quiz", lang), callback_data="start_quiz")],
            [InlineKeyboardButton(t("main_menu", lang), callback_data="menu")],
        ]
    )


def learning_paths_keyboard(lang: str = "en") -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(learning_path_label(key, lang), callback_data=f"path:{key}")]
        for key in LEARNING_PATHS if not key.startswith("deep_learning_lesson_") and not key.startswith("rag_lesson_")
    ]
    rows.append([InlineKeyboardButton(t("main_menu", lang), callback_data="menu")])
    return InlineKeyboardMarkup(rows)


def rag_lessons_keyboard(lang: str = "en") -> InlineKeyboardMarkup:
    rows = []
    row = []
    for lesson_num in range(1, 4):
        label = f"Lesson {lesson_num}" if lang == "en" else f"Урок {lesson_num}"
        row.append(InlineKeyboardButton(label, callback_data=f"rag_lesson:{lesson_num}"))
    rows.append(row)
    rows.append([InlineKeyboardButton(t("back_learning_paths", lang), callback_data="learning_paths")])
    return InlineKeyboardMarkup(rows)


def deep_learning_lessons_keyboard(lang: str = "en") -> InlineKeyboardMarkup:
    rows = []
    for i in range(1, 10, 3):
        row = []
        for j in range(3):
            lesson_num = i + j
            if lesson_num <= 9:
                label = f"Lesson {lesson_num}" if lang == "en" else f"Урок {lesson_num}"
                row.append(InlineKeyboardButton(label, callback_data=f"dl_lesson:{lesson_num}"))
        rows.append(row)
    rows.append([InlineKeyboardButton(t("back_learning_paths", lang), callback_data="learning_paths")])
    return InlineKeyboardMarkup(rows)


def low_pool_keyboard(lang: str = "en") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(t("use_mixed_difficulty", lang), callback_data="use_mixed_difficulty")],
            [InlineKeyboardButton(t("use_mixed_mode", lang), callback_data="use_mixed_mode")],
            [InlineKeyboardButton(t("settings_title", lang), callback_data="settings")],
            [InlineKeyboardButton(t("main_menu", lang), callback_data="menu")],
        ]
    )


def settings_keyboard(telegram_id: int) -> InlineKeyboardMarkup:
    settings = get_settings(telegram_id)
    lang = settings.get("language", "en")
    rows = [[InlineKeyboardButton(t("difficulty_label", lang), callback_data="noop")]]
    rows.extend(
        [
            InlineKeyboardButton(
                ("* " if settings["difficulty"] == d else "") + difficulty_label(d, lang),
                callback_data=f"setdiff:{d}",
            )
            for d in DIFFICULTIES
        ][i : i + 2]
        for i in range(0, len(DIFFICULTIES), 2)
    )
    rows.append([InlineKeyboardButton(t("question_mode_label", lang), callback_data="noop")])
    rows.extend(
        [
            InlineKeyboardButton(
                ("* " if settings["question_mode"] == m else "") + mode_label(m, lang),
                callback_data=f"setmode:{m}",
            )
            for m in MODES
        ][i : i + 2]
        for i in range(0, len(MODES), 2)
    )
    rows.append([InlineKeyboardButton(t("language_label", lang), callback_data="noop")])
    rows.extend(
        [
            InlineKeyboardButton(
                ("* " if settings["language"] == l else "") + LANGUAGE_LABELS[l],
                callback_data=f"setlang:{l}",
            )
            for l in LANGUAGES
        ][i : i + 2]
        for i in range(0, len(LANGUAGES), 2)
    )
    rows.append([InlineKeyboardButton(t("main_menu", lang), callback_data="menu")])
    return InlineKeyboardMarkup(rows)


def format_question(question: dict, number: int, total: int, lang: str) -> str:
    letters = ["A", "B", "C", "D", "E", "F"]
    options_text = []
    for idx, opt in enumerate(question["options"]):
        letter = letters[idx] if idx < len(letters) else str(idx + 1)
        options_text.append(f"*{letter}*: {opt}")
    options_str = "\n".join(options_text)
    
    return (
        f"{t('question_header', lang, number=number, total=total)}\n"
        f"{t('topic_label', lang)}: {topic_label(question['topic'], lang)} | "
        f"{t('difficulty_label', lang)}: {difficulty_label(question['difficulty'], lang)}\n\n"
        f"{question['question']}\n\n"
        f"{options_str}"
    )


def format_stats(telegram_id: int, lang: str) -> str:
    stats = user_stats(telegram_id)
    answered = stats["answered"]
    accuracy = round((stats["correct"] / answered) * 100) if answered else 0
    mastery_lines = []
    for row in stats["mastery"][:12]:
        pct = round((row["correct"] / row["answered"]) * 100) if row["answered"] else 0
        mastery_lines.append(f"- {topic_label(row['topic'], lang)}: {pct}% ({row['correct']}/{row['answered']})")
    mastery = "\n".join(mastery_lines) if mastery_lines else t("no_topic_data", lang)
    
    never_answered_lines = []
    for m in stats.get("modes", []):
        never = m["total_count"] - m["answered_count"]
        name = mode_label(m["mode"], lang)
        never_answered_lines.append(f"- {name}: {never}")
    never_answered_str = "\n".join(never_answered_lines)
    
    return (
        f"{t('stats', lang)}\n\n"
        f"{t('stats_answered', lang)}: {answered}\n"
        f"{t('stats_correct', lang)}: {stats['correct']}\n"
        f"{t('stats_accuracy', lang)}: {accuracy}%\n"
        f"{t('active_weak_questions', lang)}: {stats['active_weak']}\n"
        f"{t('current_streak', lang)}: {stats['current_streak']}\n"
        f"{t('longest_streak', lang)}: {stats['longest_streak']}\n\n"
        f"*{t('never_answered_header', lang)}*:\n{never_answered_str}\n\n"
        f"*{t('topic_mastery', lang)}*:\n{mastery}"
    )


def format_settings(telegram_id: int, lang: str | None = None) -> str:
    settings = get_settings(telegram_id)
    lang = lang or settings.get("language", "en")
    return (
        f"{t('settings_title', lang)}\n\n"
        f"{t('difficulty_label', lang)}: {difficulty_label(settings['difficulty'], lang)}\n"
        f"{t('question_mode_label', lang)}: {mode_label(settings['question_mode'], lang)}\n"
        f"{t('language_label', lang)}: {LANGUAGE_LABELS.get(settings.get('language'), 'English')}"
    )


async def begin_quiz(
    update: Update,
    telegram_id: int,
    session_type: str = "quiz",
    review_only: bool = False,
    learning_path: str | None = None,
    bookmarks_only: bool = False,
) -> None:
    settings = get_settings(telegram_id)
    question_ids = select_questions(telegram_id, settings, review_only=review_only, learning_path=learning_path, bookmarks_only=bookmarks_only)
    
    lang = settings.get("language", "en")
    if bookmarks_only and not question_ids:
        await send_or_edit(update, t("no_bookmarks", lang), main_menu_for_lang(lang))
        return
        
    if review_only and not question_ids:
        await send_or_edit(update, t("no_active_weak", lang), main_menu_for_lang(lang))
        return
        
    if len(question_ids) < QUIZ_LENGTH and not review_only and not bookmarks_only:
        pool_count = available_question_count(settings, learning_path=learning_path)
        path_label = t("path_context", lang, path=learning_path_label(learning_path, lang)) if learning_path else ""
        await send_or_edit(
            update,
            t("low_pool_prompt", lang, count=pool_count, path_label=path_label),
            low_pool_keyboard(lang),
        )
        return
    session_mode = learning_path or settings["question_mode"]
    session_id = create_session(telegram_id, question_ids, session_mode, session_type)
    logger.info("Started %s session %s for %s", session_type, session_id, telegram_id)
    await show_current_question(update, telegram_id)


async def show_current_question(update: Update, telegram_id: int) -> None:
    session = get_active_session(telegram_id)
    if not session:
        lang = _get_lang_from_update(update)
        await send_or_edit(update, t("no_active_weak", lang), main_menu_for_lang(lang))
        return
    question = get_question_for_session(session)
    # localize question text/options based on user settings
    lang = get_settings(telegram_id).get("language", "en")
    try:
        from quiz_engine import localize_question

        question = localize_question(question, lang) if question else question
    except Exception:
        pass
    ids = json.loads(session["question_ids_json"])
    if not question:
        await finish_session(update, telegram_id, session["id"])
        return
    await send_or_edit(
        update,
        format_question(question, session["current_index"] + 1, len(ids), lang),
        answer_keyboard(question, lang),
    )


async def handle_answer(update: Update, context: ContextTypes.DEFAULT_TYPE, question_id: int, selected_index: int) -> None:
    query = update.callback_query
    telegram_id = query.from_user.id
    session = get_active_session(telegram_id)
    question = get_question(question_id)
    # localize question for feedback and explanations
    lang = get_settings(telegram_id).get("language", "en")
    try:
        from quiz_engine import localize_question

        question = localize_question(question, lang) if question else question
    except Exception:
        pass
    if not session or not question:
        lang = _get_lang_from_update(update)
        await send_or_edit(update, t("no_active_weak", lang), main_menu_for_lang(lang))
        return
    ids = json.loads(session["question_ids_json"])
    
    # Check if this question has already been answered in the active session
    from database import get_db
    with get_db() as conn:
        existing_answer = conn.execute(
            "SELECT selected_index FROM answers WHERE session_id = ? AND question_id = ?",
            (session["id"], question_id)
        ).fetchone()
        
    is_already_answered = existing_answer is not None
    
    if is_already_answered:
        # Use the already recorded answer index
        selected_index = existing_answer["selected_index"]
        is_correct = selected_index == question["answer_index"]
    else:
        # Validate that this is the expected active question
        expected_id = ids[session["current_index"]] if session["current_index"] < len(ids) else None
        if expected_id != question_id:
            await query.answer(t("stale_question", lang), show_alert=True)
            return
        is_correct = selected_index == question["answer_index"]
        record_answer(session["id"], telegram_id, question_id, selected_index, is_correct)
        
    updated = get_active_session(telegram_id)
    has_next = bool(updated and updated["current_index"] < len(ids))
    
    letters = ["A", "B", "C", "D", "E", "F"]
    correct_letter = letters[question["answer_index"]] if question["answer_index"] < len(letters) else str(question["answer_index"] + 1)
    chosen_letter = letters[selected_index] if selected_index < len(letters) else str(selected_index + 1)
    
    correct_answer = f"*{correct_letter}*: {question['options'][question['answer_index']]}"
    chosen = f"*{chosen_letter}*: {question['options'][selected_index]}"
    lang = _get_lang_from_update(update)
    text = (
        f"{t('correct', lang) if is_correct else t('incorrect', lang)}\n\n"
        f"{t('your_answer', lang)} {chosen}\n"
        f"{t('correct_answer', lang)} {correct_answer}\n\n"
        f"{question['explanation']}"
    )
    from glossary import detect_glossary_terms
    combined_text = f"{question['question']} {question['explanation']}"
    has_terms = len(detect_glossary_terms(combined_text)) > 0
        
    await send_or_edit(
        update, 
        text, 
        after_answer_keyboard(
            question_id, 
            selected_index,
            has_next=has_next, 
            is_bookmarked=is_bookmarked(telegram_id, question_id), 
            lang=lang, 
            show_glossary=has_terms
        )
    )


async def finish_session(update: Update, telegram_id: int, session_id: int) -> None:
    complete_session(session_id, telegram_id)
    lang = get_settings(telegram_id).get("language", "en")
    summary = session_summary(session_id)
    try:
        from quiz_engine import localize_question

        missed_questions = [localize_question(q, lang) for q in summary["missed"][:8]]
    except Exception:
        missed_questions = summary["missed"][:8]
    weak = ", ".join(
        f"{topic_label(topic, lang)} ({count})" for topic, count in summary["weak_topics"].most_common(5)
    ) or t("none", lang)
    missed_lines = [f"- {q['question']}" for q in missed_questions]
    missed = "\n".join(missed_lines) if missed_lines else t("none", lang)
    focus = (
        topic_label(summary["weak_topics"].most_common(1)[0][0], lang)
        if summary["weak_topics"]
        else t("keep_mixing", lang)
    )
    text = (
        f"{t('quiz_complete', lang)}\n\n"
        f"{t('score', lang)}: {summary['score']}/{summary['total']}\n"
        f"{t('percentage', lang)}: {summary['percentage']}%\n"
        f"{t('weak_topics', lang)}: {weak}\n\n"
        f"{t('questions_missed', lang)}:\n{missed}\n\n"
        f"{t('suggested_next_focus', lang)}: {focus}"
    )
    await send_or_edit(
        update,
        text,
        InlineKeyboardMarkup(
            [
                [InlineKeyboardButton(t("start_another_quiz", lang), callback_data="start_quiz")],
                [InlineKeyboardButton(t("review_wrong", lang), callback_data="review")],
                [InlineKeyboardButton(t("stats", lang), callback_data="stats")],
            ]
        ),
    )


async def send_or_edit(
    update: Update,
    text: str,
    reply_markup: InlineKeyboardMarkup | None = None,
    parse_mode: str | None = None,
) -> None:
    chunks = split_message(text)
    if update.callback_query:
        try:
            await update.callback_query.edit_message_text(
                chunks[0],
                reply_markup=reply_markup if len(chunks) == 1 else None,
                parse_mode=parse_mode,
            )
        except Exception as e:
            if "Message is not modified" not in str(e):
                raise
        for idx, chunk in enumerate(chunks[1:], start=1):
            await update.callback_query.message.reply_text(
                chunk,
                reply_markup=reply_markup if idx == len(chunks) - 1 else None,
                parse_mode=parse_mode,
            )
    elif update.message:
        await reply_long(update.message, text, reply_markup, parse_mode=parse_mode)


async def handle_deep_dive(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    data = query.data or ""
    parts = data.split(":")
    question_id = int(parts[1])
    selected_index = int(parts[2])
    
    telegram_id = query.from_user.id
    lang = get_settings(telegram_id).get("language", "en")
    
    loading_text = "🔍 Searching the web..." if lang == "en" else "🔍 Ищу подробности в интернете..."
    await query.answer(loading_text)
    
    status_text = "🔍 Searching the web... / Ищу в интернете..." if lang == "en" else "🔍 Ищу подробности в интернете..."
    await query.edit_message_text(text=status_text, parse_mode=ParseMode.HTML)
    
    back_label = "⬅️ Back / Назад" if lang == "en" else "⬅️ Назад"
    back_keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(back_label, callback_data=f"back_to_ans:{question_id}:{selected_index}")]
    ])
    
    try:
        question = get_question(question_id)
        if not question:
            await query.edit_message_text("⚠️ Question not found / Вопрос не найден.", reply_markup=back_keyboard, parse_mode=ParseMode.HTML)
            return
            
        from quiz_engine import localize_question
        # Localize to English for best technical search results
        question_en = localize_question(question, "en") if question else question
            
        import httpx
        from deep_translator import GoogleTranslator
        from urllib.parse import urlparse
        
        source_url = None
        source_title = None
        explanation_en = None
        exa_api_key = os.getenv("EXA_API_KEY")
        
        # User-Agent header required by Wikipedia to prevent 403 Forbidden errors
        wiki_headers = {
            "User-Agent": "AIQuizTelegramBot/1.0 (https://github.com/Hexon200/Learning_AI_Tgbot; contact@hexon.com) httpx/0.24"
        }
        
        # Topic translation mapping for technical Wikipedia articles
        TOPIC_MAPPINGS = {
            "safety": "safety of artificial intelligence",
            "attention": "attention (machine learning)",
            "transformers": "transformer (machine learning)",
            "embeddings": "vector embedding",
            "rag": "retrieval-augmented generation",
            "pretraining": "pre-training (machine learning)"
        }
        
        # 1. Try Exa Search if API key exists
        if exa_api_key:
            try:
                headers = {
                    "accept": "application/json",
                    "content-type": "application/json",
                    "x-api-key": exa_api_key
                }
                payload = {
                    "query": question_en['question'],
                    "numResults": 1,
                    "useAutoprompt": True
                }
                async with httpx.AsyncClient(timeout=10.0) as client:
                    res = await client.post("https://api.exa.ai/search", json=payload, headers=headers)
                    if res.status_code == 200:
                        results = res.json().get("results", [])
                        if results:
                            source_url = results[0].get("url")
                            source_title = results[0].get("title", "Web Article")
            except Exception as e:
                logger.warning(f"Exa search failed: {e}")
                
        # 2. Wikipedia search fallback (Rate-limit resistant, no API key needed)
        if not source_url:
            import re
            
            def get_clean_keywords(text: str) -> set[str]:
                words = re.findall(r'[a-zA-Z0-9]+', text.lower())
                stop_words = {"what", "is", "why", "how", "do", "does", "the", "a", "an", "of", "in", "on", "with", "or", "and", "to", "for", "at", "by", "from", "basics"}
                return set(words) - stop_words
                
            PATH_FALLBACK_TITLES = {
                "transformer_basics": "Transformer (machine learning)",
                "rag_basics": "Retrieval-augmented generation",
                "rag_lesson_1": "Retrieval-augmented generation",
                "rag_lesson_2": "Retrieval-augmented generation",
                "rag_lesson_3": "Retrieval-augmented generation",
                "ai_agents_basics": "Intelligent agent",
                "coding_agents": "Intelligent agent",
                "model_evaluation": "Evaluation of machine learning models",
                "local_llms": "Large language model",
                "deep_learning": "Deep learning"
            }
            
            clean_topic = question_en['topic'].strip().lower()
            
            # Scan question for known technical AI/ML terms to find precise matches first
            TECHNICAL_TERMS = [
                # Existing terms
                "cosine similarity", "dot product", "euclidean distance",
                "attention mechanism", "self-attention", "multi-head attention",
                "backpropagation", "gradient descent", "chain rule",
                "retrieval-augmented generation", "rag", "vector database",
                "word embedding", "vector embedding", "embeddings",
                "reinforcement learning", "rlhf", "dpo",
                "transformer", "encoder", "decoder",
                "temperature", "top-p", "top-k",
                "quantization", "fine-tuning", "lora", "qlora",
                "prompt engineering", "few-shot learning", "zero-shot learning",
                "in-context learning", "context window",
                "hallucination", "alignment", "bias", "overfitting",
                "parent-child chunking", "sentence-window chunking",
                
                # Newly scanned terms
                "expert systems", "turing test", "imagenet", "alexnet",
                "foundation model", "neural scaling laws", "tokenizer",
                "instruction tuning", "mixture of experts", "mixture-of-experts",
                "mixture of agents", "mixture-of-agents", "approximate nearest neighbor",
                "ann search", "held-out evaluation data", "benchmark contamination",
                "mmlu", "swe-bench", "lost in the middle", "prompt injection",
                "jailbreak", "open-weight models", "model distillation",
                "multimodal model", "vision-language model", "coding agent",
                "beam search", "function calling", "reranker", "hybrid search",
                "red-teaming", "model calibration", "latency", "throughput",
                "batch requests", "kv cache", "encoder-decoder", "decoder-only",
                "activation function", "hidden layers", "weighted sum", "partial derivative"
            ]
            
            matched_terms = []
            question_lower = question_en['question'].lower()
            for term in TECHNICAL_TERMS:
                if term in question_lower:
                    matched_terms.append(term)
            matched_terms.sort(key=len, reverse=True)
            
            # Formulate sequential search candidates
            search_queries = []
            
            # 1. Start with matching technical terms for highly specific Wikipedia routing
            for term in matched_terms:
                search_queries.append(f"{term} (machine learning)")
                search_queries.append(f"{term} machine learning")
                search_queries.append(f"{term} artificial intelligence")
                search_queries.append(term)
                
            # 2. General topic mappings and fallback topics
            if clean_topic in TOPIC_MAPPINGS:
                search_queries.append(TOPIC_MAPPINGS[clean_topic])
            search_queries.append(f"{question_en['topic']} (machine learning)")
            search_queries.append(f"{question_en['topic']} machine learning")
            search_queries.append(f"{question_en['topic']} artificial intelligence")
            search_queries.append(question_en['topic'])
            search_queries.append(question_en['question'])
            
            # 3. Path-level fallbacks if all specific searches fail
            q_mode = question_en.get("mode")
            if q_mode in PATH_FALLBACK_TITLES:
                search_queries.append(PATH_FALLBACK_TITLES[q_mode])
                
            # Prepare keywords to validate relevance
            query_keywords = get_clean_keywords(question_en['question'])
            topic_keywords = get_clean_keywords(question_en['topic'])
            combined_keywords = query_keywords.union(topic_keywords)
            # Add fallback title keywords so fallback results are accepted
            if q_mode in PATH_FALLBACK_TITLES:
                combined_keywords = combined_keywords.union(get_clean_keywords(PATH_FALLBACK_TITLES[q_mode]))
            
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    for q in search_queries:
                        params = {
                            "action": "opensearch",
                            "search": q,
                            "limit": 1,
                            "namespace": 0,
                            "format": "json"
                        }
                        res = await client.get("https://en.wikipedia.org/w/api.php", params=params, headers=wiki_headers)
                        if res.status_code == 200:
                            res_data = res.json()
                            if len(res_data) >= 4 and res_data[1]:
                                candidate_title = res_data[1][0]
                                candidate_url = res_data[3][0]
                                
                                # Validate keyword overlap to prevent funny/incorrect biography matches
                                match_keywords = get_clean_keywords(candidate_title)
                                has_overlap = False
                                for kw in combined_keywords:
                                    for mw in match_keywords:
                                        if (kw in mw or mw in kw) and (len(kw) > 3 or len(mw) > 3):
                                            has_overlap = True
                                            break
                                        if kw == mw:
                                            has_overlap = True
                                            break
                                    if has_overlap:
                                        break
                                        
                                if not has_overlap:
                                    logger.info(f"Skipping mismatched result: {candidate_title} for query: {q}")
                                    continue
                                    
                                source_title = candidate_title
                                source_url = candidate_url
                                break
            except Exception as e:
                logger.warning(f"Wikipedia sequential search failed: {e}")
                
        if not source_url:
            await query.edit_message_text(
                "⚠️ Could not find any relevant web sources." if lang == "en" else "⚠️ Не удалось найти подходящие веб-источники.",
                reply_markup=back_keyboard,
                parse_mode=ParseMode.HTML
            )
            return
            
        # 3. Fetch summary: Try Wikipedia REST Summary API first (very clean, no boilerplate)
        if "wikipedia.org" in source_url and source_title:
            try:
                title_slug = source_title.replace(" ", "_")
                summary_url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{title_slug}"
                async with httpx.AsyncClient(timeout=10.0) as client:
                    res = await client.get(summary_url, headers=wiki_headers)
                    if res.status_code == 200:
                        extract = res.json().get("extract", "")
                        if extract:
                            explanation_en = extract
            except Exception as e:
                logger.warning(f"Wikipedia REST summary failed: {e}")
                
        # 4. Fallback to Jina Reader if summary API was not used or failed
        if not explanation_en:
            try:
                jina_url = f"https://r.jina.ai/{source_url}"
                async with httpx.AsyncClient(timeout=30.0) as client:
                    headers = {"X-Return-Format": "text"}
                    response = await client.get(jina_url, headers=headers)
                    
                if response.status_code == 200:
                    raw_text = response.text
                    clean_lines = []
                    for line in raw_text.splitlines():
                        line_str = line.strip()
                        if not line_str:
                            continue
                        if len(line_str) < 20:
                            continue
                        if any(term in line_str.lower() for term in ["cookie", "privacy policy", "sign in", "subscribe", "menu", "search", "terms of service", "support"]):
                            continue
                        clean_lines.append(line_str)
                    explanation_en = "\n\n".join(clean_lines[:10])
            except Exception as e:
                logger.warning(f"Jina scrape fallback failed: {e}")
                
        if not explanation_en:
            await query.edit_message_text(
                "⚠️ Failed to load the source page." if lang == "en" else "⚠️ Не удалось загрузить веб-страницу.",
                reply_markup=back_keyboard,
                parse_mode=ParseMode.HTML
            )
            return
            
        # Slice to 100 words
        words = explanation_en.split()
        if len(words) > 100:
            explanation_en = " ".join(words[:100]) + "..."
            
        # 5. Translate if Russian
        if lang == "ru":
            translator = GoogleTranslator(source="en", target="ru")
            explanation = translator.translate(explanation_en)
        else:
            explanation = explanation_en
            
        domain = urlparse(source_url).netloc
        title_label = "📖 <b>Web Explanation:</b>" if lang == "en" else "📖 <b>Подробное объяснение из сети:</b>"
        source_label = "Source" if lang == "en" else "Источник"
        
        explanation_safe = html.escape(explanation)
        final_text = (
            f"{title_label}\n\n"
            f"{explanation_safe}\n\n"
            f"🔗 {source_label}: <a href=\"{source_url}\">{domain}</a>"
        )
        
        await query.edit_message_text(final_text, reply_markup=back_keyboard, parse_mode=ParseMode.HTML)
        
    except Exception as e:
        logger.exception("Deep Dive failed")
        await query.edit_message_text(
            "⚠️ An error occurred while retrieving the explanation." if lang == "en" else "⚠️ Произошла ошибка при получении объяснения.",
            reply_markup=back_keyboard,
            parse_mode=ParseMode.HTML
        )


async def callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    data = query.data or ""
    if data and not data.startswith("def_terms:") and not data.startswith("deep_dive:"):
        await query.answer()
    ensure_user(query.from_user)
    lang = _get_lang_from_update(update)
    try:
        if data == "noop":
            return
        elif data.startswith("deep_dive:"):
            await handle_deep_dive(update, context)
        elif data.startswith("back_to_ans:"):
            parts = data.split(":")
            q_id = int(parts[1])
            sel_idx = int(parts[2])
            await handle_answer(update, context, q_id, sel_idx)
        elif data.startswith("ask_tutor:"):
            parts = data.split(":")
            q_id = int(parts[1])
            sel_idx = int(parts[2])
            await handle_ask_tutor(update, context, q_id, sel_idx)
        elif data.startswith("cancel_tutor:"):
            parts = data.split(":")
            q_id = int(parts[1])
            sel_idx = int(parts[2])
            tutor_sessions.pop(query.from_user.id, None)
            await handle_answer(update, context, q_id, sel_idx)
        elif data == "menu":
            await show_main_menu(update, query.from_user.id)
        elif data.startswith("choose_lang:"):
            value = data.split(":", 1)[1]
            update_setting(query.from_user.id, "language", value)
            await show_main_menu(update, query.from_user.id)
        elif data == "start_quiz":
            await begin_quiz(update, query.from_user.id, "quiz")
        elif data == "test_yourself":
            await handle_test_yourself(update, context)
        elif data == "exit_interview":
            interview_sessions.pop(query.from_user.id, None)
            await show_main_menu(update, query.from_user.id)
        elif data == "news":
            await handle_news(update, context)
        elif data == "learning_paths":
            await send_or_edit(update, t("choose_learning_path", lang), learning_paths_keyboard(lang))
        elif data.startswith("path:"):
            path_key = data.split(":", 1)[1]
            if path_key not in LEARNING_PATHS:
                await query.answer(t("unknown_learning_path", lang), show_alert=True)
            elif path_key == "deep_learning":
                await send_or_edit(update, t("choose_lesson", lang), deep_learning_lessons_keyboard(lang))
            elif path_key == "rag_basics":
                await send_or_edit(update, t("choose_lesson", lang), rag_lessons_keyboard(lang))
            else:
                await begin_quiz(update, query.from_user.id, f"path:{path_key}", learning_path=path_key)
        elif data.startswith("dl_lesson:"):
            lesson_num = int(data.split(":", 1)[1])
            video_links = [
                "https://youtu.be/aircAruvnKk?lesson=1",
                "https://youtu.be/IHZwWFHWa-w?lesson=2",
                "https://youtu.be/Ilg3gGewQ5U?lesson=3",
                "https://youtu.be/tIeHLnjs5U8?lesson=4",
                "https://youtu.be/wjZofJX0v4M?lesson=5",
                "https://youtu.be/eMlx5fFNoYc?lesson=6",
                "https://youtu.be/9-Jl0dxWQs8?lesson=7",
                "https://youtu.be/LPZh9BOjkQs?lesson=8",
                "https://youtu.be/iv-5mZ_9CPY?lesson=9"
            ]
            if 1 <= lesson_num <= 9:
                video_url = video_links[lesson_num - 1]
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("🚀 Start test / Начать тест", callback_data=f"dl_start:{lesson_num}")],
                    [InlineKeyboardButton("⬅️ Back / Назад", callback_data="path:deep_learning")]
                ])
                await send_or_edit(update, video_url, keyboard)
            else:
                await query.answer(t("lesson_not_available", lang), show_alert=True)
        elif data.startswith("dl_start:"):
            lesson_num = int(data.split(":", 1)[1])
            if 1 <= lesson_num <= 9:
                await begin_quiz(
                    update, 
                    query.from_user.id, 
                    f"path:deep_learning_lesson_{lesson_num}", 
                    learning_path=f"deep_learning_lesson_{lesson_num}"
                )
        elif data.startswith("rag_lesson:"):
            lesson_num = int(data.split(":", 1)[1])
            video_links = [
                "https://youtu.be/T-D1OfcDW1M?lesson=1",
                "https://youtu.be/tLMViADvSNE?lesson=2",
                "https://youtu.be/_HQ2H_0Ayy0?lesson=3"
            ]
            if 1 <= lesson_num <= 3:
                video_url = video_links[lesson_num - 1]
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("🚀 Start test / Начать тест", callback_data=f"rag_start:{lesson_num}")],
                    [InlineKeyboardButton("⬅️ Back / Назад", callback_data="path:rag_basics")]
                ])
                await send_or_edit(update, video_url, keyboard)
            else:
                await query.answer(t("lesson_not_available", lang), show_alert=True)
        elif data.startswith("rag_start:"):
            lesson_num = int(data.split(":", 1)[1])
            if 1 <= lesson_num <= 3:
                await begin_quiz(
                    update, 
                    query.from_user.id, 
                    f"path:rag_lesson_{lesson_num}", 
                    learning_path=f"rag_lesson_{lesson_num}"
                )
        elif data.startswith("def_terms:"):
            question_id = int(data.split(":", 1)[1])
            question = get_question(question_id)
            if question:
                try:
                    from quiz_engine import localize_question
                    question = localize_question(question, lang)
                except Exception:
                    pass
                from glossary import detect_glossary_terms, format_definitions
                combined_text = f"{question['question']} {question['explanation']}"
                found_terms = detect_glossary_terms(combined_text)
                if found_terms:
                    definitions = format_definitions(found_terms, lang)
                    if len(definitions) <= 200:
                        try:
                            await query.answer(definitions, show_alert=True)
                            return
                        except Exception:
                            pass
                    await query.answer()
                    await context.bot.send_message(
                        chat_id=query.message.chat_id,
                        text=definitions,
                        parse_mode=None
                    )
                else:
                    await query.answer("No terms found / Термины не найдены", show_alert=True)
            else:
                await query.answer("Error loading question / Ошибка загрузки вопроса", show_alert=True)
        elif data == "review":
            await begin_quiz(update, query.from_user.id, "review", review_only=True)
        elif data == "bookmarks":
            await begin_quiz(update, query.from_user.id, "bookmarks", bookmarks_only=True)
        elif data == "next":
            session = get_active_session(query.from_user.id)
            if not session:
                await send_or_edit(update, t("no_active_weak", lang), main_menu_for_lang(lang))
            else:
                ids = json.loads(session["question_ids_json"])
                if session["current_index"] >= len(ids):
                    await finish_session(update, query.from_user.id, session["id"])
                else:
                    await show_current_question(update, query.from_user.id)
        elif data.startswith("ans:"):
            _, qid, idx = data.split(":")
            await handle_answer(update, context, int(qid), int(idx))
        elif data == "stats":
            await send_or_edit(update, format_stats(query.from_user.id, lang), stats_keyboard(lang))
        elif data == "settings":
            await send_or_edit(update, format_settings(query.from_user.id, lang), settings_keyboard(query.from_user.id))
        elif data.startswith("setdiff:"):
            value = data.split(":", 1)[1]
            update_setting(query.from_user.id, "difficulty", value)
            await send_or_edit(update, format_settings(query.from_user.id, lang), settings_keyboard(query.from_user.id))
        elif data.startswith("setmode:"):
            value = data.split(":", 1)[1]
            update_setting(query.from_user.id, "question_mode", value)
            await send_or_edit(update, format_settings(query.from_user.id, lang), settings_keyboard(query.from_user.id))
        elif data.startswith("setlang:"):
            value = data.split(":", 1)[1]
            update_setting(query.from_user.id, "language", value)
            lang = value
            await send_or_edit(
                update,
                f"{t('language_updated', lang)}\n\n{format_settings(query.from_user.id, lang)}",
                settings_keyboard(query.from_user.id),
            )
        elif data == "use_mixed_difficulty":
            update_setting(query.from_user.id, "difficulty", "mixed")
            await begin_quiz(update, query.from_user.id, "quiz")
        elif data == "use_mixed_mode":
            update_setting(query.from_user.id, "question_mode", "mixed")
            await begin_quiz(update, query.from_user.id, "quiz")
        elif data.startswith("explain:"):
            question = get_question(int(data.split(":", 1)[1]))
            lang = _get_lang_from_update(update)
            try:
                from quiz_engine import localize_question

                question = localize_question(question, lang) if question else question
            except Exception:
                pass
            explanation = question["explanation"] if question else t("generic_error", lang)
            if len(explanation) <= 190:
                await query.answer(explanation, show_alert=True)
            else:
                await query.answer(t("explain_more", lang), show_alert=False)
                await reply_long(query.message, explanation)
        elif data.startswith("why:"):
            parts = data.split(":")
            question_id = int(parts[1])
            selected_index = int(parts[2]) if len(parts) > 2 else None
            question = get_question(question_id)
            lang = _get_lang_from_update(update)
            try:
                from quiz_engine import localize_question
                question = localize_question(question, lang) if question else question
            except Exception:
                pass
            if not question:
                await query.answer(t("generic_error", lang), show_alert=True)
                return
            
            lines = []
            for idx, option in enumerate(question["options"]):
                if idx == question["answer_index"]:
                    continue
                marker = t("incorrect", lang)
                lines.append(f"{marker}: {option} - {question['wrong_explanations'][idx]}")
            why_text = "\n\n".join(lines)
            
            telegram_id = query.from_user.id
            is_correct = False
            
            if selected_index is not None:
                letters = ["A", "B", "C", "D", "E", "F"]
                correct_letter = letters[question["answer_index"]] if question["answer_index"] < len(letters) else str(question["answer_index"] + 1)
                chosen_letter = letters[selected_index] if selected_index < len(letters) else str(selected_index + 1)
                
                correct_answer = f"*{correct_letter}*: {question['options'][question['answer_index']]}"
                chosen = f"*{chosen_letter}*: {question['options'][selected_index]}"
                
                text = (
                    f"{t('correct', lang) if is_correct else t('incorrect', lang)}\n\n"
                    f"{t('your_answer', lang)} {chosen}\n"
                    f"{t('correct_answer', lang)} {correct_answer}\n\n"
                    f"{question['explanation']}"
                )
            else:
                text = question["explanation"]

            text = f"{text}\n\n{why_text}"

            session = get_active_session(telegram_id)
            has_next = True
            if session:
                ids = json.loads(session["question_ids_json"])
                has_next = bool(session["current_index"] < len(ids))

            is_bookmarked_val = is_bookmarked(telegram_id, question_id)
            bookmark_label = f"✅ {t('bookmark_question', lang)}" if is_bookmarked_val else t("bookmark_question", lang)
            tutor_label = "💬 Ask AI Tutor" if lang == "en" else "💬 Спросить ИИ-Тьютора"
            rows = [
                [InlineKeyboardButton(bookmark_label, callback_data=f"bookmark:{question_id}:{selected_index}")],
                [InlineKeyboardButton(tutor_label, callback_data=f"ask_tutor:{question_id}:{selected_index}")],
            ]
            rows.append([InlineKeyboardButton(t("next_question", lang) if has_next else t("see_results", lang), callback_data="next")])
            reply_markup = InlineKeyboardMarkup(rows)

            try:
                await query.edit_message_text(
                    text=text,
                    parse_mode="Markdown",
                    reply_markup=reply_markup
                )
            except Exception as e:
                logger.error("Failed to edit message text for why callback: %s", e)

            await query.answer()
        elif data.startswith("bookmark:"):
            telegram_id = query.from_user.id
            parts = data.split(":")
            question_id = int(parts[1])
            selected_index = int(parts[2])
            saved = toggle_bookmark(telegram_id, question_id)
            await query.answer(t("bookmarked", lang) if saved else t("bookmark_removed", lang), show_alert=False)
            
            session = get_active_session(telegram_id)
            has_next = True
            if session:
                ids = json.loads(session["question_ids_json"])
                has_next = bool(session["current_index"] < len(ids))
                
            await query.edit_message_reply_markup(
                reply_markup=after_answer_keyboard(
                    question_id, 
                    selected_index,
                    has_next=has_next, 
                    is_bookmarked=saved, 
                    lang=lang
                )
            )
        elif data == "export_weak":
            rows = weak_study_list(query.from_user.id)
            header = t("export_weak", lang) + "\n\n"
            if rows:
                try:
                    from quiz_engine import localize_question

                    rows = [localize_question(r, lang) for r in rows]
                except Exception:
                    pass
                body = "\n".join(
                    f"- {topic_label(r['topic'], lang)} ({difficulty_label(r['difficulty'], lang)}): {r['question']}"
                    for r in rows
                )
            else:
                body = t("no_active_weak", lang)
            await send_or_edit(update, header + body, stats_keyboard(lang))
        elif data == "leaderboard":
            rows = leaderboard()
            text = t("leaderboard", lang) + "\n\n" + (
                "\n".join(
                    f"{i + 1}. "
                    + t(
                        "leaderboard_line",
                        lang,
                        name=html.escape(r["first_name"] or r["username"] or t("leaderboard_user", lang)),
                        correct=r["correct"],
                        streak=r["longest_streak"],
                    )
                    for i, r in enumerate(rows)
                )
                if rows
                else t("no_scores", lang)
            )
            await send_or_edit(update, text, main_menu_for_lang(lang), parse_mode=ParseMode.HTML)
        elif data == "cancel":
            cancel_active_session(query.from_user.id)
            await send_or_edit(update, t("cancelled", lang), main_menu_for_lang(lang))
        else:
            await query.answer(t("unknown_action", lang), show_alert=True)
    except Exception:
        logger.exception("Callback failed: %s", data)
        await send_or_edit(update, t("generic_error", lang), main_menu_for_lang(lang))


async def fallback_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user:
        ensure_user(update.effective_user)
        telegram_id = update.effective_user.id
        if telegram_id in tutor_sessions:
            await handle_tutor_message(update, context)
            return
        elif telegram_id in interview_sessions:
            await handle_interview_message(update, context)
            return
            
    lang = _get_lang_from_update(update)
    await reply_long(update.message, t("buttons_only", lang), main_menu_for_lang(lang))


import os
import threading
from http.server import SimpleHTTPRequestHandler, HTTPServer

class HealthCheckHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/":
            self.send_response(200)
            self.send_header("Content-type", "text/plain")
            self.end_headers()
            self.wfile.write(b"OK")
        else:
            self.send_response(404)
            self.end_headers()
    def log_message(self, format, *args):
        # Suppress logging health pings to stdout to avoid log cluttering
        pass

def run_health_server():
    port = int(os.getenv("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    logger.info(f"Starting health check server on port {port}")
    server.serve_forever()


def main() -> None:
    if not TELEGRAM_BOT_TOKEN:
        print("Set TELEGRAM_BOT_TOKEN before running the bot.", file=sys.stderr)
        raise SystemExit(1)
    
    # Start health check server for Render in a daemon thread
    thread = threading.Thread(target=run_health_server, daemon=True)
    thread.start()

    init_db()
    
    async def post_init(application) -> None:
        import asyncio
        asyncio.create_task(subscription_scheduler(application))

    # Configure longer connection timeouts for cloud environments
    request = HTTPXRequest(connect_timeout=30.0, read_timeout=30.0, write_timeout=30.0)
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).request(request).post_init(post_init).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("cancel", cancel))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("settings", settings_command))
    app.add_handler(CommandHandler("news", news_command))
    app.add_handler(CommandHandler("subscribe", subscribe_command))
    app.add_handler(CommandHandler("unsubscribe", unsubscribe_command))
    app.add_handler(CallbackQueryHandler(callback_router))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, fallback_message))
    logger.info("Bot started")
    app.run_polling(allowed_updates=Update.ALL_TYPES, bootstrap_retries=5)


if __name__ == "__main__":
    main()
