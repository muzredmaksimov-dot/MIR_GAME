import telebot
import csv
import os
import threading
import time
import random
from datetime import datetime
from telebot import types

# GitHub импорт с обработкой ошибки
try:
    from github import Github
    GITHUB_AVAILABLE = True
except ImportError:
    print("⚠️ Библиотека PyGithub не установлена. GitHub функционал будет отключен.")
    GITHUB_AVAILABLE = False

# === Настройки из переменных окружения ===
TOKEN = os.environ.get('TOKEN')
ADMIN_ID = int(os.environ.get('ADMIN_ID'))
GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN')
GITHUB_REPO = os.environ.get('GITHUB_REPO')

# === GitHub настройки ===
GITHUB_BRANCH = 'main'
CSV_FILENAME = 'contest_data.csv'

# === Константы конкурса ===
TOTAL_CITIES = 20
CONTEST_NAME = "ВСЕ ВКЛЮЧЕНО"

# === Пути к файлам ===
CSV_FILE = CSV_FILENAME

# === Инициализация бота ===
bot = telebot.TeleBot(TOKEN)

# === Структуры данных ===
user_data = {}
user_step = {}

# === GitHub инициализация ===
repo = None
if GITHUB_AVAILABLE and GITHUB_TOKEN:
    try:
        g = Github(GITHUB_TOKEN)
        repo = g.get_repo(GITHUB_REPO)
        print("✅ GitHub подключен")
        print(f"📦 Репозиторий: {GITHUB_REPO}")
        
        # Проверяем доступность репозитория
        try:
            repo.name
            print("✅ Доступ к репозиторию подтвержден")
        except:
            print("❌ Нет доступа к репозиторию. Проверьте токен и название репозитория")
            repo = None
            
    except Exception as e:
        print(f"❌ Ошибка подключения к GitHub: {e}")
        repo = None
else:
    print("⚠️ GitHub не настроен. Для работы с GitHub установите PyGithub: pip install PyGithub")

# === Работа с CSV ===
def init_csv():
    """Создает CSV файл с заголовками"""
    try:
        if not os.path.exists(CSV_FILE):
            with open(CSV_FILE, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'user_id', 
                    'registration_date',
                    'name', 
                    'phone', 
                    'cities_count',
                    'cities_list',
                    'completed_date',
                    'last_activity'
                ])
            print(f"✅ Создан файл {CSV_FILE}")
            
            # Сразу отправляем на GitHub при создании
            if repo:
                upload_to_github()
    except Exception as e:
        print(f"❌ Ошибка создания CSV: {e}")

