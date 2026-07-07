import json
import random
from collections import Counter
from typing import Any

from config import QUIZ_LENGTH
from database import get_db, row_to_question


LEARNING_PATHS = {
    "transformer_basics": {
        "label": "Transformer Basics",
        "topics": ("transformers", "attention", "pretraining", "context windows"),
    },
    "rag_basics": {
        "label": "RAG Basics",
        "topics": ("RAG", "embeddings", "vector databases"),
    },
    "rag_lesson_1": {
        "label": "RAG Basics - Lesson 1",
        "topics": ("RAG Basics",),
        "modes": ("rag_lesson_1",),
    },
    "rag_lesson_2": {
        "label": "RAG Basics - Lesson 2",
        "topics": ("RAG Basics",),
        "modes": ("rag_lesson_2",),
    },
    "rag_lesson_3": {
        "label": "RAG Basics - Lesson 3",
        "topics": ("RAG Basics",),
        "modes": ("rag_lesson_3",),
    },
    "ai_agents_basics": {
        "label": "AI Agents Basics",
        "topics": ("AI agents", "tool use", "safety"),
        "modes": ("agents",),
    },
    "coding_agents": {
        "label": "Coding Agents",
        "topics": ("coding agents",),
        "modes": ("coding_ai",),
    },
    "model_evaluation": {
        "label": "Model Evaluation",
        "topics": ("model evaluation", "benchmarks", "safety"),
    },
    "local_llms": {
        "label": "Local LLMs",
        "topics": ("local LLMs", "open-source models", "context windows", "transformers", "fine-tuning"),
        "modes": ("llms",),
    },
    "deep_learning": {
        "label": "Deep Learning",
        "topics": ("deep learning",),
        "modes": ("deep_learning_1",),
    },
    "deep_learning_lesson_1": {
        "label": "Deep Learning - Lesson 1",
        "topics": ("deep learning",),
        "modes": ("deep_learning_1",),
    },
    "deep_learning_lesson_2": {
        "label": "Deep Learning - Lesson 2",
        "topics": ("deep learning",),
        "modes": ("deep_learning_2",),
    },
    "deep_learning_lesson_3": {
        "label": "Deep Learning - Lesson 3",
        "topics": ("deep learning",),
        "modes": ("deep_learning_3",),
    },
    "deep_learning_lesson_4": {
        "label": "Deep Learning - Lesson 4",
        "topics": ("deep learning",),
        "modes": ("deep_learning_4",),
    },
    "deep_learning_lesson_5": {
        "label": "Deep Learning - Lesson 5",
        "topics": ("deep learning",),
        "modes": ("deep_learning_5",),
    },
    "deep_learning_lesson_6": {
        "label": "Deep Learning - Lesson 6",
        "topics": ("deep learning",),
        "modes": ("deep_learning_6",),
    },
    "deep_learning_lesson_7": {
        "label": "Deep Learning - Lesson 7",
        "topics": ("deep learning",),
        "modes": ("deep_learning_7",),
    },
    "deep_learning_lesson_8": {
        "label": "Deep Learning - Lesson 8",
        "topics": ("deep learning",),
        "modes": ("deep_learning_8",),
    },
    "deep_learning_lesson_9": {
        "label": "Deep Learning - Lesson 9",
        "topics": ("deep learning",),
        "modes": ("deep_learning_9",),
    },
}


def _filters(settings: dict[str, str]) -> tuple[list[str], list[Any]]:
    clauses: list[str] = []
    params: list[Any] = []
    if settings["difficulty"] != "mixed":
        clauses.append("difficulty = ?")
        params.append(settings["difficulty"])
    if settings["question_mode"] != "mixed":
        clauses.append("mode = ?")
        params.append(settings["question_mode"])
    return clauses, params


def _path_filters(learning_path: str | None) -> tuple[list[str], list[Any]]:
    if not learning_path:
        return [], []
    path = LEARNING_PATHS[learning_path]
    clauses: list[str] = []
    params: list[Any] = []
    if path.get("topics"):
        placeholders = ",".join("?" for _ in path["topics"])
        clauses.append(f"topic IN ({placeholders})")
        params.extend(path["topics"])
    if path.get("modes"):
        placeholders = ",".join("?" for _ in path["modes"])
        clauses.append(f"mode IN ({placeholders})")
        params.extend(path["modes"])
    if path.get("difficulties"):
        placeholders = ",".join("?" for _ in path["difficulties"])
        clauses.append(f"difficulty IN ({placeholders})")
        params.extend(path["difficulties"])
    return clauses, params


