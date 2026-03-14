import telebot
from telebot import types
import csv
import io
import os
import random
import time
from github import Github

# =========================
# НАСТРОЙКИ
# =========================

TOKEN = os.getenv("TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_REPO = os.getenv("GITHUB_REPO")

TOTAL_CITIES = 20
CSV_FILE = "mir_game_results.csv"

bot = telebot.TeleBot(TOKEN)

# =========================
# ПОДКЛЮЧЕНИЕ GITHUB
# =========================

repo = None
try:
    g = Github(GITHUB_TOKEN)
    repo = g.get_repo(GITHUB_REPO)
    print("GitHub подключен")
except Exception as e:
    print("Ошибка GitHub:", e)

# =========================
# ДАННЫЕ ПОЛЬЗОВАТЕЛЕЙ
# =========================

user_data = {}
user_step = {}
progress_message = {}

# =========================
# ОЧЕРЕДЬ СОХРАНЕНИЯ
# =========================

save_queue = set()  # chat_id, которые требуют сохранения
last_save_time = 0
SAVE_INTERVAL = 300  # 5 минут

def queue_save(chat_id):
    save_queue.add(chat_id)

def save_csv_batch():
    global last_save_time
    if not save_queue and time.time() - last_save_time < SAVE_INTERVAL:
        return  # нет изменений или слишком рано
    if repo is None:
        return
    try:
        output = io.StringIO()
        writer = csv.writer(output)

        header = ["id", "name", "phone"] + [f"city_{i}" for i in range(1, TOTAL_CITIES + 1)]
        writer.writerow(header)

        for chat_id, data in user_data.items():
            row = [chat_id, data["name"], data["phone"]]
            cities = data["cities"] + [""] * (TOTAL_CITIES - len(data["cities"]))
            row.extend(cities)
            writer.writerow(row)

        content = output.getvalue()

        try:
            file = repo.get_contents(CSV_FILE)
            repo.update_file(CSV_FILE, "update results", content, file.sha)
        except:
            repo.create_file(CSV_FILE, "create results", content)

        save_queue.clear()
        last_save_time = time.time()
        print("GitHub: CSV сохранён")
    except Exception as e:
        print("Ошибка сохранения CSV:", e)

# =========================
# ПРОГРЕСС
# =========================

def update_progress(chat_id):
    data = user_data[chat_id]
    sent = len(data["cities"])
    remaining = TOTAL_CITIES - sent
    text = (
        f"🎧 Игра «Все включено»\n\n"
        f"Имя: {data['name']}\n"
        f"Телефон: {data['phone']}\n\n"
        f"🏙 Городов: {sent}/{TOTAL_CITIES} (осталось: {remaining})"
    )
    # удаляем старое сообщение с прогрессом
    try:
        if chat_id in progress_message:
            bot.delete_message(chat_id, progress_message[chat_id])
    except Exception:
        pass
    try:
        msg = bot.send_message(chat_id, text)
        progress_message[chat_id] = msg.message_id
    except Exception as e:
        print(f"Ошибка отправки прогресса: {e}")

# =========================
# ПРОВЕРКА АДМИНА
# =========================

def is_admin(chat_id):
    return chat_id == ADMIN_ID

# =========================
# КОМАНДЫ АДМИНА
# =========================

@bot.message_handler(commands=["backup"])
def backup(message):
    if not is_admin(message.chat.id):
        return
    save_csv_batch()
    bot.send_message(ADMIN_ID, "Бэкап сохранён")

# =========================
# СТАРТ / ПЕРЕЗАПУСК
# =========================

@bot.message_handler(commands=["start"])
def start(message):
    chat_id = message.chat.id
    bot.send_message(chat_id, "🎧 Игра «Все включено»\n\nВведите ваше имя:")
    user_step[chat_id] = "name"

@bot.message_handler(commands=["restart"])
def restart(message):
    chat_id = message.chat.id
    user_data.pop(chat_id, None)
    user_step.pop(chat_id, None)
    bot.send_message(chat_id, "Игра начата заново.\nВведите ваше имя:")
    user_step[chat_id] = "name"

# =========================
# ОБРАБОТКА СООБЩЕНИЙ
# =========================

@bot.message_handler(func=lambda m: True)
def handler(message):
    chat_id = message.chat.id
    text = message.text.strip()
    step = user_step.get(chat_id)

    try:
        # ---------- имя ----------
        if step == "name":
            user_data[chat_id] = {"name": text, "phone": "", "cities": []}
            bot.send_message(chat_id, "Введите номер телефона:")
            user_step[chat_id] = "phone"
            return

        # ---------- телефон ----------
        if step == "phone":
            user_data[chat_id]["phone"] = text
            user_step[chat_id] = "cities"
            update_progress(chat_id)
            bot.send_message(chat_id, "Отправляйте города, которые услышите в эфире!")
            queue_save(chat_id)
            save_csv_batch()
            return

        # ---------- города ----------
        if step == "cities":
            data = user_data[chat_id]

            if len(data["cities"]) >= TOTAL_CITIES:
                bot.send_message(chat_id, "Вы уже отправили все города!")
                return

            if text.lower() in [c.lower() for c in data["cities"]]:
                bot.send_message(chat_id, "Этот город уже был!")
                return

            data["cities"].append(text)
            update_progress(chat_id)
            queue_save(chat_id)
            save_csv_batch()

            if len(data["cities"]) == TOTAL_CITIES:
                bot.send_message(chat_id, "🎉 Отлично! Все города отправлены.\nЖдите розыгрыш!")
            return

    except Exception as e:
        print(f"Ошибка при обработке сообщения: {e}")

# =========================
# ЗАПУСК
# =========================

print("Бот запущен")
bot.polling()
