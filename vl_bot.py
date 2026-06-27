import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton
import requests
import time
from datetime import datetime
from bs4 import BeautifulSoup
import re
import os
from flask import Flask
from threading import Thread

# ========== КОНФИГ ==========
BOT_TOKEN = os.getenv('BOT_TOKEN')
CHANNEL_USERNAME = "@VoidLauncher_Team"

# ========== ИНИЦИАЛИЗАЦИЯ ==========
bot = telebot.TeleBot(BOT_TOKEN)

# ========== ВЕБ-СЕРВЕР ДЛЯ RENDER ==========
app = Flask('')

@app.route('/')
def home():
    return "✅ Бот VoidLauncher работает 24/7!"

def run_web():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    """Запускает веб-сервер в фоновом потоке"""
    t = Thread(target=run_web)
    t.daemon = True
    t.start()

def wake_up():
    """Каждые 4 минуты пингует себя, чтобы Render не уснул"""
    while True:
        time.sleep(240)  # 4 минуты
        try:
            # ВАЖНО: замените НАЗВАНИЕ_СЕРВИСА на ваш URL на Render
            # Пример: https://voidlauncher-bot.onrender.com
            url = 'https://voidlauncher-bot.onrender.com'
            requests.get(url, timeout=5)
            print(f"🔄 Пинг успешен: {datetime.now().strftime('%H:%M:%S')}")
        except Exception as e:
            print(f"⚠️ Ошибка пинга: {e}")

# ========== КЛАВИАТУРА С КНОПКАМИ ==========
def get_main_keyboard():
    """Создаёт нижнюю панель с кнопками"""
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    btn_news = KeyboardButton("📰 Новости")
    btn_latest = KeyboardButton("🔥 Последнее")
    btn_about = KeyboardButton("💎 О проекте")
    btn_help = KeyboardButton("❓ Помощь")
    keyboard.add(btn_news, btn_latest, btn_about, btn_help)
    return keyboard

