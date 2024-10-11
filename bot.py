import os
import telebot
from flask import Flask, request

# Получение токена из переменной окружения (или можно указать напрямую в коде)
TOKEN = os.getenv('TELEGRAM_TOKEN')  # или укажи токен бота прямо здесь в виде строки
bot = telebot.TeleBot(TOKEN)

# Создаем приложение Flask для обработки вебхуков
app = Flask(__name__)

# Базовая команда /start
@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "Добро пожаловать! Это бот-магазин. Используй /catalog чтобы посмотреть товары.")

# Команда для отображения каталога
@bot.message_handler(commands=['catalog'])
def send_catalog(message):
    catalog_text = """
    Вот наш ассортимент:
    1. Товар 1 - 100 рублей
    2. Товар 2 - 200 рублей
    3. Товар 3 - 300 рублей
    Чтобы сделать заказ, напиши /order <номер товара>
    """
    bot.reply_to(message, catalog_text)

# Команда для оформления заказа
@bot.message_handler(commands=['order'])
def order_item(message):
    try:
        item_number = int(message.text.split()[1])  # Получаем номер товара
        bot.reply_to(message, f"Вы выбрали Товар {item_number}. Ваш заказ оформлен!")
    except (IndexError, ValueError):
        bot.reply_to(message, "Пожалуйста, укажи номер товара после команды /order.")

# Обработка вебхуков
@app.route('/' + TOKEN, methods=['POST'])
def get_message():
    json_str = request.stream.read().decode('UTF-8')
    update = telebot.types.Update.de_json(json_str)
    bot.process_new_updates([update])
    return '!', 200

# Тестовая страница для проверки работы Flask
@app.route('/')
def index():
    return 'Бот работает!'

if __name__ == "__main__":
    # Запуск Flask приложения
    app.run(host="0.0.0.0", port=int(os.environ.get('PORT', 5000)))
