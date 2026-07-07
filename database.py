import json
import logging
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent

from config import DATABASE_PATH, DEFAULT_DIFFICULTY, DEFAULT_MODE, DEFAULT_LANGUAGE
from questions import QUESTION_BANK

logger = logging.getLogger(__name__)


@contextmanager
def get_db():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    with get_db() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                telegram_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                current_streak INTEGER NOT NULL DEFAULT 0,
                longest_streak INTEGER NOT NULL DEFAULT 0,
                last_quiz_date TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS user_settings (
                telegram_id INTEGER PRIMARY KEY REFERENCES users(telegram_id) ON DELETE CASCADE,
                difficulty TEXT NOT NULL DEFAULT 'mixed',
                question_mode TEXT NOT NULL DEFAULT 'mixed',
                language TEXT NOT NULL DEFAULT 'en',
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS questions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                slug TEXT NOT NULL UNIQUE,
                topic TEXT NOT NULL,
                difficulty TEXT NOT NULL,
                mode TEXT NOT NULL,
                question TEXT NOT NULL,
                options_json TEXT NOT NULL,
                answer_index INTEGER NOT NULL,
                explanation TEXT NOT NULL,
                wrong_explanations_json TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS quiz_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE,
                mode TEXT NOT NULL,
                session_type TEXT NOT NULL DEFAULT 'quiz',
                question_ids_json TEXT NOT NULL,
                current_index INTEGER NOT NULL DEFAULT 0,
                score INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'active',
                started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                completed_at TEXT
            );

            CREATE TABLE IF NOT EXISTS answers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL REFERENCES quiz_sessions(id) ON DELETE CASCADE,
                telegram_id INTEGER NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE,
                question_id INTEGER NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
                selected_index INTEGER NOT NULL,
                is_correct INTEGER NOT NULL,
                answered_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS weak_questions (
                telegram_id INTEGER NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE,
                question_id INTEGER NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
                priority INTEGER NOT NULL DEFAULT 1,
                correct_streak INTEGER NOT NULL DEFAULT 0,
                times_wrong INTEGER NOT NULL DEFAULT 0,
                times_correct INTEGER NOT NULL DEFAULT 0,
                learned_at TEXT,
                last_seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (telegram_id, question_id)
            );

            CREATE TABLE IF NOT EXISTS bookmarks (
                telegram_id INTEGER NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE,
                question_id INTEGER NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (telegram_id, question_id)
            );
            """
        )
        seed_questions(conn)
        # Ensure older databases get the new `language` column in user_settings.
        cols = [r[1] for r in conn.execute("PRAGMA table_info(user_settings)").fetchall()]
        if "language" not in cols:
            conn.execute(
                f"ALTER TABLE user_settings ADD COLUMN language TEXT NOT NULL DEFAULT '{DEFAULT_LANGUAGE}'"
            )


def seed_questions(conn: sqlite3.Connection) -> None:
    # Load offline translations if present
    ru_path = BASE_DIR / "questions_ru.json"
    ru_data_map = {}
    if ru_path.exists():
        try:
            with open(ru_path, "r", encoding="utf-8") as f:
                ru_data_map = json.load(f)
            logger.info("Loaded %s translations from %s", len(ru_data_map), ru_path.name)
        except Exception as e:
            logger.error("Failed to load %s: %s", ru_path.name, e)

    for q in QUESTION_BANK:
        # Determine the new values from QUESTION_BANK
        new_q = q["question"]
        new_expl = q["explanation"]
        new_opts = q["options"]
        new_wrongs = q["wrong_explanations"]

        slug = q["slug"]
        ru_q_data = ru_data_map.get(slug, {})

        # Russian translations if available in JSON
        ru_question = ru_q_data.get("question")
        ru_expl = ru_q_data.get("explanation")
        ru_opts = ru_q_data.get("options")
        ru_wrongs = ru_q_data.get("wrong_explanations")

        # Check if the question already exists in the DB
        existing = conn.execute(
            "SELECT question, options_json, explanation, wrong_explanations_json FROM questions WHERE slug = ?",
            (slug,)
        ).fetchone()

        if existing:
            # Merge existing translations with the new English values
            def _merge(existing_raw: str, new_val: Any, ru_val: Any = None) -> str:
                if existing_raw.startswith("{"):
                    try:
                        data = json.loads(existing_raw)
                        if isinstance(data, dict):
                            data["en"] = new_val
                            if ru_val is not None:
                                data["ru"] = ru_val
                            return json.dumps(data)
                    except Exception:
                        pass
                # If there's no existing JSON but we have ru_val
                if ru_val is not None:
                    return json.dumps({"en": new_val, "ru": ru_val})
                if isinstance(new_val, (dict, list)):
                    return json.dumps(new_val)
                return str(new_val)

            question_val = _merge(existing["question"], new_q, ru_question)
            explanation_val = _merge(existing["explanation"], new_expl, ru_expl)
            options_val = _merge(existing["options_json"], new_opts, ru_opts)
            wrongs_val = _merge(existing["wrong_explanations_json"], new_wrongs, ru_wrongs)

            conn.execute(
                """
                UPDATE questions
                SET topic = ?, difficulty = ?, mode = ?, question = ?, options_json = ?,
                    answer_index = ?, explanation = ?, wrong_explanations_json = ?
                WHERE slug = ?
                """,
                (
                    q["topic"],
                    q["difficulty"],
                    q["mode"],
                    question_val,
                    options_val,
                    q["answer_index"],
                    explanation_val,
                    wrongs_val,
                    slug,
                ),
            )
        else:
            # Create standard values for insertion
            if ru_question:
                question_val = json.dumps({"en": new_q, "ru": ru_question})
            else:
                question_val = new_q

            if ru_expl:
                explanation_val = json.dumps({"en": new_expl, "ru": ru_expl})
            else:
                explanation_val = new_expl

            if ru_opts:
                options_val = json.dumps({"en": new_opts, "ru": ru_opts})
            else:
                options_val = json.dumps(new_opts)

            if ru_wrongs:
                wrongs_val = json.dumps({"en": new_wrongs, "ru": ru_wrongs})
            else:
                wrongs_val = json.dumps(new_wrongs)

            conn.execute(
                """
                INSERT INTO questions (
                    slug, topic, difficulty, mode, question, options_json,
                    answer_index, explanation, wrong_explanations_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    slug,
                    q["topic"],
                    q["difficulty"],
                    q["mode"],
                    question_val,
                    options_val,
                    q["answer_index"],
                    explanation_val,
                    wrongs_val,
                ),
            )
    logger.info("Seeded %s questions", len(QUESTION_BANK))