# ========== ФУНКЦИЯ ДЛЯ ПАРСИНГА НОВОСТЕЙ ==========
def get_news_with_pagination(limit=10):
    """Получает новости с пагинацией через публичную страницу"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        all_posts = []
        current_url = 'https://t.me/s/VoidLauncher_Team'
        page_count = 0
        max_pages = 10
        
        while page_count < max_pages:
            response = requests.get(current_url, headers=headers, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            posts = soup.find_all('div', class_='tgme_widget_message')
            
            if not posts:
                break
                
            for post in posts:
                link_elem = post.find('a', class_='tgme_widget_message_date')
                if link_elem and link_elem.get('href'):
                    link = link_elem.get('href')
                    msg_id = link.split('/')[-1]
                    
                    # Извлекаем текст поста
                    text_elem = post.find('div', class_='tgme_widget_message_text')
                    text = text_elem.text.strip() if text_elem else ""
                    
                    # Извлекаем дату
                    date_elem = post.find('time', class_='time')
                    date_str = None
                    if date_elem and date_elem.get('datetime'):
                        date_str = date_elem.get('datetime')
                    elif link_elem.find('time'):
                        date_str = link_elem.find('time').get('datetime')
                    
                    post_date = None
                    if date_str:
                        try:
                            if 'T' in date_str:
                                post_date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                        except:
                            pass
                    
                    all_posts.append({
                        'link': link,
                        'msg_id': msg_id,
                        'text': text,
                        'date': post_date,
                        'date_str': date_str
                    })
            
            # Пытаемся найти ссылку на следующую страницу
            next_link = soup.find('a', class_='tme_messages_more')
            if next_link and next_link.get('href'):
                current_url = 'https://t.me' + next_link.get('href')
                page_count += 1
                time.sleep(0.5)
            else:
                break
        
        # Сортируем по дате (самые новые сверху)
        all_posts.sort(
            key=lambda x: (x['date'] is None, x['date'] if x['date'] else datetime.min),
            reverse=True
        )
        
        # Возвращаем уникальные посты
        seen = set()
        unique_posts = []
        for post in all_posts:
            if post['msg_id'] not in seen:
                seen.add(post['msg_id'])
                unique_posts.append(post)
        
        return unique_posts[:limit] if unique_posts else None
        
    except Exception as e:
        print(f"Ошибка парсинга: {e}")
        return None

def is_photo_update(text):
    """Проверяет, является ли сообщение обновлением фото профиля"""
    if not text:
        return False
    text_lower = text.lower().strip()
    return text_lower == "channel photo updated..." or text_lower == "channel photo updated"

def forward_post(chat_id, post):
    """Пересылает пост с сохранением всех медиа"""
    try:
        msg_id = post['msg_id']
        
        # Пробуем переслать через forward_message (это самый надежный способ)
        try:
            forwarded = bot.forward_message(chat_id, CHANNEL_USERNAME, int(msg_id))
            return True
        except Exception as e:
            print(f"Ошибка forward: {e}")
            
            # Если forward не работает, пробуем скопировать
            try:
                # Получаем сообщение из канала
                msg = bot.forward_message(chat_id, CHANNEL_USERNAME, int(msg_id))
                return True
            except Exception as e2:
                print(f"Ошибка копирования: {e2}")
                return False
                
    except Exception as e:
        print(f"Ошибка пересылки: {e}")
        return False

# ========== КОМАНДЫ ==========

@bot.message_handler(commands=['start'])
def cmd_start(message):
    welcome_text = (
        "🚀 **VoidLauncher News Bot**\n\n"
        "Привет! Я показываю последние новости из канала VoidLauncher.\n"
        "Используй кнопки внизу или команды.\n\n"
        "📌 **Доступно:**\n"
        "• 📰 Последние 5 новостей\n"
        "• 🔥 Только последняя\n"
        "• 💎 Информация о проекте"
    )
    bot.send_message(
        message.chat.id,
        welcome_text,
        parse_mode='Markdown',
        reply_markup=get_main_keyboard()
    )

@bot.message_handler(commands=['help'])
def cmd_help(message):
    help_text = (
        "📖 **Помощь**\n\n"
        "**Команды:**\n"
        "/start - Главное меню\n"
        "/news - Последние 5 новостей\n"
        "/latest - Последняя новость\n"
        "/about - О проекте\n"
        "/help - Эта справка\n\n"
        "**Или используй кнопки внизу!** 👇"
    )
    bot.send_message(
        message.chat.id,
        help_text,
        parse_mode='Markdown',
        reply_markup=get_main_keyboard()
    )

@bot.message_handler(commands=['news'])
def cmd_news(message):
    status_msg = bot.send_message(
        message.chat.id,
        "⏳ Загружаю свежие новости... Это может занять несколько секунд",
        reply_markup=get_main_keyboard()
    )
    
    news_links = get_news_with_pagination(5)
    
    if not news_links:
        try:
            bot.edit_message_text(
                "❌ Не удалось загрузить новости. Попробуй позже.",
                message.chat.id,
                status_msg.message_id,
                reply_markup=get_main_keyboard()
            )
        except:
            bot.send_message(
                message.chat.id,
                "❌ Не удалось загрузить новости. Попробуй позже.",
                reply_markup=get_main_keyboard()
            )
        return
    
    try:
        bot.delete_message(message.chat.id, status_msg.message_id)
    except:
        pass
    
    # Показываем список найденных новостей
    news_info = "📰 **Свежие новости:**\n\n"
    for i, news in enumerate(news_links, 1):
        date_str = news['date'].strftime('%d.%m.%Y %H:%M') if news['date'] else 'Дата неизвестна'
        
        # Проверяем, является ли это изменением фото
        if is_photo_update(news['text']):
            news_info += f"{i}. 📅 {date_str}\n   🖼️ **Обновлено фото профиля канала**\n\n"
        else:
            news_info += f"{i}. 📅 {date_str}\n   📝 {news['text'][:80]}...\n\n"
    
    bot.send_message(
        message.chat.id,
        news_info,
        parse_mode='Markdown',
        reply_markup=get_main_keyboard()
    )
    
    # Пересылаем каждое сообщение
    sent_count = 0
    for news in news_links:
        try:
            # Проверяем, является ли это изменением фото
            if is_photo_update(news['text']):
                continue  # Пропускаем пересылку
            
            forwarded = forward_post(message.chat.id, news)
            if forwarded:
                sent_count += 1
            time.sleep(0.3)
        except Exception as e:
            print(f"Ошибка пересылки: {e}")
            continue
    
    if sent_count == 0:
        all_photo_updates = all(is_photo_update(news['text']) for news in news_links)
        if not all_photo_updates:
            bot.send_message(
                message.chat.id,
                "❌ Не удалось переслать новости. Проверь, что бот есть в канале.",
                reply_markup=get_main_keyboard()
            )

@bot.message_handler(commands=['latest'])
def cmd_latest(message):
    status_msg = bot.send_message(
        message.chat.id,
        "⏳ Ищу самую свежую новость...",
        reply_markup=get_main_keyboard()
    )
    
    all_news = get_news_with_pagination(20)
    
    if not all_news:
        try:
            bot.edit_message_text(
                "❌ Не удалось загрузить последнюю новость.",
                message.chat.id,
                status_msg.message_id,
                reply_markup=get_main_keyboard()
            )
        except:
            bot.send_message(
                message.chat.id,
                "❌ Не удалось загрузить последнюю новость.",
                reply_markup=get_main_keyboard()
            )
        return
    
    try:
        bot.delete_message(message.chat.id, status_msg.message_id)
    except:
        pass
    
    # Ищем первое НЕ фото-обновление
    latest_news = None
    for news in all_news:
        if not is_photo_update(news['text']):
            latest_news = news
            break
    
    # Если все новости - это обновления фото
    if not latest_news:
        bot.send_message(
            message.chat.id,
            "❌ Нет доступных новостей для отображения.",
            reply_markup=get_main_keyboard()
        )
        return
    
    try:
        forwarded = forward_post(message.chat.id, latest_news)
        
        if not forwarded:
            bot.send_message(
                message.chat.id,
                "❌ Не удалось переслать новость.",
                reply_markup=get_main_keyboard()
            )
    except Exception as e:
        print(f"Ошибка: {e}")
        bot.send_message(
            message.chat.id,
            f"❌ Ошибка: {str(e)}",
            reply_markup=get_main_keyboard()
        )

@bot.message_handler(commands=['about'])
def cmd_about(message):
    about_text = (
        "💎 **О VoidLauncher**\n\n"
        "VoidLauncher — это абсолютно новый лаунчер для Minecraft, "
        "который объединяет все необходимые функции в одном месте.\n\n"
        "📌 **Особенности:**\n"
        "• Быстрая загрузка\n"
        "• Поддержка модов\n"
        "• Удобный интерфейс\n"
        "• Безопасный вход\n\n"
        "🔗 **Ссылки:**\n"
        "• [Telegram канал](https://t.me/VoidLauncher_Team)\n"
        "• [Веб-сайт]()\n"
        "• [TikTok]()\n"
        "• [Discord]()\n\n"
        "🌐 Ссылки будут добавлены позже!"
    )
    bot.send_message(
        message.chat.id,
        about_text,
        parse_mode='Markdown',
        disable_web_page_preview=True,
        reply_markup=get_main_keyboard()
    )

# ========== ОБРАБОТКА КНОПОК ==========
@bot.message_handler(func=lambda message: message.text == "📰 Новости")
def button_news(message):
    cmd_news(message)

@bot.message_handler(func=lambda message: message.text == "🔥 Последнее")
def button_latest(message):
    cmd_latest(message)

@bot.message_handler(func=lambda message: message.text == "💎 О проекте")
def button_about(message):
    cmd_about(message)

@bot.message_handler(func=lambda message: message.text == "❓ Помощь")
def button_help(message):
    cmd_help(message)

# Обработка обычных сообщений
@bot.message_handler(func=lambda message: True)
def handle_other(message):
    if message.text and message.text.startswith('/'):
        return
    bot.reply_to(
        message,
        "❓ Используй кнопки внизу или команды.\n"
        "Напиши /help для списка команд.",
        reply_markup=get_main_keyboard()
    )

# ========== ЗАПУСК ==========
if __name__ == "__main__":
    # Запускаем веб-сервер для Render
    keep_alive()
    
    # Запускаем пинг-защиту от засыпания
    Thread(target=wake_up, daemon=True).start()
    
    print("🚀 VoidLauncher News Bot запущен...")
    print(f"📡 Токен: {BOT_TOKEN[:10]}...")
    print(f"📢 Канал: {CHANNEL_USERNAME}")
    print("✅ Готов к работе!")
    print("\n⚠️ ВАЖНО: Бот должен быть администратором канала для пересылки!")
    print("🔄 Парсинг может занять время...")
    
    try:
        bot.infinity_polling(timeout=10, long_polling_timeout=5)
    except Exception as e:
        print(f"❌ Ошибка: {e}")