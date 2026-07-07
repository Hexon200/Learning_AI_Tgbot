---
title: Tg Bot AI
emoji: 🧠
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
pinned: false
---

# Telegram AI and LLM Quiz Bot

A local Telegram bot that teaches AI and LLM concepts through button-driven quiz sessions.

## Features

- `/start` menu with quiz, review, stats, settings, daily challenge, leaderboard, and learning paths.
- 20-question quiz sessions with no duplicate questions in a session.
- Multiple-choice answers through Telegram inline buttons.
- Immediate feedback with correct answer and short explanation.
- Low-pool warnings when a difficulty/mode combination has fewer than 20 questions.
- Weak-question tracking with spaced repetition:
  - wrong answer increases review priority;
  - correct answer on a weak question reduces priority;
  - two correct answers marks the weak question learned.
- Review mode quizzes only active weak questions.
- SQLite persistence for users, questions, sessions, answers, weak questions, settings, and bookmarks.
- Difficulty settings: Mixed, Beginner, Intermediate, Advanced.
- Question modes: Mixed, Core AI, LLMs, Agents, Coding AI.
- Learning paths: Transformer Basics, RAG Basics, AI Agents Basics, Coding Agents, Model Evaluation, and Local LLMs.
- Seeded with 260 practical AI questions:
  - Core AI: 60
  - LLMs: 80
  - Agents: 60
  - Coding AI: 60
  - Beginner: 80
  - Intermediate: 84
  - Advanced: 96
- Streak tracking, topic mastery stats, weak-topic export, bookmarks, and optional leaderboard.

## Setup

1. Create a bot with Telegram's BotFather and copy the bot token.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Set the token environment variable.

PowerShell:

```powershell
$env:TELEGRAM_BOT_TOKEN="123456789:your_token_here"
```

macOS/Linux:

```bash
export TELEGRAM_BOT_TOKEN="123456789:your_token_here"
```

Optional: set a custom SQLite path:

```bash
export DATABASE_PATH="quiz_bot.sqlite3"
```

4. Run the bot:

```bash
python bot.py
```

The database is created automatically and seeded with the question bank on startup.

## Commands

- `/start` - open the main menu
- `/stats` - view score, streak, weak questions, and topic mastery
- `/settings` - set difficulty and question mode
- `/daily` - start a daily 20-question challenge
- `/cancel` - cancel the active quiz
- `/help` - show help

## Adding Questions

Edit `questions.py`.

Each question needs:

- `slug`: stable unique ID
- `topic`
- `difficulty`: `beginner`, `intermediate`, or `advanced`
- `mode`: `core_ai`, `llms`, `agents`, or `coding_ai`
- `question`
- `options`: 4-6 choices
- `answer_index`
- `explanation`
- `wrong_explanations`: one explanation per option

For larger topic expansions, `questions.py` also includes compact practical drill lists that generate complete question records with option-level explanations.

Restart the bot after editing. Questions are upserted by `slug`, so text edits are applied without deleting user history.
