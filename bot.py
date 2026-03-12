import csv
import os
import threading
import time
import requests
import base64

from telegram import Update
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext

# -----------------------
# Настройки
# -----------------------
TOKEN = os.getenv("TOKEN")  # токен бота
ADMIN_ID = int(os.getenv("ADMIN_ID"))  # Telegram ID админа
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_REPO = os.getenv("GITHUB_REPO")  # username/repo

DATA_DIR = "data"
FILE = os.path.join(DATA_DIR, "data.csv")
TOTAL = 20  # количество городов

users = {}
steps = {}

# -----------------------
# Создаем папку data при первом запуске
# -----------------------
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)
    print(f"Создана папка {DATA_DIR}")

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
# GitHub
# -----------------------
def headers():
    return {"Authorization": f"token {GITHUB_TOKEN}", "User-Agent":"radio-mir-bot"}

def upload_csv():
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{FILE}"
    r = requests.get(url, headers=headers())
    sha = r.json()["sha"] if r.status_code==200 else None
    with open(FILE, "r", encoding="utf-8") as f:
        content = f.read()
    encoded = base64.b64encode(content.encode()).decode()
    data = {"message":"auto backup csv","content":encoded,"sha":sha}
    try:
        requests.put(url, json=data, headers=headers())
    except Exception as e:
        print("GitHub upload error:", e)

def backup_loop():
    while True:
        try:
            upload_csv()
        except Exception as e:
            print("Backup error:", e)
        time.sleep(300)  # каждые 5 минут

# -----------------------
# Handlers
# -----------------------
def start(update: Update, context: CallbackContext):
    user_id = str(update.effective_user.id)
    if user_id in users:
        update.message.reply_text("Вы уже участвуете. Отправляйте следующий город.")
        return
    steps[user_id] = "name"
    update.message.reply_text("Добро пожаловать в игру Радио МИР!\n\nНапишите ваше имя:")

def handle_message(update: Update, context: CallbackContext):
    user_id = str(update.effective_user.id)
    text = update.message.text.strip()
    print(f"[LOG] Received message: {text} from {user_id}")  # лог для теста

    if user_id not in users and user_id not in steps:
        update.message.reply_text("Нажмите /start")
        return

    # ввод имени
    if steps.get(user_id) == "name":
        steps[user_id] = ("phone", text)
        update.message.reply_text("Отправьте номер телефона")
        return

    # ввод телефона
    if isinstance(steps.get(user_id), tuple):
        name = steps[user_id][1]
        phone = text
        row = [user_id, phone, name] + [""]*TOTAL
        users[user_id] = row
        save_data(users)
        steps[user_id] = None
        update.message.reply_text("Отлично! Теперь отправляйте города из эфира Радио МИР.")
        return

    # добавление города
    row = users[user_id]
    number = None
    for i in range(TOTAL):
        if row[3+i] == "":
            row[3+i] = text
            number = i + 1
            break
    if number is None:
        update.message.reply_text("Вы уже отправили все 20 городов.")
        return
    save_data(users)
    if number < TOTAL:
        update.message.reply_text(f"Это город номер {number}.\nОсталось {TOTAL-number}.\n\nСлушайте Радио МИР завтра!")
    else:
        update.message.reply_text("Отлично! Это был последний город!\n\nЗавтра мы выберем победителя.")

    # уведомление админу
    try:
        context.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"Новый город\n\nИмя: {row[2]}\nТелефон: {row[1]}\nГород №{number}: {text}"
        )
    except Exception as e:
        print("Admin notification error:", e)

# -----------------------
# Admin commands
# -----------------------
def send_csv(update: Update, context: CallbackContext):
    if update.effective_user.id != ADMIN_ID:
        return
    update.message.reply_document(document=open(FILE,"rb"), filename="radio_mir_data.csv")

def force_backup(update: Update, context: CallbackContext):
    if update.effective_user.id != ADMIN_ID:
        return
    upload_csv()
    update.message.reply_text("CSV выгружен в GitHub.")

def stats_users(update: Update, context: CallbackContext):
    if update.effective_user.id != ADMIN_ID:
        return
    update.message.reply_text(f"Участников: {len(users)}")

# -----------------------
# Main
# -----------------------
if __name__=="__main__":
    users = load_data()
    updater = Updater(TOKEN)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("csv", send_csv))
    dp.add_handler(CommandHandler("backup", force_backup))
    dp.add_handler(CommandHandler("users", stats_users))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))

    # бэкап GitHub в отдельном потоке
    threading.Thread(target=backup_loop, daemon=True).start()

    print("Bot started")
    updater.start_polling()
    updater.idle()