def available_question_count(settings: dict[str, str], learning_path: str | None = None) -> int:
    if learning_path:
        clauses, params = _path_filters(learning_path)
    else:
        clauses, params = _filters(settings)
    where = " AND ".join([f"q.{c}" for c in clauses]) if clauses else "1=1"
    with get_db() as conn:
        row = conn.execute(f"SELECT COUNT(*) AS total FROM questions q WHERE {where}", params).fetchone()
        return int(row["total"])


def select_questions(
    telegram_id: int,
    settings: dict[str, str],
    review_only: bool = False,
    learning_path: str | None = None,
    bookmarks_only: bool = False,
) -> list[int]:
    if bookmarks_only:
        with get_db() as conn:
            rows = conn.execute(
                """
                SELECT question_id
                FROM bookmarks
                WHERE telegram_id = ?
                ORDER BY rowid DESC
                """,
                [telegram_id],
            ).fetchall()
            return [row["question_id"] for row in rows]

    if learning_path:
        clauses, params = _path_filters(learning_path)
    else:
        clauses, params = _filters(settings)
    where = " AND ".join([f"q.{c}" for c in clauses]) if clauses else "1=1"
    with get_db() as conn:
        weak_rows = conn.execute(
            f"""
            SELECT q.id
            FROM weak_questions w
            JOIN questions q ON q.id = w.question_id
            WHERE w.telegram_id = ?
              AND w.learned_at IS NULL
              AND {where}
            ORDER BY w.priority DESC, w.last_seen_at ASC
            LIMIT ?
            """,
            [telegram_id, *params, QUIZ_LENGTH],
        ).fetchall()
        weak_ids = [row["id"] for row in weak_rows]
        if review_only:
            return weak_ids[:QUIZ_LENGTH]

        target_weak = min(len(weak_ids), 8)
        selected = weak_ids[:target_weak]
        remaining = QUIZ_LENGTH - len(selected)
        exclude = selected or [-1]
        placeholders = ",".join("?" for _ in exclude)
        new_rows = conn.execute(
            f"""
            SELECT q.id
            FROM questions q
            WHERE {where}
              AND q.id NOT IN ({placeholders})
              AND q.id NOT IN (
                SELECT question_id FROM answers WHERE telegram_id = ?
              )
            ORDER BY RANDOM()
            LIMIT ?
            """,
            [*params, *exclude, telegram_id, remaining],
        ).fetchall()
        selected.extend(row["id"] for row in new_rows)
        remaining = QUIZ_LENGTH - len(selected)
        if remaining > 0:
            exclude = selected or [-1]
            placeholders = ",".join("?" for _ in exclude)
            fill_rows = conn.execute(
                f"""
                SELECT q.id
                FROM questions q
                WHERE {where}
                  AND q.id NOT IN ({placeholders})
                ORDER BY RANDOM()
                LIMIT ?
                """,
                [*params, *exclude, remaining],
            ).fetchall()
            selected.extend(row["id"] for row in fill_rows)
    random.shuffle(selected)
    return selected[:QUIZ_LENGTH]


def get_question_for_session(session: Any) -> dict[str, Any] | None:
    ids = json.loads(session["question_ids_json"])
    if session["current_index"] >= len(ids):
        return None
    question_id = ids[session["current_index"]]
    with get_db() as conn:
        row = conn.execute("SELECT * FROM questions WHERE id = ?", (question_id,)).fetchone()
        q = row_to_question(row) if row else None
        return q