def save_csv():
    """Сохраняет данные в CSV"""
    try:
        with open(CSV_FILE, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow([
                'user_id', 'registration_date', 'name', 'phone', 
                'cities_count', 'cities_list', 'completed_date', 'last_activity'
            ])
            
            for chat_id, data in user_data.items():
                writer.writerow([
                    chat_id,
                    data.get('registration_date', ''),
                    data.get('name', ''),
                    data.get('phone', ''),
                    data.get('cities_count', 0),
                    '|'.join(data.get('cities', [])),
                    data.get('completed_date', ''),
                    data.get('last_activity', '')
                ])
        print(f"💾 Данные сохранены в CSV ({len(user_data)} записей)")
        return True
    except Exception as e:
        print(f"❌ Ошибка сохранения CSV: {e}")
        return False

def load_csv():
    """Загружает данные из CSV"""
    try:
        if os.path.exists(CSV_FILE):
            with open(CSV_FILE, 'r', encoding='utf-8-sig') as f:
                reader = csv.reader(f)
                next(reader, None)  # Пропускаем заголовки
                loaded = 0
                for row in reader:
                    if len(row) >= 7:
                        try:
                            chat_id = int(row[0])
                            cities = row[5].split('|') if row[5] else []
                            
                            user_data[chat_id] = {
                                'user_id': chat_id,
                                'registration_date': row[1],
                                'name': row[2],
                                'phone': row[3],
                                'cities_count': int(row[4]) if row[4] else 0,
                                'cities': cities,
                                'completed_date': row[6],
                                'last_activity': row[7] if len(row) > 7 else '',
                                'completed': bool(row[6])  # completed если есть дата завершения
                            }
                            loaded += 1
                        except ValueError as e:
                            print(f"Ошибка обработки строки {row}: {e}")
                            continue
            print(f"✅ Загружено {loaded} участников")
    except Exception as e:
        print(f"❌ Ошибка загрузки CSV: {e}")

# === GitHub загрузка ===
def upload_to_github():
    """Загружает CSV на GitHub"""
    if not repo:
        print("ℹ️ GitHub не настроен, пропускаем загрузку")
        return False
    
    try:
        if not os.path.exists(CSV_FILE):
            print("❌ CSV файл не найден")
            return False
            
        with open(CSV_FILE, 'rb') as f:
            content = f.read()
        
        try:
            # Пробуем обновить существующий файл
            contents = repo.get_contents(CSV_FILENAME, ref=GITHUB_BRANCH)
            repo.update_file(contents.path, f"Обновление данных {datetime.now().strftime('%Y-%m-%d %H:%M')}", content, contents.sha, branch=GITHUB_BRANCH)
            print(f"✅ Файл обновлен на GitHub: {CSV_FILENAME}")
        except Exception as e:
            # Файла нет, создаем новый
            try:
                repo.create_file(CSV_FILENAME, f"Создание файла {datetime.now().strftime('%Y-%m-%d %H:%M')}", content, branch=GITHUB_BRANCH)
                print(f"✅ Файл создан на GitHub: {CSV_FILENAME}")
            except Exception as create_error:
                print(f"❌ Ошибка создания файла на GitHub: {create_error}")
                return False
        
        # Создаем бэкап
        try:
            backup_name = f"backups/contest_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            try:
                repo.create_file(backup_name, f"Бэкап {datetime.now().strftime('%Y-%m-%d %H:%M')}", content, branch=GITHUB_BRANCH)
                print(f"✅ Создан бэкап: {backup_name}")
            except:
                # Если папки backups нет, пробуем создать файл без папки
                backup_name = f"contest_data_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
                repo.create_file(backup_name, f"Бэкап {datetime.now().strftime('%Y-%m-%d %H:%M')}", content, branch=GITHUB_BRANCH)
                print(f"✅ Создан бэкап: {backup_name}")
        except Exception as backup_error:
            print(f"⚠️ Не удалось создать бэкап: {backup_error}")
            
        return True
    except Exception as e:
        print(f"❌ Ошибка загрузки на GitHub: {e}")
        return False

def backup_loop():
    """Периодический бэкап"""
    while True:
        time.sleep(300)  # 5 минут
        if os.path.exists(CSV_FILE) and repo:
            print(f"🔄 Автоматический бэкап... {datetime.now().strftime('%H:%M:%S')}")
            upload_to_github()

# === Проверка админа ===
def is_admin(user_id):
    return user_id == ADMIN_ID

# === Команды ===
@bot.message_handler(commands=['start'])
def start(message):
    chat_id = message.chat.id
    
    welcome_text = (
        f"🎉 Добро пожаловать в конкурс {CONTEST_NAME}!\n\n"
        f"📻 Слушайте радио каждый день — в эфире звучат названия городов.\n"
        f"Всего нужно собрать {TOTAL_CITIES} городов.\n\n"
        f"🏆 Главный приз: поездка «Все включено»!\n\n"
        f"Правила простые:\n"
        f"1. Слушайте радио и запоминайте города\n"
        f"2. Отправляйте их боту (по одному сообщению)\n"
        f"3. Соберите все {TOTAL_CITIES} городов\n"
        f"4. Чем больше городов вы отправите — тем ближе к победе!\n\n"
        f"Готовы? Давайте начнем!"
    )
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("✅ Участвовать", callback_data="register"))
    
    bot.send_message(chat_id, welcome_text, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "register")
