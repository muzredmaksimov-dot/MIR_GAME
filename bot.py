import telebot
import csv
import os
import threading
import time
import requests
import base64
from telebot import types

# === Настройки ===
TOKEN = os.getenv("TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_REPO = os.getenv("GITHUB_REPO")  # username/repo
DATA_DIR = "data"
CSV_FILE = os.path.join(DATA_DIR, "cities.csv")
TOTAL_CITIES = 20

# === Создаём папку data ===
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

# === Словари состояния пользователей ===
user_steps = {}   # на каком шаге (имя, телефон, город)
user_data  = {}   # хранит id, имя, телефон, города
user_city_index = {}  # какой город последний

# === Функции CSV ===
def load_csv():
    data = {}
    if not os.path.exists(CSV_FILE):
        return data
    with open(CSV_FILE, newline='', encoding='utf-8') as f:
        reader = csv.reader(f)
        next(reader)
        for row in reader:
            data[row[0]] = row
    return data

def save_csv():
    header = ["id", "phone", "name"] + [f"city{i+1}" for i in range(TOTAL_CITIES)]
    with open(CSV_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        for row in user_data.values():
            writer.writerow(row)

# === GitHub backup ===
def github_headers():
    return {"Authorization": f"token {GITHUB_TOKEN}", "User-Agent":"radio-mir-bot"}

def upload_csv():
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{CSV_FILE}"
    r = requests.get(url, headers=github_headers())
    sha = r.json().get("sha") if r.status_code==200 else None
    with open(CSV_FILE,"r",encoding="utf-8") as f:
        content = f.read()
    encoded = base64.b64encode(content.encode()).decode()
    data = {"message":"auto backup csv","content":encoded,"sha":sha}
    try:
        requests.put(url,json=data,headers=github_headers())
    except Exception as e:
        print("GitHub backup error:", e)

def backup_loop():
    while True:
        if os.path.exists(CSV_FILE):
            upload_csv()
        time.sleep(300)  # каждые 5 минут

# === Инициализация бота ===
bot = telebot.TeleBot(TOKEN)

# === Обработчики ===
@bot.message_handler(commands=['start'])
def handle_start(message):
    chat_id = message.chat.id
    if str(chat_id) in user_data:
        bot.send_message(chat_id,"Вы уже зарегистрированы. Отправляйте следующий город.")
        return
    user_steps[chat_id] = "name"
    bot.send_message(chat_id,"Привет! Для участия в игре укажи своё имя:")

@bot.message_handler(func=lambda m: True)
def handle_all(message):
    chat_id = message.chat.id
    text = message.text.strip()
    
    # --- Шаг имя ---
    if user_steps.get(chat_id) == "name":
        user_steps[chat_id] = "phone"
        user_data[chat_id] = [chat_id, "", text] + [""]*TOTAL_CITIES
        bot.send_message(chat_id,"Отправьте номер телефона:")
        return

    # --- Шаг телефон ---
    if user_steps.get(chat_id) == "phone":
        user_steps[chat_id] = "city"
        user_data[chat_id][1] = text
        user_city_index[chat_id] = 0
        save_csv()
        bot.send_message(chat_id,"Отлично! Теперь отправляйте город из эфира Радио МИР:")
        return

    # --- Шаг город ---
    if user_steps.get(chat_id) == "city":
        idx = user_city_index.get(chat_id,0)
        if idx >= TOTAL_CITIES:
            bot.send_message(chat_id,"Вы уже отправили все города.")
            return
        user_data[chat_id][3+idx] = text
        user_city_index[chat_id] = idx+1
        save_csv()
        # --- уведомление админу ---
        try:
            bot.send_message(ADMIN_ID,
                f"Новый город от пользователя:\nИмя: {user_data[chat_id][2]}\nТелефон: {user_data[chat_id][1]}\nГород №{idx+1}: {text}")
        except:
            pass
        if idx+1 < TOTAL_CITIES:
            bot.send_message(chat_id,
                f"Это город номер {idx+1}. Осталось {TOTAL_CITIES-(idx+1)}.\nСлушайте Радио МИР завтра!")
        else:
            bot.send_message(chat_id,"Отлично! Это был последний город! Завтра мы выберем победителя.")
        return

    bot.send_message(chat_id,"Нажмите /start для начала участия.")

# === Команды для админа ===
@bot.message_handler(commands=['csv'])
def send_csv(message):
    if message.chat.id != ADMIN_ID:
        return
    if os.path.exists(CSV_FILE):
        bot.send_document(message.chat.id, open(CSV_FILE,"rb"))

@bot.message_handler(commands=['backup'])
def force_backup(message):
    if message.chat.id != ADMIN_ID:
        return
    if os.path.exists(CSV_FILE):
        upload_csv()
        bot.send_message(message.chat.id,"CSV выгружен на GitHub.")

# === Запуск бэкапа в отдельном потоке ===
threading.Thread(target=backup_loop,daemon=True).start()

# === Старт бота ===
print("Bot started")
bot.infinity_polling()
