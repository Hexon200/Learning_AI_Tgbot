import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "flasgs_bot.sqlite3"

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                     telegram_id INTEGER PRIMARY KEY,
                     username TEXT,
                     score INTEGER DEFAULT 0,
                     streak INTEGER DEFAULT 0,
                     max_streak INTEGER DEFAULT 0
            )
        """)
        conn.commit()

def ensure_user(telegram_id: int, username: str):
    with get_db_connection() as conn:
        user = conn.execute("SELECT * FROM USERS WHERE telegram_id = ?", (telegram_id,)).fetchone()
        if not user:
            conn.execute("INSERT INTO users (telegram_id, username) VALUES (?, ?)", (telegram_id, username))
            conn.commit()
         
def get_user_stats(telegram_id: int):
    with get_db_connection() as conn:
        return conn.execute(
"SELECT score, streak, max_streak FROM users WHERE telegram_id = ?", (telegram_id,)
        ).fetchone()
    
def update_score(telegram_id: int, is_correct: bool):
    stats = get_user_stats(telegram_id)
    if not stats:
        return
    
    score = stats["score"]
    streak = stats["streak"]
    max_streak = stats["max_streak"]

    if is_correct:
        score += 1
        streak += 1
        if streak > max_streak:
            max_streak = streak
    else:
        streak = 0

    with get_db_connection() as conn:
        conn.execute(
            "UPDATE users SET score = ?, streak = ?, max_streak = ? WHERE telegram_id = ?",
            (score, streak, max_streak, telegram_id)
        )
        conn.commit()
    
    return {"score": score, "streak": streak, "max_streak": max_streak}
    
def get_leaderboard(limit: int = 10):
    with get_db_connection() as conn:
        return conn.execute(
            "SELECT username, score, streak, max_streak FROM users ORDER BY score DESC LIMIT ?",
            (limit,)
        ).fetchall()