def register_callback(call):
    chat_id = call.message.chat.id
    
    if chat_id in user_data:
        if user_data[chat_id].get('completed', False):
            bot.edit_message_text(
                "🎉 Вы уже собрали все города! Ждите розыгрыша приза.",
                chat_id,
                call.message.message_id
            )
        else:
            cities_done = user_data[chat_id].get('cities_count', 0)
            remaining = TOTAL_CITIES - cities_done
            bot.edit_message_text(
                f"Вы уже в игре! 🎯\n\n"
                f"Собрано городов: {cities_done} из {TOTAL_CITIES}\n"
                f"Осталось: {remaining}\n\n"
                f"Продолжайте слушать радио и отправлять города!",
                chat_id,
                call.message.message_id
            )
    else:
        bot.edit_message_text(
            "Отлично! Давайте зарегистрируемся.\n\n"
            "Введите ваше имя:",
            chat_id,
            call.message.message_id
        )
        user_step[chat_id] = 'waiting_name'

@bot.message_handler(func=lambda message: user_step.get(message.chat.id) == 'waiting_name')
def get_name(message):
    chat_id = message.chat.id
    name = message.text.strip()
    
    if len(name) < 2:
        bot.send_message(chat_id, "Имя слишком короткое. Введите еще раз:")
        return
    
    if chat_id not in user_data:
        user_data[chat_id] = {}
    
    user_data[chat_id]['name'] = name
    user_step[chat_id] = 'waiting_phone'
    
    bot.send_message(chat_id, f"Приятно познакомиться, {name}!\nТеперь укажите ваш номер телефона для связи:")

@bot.message_handler(func=lambda message: user_step.get(message.chat.id) == 'waiting_phone')
def get_phone(message):
    chat_id = message.chat.id
    phone = message.text.strip()
    
    if len(phone) < 5:
        bot.send_message(chat_id, "Пожалуйста, введите корректный номер телефона:")
        return
    
    user_data[chat_id].update({
        'user_id': chat_id,
        'phone': phone,
        'registration_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'cities': [],
        'cities_count': 0,
        'completed': False,
        'last_activity': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    })
    
    save_csv()
    if repo:
        upload_to_github()
    
    user_step[chat_id] = 'active'
    
    success_text = (
        f"✅ Регистрация завершена!\n\n"
        f"Теперь вы участник конкурса {CONTEST_NAME}.\n\n"
        f"📻 Слушайте радио и отправляйте города, которые услышите\n"
        f"🎯 Всего нужно собрать {TOTAL_CITIES} городов\n"
        f"📊 Отправляйте по одному городу в сообщении\n\n"
        f"Удачи! 🍀"
    )
    
    bot.send_message(chat_id, success_text)
    
    # Уведомление админу
    try:
        bot.send_message(ADMIN_ID, 
            f"🎉 Новый участник!\n"
            f"Имя: {user_data[chat_id]['name']}\n"
            f"Телефон: {phone}\n"
            f"Дата: {user_data[chat_id]['registration_date']}")
    except Exception as e:
        print(f"Ошибка уведомления админа: {e}")

