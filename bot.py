import html
import json
import logging
import sys

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
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
        "en": "Commands:\n/start - open the main menu\n/stats - see your score, streak, and topic mastery\n/settings - choose difficulty and question mode\n/daily - start today's challenge\n/cancel - stop the active quiz\n/help - show this help",
        "ru": "Команды:\n/start - открыть главное меню\n/stats - посмотреть очки, серию и освоение тем\n/settings - выбрать сложность и режим вопросов\n/daily - начать ежедневный вызов\n/cancel - остановить текущую викторину\n/help - показать справку",
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
    "daily": {"en": "Daily challenge", "ru": "Ежедневный вызов"},
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
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(t("start_quiz", lang), callback_data="start_quiz")],
            [
                InlineKeyboardButton(t("review_wrong", lang), callback_data="review"),
                InlineKeyboardButton(t("bookmarked_menu", lang), callback_data="bookmarks"),
            ],
            [
                InlineKeyboardButton(t("stats", lang), callback_data="stats"),
                InlineKeyboardButton(t("settings_title", lang), callback_data="settings"),
            ],
            [
                InlineKeyboardButton(t("daily", lang), callback_data="daily"),
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


async def daily_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    ensure_user(update.effective_user)
    await begin_quiz(update, update.effective_user.id, "daily")


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


def after_answer_keyboard(question_id: int, has_next: bool = True, is_bookmarked: bool = False, lang: str = "en", show_glossary: bool = False) -> InlineKeyboardMarkup:
    bookmark_label = f"✅ {t('bookmark_question', lang)}" if is_bookmarked else t("bookmark_question", lang)
    first_row = [
        InlineKeyboardButton(t("why_not", lang), callback_data=f"why:{question_id}"),
    ]
    if show_glossary:
        define_label = "❓ Define Terms" if lang == "en" else "❓ Термины"
        first_row.append(InlineKeyboardButton(define_label, callback_data=f"def_terms:{question_id}"))
    rows = [
        first_row,
        [InlineKeyboardButton(bookmark_label, callback_data=f"bookmark:{question_id}")],
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


async def callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    data = query.data or ""
    if data and not data.startswith("def_terms:"):
        await query.answer()
    ensure_user(query.from_user)
    lang = _get_lang_from_update(update)
    try:
        if data == "noop":
            return
        if data == "menu":
            await show_main_menu(update, query.from_user.id)
        elif data.startswith("choose_lang:"):
            value = data.split(":", 1)[1]
            update_setting(query.from_user.id, "language", value)
            await show_main_menu(update, query.from_user.id)
        elif data == "start_quiz":
            await begin_quiz(update, query.from_user.id, "quiz")
        elif data == "daily":
            await begin_quiz(update, query.from_user.id, "daily")
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
            question_id = int(data.split(":", 1)[1])
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
            selected_index = None
            is_correct = False
            with get_db() as conn:
                row = conn.execute(
                    """
                    SELECT selected_index, is_correct 
                    FROM answers 
                    WHERE telegram_id = ? AND question_id = ?
                    ORDER BY id DESC LIMIT 1
                    """,
                    (telegram_id, question_id)
                ).fetchone()
                if row:
                    selected_index = row["selected_index"]
                    is_correct = bool(row["is_correct"])

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
            rows = [
                [InlineKeyboardButton(bookmark_label, callback_data=f"bookmark:{question_id}")],
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
            question_id = int(data.split(":", 1)[1])
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
    lang = _get_lang_from_update(update)
    await reply_long(update.message, t("buttons_only", lang), main_menu_for_lang(lang))


def main() -> None:
    if not TELEGRAM_BOT_TOKEN:
        print("Set TELEGRAM_BOT_TOKEN before running the bot.", file=sys.stderr)
        raise SystemExit(1)
    init_db()
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("cancel", cancel))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("settings", settings_command))
    app.add_handler(CommandHandler("daily", daily_command))
    app.add_handler(CallbackQueryHandler(callback_router))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, fallback_message))
    logger.info("Bot started")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
