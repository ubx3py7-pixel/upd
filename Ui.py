import os
import sys
import time
import shutil
import sqlite3
import subprocess
import signal
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters
)

# ================= 🔧 CONFIG =================
BOSS_BOT_TOKEN = "8463525599:AAHqiJAEWgTXls7y9pZuODiVTCXK-eBAN2U"
OWNER_ID = 6940098775  # 👑 Admin Telegram ID (numbers only)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
USERS_DIR = os.path.join(BASE_DIR, "users")
DB_FILE = os.path.join(BASE_DIR, "users.db")

BOT_TEMPLATE = os.path.join(BASE_DIR, "spbot5.py")
MSG_TEMPLATE = os.path.join(BASE_DIR, "msg.py")

PYTHON_BIN = sys.executable   # ✅ USE SAME PYTHON AS BOSS BOT
LOG_NAME = "bot.log"
# ============================================

os.makedirs(USERS_DIR, exist_ok=True)

# ================= 🗄️ DATABASE =================
conn = sqlite3.connect(DB_FILE, check_same_thread=False)
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS bots (
    user_id INTEGER PRIMARY KEY,
    pid INTEGER,
    start_time INTEGER
)
""")
conn.commit()

# ================= 🛠️ HELPERS =================
def get_bot(uid):
    cur.execute("SELECT pid, start_time FROM bots WHERE user_id=?", (uid,))
    return cur.fetchone()

def kill_pid(pid):
    try:
        os.kill(pid, signal.SIGTERM)
        time.sleep(1)
        os.kill(pid, signal.SIGKILL)
    except:
        pass

def start_user_bot(uid, token, chat_id):
    # 🔥 Kill old instance if exists
    old = get_bot(uid)
    if old:
        kill_pid(old[0])

    user_dir = os.path.join(USERS_DIR, f"user_{uid}")
    os.makedirs(user_dir, exist_ok=True)

    # 📂 Copy bot files
    shutil.copy(BOT_TEMPLATE, user_dir)
    shutil.copy(MSG_TEMPLATE, user_dir)

    # ✏️ Inject token & chat id
    spbot_path = os.path.join(user_dir, "spbot5.py")
    with open(spbot_path, "r", encoding="utf-8") as f:
        code = f.read()

    code = code.replace("__BOT_TOKEN__", token)
    code = code.replace("__CHAT_ID__", str(chat_id))

    with open(spbot_path, "w", encoding="utf-8") as f:
        f.write(code)

    # 📝 Logs
    log_path = os.path.join(user_dir, LOG_NAME)
    log_f = open(log_path, "a", buffering=1)

    # 🚀 Start child bot
    proc = subprocess.Popen(
        [PYTHON_BIN, "spbot5.py"],
        cwd=user_dir,
        stdout=log_f,
        stderr=log_f
    )

    cur.execute(
        "REPLACE INTO bots VALUES (?,?,?)",
        (uid, proc.pid, int(time.time()))
    )
    conn.commit()

# ================= 🤖 COMMANDS =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 *Bot Hosting Service*\n\n"
        "✨ User Commands:\n"
        "➕ /addbot – Host your bot\n"
        "🛑 /stop – Stop your bot\n"
        "🔄 /restart – Restart your bot\n"
        "📊 /status – Bot status\n"
        "📜 /logs – View bot logs\n"
        "⏱ /uptime – Bot uptime\n\n"
        "👑 Admin:\n"
        "👥 /users – List active users",
        parse_mode="Markdown"
    )

async def addbot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    context.user_data["step"] = "token"
    await update.message.reply_text("🔑 *Send BOT TOKEN:*", parse_mode="Markdown")

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    bot = get_bot(uid)

    if not bot:
        await update.message.reply_text("ℹ️ No running bot found")
        return

    kill_pid(bot[0])
    cur.execute("DELETE FROM bots WHERE user_id=?", (uid,))
    conn.commit()

    await update.message.reply_text("🛑 *Bot stopped successfully*", parse_mode="Markdown")

async def restart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    bot = get_bot(uid)

    if not bot:
        await update.message.reply_text("❌ No bot to restart")
        return

    kill_pid(bot[0])

    user_dir = os.path.join(USERS_DIR, f"user_{uid}")
    log_path = os.path.join(user_dir, LOG_NAME)
    log_f = open(log_path, "a", buffering=1)

    proc = subprocess.Popen(
        [PYTHON_BIN, "spbot5.py"],
        cwd=user_dir,
        stdout=log_f,
        stderr=log_f
    )

    cur.execute(
        "UPDATE bots SET pid=?, start_time=? WHERE user_id=?",
        (proc.pid, int(time.time()), uid)
    )
    conn.commit()

    await update.message.reply_text("🔄 *Bot restarted*", parse_mode="Markdown")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    bot = get_bot(uid)

    if not bot:
        await update.message.reply_text("❌ Bot is not running")
        return

    await update.message.reply_text("✅ Bot is *running*", parse_mode="Markdown")

async def uptime(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    bot = get_bot(uid)

    if not bot:
        await update.message.reply_text("❌ No bot running")
        return

    seconds = int(time.time() - bot[1])
    await update.message.reply_text(f"⏱ *Uptime:* `{seconds}` seconds", parse_mode="Markdown")

async def logs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    log_path = os.path.join(USERS_DIR, f"user_{uid}", LOG_NAME)

    if not os.path.exists(log_path):
        await update.message.reply_text("📭 No logs found")
        return

    with open(log_path, "r", encoding="utf-8") as f:
        data = f.read()[-3500:]

    await update.message.reply_text(
        f"```\n{data}\n```",
        parse_mode="Markdown"
    )

# ================= 👑 ADMIN =================
async def users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return

    cur.execute("SELECT user_id, pid, start_time FROM bots")
    rows = cur.fetchall()

    if not rows:
        await update.message.reply_text("👥 No active user bots")
        return

    msg = "👑 *Active User Bots*\n\n"
    for uid, pid, st in rows:
        up = int(time.time() - st)
        msg += f"• 👤 `{uid}` | 🆔 `{pid}` | ⏱ `{up}s`\n"

    await update.message.reply_text(msg, parse_mode="Markdown")

# ================= 💬 TEXT FLOW =================
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    text = update.message.text.strip()

    if context.user_data.get("step") == "token":
        context.user_data["token"] = text
        context.user_data["step"] = "chat"
        await update.message.reply_text("💬 *Send CHAT ID:*", parse_mode="Markdown")
        return

    if context.user_data.get("step") == "chat":
        token = context.user_data["token"]
        chat_id = int(text)

        start_user_bot(uid, token, chat_id)
        context.user_data.clear()

        await update.message.reply_text("✅ *Your bot is now LIVE!* 🚀", parse_mode="Markdown")

# ================= 🚀 RUN =================
print("🔥 Boss bot is running...")

app = ApplicationBuilder().token(BOSS_BOT_TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("addbot", addbot))
app.add_handler(CommandHandler("stop", stop))
app.add_handler(CommandHandler("restart", restart))
app.add_handler(CommandHandler("status", status))
app.add_handler(CommandHandler("uptime", uptime))
app.add_handler(CommandHandler("logs", logs))
app.add_handler(CommandHandler("users", users))

app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

app.run_polling()
