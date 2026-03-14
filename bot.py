import telebot
from telebot import types
import csv
import io
import random
import os
from github import Github

# === НАСТРОЙКИ ===
TOKEN = os.getenv("TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_REPO = os.getenv("GITHUB_REPO")

TOTAL_CITIES = 20
CSV_NAME = "cities.csv"

bot = telebot.TeleBot(TOKEN)

# === GitHub ===
g = Github(GITHUB_TOKEN)
repo = g.get_repo(GITHUB_REPO)

# === ДАННЫЕ ===
user_data = {}
user_step = {}
progress_messages = {}

# =============================
# СОХРАНЕНИЕ CSV
# =============================

def save_csv_to_github():

    output = io.StringIO()
    writer = csv.writer(output)

    header = ["id","name","phone"] + [f"city{i}" for i in range(1, TOTAL_CITIES+1)]
    writer.writerow(header)

    for chat_id,data in user_data.items():

        row = [
            chat_id,
            data["name"],
            data["phone"]
        ]

        cities = data["cities"] + [""]*(TOTAL_CITIES-len(data["cities"]))
        row.extend(cities)

        writer.writerow(row)

    content = output.getvalue()

    try:
        file = repo.get_contents(CSV_NAME)
        repo.update_file(CSV_NAME,"update csv",content,file.sha)
    except:
        repo.create_file(CSV_NAME,"create csv",content)

# =============================
# ПРОГРЕСС
# =============================

def update_progress(chat_id):

    data = user_data[chat_id]
    cities = data["cities"]

    text = (
        f"🎧 Игра «Все включено»\n\n"
        f"Имя: {data['name']}\n"
        f"Телефон: {data['phone']}\n\n"
        f"🏙 Городов: {len(cities)}/{TOTAL_CITIES}\n\n"
    )

    for i,city in enumerate(cities,1):
        text += f"{i}. {city}\n"

    if chat_id in progress_messages:
        try:
            bot.edit_message_text(
                text,
                chat_id,
                progress_messages[chat_id]
            )
            return
        except:
            pass

    msg = bot.send_message(chat_id,text)
    progress_messages[chat_id] = msg.message_id


# =============================
# СТАРТ
# =============================

@bot.message_handler(commands=["start"])
def start(message):

    chat_id = message.chat.id

    bot.send_message(chat_id,"Введите ваше имя:")
    user_step[chat_id] = "name"


# =============================
# РЕГИСТРАЦИЯ
# =============================

@bot.message_handler(func=lambda m: True)
def handler(message):

    chat_id = message.chat.id
    text = message.text.strip()

    step = user_step.get(chat_id)

    # === ИМЯ ===

    if step == "name":

        user_data[chat_id] = {
            "name": text,
            "phone": "",
            "cities": []
        }

        bot.send_message(chat_id,"Введите номер телефона:")
        user_step[chat_id] = "phone"
        return


    # === ТЕЛЕФОН ===

    if step == "phone":

        user_data[chat_id]["phone"] = text
        user_step[chat_id] = "cities"

        update_progress(chat_id)

        bot.send_message(chat_id,"Теперь отправляйте города из эфира")

        save_csv_to_github()

        return


    # === ГОРОДА ===

    if step == "cities":

        data = user_data[chat_id]

        if len(data["cities"]) >= TOTAL_CITIES:
            bot.send_message(chat_id,"Вы уже отправили все города")
            return

        data["cities"].append(text)

        update_progress(chat_id)

        save_csv_to_github()

        if len(data["cities"]) == TOTAL_CITIES:

            bot.send_message(
                chat_id,
                "🎉 Отлично! Вы отправили все города.\n"
                "Ждите розыгрыш в эфире!"
            )

        return


# =============================
# АДМИН
# =============================

def is_admin(chat_id):
    return chat_id == ADMIN_ID


# CSV файл

@bot.message_handler(commands=["csv"])
def admin_csv(message):

    if not is_admin(message.chat.id):
        return

    try:
        file = repo.get_contents(CSV_NAME)

        bot.send_document(
            ADMIN_ID,
            io.BytesIO(file.decoded_content),
            caption="Актуальный CSV"
        )

    except:
        bot.send_message(ADMIN_ID,"Файл не найден")


# ручной бэкап

@bot.message_handler(commands=["backup"])
def admin_backup(message):

    if not is_admin(message.chat.id):
        return

    save_csv_to_github()

    bot.send_message(ADMIN_ID,"Бэкап выполнен")


# список финалистов

@bot.message_handler(commands=["finalists"])
def admin_finalists(message):

    if not is_admin(message.chat.id):
        return

    finalists = []

    for chat_id,data in user_data.items():

        if len(data["cities"]) == TOTAL_CITIES:
            finalists.append((chat_id,data))

    if not finalists:
        bot.send_message(ADMIN_ID,"Финалистов нет")
        return

    text = "Финалисты:\n\n"

    for i,(cid,data) in enumerate(finalists,1):
        text += f"{i}. {data['name']} {data['phone']}\n"

    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("🎲 Выбрать победителя",callback_data="draw"))

    bot.send_message(ADMIN_ID,text,reply_markup=kb)


# розыгрыш

@bot.callback_query_handler(func=lambda c: c.data=="draw")
def draw_winner(call):

    finalists = []

    for chat_id,data in user_data.items():
        if len(data["cities"]) == TOTAL_CITIES:
            finalists.append((chat_id,data))

    if not finalists:
        bot.answer_callback_query(call.id,"Нет финалистов")
        return

    winner = random.choice(finalists)

    chat_id,data = winner

    text = (
        f"🏆 Победитель!\n\n"
        f"{data['name']}\n"
        f"{data['phone']}"
    )

    bot.edit_message_text(
        text,
        call.message.chat.id,
        call.message.message_id
    )


# =============================
# ЗАПУСК
# =============================

print("Бот запущен")

bot.infinity_polling(skip_pending=True)