@bot.message_handler(func=lambda message: True)
def handle_city(message):
    chat_id = message.chat.id
    text = message.text.strip()
    
    # Проверка регистрации
    if chat_id not in user_data:
        bot.send_message(chat_id, "❌ Сначала зарегистрируйтесь через /start")
        return
    
    # Проверка на завершение
    if user_data[chat_id].get('completed', False):
        bot.send_message(chat_id, 
            "🎉 Вы уже собрали все 20 городов!\n"
            "Ждите розыгрыша главного приза!")
        return
    
    # Текущий прогресс
    current_count = user_data[chat_id].get('cities_count', 0)
    
    # Проверка на дубликат
    if text in user_data[chat_id].get('cities', []):
        bot.send_message(chat_id, 
            f"❌ Город '{text}' вы уже отправляли.\n"
            f"Попробуйте другой город из эфира!")
        return
    
    # Сохраняем город
    user_data[chat_id]['cities'].append(text)
    user_data[chat_id]['cities_count'] = current_count + 1
    user_data[chat_id]['last_activity'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    # Проверка на победу (все 20 городов)
    if user_data[chat_id]['cities_count'] >= TOTAL_CITIES:
        user_data[chat_id]['completed'] = True
        user_data[chat_id]['completed_date'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        congrats_text = (
            f"🏆 ПОЗДРАВЛЯЕМ! 🏆\n\n"
            f"Вы собрали все {TOTAL_CITIES} городов!\n\n"
            f"Вы стали финалистом конкурса {CONTEST_NAME}.\n"
            f"Победитель будет выбран случайным образом среди всех финалистов.\n\n"
            f"Следите за эфиром и удачи! 🍀"
        )
        bot.send_message(chat_id, congrats_text)
        
        # Уведомление админу
        try:
            cities_list = "\n".join([f"{i+1}. {city}" for i, city in enumerate(user_data[chat_id]['cities'])])
            bot.send_message(ADMIN_ID,
                f"🏆 ФИНИШ!\n"
                f"Имя: {user_data[chat_id]['name']}\n"
                f"Телефон: {user_data[chat_id]['phone']}\n"
                f"Собрано городов: {TOTAL_CITIES}\n\n"
                f"Список:\n{cities_list}")
        except Exception as e:
            print(f"Ошибка уведомления админа: {e}")
    else:
        remaining = TOTAL_CITIES - user_data[chat_id]['cities_count']
        progress_bar = "█" * user_data[chat_id]['cities_count'] + "░" * remaining
        
        bot.send_message(chat_id,
            f"✅ Город '{text}' принят!\n\n"
            f"📊 Прогресс:\n"
            f"{progress_bar}\n"
            f"Собрано: {user_data[chat_id]['cities_count']} из {TOTAL_CITIES}\n"
            f"Осталось: {remaining}")
    
    # Сохраняем данные
    save_csv()
    if repo:
        upload_to_github()

# === Админские команды ===
@bot.message_handler(commands=['admin'])
def admin_panel(message):
    if not is_admin(message.chat.id):
        bot.send_message(message.chat.id, "❌ У вас нет прав администратора")
        return
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(
        types.KeyboardButton("📊 Статистика"),
        types.KeyboardButton("🏆 Розыгрыш"),
        types.KeyboardButton("📥 CSV"),
        types.KeyboardButton("💾 GitHub")
    )
    
    bot.send_message(message.chat.id, "👨💼 Панель администратора:", reply_markup=markup)

@bot.message_handler(func=lambda message: message.text == "📊 Статистика")
def admin_stats(message):
    if not is_admin(message.chat.id):
        return
    
    total_users = len(user_data)
    completed_users = sum(1 for data in user_data.values() if data.get('completed', False))
    active_users = sum(1 for data in user_data.values() 
                      if not data.get('completed', False) and data.get('cities_count', 0) > 0)
    
    stats_text = (
        f"📊 СТАТИСТИКА КОНКУРСА\n"
        f"📅 {datetime.now().strftime('%d.%m.%Y %H:%M')}\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"👥 Всего участников: {total_users}\n"
        f"🏆 Финалистов: {completed_users}\n"
        f"🎯 Активных: {active_users}\n"
        f"━━━━━━━━━━━━━━━━\n"
    )
    
    bot.send_message(ADMIN_ID, stats_text)

@bot.message_handler(func=lambda message: message.text == "🏆 Розыгрыш")
def admin_draw(message):
    if not is_admin(message.chat.id):
        return
    
    finalists = [
        (chat_id, data) for chat_id, data in user_data.items() 
        if data.get('completed', False)
    ]
    
    if not finalists:
        bot.send_message(ADMIN_ID, "❌ Пока нет финалистов")
        return
    
    finalists_list = "🏆 ФИНАЛИСТЫ:\n\n"
    for i, (chat_id, data) in enumerate(finalists, 1):
        finalists_list += f"{i}. {data['name']} - {data['phone']}\n"
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🎲 Выбрать победителя", callback_data="draw_winner"))
    
    bot.send_message(ADMIN_ID, finalists_list, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "draw_winner")
def draw_winner(call):
    if not is_admin(call.message.chat.id):
        bot.answer_callback_query(call.id, "❌ Нет доступа")
        return
    
    finalists = [
        (chat_id, data) for chat_id, data in user_data.items() 
        if data.get('completed', False)
    ]
    
    if not finalists:
        bot.answer_callback_query(call.id, "Нет финалистов!", show_alert=True)
        return
    
    winner_chat_id, winner_data = random.choice(finalists)
    
    winner_text = (
        f"🎉 ПОБЕДИТЕЛЬ ОПРЕДЕЛЕН! 🎉\n\n"
        f"Имя: {winner_data['name']}\n"
        f"Телефон: {winner_data['phone']}\n"
        f"ID: {winner_chat_id}\n\n"
        f"Список городов:\n"
    )
    
    for i, city in enumerate(winner_data['cities'], 1):
        winner_text += f"{i}. {city}\n"
    
    bot.edit_message_text(
        winner_text,
        call.message.chat.id,
        call.message.message_id
    )
    
    # Уведомление победителю
    try:
        bot.send_message(winner_chat_id,
            "🎉 ПОЗДРАВЛЯЕМ! 🎉\n\n"
            "Вы стали победителем конкурса «Все включено»!\n"
            "С вами свяжется наш менеджер для вручения приза.")
    except:
        pass

@bot.message_handler(func=lambda message: message.text == "📥 CSV")
def admin_csv(message):
    if not is_admin(message.chat.id):
        return
    
    if os.path.exists(CSV_FILE):
        with open(CSV_FILE, 'rb') as f:
            bot.send_document(ADMIN_ID, f, caption=f"Данные конкурса на {datetime.now().strftime('%d.%m.%Y %H:%M')}")
    else:
        bot.send_message(ADMIN_ID, "CSV файл не найден")

@bot.message_handler(func=lambda message: message.text == "💾 GitHub")
def admin_github(message):
    if not is_admin(message.chat.id):
        return
    
    if not repo:
        bot.send_message(ADMIN_ID, "❌ GitHub не настроен. Установите PyGithub: pip install PyGithub")
        return
    
    if upload_to_github():
        bot.send_message(ADMIN_ID, "✅ Данные успешно загружены на GitHub")
    else:
        bot.send_message(ADMIN_ID, "❌ Ошибка загрузки на GitHub")

@bot.message_handler(commands=['backup'])
def force_backup(message):
    if not is_admin(message.chat.id):
        return
    
    if not repo:
        bot.send_message(ADMIN_ID, "❌ GitHub не настроен")
        return
    
    if upload_to_github():
        bot.send_message(ADMIN_ID, "✅ Ручной бэкап выполнен успешно")
    else:
        bot.send_message(ADMIN_ID, "❌ Ошибка при бэкапе")

@bot.message_handler(commands=['id'])
def get_id(message):
    """Команда для получения своего ID"""
    bot.send_message(message.chat.id, f"Ваш Telegram ID: {message.chat.id}")

@bot.message_handler(commands=['status'])
def status(message):
    """Проверка статуса бота"""
    if is_admin(message.chat.id):
        status_text = (
            f"🤖 СТАТУС БОТА\n"
            f"━━━━━━━━━━━━━━━━\n"
            f"⏰ Время: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}\n"
            f"👥 Пользователей: {len(user_data)}\n"
            f"🐙 GitHub: {'✅ Подключен' if repo else '❌ Отключен'}\n"
            f"📁 CSV файл: {'✅ Есть' if os.path.exists(CSV_FILE) else '❌ Нет'}\n"
            f"━━━━━━━━━━━━━━━━"
        )
        bot.send_message(ADMIN_ID, status_text)

# === Запуск ===
if __name__ == "__main__":
    print("🎮 Запуск бота конкурса 'Все включено' на Render")
    print("=" * 50)
    print(f"🤖 Токен: {TOKEN[:10]}...")
    print(f"👑 Admin ID: {ADMIN_ID}")
    print(f"📁 CSV файл: {CSV_FILE}")
    print(f"🏙 Всего городов: {TOTAL_CITIES}")
    print(f"🐙 GitHub репозиторий: {GITHUB_REPO}")
    print("=" * 50)
    
    # Инициализация
    init_csv()
    load_csv()
    
    # Запуск бэкапа
    if repo:
        threading.Thread(target=backup_loop, daemon=True).start()
        print("💾 Автобэкап на GitHub запущен (каждые 5 минут)")
    else:
        print("ℹ️ GitHub бэкап отключен")
    
    # Запуск бота
    print("✅ Бот готов к работе!")
    print("=" * 50)
    
    try:
        bot.infinity_polling()
    except Exception as e:
        print(f"❌ Ошибка запуска бота: {e}")
