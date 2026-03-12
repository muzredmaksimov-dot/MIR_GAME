import csv
import os
import asyncio
import requests
import base64

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

# -----------------------
# Настройки
# -----------------------

TOKEN = os.getenv("TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_REPO = os.getenv("GITHUB_REPO")

DATA_DIR = "data"
FILE = os.path.join(DATA_DIR, "data.csv")
TOTAL = 20

users = {}
steps = {}

# -----------------------
# Убедимся, что папка data существует
# -----------------------
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)
    print(f"Создана папка {DATA_DIR}")

# -----------------------
# GitHub
# -----------------------

def headers():
    return {
        "Authorization": f"token {GITHUB_TOKEN}",
        "User-Agent": "radio-mir-bot"
    }

def download_csv():
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{FILE}"
    r = requests.get(url, headers=headers())
    if r.status_code == 200:
        content = base64.b64decode(r.json()["content"]).decode()
        with open(FILE, "w", encoding="utf-8") as f:
            f.write(content)
        print("CSV downloaded from GitHub")
    else:
        if not os.path.exists(FILE):
            print("CSV не найден на GitHub. Создаём новый файл.")
            header = ["id", "phone", "name"] + [f"city{i}" for i in range(1, TOTAL+1)]
            with open(FILE, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(header)

def upload_csv():
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{FILE}"
    r = requests.get(url, headers=headers())
    sha = None
    if r.status_code == 200:
        sha = r.json()["sha"]
    with open(FILE, "r", encoding="utf-8") as f:
        content = f.read()
    encoded = base64.b64encode(content.encode()).decode()
    data = {"message": "auto backup csv", "content": encoded, "sha": sha}
    requests.put(url, json=data, headers=headers())
    print("CSV uploaded to GitHub")

async def backup_loop():
    while True:
        try:
            upload_csv()
        except Exception as e:
            print("Backup error:", e)
        await asyncio.sleep(300)  # каждые 5 минут

# -----------------------
# CSV
# -----------------------

def load_data():
    data = {}
    if not os.path.exists(FILE):
        return data
    with open(FILE, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader)
        for row in reader:
            data[row[0]] = row
    return data

def save_data(data):
    header = ["id", "phone", "name"] + [f"city{i}" for i in range(1, TOTAL+1)]
    with open(FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        for row in data.values():
            writer.writerow(row)

# -----------------------
# BOT
# -----------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if user_id in users:
        await update.message.reply_text("Вы уже участвуете. Отправляйте следующий город.")
        return
    steps[user_id] = "name"
    await update.message.reply_text("Добро пожаловать в игру Радио МИР!\n\nНапишите ваше имя:")

async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    text = update.message.text.strip()
    if user_id not in users and user_id not in steps:
        await update.message.reply_text("Нажмите /start")
        return

    # ввод имени
    if steps.get(user_id) == "name":
        steps[user_id] = ("phone", text)
        await update.message.reply_text("Отправьте номер телефона")
        return

    # ввод телефона
    if isinstance(steps.get(user_id), tuple):
        name = steps[user_id][1]
        phone = text
        row = [user_id, phone, name] + [""]*TOTAL
        users[user_id] = row
        save_data(users)
        steps[user_id] = None
        await update.message.reply_text("Отлично! Теперь отправляйте города из эфира Радио МИР.")
        return

    # добавление города
    if user_id in users:
        row = users[user_id]
        number = None
        for i in range(TOTAL):
            if row[3+i] == "":
                row[3+i] = text
                number = i + 1
                break
        if number is None:
            await update.message.reply_text("Вы уже отправили все 20 городов.")
            return
        save_data(users)
        if number < TOTAL:
            await update.message.reply_text(f"Это город номер {number}.\nОсталось {TOTAL-number}.\n\nСлушайте Радио МИР завтра!")
        else:
            await update.message.reply_text("Отлично! Это был последний город!\n\nЗавтра мы выберем победителя.")
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"Новый город\n\nИмя: {row[2]}\nТелефон: {row[1]}\nГород №{number}: {text}"
        )

# -----------------------
# ADMIN
# -----------------------

async def send_csv(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    await update.message.reply_document(document=open(FILE, "rb"), filename="radio_mir_data.csv")

async def force_backup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    upload_csv()
    await update.message.reply_text("CSV выгружен в GitHub.")

async def stats_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    await update.message.reply_text(f"Участников: {len(users)}")

# -----------------------
# MAIN
# -----------------------

async def main():
    global users
    download_csv()
    users = load_data()
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("csv", send_csv))
    app.add_handler(CommandHandler("backup", force_backup))
    app.add_handler(CommandHandler("users", stats_users))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))

    asyncio.create_task(backup_loop())

    print("Bot started")
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())import csv
import os
import asyncio
import requests
import base64

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

