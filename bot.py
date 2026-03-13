# bot.py
import telebot
from telebot import types
import io
import csv
import threading
import time
from github import Github

# ================== НАСТРОЙКИ ==================
TOKEN = os.getenv("TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_REPO = os.getenv("GITHUB_REPO")TOTAL_CITIES = 20

# ================== ИНИЦИАЛИЗАЦИЯ ==================
bot = telebot.TeleBot(TOKEN)

# GitHub репозиторий
g = Github(GITHUB_TOKEN)
repo = g.get_repo(GITHUB_REPO)

# ================== ХРАНЕНИЕ ДАННЫХ ==================
user_data = {}         # chat_id -> {"name":..., "phone":..., "cities":[], "message_id":...}
user_messages = {}     # chat_id -> message_id

# ================== ВСПОМОГАЛКИ ==================
def upload_csv_to_github():
    output = io.StringIO()
    writer = csv.writer(output)
    header = ["id","phone","name"] + [f"city{i}" for i in range(1, TOTAL_CITIES+1)]
    writer.writerow(header)
    for chat_id, data in user_data.items():
        row = [chat_id, data["phone"], data["name"]] + data["cities"]
        writer.writerow(row)
    content = output.getvalue()
    try:
        file = repo.get_contents("cities.csv")
        repo.update_file("cities.csv", "Обновление данных", content, file.sha)
    except:
        repo.create_file("cities.csv", "Создание файла", content)

def update_progress(chat_id):
    data = user_data[chat_id]
    cities = [c for c in data["cities"] if c]
    text = (
        f"🎧 Конкурс Радио МИР\n\n"
        f"Имя: {data['name']}\n"
        f"Телефон: {data['phone']}\n\n"
        f"🏙 Городов: {len(cities)}/{TOTAL_CITIES}\n\n"
    )
    for i, city in enumerate(cities, 1):
        text += f"{i}. {city}\n"

    if chat_id in user_messages:
        try:
            bot.edit_message_text(text, chat_id, user_messages[chat_id])
            return
        except:
            pass

    msg = bot.send_message(chat_id, text)
    user_messages[chat_id] = msg.message_id

# ================== РЕГИСТРАЦИЯ ==================
@bot.message_handler(commands=["start"])
def start(message):
    chat_id = message.chat.id
    bot.send_message(chat_id, "👋 Добро пожаловать! Введите ваше имя:")
    bot.register_next_step_handler(message, get_name)

def get_name(message):
    chat_id = message.chat.id
    name = message.text.strip()
    user_data[chat_id] = {"name": name, "phone": "", "cities": []}
    bot.send_message(chat_id, f"Отлично, {name}! Теперь введите номер телефона:")
    bot.register_next_step_handler(message, get_phone)

def get_phone(message):
    chat_id = message.chat.id
    phone = message.text.strip()
    user_data[chat_id]["phone"] = phone
    update_progress(chat_id)
    bot.send_message(chat_id, "✅ Регистрация завершена! Теперь отправляйте города по одному.\nНапример: Минск")

# ================== ПРИЁМ ГОРОДОВ ==================
@bot.message_handler(func=lambda m: m.chat.id in user_data)
def handle_city(message):
    chat_id = message.chat.id
    city = message.text.strip()
    data = user_data[chat_id]
    if len(data["cities"]) >= TOTAL_CITIES:
        bot.send_message(chat_id, "Все города уже добавлены.")
        return
    data["cities"].append(city)
    update_progress(chat_id)
    upload_csv_to_github()
    if len(data["cities"]) == TOTAL_CITIES:
        bot.send_message(chat_id, "🎉 Отлично, это был последний город! Ждите эфир, имя победителя прозвучит в радио и появится в Telegram.")

# ================== АДМИН-КОМАНДЫ ==================
def is_admin(chat_id):
    return chat_id == ADMIN_ID

@bot.message_handler(commands=["backup"])
def admin_backup(message):
    if not is_admin(message.chat.id):
        return
    try:
        upload_csv_to_github()
        bot.send_message(ADMIN_ID, "✅ Ручной бэкап на GitHub выполнен успешно")
    except Exception as e:
        bot.send_message(ADMIN_ID, f"❌ Ошибка бэкапа: {e}")

@bot.message_handler(commands=["csv"])
def admin_csv(message):
    if not is_admin(message.chat.id):
        return
    try:
        file = repo.get_contents("cities.csv")
        bot.send_document(ADMIN_ID, io.BytesIO(file.decoded_content), caption="Актуальный CSV")
    except:
        bot.send_message(ADMIN_ID, "❌ Файл CSV на GitHub не найден")

# ================== АВТОБЭКАП КАЖДЫЕ 5 МИНУТ ==================
def auto_backup_loop():
    while True:
        try:
            upload_csv_to_github()
        except:
            pass
        time.sleep(300)  # 5 минут

threading.Thread(target=auto_backup_loop, daemon=True).start()

# ================== ЗАПУСК БОТА ==================
bot.infinity_polling(skip_pending=True)
