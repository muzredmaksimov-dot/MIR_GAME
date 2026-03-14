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
user_data = {}        # chat_id -> {name, phone, cities}
user_step = {}        # chat_id -> текущий шаг
progress_message = {} # chat_id -> message_id прогресса

# =========================
# CSV ЗАГРУЗКА ПРИ СТАРТЕ
# =========================
def load_csv():
    global user_data
    if repo is None:
        return
    try:
        file = repo.get_contents(CSV_FILE)
        content = file.decoded_content.decode()
        reader = csv.DictReader(io.StringIO(content))
        for row in reader:
            chat_id = int(row['id'])
            cities = [row[f'city_{i}'] for i in range(1, TOTAL_CITIES+1) if row[f'city_{i}']]
            user_data[chat_id] = {
                "name": row['name'],
                "phone": row['phone'],
                "cities": cities
            }
            if len(cities) < TOTAL_CITIES:
                user_step[chat_id] = "cities"
        print(f"CSV загружен, участников: {len(user_data)}")
    except Exception as e:
        print("CSV не найден или ошибка чтения:", e)

load_csv()

# =========================
# СОХРАНЕНИЕ CSV
# =========================
def save_csv():
    if repo is None:
        return
    try:
        output = io.StringIO()
        writer = csv.writer(output)
        header = ["id","name","phone"] + [f"city_{i}" for i in range(1, TOTAL_CITIES+1)]
        writer.writerow(header)
        for chat_id, data in user_data.items():
            row = [chat_id, data["name"], data["phone"]]
            cities = data["cities"] + [""]*(TOTAL_CITIES-len(data["cities"]))
            row.extend(cities)
            writer.writerow(row)
        content = output.getvalue()
        try:
            file = repo.get_contents(CSV_FILE)
            repo.update_file(CSV_FILE, "update results", content, file.sha)
        except:
            repo.create_file(CSV_FILE, "create results", content)
        print("GitHub: CSV сохранён")
    except Exception as e:
        print("Ошибка сохранения CSV:", e)

# =========================
# ПРОВЕРКА АДМИНА
# =========================
def is_admin(chat_id):
    return chat_id == ADMIN_ID

# =========================
# ОБНОВЛЕНИЕ ПРОГРЕССА
# =========================
def update_progress(chat_id):
    data = user_data[chat_id]
    sent = len(data["cities"])
    remaining = TOTAL_CITIES - sent
    text = f"🎧 Игра «Все включено»\n\nИмя: {data['name']}\nТелефон: {data['phone']}\n\n🏙 Городов: {sent}/{TOTAL_CITIES} (осталось: {remaining})"
    # удаляем старое сообщение
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
# АДМИН-КОМАНДЫ
# =========================
@bot.message_handler(commands=["backup"])
def cmd_backup(message):
    if not is_admin(message.chat.id):
        return
    save_csv()
    bot.send_message(ADMIN_ID, "Бэкап сохранён")

@bot.message_handler(commands=["stats"])
def cmd_stats(message):
    if not is_admin(message.chat.id):
        return
    players = len(user_data)
    finalists = len([u for u in user_data.values() if len(u["cities"])==TOTAL_CITIES])
    bot.send_message(ADMIN_ID, f"Игроков: {players}\nФиналистов: {finalists}")

@bot.message_handler(commands=["players"])
def cmd_players(message):
    if not is_admin(message.chat.id):
        return
    text = "Игроки:\n\n"
    for data in user_data.values():
        text += f"{data['name']} | {data['phone']} | {len(data['cities'])} городов\n"
    bot.send_message(ADMIN_ID, text)

@bot.message_handler(commands=["winner"])
def cmd_winner(message):
    if not is_admin(message.chat.id):
        return
    finalists = [(cid,data) for cid,data in user_data.items() if len(data["cities"])==TOTAL_CITIES]
    if not finalists:
        bot.send_message(ADMIN_ID, "Финалистов нет")
        return
    chat_id, data = random.choice(finalists)
    bot.send_message(ADMIN_ID, f"🏆 Победитель:\n\n{data['name']}\n{data['phone']}")

@bot.message_handler(commands=["reset_game"])
def cmd_reset(message):
    if not is_admin(message.chat.id):
        return
    user_data.clear()
    user_step.clear()
    bot.send_message(ADMIN_ID, "Игра очищена")
    save_csv()

# =========================
# СТАРТ / ПЕРЕЗАПУСК
# =========================
@bot.message_handler(commands=["start"])
def cmd_start(message):
    chat_id = message.chat.id
    bot.send_message(chat_id, "🎧 Игра «Все включено»\n\nВведите ваше имя:")
    user_step[chat_id] = "name"

@bot.message_handler(commands=["restart"])
def cmd_restart(message):
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

    # Если это админ-команда, пропускаем
    if text.startswith('/') and is_admin(chat_id):
        return

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
            bot.send_message(chat_id, "Отправляйте город дня, который услышите в эфире!")
            save_csv()
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
            save_csv()
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