# -----------------------
# Настройки
# -----------------------

TOKEN = os.getenv("TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_REPO = os.getenv("GITHUB_REPO")

DATA_DIR = "data"
FILE = os.path.join(DATA_DIR, "data.csv")
TOTAL = 20

users = {}
steps = {}

# -----------------------
# Убедимся, что папка data существует
# -----------------------
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)
    print(f"Создана папка {DATA_DIR}")

# -----------------------
# GitHub
# -----------------------

def headers():
    return {
        "Authorization": f"token {GITHUB_TOKEN}",
        "User-Agent": "radio-mir-bot"
    }

def download_csv():
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{FILE}"
    r = requests.get(url, headers=headers())
    if r.status_code == 200:
        content = base64.b64decode(r.json()["content"]).decode()
        with open(FILE, "w", encoding="utf-8") as f:
            f.write(content)
        print("CSV downloaded from GitHub")
    else:
        if not os.path.exists(FILE):
            print("CSV не найден на GitHub. Создаём новый файл.")
            header = ["id", "phone", "name"] + [f"city{i}" for i in range(1, TOTAL+1)]
            with open(FILE, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(header)

def upload_csv():
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{FILE}"
    r = requests.get(url, headers=headers())
    sha = None
    if r.status_code == 200:
        sha = r.json()["sha"]
    with open(FILE, "r", encoding="utf-8") as f:
        content = f.read()
    encoded = base64.b64encode(content.encode()).decode()
    data = {"message": "auto backup csv", "content": encoded, "sha": sha}
    requests.put(url, json=data, headers=headers())
    print("CSV uploaded to GitHub")

async def backup_loop():
    while True:
        try:
            upload_csv()
        except Exception as e:
            print("Backup error:", e)
        await asyncio.sleep(300)  # каждые 5 минут

# -----------------------
# CSV
# -----------------------

def load_data():
    data = {}
    if not os.path.exists(FILE):
        return data
    with open(FILE, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader)
        for row in reader:
            data[row[0]] = row
    return data

def save_data(data):
    header = ["id", "phone", "name"] + [f"city{i}" for i in range(1, TOTAL+1)]
    with open(FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        for row in data.values():
            writer.writerow(row)

# -----------------------
# BOT
# -----------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if user_id in users:
        await update.message.reply_text("Вы уже участвуете. Отправляйте следующий город.")
        return
    steps[user_id] = "name"
    await update.message.reply_text("Добро пожаловать в игру Радио МИР!\n\nНапишите ваше имя:")

async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    text = update.message.text.strip()
    if user_id not in users and user_id not in steps:
        await update.message.reply_text("Нажмите /start")
        return

    # ввод имени
    if steps.get(user_id) == "name":
        steps[user_id] = ("phone", text)
        await update.message.reply_text("Отправьте номер телефона")
        return

    # ввод телефона
    if isinstance(steps.get(user_id), tuple):
        name = steps[user_id][1]
        phone = text
        row = [user_id, phone, name] + [""]*TOTAL
        users[user_id] = row
        save_data(users)
        steps[user_id] = None
        await update.message.reply_text("Отлично! Теперь отправляйте города из эфира Радио МИР.")
        return

    # добавление города
    if user_id in users:
        row = users[user_id]
        number = None
        for i in range(TOTAL):
            if row[3+i] == "":
                row[3+i] = text
                number = i + 1
                break
        if number is None:
            await update.message.reply_text("Вы уже отправили все 20 городов.")
            return
        save_data(users)
        if number < TOTAL:
            await update.message.reply_text(f"Это город номер {number}.\nОсталось {TOTAL-number}.\n\nСлушайте Радио МИР завтра!")
        else:
            await update.message.reply_text("Отлично! Это был последний город!\n\nЗавтра мы выберем победителя.")
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"Новый город\n\nИмя: {row[2]}\nТелефон: {row[1]}\nГород №{number}: {text}"
        )

# -----------------------
# ADMIN
# -----------------------

async def send_csv(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    await update.message.reply_document(document=open(FILE, "rb"), filename="radio_mir_data.csv")

async def force_backup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    upload_csv()
    await update.message.reply_text("CSV выгружен в GitHub.")

async def stats_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    await update.message.reply_text(f"Участников: {len(users)}")

# -----------------------
# MAIN
# -----------------------

async def main():
    global users
    download_csv()
    users = load_data()
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("csv", send_csv))
    app.add_handler(CommandHandler("backup", force_backup))
    app.add_handler(CommandHandler("users", stats_users))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))

    asyncio.create_task(backup_loop())

    print("Bot started")
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
