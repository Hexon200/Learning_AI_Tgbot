# bot.py
import logging
import os
import sys
import random
import html
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.request import HTTPXRequest
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters

# Import our countries dataset and database functions
from countries import COUNTRIES
import database

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Fetch Telegram Bot Token from environment variables
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send welcome message and introduce the game."""
    user = update.effective_user
    database.ensure_user(user.id, user.username or user.first_name)
    
    welcome_text = (
        f"👋 Hello {html.escape(user.first_name)}!\n\n"
        "Welcome to the <b>Country Flag Guessing Bot</b>! 🌍🚩\n\n"
        "<b>Rules:</b>\n"
        "• I will show you a country's flag.\n"
        "• You choose the correct country from 4 options.\n"
        "• Correct answers increase your score and streak! 🔥\n"
        "• A wrong answer resets your streak.\n"
        "• Flags will not repeat during a quiz session.\n\n"
        "<b>Commands:</b>\n"
        "/quiz - Choose a continent and start guessing!\n"
        "/stats - Check your score and streak\n"
        "/leaderboard - See top players"
    )
    
    # Start button
    keyboard = [[InlineKeyboardButton("🎮 Start Guessing!", callback_data="start_quiz")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)


async def show_continent_menu(update_or_query, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show the menu to select a continent."""
    keyboard = [
        [
            InlineKeyboardButton("🌍 Africa", callback_data="continent:Africa"),
            InlineKeyboardButton("🌏 Asia", callback_data="continent:Asia")
        ],
        [
            InlineKeyboardButton("🇪🇺 Europe", callback_data="continent:Europe"),
            InlineKeyboardButton("🌎 North America", callback_data="continent:North America")
        ],
        [
            InlineKeyboardButton("🌎 South America", callback_data="continent:South America"),
            InlineKeyboardButton("🌏 Oceania", callback_data="continent:Oceania")
        ],
        [
            InlineKeyboardButton("🌐 All Continents", callback_data="continent:All")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    text = "Select a continent to start the flag guessing quiz:"
    
    # Check if we should send a new message or edit the existing one
    if isinstance(update_or_query, Update) and update_or_query.message:
        await update_or_query.message.reply_text(text, reply_markup=reply_markup)
    else:
        # Edit text if called from a button callback
        await update_or_query.edit_message_text(text, reply_markup=reply_markup)


async def select_continent(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Initialize the session's list of remaining flags based on selected continent."""
    query = update.callback_query
    await query.answer()
    
    selected = query.data.split(":")[1]
    
    # Filter countries
    if selected == "All":
        filtered = COUNTRIES
        display_name = "All Continents"
    else:
        filtered = [c for c in COUNTRIES if c["continent"] == selected]
        display_name = selected
        
    # Store the remaining country names in session
    context.user_data["remaining_countries"] = [c["name"] for c in filtered]
    context.user_data["selected_continent"] = display_name
    
    # Notify the user and start the quiz
    await query.delete_message()
    await query.message.reply_text(
        f"🏁 Starting quiz for <b>{display_name}</b> ({len(filtered)} flags)!",
        parse_mode=ParseMode.HTML
    )
    
    # Send the first flag!
    await send_new_flag(query, context)


async def send_new_flag(update_or_query, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Pick a random country from the remaining list and send the flag photo."""
    remaining = context.user_data.get("remaining_countries")
    continent = context.user_data.get("selected_continent", "All")
    
    # If the list is empty or doesn't exist, they have finished all flags!
    if not remaining:
        msg = f"🏆 <b>Congratulations!</b> You have successfully guessed all flags in <b>{html.escape(continent)}</b>!"
        await update_or_query.message.reply_text(msg, parse_mode=ParseMode.HTML)
        await show_continent_menu(update_or_query, context)
        return
        
    # 1. Pick a random country from the remaining list
    correct_name = random.choice(remaining)
    
    # Get the country dictionary from our COUNTRIES database
    correct_country = next(c for c in COUNTRIES if c["name"] == correct_name)
    
    # Remove it so it doesn't repeat
    remaining.remove(correct_name)
    context.user_data["remaining_countries"] = remaining
    
    # 2. Pick 3 wrong options from the full list
    wrong_countries = random.sample([c for c in COUNTRIES if c["name"] != correct_name], 3)
    
    # 3. Combine and shuffle options
    options = [correct_country] + wrong_countries
    random.shuffle(options)
    
    # Store session answers
    context.user_data["correct_name"] = correct_name
    context.user_data["options"] = [c["name"] for c in options]
    context.user_data["is_processing"] = False
    
    # Create the inline keyboard buttons (2x2 grid)
    keyboard = [
        [
            InlineKeyboardButton(options[0]["name"], callback_data="guess:0"),
            InlineKeyboardButton(options[1]["name"], callback_data="guess:1")
        ],
        [
            InlineKeyboardButton(options[2]["name"], callback_data="guess:2"),
            InlineKeyboardButton(options[3]["name"], callback_data="guess:3")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Send the flag image
    caption = f"What country does this flag belong to?\n(Remaining: {len(remaining) + 1} flags)"
    
    await update_or_query.message.reply_photo(
        photo=correct_country["flag_url"],
        caption=caption,
        reply_markup=reply_markup
    )


async def quiz_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /quiz command."""
    user = update.effective_user
    database.ensure_user(user.id, user.username or user.first_name)
    await show_continent_menu(update, context)


async def handle_guess(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Check the user's guess, update database, and trigger next flag."""
    query = update.callback_query
    await query.answer()
    
    # Prevent double-click race conditions
    if context.user_data.get("is_processing"):
        return
    context.user_data["is_processing"] = True
    
    correct_name = context.user_data.get("correct_name")
    options = context.user_data.get("options")
    
    if not correct_name or not options:
        await query.message.reply_text("Session expired. Start a new game with /quiz!")
        context.user_data["is_processing"] = False
        return
        
    guessed_index = int(query.data.split(":")[1])
    guessed_name = options[guessed_index]
    is_correct = (guessed_name == correct_name)
    
    try:
        user_id = query.from_user.id
        new_stats = database.update_score(user_id, is_correct)
    except Exception as e:
        logger.error(f"Database error in handle_guess: {e}")
        await query.message.reply_text("⚠️ There was an issue saving your score. Please try again.")
        context.user_data["is_processing"] = False
        return
    
    safe_correct = html.escape(correct_name)
    if is_correct:
        result_text = f"✅ <b>Correct!</b> It is {safe_correct}.\n🔥 Current Streak: <b>{new_stats['streak']}</b>"
    else:
        result_text = f"❌ <b>Incorrect.</b> The correct country was <b>{safe_correct}</b>.\nStreak reset to 0."
        
    await query.edit_message_caption(caption=result_text, reply_markup=None, parse_mode=ParseMode.HTML)
    
    # Send next flag automatically
    await send_new_flag(query, context)


async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show the user's score and streak details."""
    user = update.effective_user
    database.ensure_user(user.id, user.username or user.first_name)
    
    try:
        stats = database.get_user_stats(user.id)
        stats_text = (
            f"📊 <b>Your Stats ({html.escape(user.first_name)}):</b>\n\n"
            f"🏆 Total Score: <b>{stats['score']}</b> points\n"
            f"🔥 Current Streak: <b>{stats['streak']}</b>\n"
            f"⚡ Longest Streak: <b>{stats['max_streak']}</b>"
        )
        await update.message.reply_text(stats_text, parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.error(f"Database error in stats: {e}")
        await update.message.reply_text("⚠️ Failed to retrieve stats. Please try again.")


async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Display the top players."""
    try:
        rows = database.get_leaderboard()
        if not rows:
            await update.message.reply_text("No scores recorded yet. Be the first with /quiz!")
            return
            
        text = "🏆 <b>Leaderboard:</b>\n\n"
        for idx, row in enumerate(rows, 1):
            username = html.escape(row['username'] or "Player")
            text += f"{idx}. <b>{username}</b> — {row['score']} pts (Max Streak: {row['max_streak']})\n"
            
        await update.message.reply_text(text, parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.error(f"Database error in leaderboard: {e}")
        await update.message.reply_text("⚠️ Failed to load leaderboard. Please try again.")


async def start_quiz_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle start_quiz button click from welcome menu."""
    query = update.callback_query
    await query.answer()
    await show_continent_menu(query, context)


async def fallback_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle non-command text inputs by guiding users to commands."""
    await update.message.reply_text("Please use buttons or commands like /quiz, /stats, or /leaderboard to play!")


def main() -> None:
    if not TELEGRAM_BOT_TOKEN:
        print("Error: TELEGRAM_BOT_TOKEN environment variable not set.", file=sys.stderr)
        sys.exit(1)
        
    # Initialize the database tables
    database.init_db()
    
    # Configure longer connection timeouts for serverless/cloud environments
    request = HTTPXRequest(connect_timeout=30.0, read_timeout=30.0, write_timeout=30.0)
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).request(request).build()
    
    # Register command handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("quiz", quiz_command))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("leaderboard", leaderboard))
    
    # Register callback query handlers (for button clicks)
    app.add_handler(CallbackQueryHandler(start_quiz_callback, pattern="^start_quiz$"))
    app.add_handler(CallbackQueryHandler(select_continent, pattern="^continent:"))
    app.add_handler(CallbackQueryHandler(handle_guess, pattern="^guess:"))
    
    # Register fallback message handler
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, fallback_message))
    
    logger.info("Flag guessing bot started!")
    app.run_polling(allowed_updates=Update.ALL_TYPES, bootstrap_retries=5)


if __name__ == "__main__":
    main()