def localize_question(question: dict[str, Any], lang: str = "en") -> dict[str, Any]:
    if not question:
        return question
    q = dict(question)
    # Ensure translations exist in DB for this language if possible
    try:
        from database import translate_question_if_missing
        if lang != "en":
            translate_question_if_missing(q.get("id"), lang)
            # reload localized fields from DB to pick up persisted translations
            from database import get_question
            q = get_question(q.get("id")) or q
    except Exception:
        pass
    # question text
    qtext = q.get("question")
    if isinstance(qtext, dict):
        q["question"] = qtext.get(lang) or qtext.get("en") or next(iter(qtext.values()))
    else:
        q["question"] = qtext

    # explanation
    expl = q.get("explanation")
    if isinstance(expl, dict):
        q["explanation"] = expl.get(lang) or expl.get("en") or next(iter(expl.values()))
    else:
        q["explanation"] = expl

    # options
    opts = q.get("options")
    if isinstance(opts, dict):
        q["options"] = opts.get(lang) or opts.get("en") or next(iter(opts.values()))

    # wrong_explanations
    wrongs = q.get("wrong_explanations")
    if isinstance(wrongs, dict):
        q["wrong_explanations"] = wrongs.get(lang) or wrongs.get("en") or next(iter(wrongs.values()))

    return q


def session_summary(session_id: int) -> dict[str, Any]:
    with get_db() as conn:
        session = conn.execute("SELECT * FROM quiz_sessions WHERE id = ?", (session_id,)).fetchone()
        rows = conn.execute(
            """
            SELECT a.is_correct, a.selected_index, q.*
            FROM answers a
            JOIN questions q ON q.id = a.question_id
            WHERE a.session_id = ?
            ORDER BY a.id
            """,
            (session_id,),
        ).fetchall()
        missed = [row_to_question(r) | {"selected_index": r["selected_index"]} for r in rows if not r["is_correct"]]
        weak_topics = Counter(q["topic"] for q in missed)
        score = session["score"] if session else 0
        total = len(rows)
        return {
            "score": score,
            "total": total,
            "percentage": round((score / total) * 100) if total else 0,
            "weak_topics": weak_topics,
            "missed": missed,
        }


def user_stats(telegram_id: int) -> dict[str, Any]:
    with get_db() as conn:
        user = conn.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)).fetchone()
        totals = conn.execute(
            """
            SELECT COUNT(*) AS answered, COALESCE(SUM(is_correct), 0) AS correct
            FROM answers WHERE telegram_id = ?
            """,
            (telegram_id,),
        ).fetchone()
        weak = conn.execute(
            """
            SELECT COUNT(*) AS active
            FROM weak_questions
            WHERE telegram_id = ? AND learned_at IS NULL
            """,
            (telegram_id,),
        ).fetchone()
        mastery_rows = conn.execute(
            """
            SELECT q.topic,
                   COUNT(*) AS answered,
                   SUM(a.is_correct) AS correct
            FROM answers a
            JOIN questions q ON q.id = a.question_id
            WHERE a.telegram_id = ?
            GROUP BY q.topic
            ORDER BY q.topic
            """,
            (telegram_id,),
        ).fetchall()
        mode_rows = conn.execute(
            """
            SELECT 
                q.mode,
                COUNT(DISTINCT q.id) as total_count,
                COUNT(DISTINCT a.question_id) as answered_count
            FROM questions q
            LEFT JOIN answers a ON a.question_id = q.id AND a.telegram_id = ?
            GROUP BY q.mode
            """,
            (telegram_id,),
        ).fetchall()
        return {
            "current_streak": user["current_streak"] if user else 0,
            "longest_streak": user["longest_streak"] if user else 0,
            "answered": totals["answered"],
            "correct": totals["correct"],
            "active_weak": weak["active"],
            "mastery": [dict(row) for row in mastery_rows],
            "modes": [dict(row) for row in mode_rows],
        }


def weak_study_list(telegram_id: int) -> list[dict[str, Any]]:
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT q.id, q.topic, q.difficulty, q.question, w.priority, w.times_wrong
            FROM weak_questions w
            JOIN questions q ON q.id = w.question_id
            WHERE w.telegram_id = ? AND w.learned_at IS NULL
            ORDER BY w.priority DESC, w.times_wrong DESC, q.topic
            LIMIT 50
            """,
            (telegram_id,),
        ).fetchall()
        return [dict(row) for row in rows]


def leaderboard(limit: int = 10) -> list[dict[str, Any]]:
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT u.first_name, u.username, COUNT(a.id) AS answered, SUM(a.is_correct) AS correct,
                   u.longest_streak
            FROM users u
            LEFT JOIN answers a ON a.telegram_id = u.telegram_id
            GROUP BY u.telegram_id
            HAVING answered > 0
            ORDER BY correct DESC, longest_streak DESC, answered DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [dict(row) for row in rows]
