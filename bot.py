import telebot
import csv
import os
import threading
import time
import random
from telebot import types
from github import Github

TOKEN = os.getenv("TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_REPO = os.getenv("GITHUB_REPO")

TOTAL_CITIES = 20
DATA_DIR = "data"
CSV_FILE = f"{DATA_DIR}/cities.csv"

bot = telebot.TeleBot(TOKEN)

user_data = {}
user_steps = {}

repo = None


# =========================
# ADMIN CHECK
# =========================

def is_admin(chat_id):
    return int(chat_id) == ADMIN_ID


# =========================
# GITHUB INIT
# =========================

if GITHUB_TOKEN and GITHUB_REPO:
    try:
        g = Github(GITHUB_TOKEN)
        repo = g.get_repo(GITHUB_REPO)
        print("GitHub подключен")
    except Exception as e:
        print("GitHub error:", e)


# =========================
# CSV INIT
# =========================

def init_csv():

    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)

    if not os.path.exists(CSV_FILE):

        header = ["id","phone","name"]

        for i in range(1, TOTAL_CITIES+1):
            header.append(f"city{i}")

        with open(CSV_FILE,"w",newline="",encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(header)

        print("CSV создан")


# =========================
# CSV LOAD
# =========================

def load_csv():

    if not os.path.exists(CSV_FILE):
        return

    with open(CSV_FILE,encoding="utf-8") as f:

        reader = csv.DictReader(f)

        for row in reader:

            chat_id = int(row["id"])

            cities = []

            for i in range(1, TOTAL_CITIES+1):
                cities.append(row.get(f"city{i}") or "")

            user_data[chat_id] = {
                "name": row["name"],
                "phone": row["phone"],
                "cities": cities
            }

    print("CSV загружен")


# =========================
# CSV SAVE
# =========================

def save_csv():

    header = ["id","phone","name"]

    for i in range(1, TOTAL_CITIES+1):
        header.append(f"city{i}")

    with open(CSV_FILE,"w",newline="",encoding="utf-8") as f:

        writer = csv.writer(f)
        writer.writerow(header)

        for chat_id,data in user_data.items():

            row = [chat_id,data["phone"],data["name"]]

            row += data["cities"]

            writer.writerow(row)


# =========================
# GITHUB BACKUP
# =========================

def upload_to_github():

    if not repo:
        return False

    try:

        with open(CSV_FILE,"r",encoding="utf-8") as f:
            content = f.read()

        path = "cities.csv"

        try:

            file = repo.get_contents(path)

            repo.update_file(
                path,
                "update csv",
                content,
                file.sha
            )

        except:

            repo.create_file(
                path,
                "create csv",
                content
            )

        print("GitHub backup OK")

        return True

    except Exception as e:

        print("GitHub error:", e)

        return False


# =========================
# AUTO BACKUP LOOP
# =========================

def backup_loop():

    while True:

        upload_to_github()

        time.sleep(300)


# =========================
# ADMIN KEYBOARD
# =========================

def admin_keyboard():

    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)

    kb.add("📥 CSV","💾 GitHub")
    kb.add("🏆 Финалисты")

    return kb


# =========================
# START
# =========================

@bot.message_handler(commands=["start"])
def start(message):

    chat_id = message.chat.id

    if chat_id in user_data:

        bot.send_message(chat_id,"Вы уже зарегистрированы")

        return

    user_steps[chat_id] = "name"

    bot.send_message(chat_id,"Введите ваше имя:")


# =========================
# MAIN HANDLER
# =========================

@bot.message_handler(func=lambda m: True)
def handle(message):

    chat_id = message.chat.id
    text = message.text.strip()

    # NAME

    if user_steps.get(chat_id) == "name":

        user_data[chat_id] = {
            "name": text,
            "phone": "",
            "cities": [""]*TOTAL_CITIES
        }

        user_steps[chat_id] = "phone"

        bot.send_message(chat_id,"Введите номер телефона:")

        return


    # PHONE

    if user_steps.get(chat_id) == "phone":

        user_data[chat_id]["phone"] = text

        user_steps[chat_id] = "city"

        save_csv()

        bot.send_message(chat_id,"Теперь отправляйте город из эфира")

        return


    # CITY

    if user_steps.get(chat_id) == "city":

        cities = user_data[chat_id]["cities"]

        try:

            index = cities.index("")

        except:

            bot.send_message(chat_id,"Вы уже отправили все города")

            return


        cities[index] = text

        save_csv()

        bot.send_message(
            ADMIN_ID,
            f"🏙 Новый город\n\n"
            f"{user_data[chat_id]['name']}\n"
            f"{user_data[chat_id]['phone']}\n"
            f"Город {index+1}: {text}"
        )

        if index+1 == TOTAL_CITIES:

            bot.send_message(chat_id,"Это последний город!")

        else:

            bot.send_message(
                chat_id,
                f"Город №{index+1}. Осталось {TOTAL_CITIES-index-1}"
            )


# =========================
# ADMIN CSV
# =========================

@bot.message_handler(func=lambda m: m.text=="📥 CSV")
def admin_csv(message):

    if not is_admin(message.chat.id):
        return

    with open(CSV_FILE,"rb") as f:
        bot.send_document(ADMIN_ID,f)


# =========================
# ADMIN GITHUB
# =========================

@bot.message_handler(func=lambda m: m.text=="💾 GitHub")
def admin_git(message):

    if not is_admin(message.chat.id):
        return

    if upload_to_github():

        bot.send_message(ADMIN_ID,"Backup OK")

    else:

        bot.send_message(ADMIN_ID,"Backup error")


# =========================
# FINALISTS
# =========================

@bot.message_handler(func=lambda m: m.text=="🏆 Финалисты")
def finalists(message):

    if not is_admin(message.chat.id):
        return

    finalists = []

    for chat_id,data in user_data.items():

        if "" not in data["cities"]:

            finalists.append((chat_id,data))

    if not finalists:

        bot.send_message(ADMIN_ID,"Финалистов нет")

        return

    text = "Финалисты:\n\n"

    for i,(chat_id,data) in enumerate(finalists,1):

        text += f"{i}. {data['name']} {data['phone']}\n"

    kb = types.InlineKeyboardMarkup()

    kb.add(types.InlineKeyboardButton(
        "🎲 Выбрать победителя",
        callback_data="draw"
    ))

    bot.send_message(ADMIN_ID,text,reply_markup=kb)


# =========================
# DRAW WINNER
# =========================

@bot.callback_query_handler(func=lambda c: c.data=="draw")
def draw(call):

    finalists = []

    for chat_id,data in user_data.items():

        if "" not in data["cities"]:
            finalists.append((chat_id,data))

    if not finalists:

        bot.answer_callback_query(call.id,"Нет финалистов")

        return

    winner = random.choice(finalists)

    chat_id,data = winner

    text = f"Победитель:\n\n{data['name']}\n{data['phone']}"

    bot.edit_message_text(
        text,
        call.message.chat.id,
        call.message.message_id
    )


# =========================
# START BOT
# =========================

if __name__ == "__main__":

    print("Бот запускается")

    init_csv()

    load_csv()

    if repo:

        threading.Thread(
            target=backup_loop,
            daemon=True
        ).start()

    bot.infinity_polling()