def ensure_user(user: Any) -> None:
    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO users (telegram_id, username, first_name)
            VALUES (?, ?, ?)
            ON CONFLICT(telegram_id) DO UPDATE SET
                username = excluded.username,
                first_name = excluded.first_name
            """,
            (user.id, user.username, user.first_name),
        )
        conn.execute(
            """
            INSERT OR IGNORE INTO user_settings (telegram_id, difficulty, question_mode)
            VALUES (?, ?, ?)
            """,
            (user.id, DEFAULT_DIFFICULTY, DEFAULT_MODE),
        )


def row_to_question(row: sqlite3.Row) -> dict[str, Any]:
    data = dict(row)
    # options_json and wrong_explanations_json may be JSON for a list or a language map
    options_raw = json.loads(data.pop("options_json"))
    wrongs_raw = json.loads(data.pop("wrong_explanations_json"))
    data["options"] = options_raw
    data["wrong_explanations"] = wrongs_raw

    # question and explanation columns may contain plain text or JSON maps
    try:
        q = json.loads(data["question"])
        data["question"] = q
    except Exception:
        # keep original string
        pass

    try:
        e = json.loads(data["explanation"])
        data["explanation"] = e
    except Exception:
        pass

    return data


def get_question(question_id: int) -> dict[str, Any] | None:
    with get_db() as conn:
        row = conn.execute("SELECT * FROM questions WHERE id = ?", (question_id,)).fetchone()
        return row_to_question(row) if row else None


def translate_question_if_missing(question_id: int, target_lang: str = "ru") -> None:
    """Translate question text/options/explanations into target_lang if missing, and persist them.

    Uses deep-translator's GoogleTranslator. If the package isn't installed or translation fails,
    the function logs and returns without raising to keep the bot running.
    """
    try:
        from deep_translator import GoogleTranslator
    except Exception:
        logger.warning("deep-translator not available; install requirements to enable auto-translation")
        return

    with get_db() as conn:
        row = conn.execute("SELECT * FROM questions WHERE id = ?", (question_id,)).fetchone()
        if not row:
            return
        q = row_to_question(row)

        updated = False

        translation_failed = False

        # Helper to translate a single string
        def _translate_str(s: str) -> str:
            nonlocal translation_failed
            try:
                return GoogleTranslator(source='auto', target=target_lang).translate(s)
            except Exception:
                logger.exception("Translation failed for text")
                translation_failed = True
                return s

        # Question text
        qtext = q.get("question")
        if isinstance(qtext, dict):
            if target_lang not in qtext:
                qtext[target_lang] = _translate_str(qtext.get("en") or next(iter(qtext.values())))
                updated = True
        else:
            # plain string -> convert to map
            qtext = {"en": qtext, target_lang: _translate_str(qtext)}
            updated = True

        # Explanation
        expl = q.get("explanation")
        if isinstance(expl, dict):
            if target_lang not in expl:
                expl[target_lang] = _translate_str(expl.get("en") or next(iter(expl.values())))
                updated = True
        else:
            expl = {"en": expl, target_lang: _translate_str(expl)}
            updated = True

        # Options
        opts = q.get("options")
        if isinstance(opts, dict):
            if target_lang not in opts:
                base = opts.get("en") or next(iter(opts.values()))
                opts[target_lang] = [ _translate_str(o) for o in base ]
                updated = True
        else:
            opts = {"en": opts, target_lang: [ _translate_str(o) for o in opts ]}
            updated = True

        # Wrong explanations
        wrongs = q.get("wrong_explanations")
        if isinstance(wrongs, dict):
            if target_lang not in wrongs:
                base = wrongs.get("en") or next(iter(wrongs.values()))
                wrongs[target_lang] = [ _translate_str(w) for w in base ]
                updated = True
        else:
            wrongs = {"en": wrongs, target_lang: [ _translate_str(w) for w in wrongs ]}
            updated = True

        if updated and not translation_failed:
            conn.execute(
                """
                UPDATE questions
                SET question = ?, options_json = ?, explanation = ?, wrong_explanations_json = ?
                WHERE id = ?
                """,
                (
                    json.dumps(qtext) if isinstance(qtext, dict) else qtext,
                    json.dumps(opts) if isinstance(opts, dict) else json.dumps(opts),
                    json.dumps(expl) if isinstance(expl, dict) else expl,
                    json.dumps(wrongs) if isinstance(wrongs, dict) else json.dumps(wrongs),
                    question_id,
                ),
            )


def get_settings(telegram_id: int) -> dict[str, str]:
    with get_db() as conn:
        row = conn.execute(
            "SELECT difficulty, question_mode, language FROM user_settings WHERE telegram_id = ?",
            (telegram_id,),
        ).fetchone()
        return dict(row) if row else {"difficulty": DEFAULT_DIFFICULTY, "question_mode": DEFAULT_MODE, "language": DEFAULT_LANGUAGE}


def update_setting(telegram_id: int, key: str, value: str) -> None:
    if key == "difficulty":
        column = "difficulty"
    elif key == "question_mode":
        column = "question_mode"
    elif key == "language":
        column = "language"
    else:
        column = "difficulty"
    with get_db() as conn:
        conn.execute(
            f"UPDATE user_settings SET {column} = ?, updated_at = CURRENT_TIMESTAMP WHERE telegram_id = ?",
            (value, telegram_id),
        )


def create_session(telegram_id: int, question_ids: list[int], mode: str, session_type: str = "quiz") -> int:
    with get_db() as conn:
        conn.execute(
            "UPDATE quiz_sessions SET status = 'cancelled' WHERE telegram_id = ? AND status = 'active'",
            (telegram_id,),
        )
        cur = conn.execute(
            """
            INSERT INTO quiz_sessions (telegram_id, mode, session_type, question_ids_json)
            VALUES (?, ?, ?, ?)
            """,
            (telegram_id, mode, session_type, json.dumps(question_ids)),
        )
        return int(cur.lastrowid)


def get_active_session(telegram_id: int) -> sqlite3.Row | None:
    with get_db() as conn:
        return conn.execute(
            """
            SELECT * FROM quiz_sessions
            WHERE telegram_id = ? AND status = 'active'
            ORDER BY id DESC LIMIT 1
            """,
            (telegram_id,),
        ).fetchone()


def get_session(session_id: int) -> sqlite3.Row | None:
    with get_db() as conn:
        return conn.execute("SELECT * FROM quiz_sessions WHERE id = ?", (session_id,)).fetchone()


def record_answer(session_id: int, telegram_id: int, question_id: int, selected_index: int, is_correct: bool) -> None:
    with get_db() as conn:
        session = conn.execute("SELECT * FROM quiz_sessions WHERE id = ?", (session_id,)).fetchone()
        if not session or session["status"] != "active":
            return
        existing = conn.execute(
            "SELECT 1 FROM answers WHERE session_id = ? AND question_id = ?",
            (session_id, question_id),
        ).fetchone()
        if existing:
            return

        conn.execute(
            """
            INSERT INTO answers (session_id, telegram_id, question_id, selected_index, is_correct)
            VALUES (?, ?, ?, ?, ?)
            """,
            (session_id, telegram_id, question_id, selected_index, int(is_correct)),
        )
        score_delta = 1 if is_correct else 0
        conn.execute(
            """
            UPDATE quiz_sessions
            SET score = score + ?, current_index = current_index + 1
            WHERE id = ?
            """,
            (score_delta, session_id),
        )
        update_weak_question(conn, telegram_id, question_id, is_correct)


def update_weak_question(conn: sqlite3.Connection, telegram_id: int, question_id: int, is_correct: bool) -> None:
    row = conn.execute(
        "SELECT * FROM weak_questions WHERE telegram_id = ? AND question_id = ?",
        (telegram_id, question_id),
    ).fetchone()
    if is_correct:
        if not row or row["learned_at"]:
            return
        streak = row["correct_streak"] + 1
        learned_at = datetime.utcnow().isoformat(timespec="seconds") if streak >= 2 else None
        conn.execute(
            """
            UPDATE weak_questions
            SET priority = MAX(priority - 1, 0),
                correct_streak = ?,
                times_correct = times_correct + 1,
                learned_at = ?,
                last_seen_at = CURRENT_TIMESTAMP
            WHERE telegram_id = ? AND question_id = ?
            """,
            (streak, learned_at, telegram_id, question_id),
        )
        return

    if row:
        conn.execute(
            """
            UPDATE weak_questions
            SET priority = priority + 2,
                correct_streak = 0,
                times_wrong = times_wrong + 1,
                learned_at = NULL,
                last_seen_at = CURRENT_TIMESTAMP
            WHERE telegram_id = ? AND question_id = ?
            """,
            (telegram_id, question_id),
        )
    else:
        conn.execute(
            """
            INSERT INTO weak_questions (telegram_id, question_id, priority, times_wrong)
            VALUES (?, ?, 2, 1)
            """,
            (telegram_id, question_id),
        )


def complete_session(session_id: int, telegram_id: int) -> None:
    today = date.today()
    yesterday = today - timedelta(days=1)
    with get_db() as conn:
        conn.execute(
            """
            UPDATE quiz_sessions
            SET status = 'completed', completed_at = CURRENT_TIMESTAMP
            WHERE id = ? AND status = 'active'
            """,
            (session_id,),
        )
        user = conn.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)).fetchone()
        if not user:
            return
        last = date.fromisoformat(user["last_quiz_date"]) if user["last_quiz_date"] else None
        if last == today:
            return
        current = user["current_streak"] + 1 if last == yesterday else 1
        longest = max(user["longest_streak"], current)
        conn.execute(
            """
            UPDATE users
            SET current_streak = ?, longest_streak = ?, last_quiz_date = ?
            WHERE telegram_id = ?
            """,
            (current, longest, today.isoformat(), telegram_id),
        )


def cancel_active_session(telegram_id: int) -> None:
    with get_db() as conn:
        conn.execute(
            "UPDATE quiz_sessions SET status = 'cancelled' WHERE telegram_id = ? AND status = 'active'",
            (telegram_id,),
        )


def toggle_bookmark(telegram_id: int, question_id: int) -> bool:
    with get_db() as conn:
        row = conn.execute(
            "SELECT 1 FROM bookmarks WHERE telegram_id = ? AND question_id = ?",
            (telegram_id, question_id),
        ).fetchone()
        if row:
            conn.execute(
                "DELETE FROM bookmarks WHERE telegram_id = ? AND question_id = ?",
                (telegram_id, question_id),
            )
            return False
        conn.execute(
            "INSERT INTO bookmarks (telegram_id, question_id) VALUES (?, ?)",
            (telegram_id, question_id),
        )
        return True


def is_bookmarked(telegram_id: int, question_id: int) -> bool:
    with get_db() as conn:
        row = conn.execute(
            "SELECT 1 FROM bookmarks WHERE telegram_id = ? AND question_id = ?",
            (telegram_id, question_id),
        ).fetchone()
        return bool(row)
