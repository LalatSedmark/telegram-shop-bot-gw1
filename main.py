from typing import Dict, Any
import telebot
from init import TOKEN, cursor, db, ADMIN_CHAT_ID, MODERATOR_IDS
from user_manager import UserManager
from cart_manager import CartManager
from logger import setup_logger
from telebot.types import Message, ReplyKeyboardRemove, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton, KeyboardButton
import threading
import time

# Настройка логирования
logger = setup_logger()

# Настройка токенок и айди из .env
bot = telebot.TeleBot(TOKEN)
admin_chat_id = ADMIN_CHAT_ID
moderator_ids = MODERATOR_IDS

user_manager = UserManager(cursor, db)
cart_manager = CartManager()

# Логирование событий
logger.info("Бот запущен")

# Команда /start
@bot.message_handler(commands=['start'])
def send_welcome(message):
    logger.info(f"Получена команда /start от пользователя {message.chat.id}")
    user_info = user_manager.get_user_info_from_db(message.chat.id)  # Получаем информацию из базы данных

    if user_info:
        bot.reply_to(message, f"Добро пожаловать в бот-каталог GREENWAY, {user_info['fio']}!")  # Приветствие для существующего пользователя
        main_menu(message.chat.id)  # Показываем главное меню
    else:
        # Новый пользователь, начинаем процесс регистрации
        bot.reply_to(message, "Добро пожаловать в бот-каталог GREENWAY! Давайте познакомимся.")
        request_user_info(message.chat.id)  # Запрос информации о пользователе

def is_moderator(user_id):
    return user_id in moderator_ids

def main_menu(chat_id: int):
    # Отображение главного меню с проверкой на модератора
    logger.info(f"Отправка главного меню пользователю {chat_id}")
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("Каталог", "Поиск по каталогу", "Корзина", "История заказов", "Личные данные", "О Greenway")

    # Добавляем кнопку "Отправить промо" только если это модератор
    if is_moderator(chat_id):
        markup.add("Отправить промо")

    bot.send_message(chat_id, "Главное меню:", reply_markup=markup)
    user_manager.set_state(chat_id, 'main_menu_choose')

@bot.message_handler(func=lambda message: user_manager.get_state(message.chat.id) == 'main_menu_choose')
def handle_main_menu_choose(message):
    # Обработка выбора пользователя в главном меню
    if message.text in ["Каталог", "Поиск по каталогу", "Корзина", "История заказов", "Личные данные", "О Greenway", "Отправить промо"]:
        if message.text == "Корзина":
            user_manager.set_state(message.chat.id, 'cart')
            handle_cart(message)  # Переходим в корзину
        elif message.text == "Поиск по каталогу":
            user_manager.set_state(message.chat.id, 'search')  # Устанавливаем состояние поиска
            handle_search_start(message)  # Запускаем поиск
        elif message.text == "Каталог":
            handle_catalog(message)  # Открываем каталог, не меняя состояние
        elif message.text == "История заказов":
            user_manager.set_state(message.chat.id, 'order_history')
            handle_order_history(message)  # Обрабатываем выбор истории
        elif message.text == "Личные данные":
            user_manager.set_state(message.chat.id, 'user_profile')
            handle_user_info_selection(message)  # Обрабатываем выбор личных данных
        elif message.text == "О Greenway":
            user_manager.set_state(message.chat.id, 'about_company')
            handle_about_greenway(message)  # Запускаем ряд информативных сообщений о компани
        elif message.text == "Отправить промо" and is_moderator(message.chat.id):
            bot.send_message(message.chat.id,
                             "Введите текст сообщения для отправки промо и прикрепите фото (по желанию):")
            user_manager.set_state(message.chat.id, 'promo_input')
    else:
        bot.send_message(message.chat.id, "Пожалуйста, выберите действие.")

@bot.message_handler(func=lambda message: user_manager.get_state(message.chat.id) == 'promo_input', content_types=['text', 'photo'])
def handle_promo_input(message: Message):
    # Обработка ввода промо-сообщения модератором
    logger.info(f"Модератор {message.chat.id} готовит промо")
    promo_text = message.text
    promo_photo = message.photo[-1].file_id if message.photo else None

    # Если фото не было отправлено, то используем только текст
    if promo_photo:
        promo_text = promo_text if promo_text else "Внимание!"  # Добавляем текст по умолчанию, если его нет

    # Показываем пользователю превью сообщения
    preview_text = f"Вот как будет выглядеть сообщение:\n\n{promo_text}"
    if promo_photo:
        bot.send_photo(message.chat.id, promo_photo, caption=preview_text)
    else:
        bot.send_message(message.chat.id, preview_text)

    # Клавиатура с вариантами
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("Отредактировать", "Отправить", "Отмена")

    # Отправляем клавиатуру после превью
    bot.send_message(message.chat.id, "Выберите действие:", reply_markup=markup)

    user_manager.set_state(message.chat.id, 'promo_confirm')
    user_manager.save_info(message.chat.id, promo_text=promo_text, promo_photo=promo_photo)

@bot.message_handler(func=lambda message: user_manager.get_state(message.chat.id) == 'promo_confirm')
def handle_promo_confirm(message):
    # Подтверждение отправки или редактирование промо-сообщения
    if message.text == "Отправить":
        logger.info(f"Модератор {message.chat.id} отправил промо")
        promo_text = user_manager.get_info(message.chat.id)['promo_text']
        promo_photo = user_manager.get_info(message.chat.id).get('promo_photo')

        # Отправка всем пользователям, которые взаимодействовали с ботом
        user_ids = user_manager.get_all_user_ids()
        for user_id in user_ids:
            if promo_photo:
                bot.send_photo(user_id, promo_photo, caption=promo_text)
            else:
                bot.send_message(user_id, promo_text)

        bot.send_message(message.chat.id, "Промо-сообщение успешно отправлено.")
        main_menu(message.chat.id)

    elif message.text == "Отредактировать":
        logger.info(f"Модератор {message.chat.id} редактирует промо")
        bot.send_message(message.chat.id, "Введите текст и фото для промо-сообщения заново.")
        user_manager.set_state(message.chat.id, 'promo_input')

    elif message.text == "Отмена":
        logger.info(f"Модератор {message.chat.id} отменил отправку промо")
        main_menu(message.chat.id)

@bot.message_handler(func=lambda message: user_manager.get_state(message.chat.id) == 'user_profile')
def handle_user_info_selection(message):
    # Обработка выбора личных данных
    logger.info(f"Пользователь {message.chat.id} открыл личные данные")
    chat_id = message.chat.id
    user_info = user_manager.get_user_info_from_db(chat_id)  # Проверяем информацию в базе данных

    if user_info:
        # Если данные есть, показываем их пользователю
        fio = user_info.get('fio', "Не указано")
        phone = user_info.get('phone', "Не указано")
        address = user_info.get('address', "Не указано")
        user_manager.save_info(message.chat.id, fio=fio, phone=phone, address=address)

        user_info_message = (
            f"Ваши личные данные:\n"
            f"ФИО: {fio}\n"
            f"Телефон: {phone}\n"
            f"Адрес доставки: {address}\n"
        )

        bot.send_message(chat_id, user_info_message)
        edit_user_info(chat_id)  # Предлагаем пользователю отредактировать данные
    else:
        # Если данные не найдены, предлагаем ввести их
        bot.send_message(chat_id, "Ваши данные не найдены. Пожалуйста, введите их заново.")
        request_user_info(chat_id)

@bot.message_handler(func=lambda message: user_manager.get_state(message.chat.id) == 'waiting_for_fio')
def handle_user_fio_input(message):
    logger.info(f"Пользователь {message.chat.id} ввел ФИО")
    fio = message.text
    bot.send_message(message.chat.id, "Пожалуйста, введите свой номер телефона:")
    user_manager.set_state(message.chat.id, 'waiting_for_phone')
    user_manager.save_info(message.chat.id, fio=fio, phone='', address='')

@bot.message_handler(func=lambda message: user_manager.get_state(message.chat.id) == 'waiting_for_phone')
def handle_user_phone_input(message):
    logger.info(f"Пользователь {message.chat.id} ввел номер телефона")
    phone = message.text
    bot.send_message(message.chat.id, "Пожалуйста, введите адрес доставки:")
    user_manager.set_state(message.chat.id, 'waiting_for_address')
    user_manager.save_info(message.chat.id, fio=user_manager.get_info(message.chat.id)['fio'], phone=phone, address='')

@bot.message_handler(func=lambda message: user_manager.get_state(message.chat.id) == 'waiting_for_address')
def handle_user_address_input(message):
    logger.info(f"Пользователь {message.chat.id} ввел адрес доставки")
    address = message.text
    user_manager.save_info(message.chat.id, fio=user_manager.get_info(message.chat.id)['fio'], phone=user_manager.get_info(message.chat.id)['phone'], address=address)
    user_manager.save_user_to_db(message.chat.id, fio=user_manager.get_info(message.chat.id)['fio'], phone=user_manager.get_info(message.chat.id)['phone'], address=address)
    bot.send_message(message.chat.id, "Спасибо! Ваши данные сохранены.")
    main_menu(message.chat.id)

def edit_user_info(chat_id: int):
    # Запрос на редактирование личных данных
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("Редактировать ФИО", "Редактировать телефон", "Редактировать адрес", "Назад")
    bot.send_message(chat_id, "Выберите, что хотите изменить:", reply_markup=markup)
    user_manager.set_state(chat_id, 'waiting_for_edit_choice')

def request_user_info(chat_id: int):
    # Запрос информации о пользователе (ввод данных впервые)
    logger.info(f"Запрос информации у пользователя {chat_id}")
    bot.send_message(chat_id, "Пожалуйста, введите свои ФИО:")
    user_manager.set_state(chat_id, 'waiting_for_fio')

@bot.message_handler(func=lambda message: user_manager.get_state(message.chat.id) == 'waiting_for_edit_choice' and message.text == "Назад")
def handle_back_to_main_menu(message):
    # Обработка нажатия кнопки 'Назад' в меню редактирования
    logger.info(f"Пользователь {message.chat.id} вышел из окна редактирования данных")
    chat_id = message.chat.id
    user_manager.set_state(chat_id, '')  # Очистка состояния
    main_menu(chat_id)

@bot.message_handler(func=lambda message: user_manager.get_state(message.chat.id) == 'waiting_for_edit_choice')
def handle_edit_choice(message):
    # Обработка выбора, что редактировать
    logger.info(f"Пользователь {message.chat.id} выбирает, что отредактировать в личных данных")
    chat_id = message.chat.id
    if message.text == "Редактировать ФИО":
        bot.send_message(chat_id, "Введите ФИО:")
        user_manager.set_state(chat_id, 'waiting_for_edit_fio')
    elif message.text == "Редактировать телефон":
        bot.send_message(chat_id, "Введите номер телефона:")
        user_manager.set_state(chat_id, 'waiting_for_edit_phone')
    elif message.text == "Редактировать адрес":
        bot.send_message(chat_id, "Введите адрес доставки:")
        user_manager.set_state(chat_id, 'waiting_for_edit_address')

@bot.message_handler(func=lambda message: user_manager.get_state(message.chat.id) == 'waiting_for_edit_fio')
def handle_user_edit_fio_input(message):
    # Обработка ввода ФИО пользователя
    chat_id = message.chat.id
    fio = message.text
    user_manager.save_info(chat_id, fio=fio, phone=user_manager.get_info(chat_id).get('phone', ''),
                           address=user_manager.get_info(chat_id).get('address', ''))
    user_manager.save_user_to_db(chat_id, fio=fio, phone=user_manager.get_info(chat_id).get('phone', ''),
                           address=user_manager.get_info(chat_id).get('address', ''))
    bot.send_message(chat_id, "ФИО обновлено.")
    user_manager.set_state(chat_id, '')  # Очистка состояния
    edit_user_info(chat_id)

@bot.message_handler(func=lambda message: user_manager.get_state(message.chat.id) == 'waiting_for_edit_phone')
def handle_user_edit_phone_input(message):
    # Обработка ввода номера телефона пользователя
    chat_id = message.chat.id
    phone = message.text
    user_manager.save_info(chat_id, fio=user_manager.get_info(chat_id).get('fio', ''), phone=phone,
                           address=user_manager.get_info(chat_id).get('address', ''))
    user_manager.save_user_to_db(chat_id, fio=user_manager.get_info(chat_id).get('fio', ''), phone=phone,
                           address=user_manager.get_info(chat_id).get('address', ''))
    bot.send_message(chat_id, "Номер телефона обновлен.")
    user_manager.set_state(chat_id, '')  # Очистка состояния
    edit_user_info(chat_id)

@bot.message_handler(func=lambda message: user_manager.get_state(message.chat.id) == 'waiting_for_edit_address')
def handle_user_edit_address_input(message):
    # Обработка ввода адреса пользователя
    chat_id = message.chat.id
    address = message.text
    user_manager.save_info(chat_id, fio=user_manager.get_info(chat_id).get('fio', ''),
                           phone=user_manager.get_info(chat_id).get('phone', ''), address=address)
    user_manager.save_user_to_db(chat_id, fio=user_manager.get_info(chat_id).get('fio', ''),
                                 phone=user_manager.get_info(chat_id).get('phone', ''), address=address)
    bot.send_message(chat_id, "Адрес доставки обновлен.")
    user_manager.set_state(chat_id, '')  # Очистка состояния
    edit_user_info(chat_id)

def fetch_groups():
    # Получение всех групп товаров
    cursor.execute("SELECT id, name FROM `groups`")
    return cursor.fetchall()

def fetch_subgroups(group_id):
    # Получение подгрупп по ID группы
    cursor.execute("SELECT id, name FROM subgroups WHERE group_id = %s", (group_id,))
    return cursor.fetchall()

def fetch_products(subgroup_id):
    # Получение товаров по ID подгруппы через таблицу связи
    query = """
        SELECT p.id, p.name, p.price, p.description 
        FROM products p
        JOIN subgroup_product sp ON p.id = sp.product_id
        WHERE sp.subgroup_id = %s
    """
    cursor.execute(query, (subgroup_id,))
    return cursor.fetchall()


@bot.message_handler(func=lambda message: user_manager.get_state(message.chat.id) == 'shop')
def handle_catalog(message):
    # Обработка выбора каталога и отображение групп товаров
    logger.info(f"Пользователь {message.chat.id} открыл каталог")  # Логируем, что каталог открыт

    catalog_items = fetch_groups()  # Получение всех групп
    if catalog_items:
        markup = InlineKeyboardMarkup()
        for item in catalog_items:
            markup.add(
                InlineKeyboardButton(item[1], callback_data=f"group_{item[0]}"))  # Отправляем callback с ID группы
        bot.send_message(message.chat.id, "Выберите группу товаров:", reply_markup=markup)
    else:
        bot.send_message(message.chat.id, "Каталог пока пуст.")

def get_group_name(group_id):
    # Возвращает название группы по её ID
    cursor.execute("SELECT name FROM `groups` WHERE id = %s", (group_id,))
    result = cursor.fetchone()
    return result[0] if result else None

def get_subgroup_name(subgroup_id):
    # Возвращает название подгруппы по её ID
    cursor.execute("SELECT name FROM subgroups WHERE id = %s", (subgroup_id,))
    result = cursor.fetchone()
    return result[0] if result else None

def get_product_name(product_id):
    # Возвращает название товара по его ID
    cursor.execute("SELECT name FROM products WHERE id = %s", (product_id,))
    result = cursor.fetchone()
    return result[0] if result else None

# Количество подгрупп на одной странице
SUBGROUPS_PER_PAGE = 10

@bot.callback_query_handler(func=lambda call: call.data.startswith('group_'))
def handle_group_selection(call):
    group_id = int(call.data.split('_')[1])
    # Получаем название группы и логируем
    group_name = get_group_name(group_id)
    if group_name:
        logger.info(f"Пользователь {call.message.chat.id} открыл группу: {group_name}")

    # Если в callback_data указана страница, извлекаем её, иначе устанавливаем в 0
    page = int(call.data.split('_')[2]) if len(call.data.split('_')) > 2 else 0

    subgroups = fetch_subgroups(group_id)  # Получение всех подгрупп для выбранной группы
    total_subgroups = len(subgroups)

    # Определение предела для текущей страницы
    start = page * SUBGROUPS_PER_PAGE
    end = start + SUBGROUPS_PER_PAGE
    subgroups_page = subgroups[start:end]  # Текущая страница подгрупп

    if subgroups_page:
        markup = InlineKeyboardMarkup()
        for subgroup in subgroups_page:
            markup.add(InlineKeyboardButton(subgroup[1], callback_data=f"subgroup_{subgroup[0]}"))

        # Добавляем кнопки навигации, если нужно
        if end < total_subgroups:
            markup.add(InlineKeyboardButton("Следующая страница", callback_data=f"group_{group_id}_{page + 1}"))
        if page > 0:
            markup.add(InlineKeyboardButton("Предыдущая страница", callback_data=f"group_{group_id}_{page - 1}"))

        bot.send_message(call.message.chat.id, "Выберите подгруппу:", reply_markup=markup)
    else:
        bot.send_message(call.message.chat.id, "В этой группе нет подгрупп.")

# Количество товара на одной странице
PRODUCTS_PER_PAGE = 10

# Открываем подгруппу
@bot.callback_query_handler(func=lambda call: call.data.startswith('subgroup_'))
def handle_subgroup_selection(call):
    subgroup_id = int(call.data.split('_')[1])
    subgroup_name = get_subgroup_name(subgroup_id)
    if subgroup_name:
        logger.info(f"Пользователь {call.message.chat.id} открыл подгруппу: {subgroup_name}")

    # Если в callback_data указана страница, извлекаем её, иначе устанавливаем в 0
    page = int(call.data.split('_')[2]) if len(call.data.split('_')) > 2 else 0

    products = fetch_products(subgroup_id)  # Получение всех продуктов для подгруппы
    total_products = len(products)

    # Определение предела для текущей страницы
    start = page * PRODUCTS_PER_PAGE
    end = start + PRODUCTS_PER_PAGE
    products_page = products[start:end]  # Текущая страница товаров

    if products_page:
        markup = InlineKeyboardMarkup()
        for product in products_page:
            markup.add(InlineKeyboardButton(f"{product[1]} - {product[2]}₽", callback_data=f"product_{product[0]}"))

        # Добавляем кнопки навигации, если нужно
        if end < total_products:
            markup.add(InlineKeyboardButton("Следующая страница", callback_data=f"subgroup_{subgroup_id}_{page + 1}"))
        if page > 0:
            markup.add(InlineKeyboardButton("Предыдущая страница", callback_data=f"subgroup_{subgroup_id}_{page - 1}"))

        bot.send_message(call.message.chat.id, "Выберите товар:", reply_markup=markup)
    else:
        bot.send_message(call.message.chat.id, "В этой подгруппе нет товаров.")

# Открываем товар
@bot.callback_query_handler(func=lambda call: call.data.startswith('product_'))
def handle_product_selection(call):
    # Обработка выбора товара
    product_id = int(call.data.split('_')[1])
    product_name = get_product_name(product_id)
    if product_name:
        logger.info(f"Пользователь {call.message.chat.id} открыл товар: {product_name}")

    product = fetch_product_details(product_id)  # Функция для получения деталей товара

    if product:
        product_price = product['price']
        product_description = product['description']
        product_image_url = product.get('image_url')

        product_info = f"✅ *Товар:* {product_name}\n\n📄 *Описание:* {product_description}\n\n💵 *Цена:* {product_price}₽"

        if product_image_url:
            bot.send_photo(call.message.chat.id, product_image_url, caption=product_info, parse_mode="Markdown")
        else:
            bot.send_message(call.message.chat.id, product_info, parse_mode="Markdown")

        # Настраиваем кнопки действия
        markup = ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add("Добавить в корзину", "Отмена")
        if is_moderator(call.message.chat.id):
            markup.add("Редактировать товар")
        bot.send_message(call.message.chat.id, "Выберите действие", reply_markup=markup)

        # Сохраняем состояние и product_id для модераторов и пользователей
        user_manager.set_state(call.message.chat.id, 'confirm_add_to_cart')
        user_manager.save_info(call.message.chat.id, product_id=product_id)
    else:
        bot.send_message(call.message.chat.id, "Товар не найден.")

# Предоставляет модератору варианты для редактирования товара
@bot.message_handler(func=lambda message: user_manager.get_state(message.chat.id) == 'edit_product')
def handle_edit_product(message):
    logger.info(f"Модератор {message.chat.id} открыл товар: {product_name} открыл редактирование карточки товара")
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("Изменить название", "Изменить описание")
    markup.row("Изменить цену", "Изменить фото")
    markup.add("Отмена редактирования")

    bot.send_message(message.chat.id, "Что вы хотите изменить?", reply_markup=markup)

    user_manager.set_state(message.chat.id, 'edit_product_action')

# Обработка выбора параметра для редактирования
@bot.message_handler(func=lambda message: user_manager.get_state(message.chat.id) == 'edit_product_action')
def handle_edit_product_action(message):
    product_id = user_manager.get_info(message.chat.id).get('product_id')

    if message.text == "Изменить название":
        bot.send_message(message.chat.id, "Введите новое название товара:")
        user_manager.set_state(message.chat.id, 'edit_product_name')

    elif message.text == "Изменить описание":
        bot.send_message(message.chat.id, "Введите новое описание товара:")
        user_manager.set_state(message.chat.id, 'edit_product_description')

    elif message.text == "Изменить цену":
        bot.send_message(message.chat.id, "Введите новую цену товара:")
        user_manager.set_state(message.chat.id, 'edit_product_price')

    elif message.text == "Изменить фото":
        bot.send_message(message.chat.id, "Прикрепите новое фото товара (ссылка, не более 5 МБ):")
        user_manager.set_state(message.chat.id, 'edit_product_photo')

    elif message.text == "Отмена редактирования":
        main_menu(message.chat.id)

    elif message.text == "Отмена редактирования":
        # Возвращаемся к карточке товара без дополнительных сообщений
        product = fetch_product_details(product_id)  # Получаем информацию о товаре
        if product:
            product_name = product['name']
            product_price = product['price']
            product_description = product['description']
            product_image_url = product.get('image_url')

            product_info = f"✅ *Товар:* {product_name}\n\n📄 *Описание:* {product_description}\n\n💵 *Цена:* {product_price}₽"

            if product_image_url:
                bot.send_photo(message.chat.id, product_image_url, caption=product_info, parse_mode="Markdown")
            else:
                bot.send_message(message.chat.id, product_info, parse_mode="Markdown")

            # Возвращаем кнопки действия
            markup = ReplyKeyboardMarkup(resize_keyboard=True)
            markup.add("Добавить в корзину", "Отмена")
            if is_moderator(message.chat.id):
                markup.add("Редактировать товар")
            bot.send_message(message.chat.id, "Выберите действие", reply_markup=markup)

        # Сбрасываем состояние редактирования
        user_manager.set_state(message.chat.id, 'confirm_add_to_cart')

def show_edit_options(chat_id):
    # Отображает кнопки 'Сохранить изменение' и 'Отмена' при редактировании
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("Сохранить изменение", "Отмена")
    bot.send_message(chat_id, "Выберите действие:", reply_markup=markup)

# Сохраняет новое название для подтверждения перед применением изменений
@bot.message_handler(func=lambda message: user_manager.get_state(message.chat.id) == 'edit_product_name')
def update_product_name(message):
    new_name = message.text
    user_manager.save_info(message.chat.id, temp_product_name=new_name)
    bot.send_message(message.chat.id, f"Новое название: {new_name}")
    show_edit_options(message.chat.id)
    user_manager.set_state(message.chat.id, 'confirm_product_name')

@bot.message_handler(func=lambda message: user_manager.get_state(message.chat.id) == 'confirm_product_name')
def confirm_product_name(message):
    product_id = user_manager.get_info(message.chat.id)['product_id']
    new_name = user_manager.get_info(message.chat.id).get('temp_product_name')

    if message.text == "Сохранить изменение":
        cursor.execute("UPDATE products SET name = %s WHERE id = %s", (new_name, product_id))
        db.commit()
        bot.send_message(message.chat.id, "Название товара обновлено.")
    else:
        bot.send_message(message.chat.id, "Изменение отменено.")

    main_menu(message.chat.id)

@bot.message_handler(func=lambda message: user_manager.get_state(message.chat.id) == 'edit_product_description')
def update_product_description(message):
    """Сохраняет новое описание для подтверждения перед применением изменений."""
    new_description = message.text
    user_manager.save_info(message.chat.id, temp_product_description=new_description)
    bot.send_message(message.chat.id, f"Новое описание: {new_description}")
    show_edit_options(message.chat.id)
    user_manager.set_state(message.chat.id, 'confirm_product_description')

@bot.message_handler(func=lambda message: user_manager.get_state(message.chat.id) == 'confirm_product_description')
def confirm_product_description(message):
    product_id = user_manager.get_info(message.chat.id)['product_id']
    new_description = user_manager.get_info(message.chat.id).get('temp_product_description')

    if message.text == "Сохранить изменение":
        cursor.execute("UPDATE products SET description = %s WHERE id = %s", (new_description, product_id))
        db.commit()
        bot.send_message(message.chat.id, "Описание товара обновлено.")
    else:
        bot.send_message(message.chat.id, "Изменение отменено.")

    main_menu(message.chat.id)

@bot.message_handler(func=lambda message: user_manager.get_state(message.chat.id) == 'edit_product_price')
def update_product_price(message):
    """Сохраняет новую цену для подтверждения перед применением изменений."""
    try:
        new_price = float(message.text)
        user_manager.save_info(message.chat.id, temp_product_price=new_price)
        bot.send_message(message.chat.id, f"Новая цена: {new_price}₽")
        show_edit_options(message.chat.id)
        user_manager.set_state(message.chat.id, 'confirm_product_price')
    except ValueError:
        bot.send_message(message.chat.id, "Введите корректную цену.")

@bot.message_handler(func=lambda message: user_manager.get_state(message.chat.id) == 'confirm_product_price')
def confirm_product_price(message):
    product_id = user_manager.get_info(message.chat.id)['product_id']
    new_price = user_manager.get_info(message.chat.id).get('temp_product_price')

    if message.text == "Сохранить изменение":
        cursor.execute("UPDATE products SET price = %s WHERE id = %s", (new_price, product_id))
        db.commit()
        bot.send_message(message.chat.id, "Цена товара обновлена.")
    else:
        bot.send_message(message.chat.id, "Изменение отменено.")

    main_menu(message.chat.id)

@bot.message_handler(func=lambda message: user_manager.get_state(message.chat.id) == 'edit_product_photo')
def update_product_photo(message):
    """Запрашивает ссылку на новое фото для товара и выводит предупреждение."""
    bot.send_message(message.chat.id, "Отправьте ссылку на новое фото товара (размер не больше 5 МБ).")
    user_manager.set_state(message.chat.id, 'confirm_product_photo')

@bot.message_handler(func=lambda message: user_manager.get_state(message.chat.id) == 'confirm_product_photo')
def confirm_product_photo(message):
    product_id = user_manager.get_info(message.chat.id)['product_id']
    new_photo_url = message.text

    if message.text == "Сохранить изменение":
        cursor.execute("UPDATE products SET image_url = %s WHERE id = %s", (new_photo_url, product_id))
        db.commit()
        bot.send_message(message.chat.id, "Фото товара обновлено.")
    else:
        bot.send_message(message.chat.id, "Изменение отменено.")

    main_menu(message.chat.id)

# Максимальное количество одного товара в заказе
MAX_QUANTITY = 1000

@bot.message_handler(func=lambda message: user_manager.get_state(message.chat.id) == 'confirm_add_to_cart')
def handle_add_to_cart_confirmation(message):
    """Подтверждение добавления товара в корзину и запрос количества"""
    if message.text == "Добавить в корзину":
        logger.info(f"Пользователь {message.chat.id} добавляет товар в корзину")
        bot.send_message(message.chat.id, f"Введите количество товара (максимум {MAX_QUANTITY}):")
        user_manager.set_state(message.chat.id, 'waiting_for_quantity')

    elif message.text == "Редактировать товар" and is_moderator(message.chat.id):
        # Переключаем на режим редактирования для модераторов
        handle_edit_product(message)

    elif message.text == "Отмена":
        logger.info(f"Пользователь {message.chat.id} отменил добавление товара в корзину")
        bot.send_message(message.chat.id, "Вы вернулись в каталог.")
        main_menu(message.chat.id)  # Возврат в каталог

@bot.message_handler(func=lambda message: user_manager.get_state(message.chat.id) == 'waiting_for_quantity')
def handle_quantity_input(message):
    """Обработка ввода количества товара"""
    try:
        quantity = int(message.text)
        if quantity <= 0:
            bot.send_message(message.chat.id, "Количество должно быть положительным числом. Попробуйте снова.")
            return
        if quantity > MAX_QUANTITY:
            bot.send_message(message.chat.id, f"Извините, но можно заказать не более {MAX_QUANTITY} шт.")
            return

        product_id = user_manager.get_info(message.chat.id)['product_id']
        product = fetch_product_details(product_id)

        if product:
            total_price = product['price'] * quantity
            confirmation_message = (
                f"Вы выбрали {product['name']} в количестве {quantity} шт.\n\n"
                f"Общая сумма: {total_price}₽."
            )

            markup = ReplyKeyboardMarkup(resize_keyboard=True)
            markup.add("Подтвердить", "Отменить")
            bot.send_message(message.chat.id, confirmation_message, reply_markup=markup)

            # Сохраняем количество и общую сумму
            user_manager.set_state(message.chat.id, 'confirm_quantity')
            user_manager.save_info(
                message.chat.id,
                quantity=quantity,
                total_price=total_price,
                product_id=product_id,
                product_name=product['name'],
                product_price=product['price']
            )
        else:
            bot.send_message(message.chat.id, "Ошибка при получении товара.")
            main_menu(message.chat.id)
    except ValueError:
        bot.send_message(message.chat.id, "Пожалуйста, введите корректное количество.")

@bot.message_handler(func=lambda message: user_manager.get_state(message.chat.id) == 'confirm_quantity')
def handle_quantity_confirmation(message):
    """Подтверждение выбора количества товара и добавление в корзину"""
    if message.text == "Подтвердить":
        logger.info(f"Пользователь {message.chat.id} добавил товар в корзину")
        product_id = user_manager.get_info(message.chat.id)['product_id']
        quantity = user_manager.get_info(message.chat.id)['quantity']
        product_name = user_manager.get_info(message.chat.id).get('product_name')
        product_price = user_manager.get_info(message.chat.id).get('product_price')

        # Проверка на None для product_price
        if product_price is None:
            bot.send_message(message.chat.id, "Цена товара не найдена. Пожалуйста, выберите товар снова.")
            return

        # Добавляем товар в корзину
        cart_manager.add_to_cart(message.chat.id, product_id, product_name, product_price, quantity)

        bot.send_message(message.chat.id, f"Товар добавлен в корзину!")

        # Вопрос: продолжить покупки или перейти в корзину
        markup = ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add("Корзина", "Продолжить покупки")
        bot.send_message(message.chat.id, "Что хотите сделать дальше?", reply_markup=markup)

        user_manager.set_state(message.chat.id, 'next_action')
    else:
        bot.send_message(message.chat.id, "Операция отменена.")
        main_menu(message.chat.id)

@bot.message_handler(func=lambda message: user_manager.get_state(message.chat.id) == 'next_action')
def handle_next_action(message):
    """Обработка выбора пользователя: продолжить покупки или перейти в корзину"""
    if message.text == "Корзина":
        logger.info(f"Пользователь {message.chat.id} перешел в корзину")
        user_manager.set_state(message.chat.id, 'cart')
        handle_cart(message)  # Переходим в корзину
    elif message.text == "Продолжить покупки":
        logger.info(f"Пользователь {message.chat.id} вернулся в каталог")
        user_manager.set_state(message.chat.id, 'shop')
        handle_catalog(message) # Переходим в каталог
    else:
        bot.send_message(message.chat.id, "Пожалуйста, выберите действие.")

def fetch_product_details(product_id: int) -> Dict[str, Any]:
    """Получение информации о товаре по его ID"""
    cursor.execute("SELECT name, price, description, image_url FROM products WHERE id = %s", (product_id,))
    result = cursor.fetchone()
    if result:
        name, price, description, image_url = result  # Распакуйте все 4 значения
        return {'name': name, 'price': price, 'description': description, 'image_url': image_url}
    return None

@bot.message_handler(func=lambda message: user_manager.get_state(message.chat.id) == 'cart')
def handle_cart(message):
    """Обработка нажатия кнопки 'Корзина' и отображение содержимого корзины"""
    logger.info(f"Пользователь {message.chat.id} открыл корзину")
    """Если пользователь просто открыл корзину, отображаем ее содержимое"""
    cart_items = cart_manager.get_cart(message.chat.id)

    if not cart_items:
        bot.send_message(message.chat.id, "Ваша корзина пуста.")
        logger.info(f"Корзина пользователя {message.chat.id} пуста")
        user_manager.set_state(message.chat.id, 'main_menu_choose')
        return
    else:
        cart_message = "Ваша корзина:\n"
        total_price = 0
        for idx, item in enumerate(cart_items, start=1):
            cart_message += f"{idx}. {item['product_name']} - {item['product_price']}₽ x{item['quantity']} = {item['total_price']}₽\n"
            total_price += item['total_price']
        cart_message += f"\nИтого: {total_price}₽"

        markup = ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add("Подтвердить заказ", "Очистить корзину", "Отредактировать заказ", "Главное меню")
        bot.send_message(message.chat.id, cart_message, reply_markup=markup)

        user_manager.set_state(message.chat.id, 'next_cart_action')

@bot.message_handler(func=lambda message: user_manager.get_state(message.chat.id) == 'next_cart_action')
def handle_next_cart_action(message):
    """Обрабатываем действия в корзине"""
    if message.text == "Очистить корзину":
        cart_manager.clear_cart(message.chat.id)
        bot.send_message(message.chat.id, "Корзина очищена.")
        logger.info(f"Корзина пользователя {message.chat.id} очищена")
        user_manager.set_state(message.chat.id, 'main_menu_choose')  # Возвращаемся в главное меню
        main_menu(message.chat.id)
        return  # Завершаем обработчик

    elif message.text == "Главное меню":
        logger.info(f"Пользователь {message.chat.id} перешел в главное меню")
        user_manager.set_state(message.chat.id, 'main_menu_choose')  # Смена состояния
        main_menu(message.chat.id)
        return  # Завершаем обработчик

    elif message.text == "Подтвердить заказ":
        handle_confirm_order(message)  # Вызываем функцию для подтверждения заказа

    elif message.text == "Отредактировать заказ":
        logger.info(f"Пользователь {message.chat.id} редактирует корзину")
        cart_items = cart_manager.get_cart(message.chat.id)
        if not cart_items:
            bot.send_message(message.chat.id, "Ваша корзина пуста.")
            user_manager.set_state(message.chat.id, 'main_menu_choose')
            main_menu(message.chat.id)
            return

        edit_message = "Выберите номер товара для редактирования:\n"
        for idx, item in enumerate(cart_items, start=1):
            edit_message += f"{idx}. {item['product_name']} - {item['quantity']} шт.\n"

        # Создаем клавиатуру с кнопкой "Отмена редактирования"
        markup = ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add("Отмена редактирования")  # Добавляем кнопку отмены
        bot.send_message(message.chat.id, edit_message, reply_markup=markup)

        user_manager.set_state(message.chat.id, 'edit_cart_item')

@bot.message_handler(func=lambda message: user_manager.get_state(message.chat.id) == 'edit_cart_item')
def handle_edit_cart_item(message):
    """Обрабатываем выбор товара для редактирования"""
    if message.text == "Отмена редактирования":
        logger.info(f"Пользователь {message.chat.id} отменил редактирование корзины")
        user_manager.set_state(message.chat.id, 'cart')
        handle_cart(message)
        return

    try:
        item_index = int(message.text) - 1
        cart_items = cart_manager.get_cart(message.chat.id)

        if item_index < 0 or item_index >= len(cart_items):
            raise ValueError("Неверный номер товара.")

        user_manager.set_edit_item(message.chat.id, item_index)  # Сохраняем выбранный товар для редактирования

        markup = ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add("Изменить количество", "Удалить товар", "Отмена действия")
        bot.send_message(message.chat.id, "Выберите действие:", reply_markup=markup)
        user_manager.set_state(message.chat.id, 'choose_edit_action')

    except ValueError:
        bot.send_message(message.chat.id, "Пожалуйста, выберите корректный номер товара.")

@bot.message_handler(func=lambda message: user_manager.get_state(message.chat.id) == 'choose_edit_action')
def handle_choose_edit_action(message):
    """Обрабатываем выбранное действие для товара"""
    cart_items = cart_manager.get_cart(message.chat.id)
    item_index = user_manager.get_edit_item(message.chat.id)  # Получаем индекс редактируемого товара

    if message.text == "Изменить количество":
        logger.info(f"Пользователь {message.chat.id} хочет изменить количество товара")
        bot.send_message(message.chat.id, f"Введите новое количество для {cart_items[item_index]['product_name']}:")
        user_manager.set_state(message.chat.id, 'edit_quantity')

    elif message.text == "Удалить товар":
        logger.info(f"Пользователь {message.chat.id} удалил товар в корзину")
        cart_manager.remove_item(message.chat.id, item_index)
        bot.send_message(message.chat.id, f"{cart_items[item_index]['product_name']} удален из корзины.")
        user_manager.set_state(message.chat.id, 'cart')
        handle_cart(message)  # Отображаем обновленную корзину

    elif message.text == "Отмена действия":
        logger.info(f"Пользователь {message.chat.id} вернулся в корзину")
        user_manager.set_state(message.chat.id, 'cart')
        handle_cart(message)

@bot.message_handler(func=lambda message: user_manager.get_state(message.chat.id) == 'edit_quantity')
def handle_edit_quantity(message):
    """Обработка изменения количества товара в корзине"""
    try:
        new_quantity = int(message.text)
        if new_quantity < 1:
            raise ValueError("Количество должно быть положительным числом.")
        if new_quantity > MAX_QUANTITY:
            bot.send_message(message.chat.id, f"Извините, но можно заказать не более {MAX_QUANTITY} шт.")
            return

        cart_items = cart_manager.get_cart(message.chat.id)
        item_index = user_manager.get_edit_item(message.chat.id)

        cart_manager.update_item_quantity(message.chat.id, item_index, new_quantity)
        bot.send_message(message.chat.id,
                         f"Количество для {cart_items[item_index]['product_name']} обновлено до {new_quantity}.")
        user_manager.set_state(message.chat.id, 'cart')
        handle_cart(message)  # Отображаем обновленную корзину

    except ValueError:
        bot.send_message(message.chat.id, "Введите корректное количество.")

def save_order(user_id, cart_items, total_price):
    """Сохраняет заказ в базе данных."""
    db_cursor = db.cursor()  # Переименовали cursor на db_cursor
    # Вставляем основной заказ в таблицу orders
    order_query = "INSERT INTO orders (user_id, total_price, order_date) VALUES (%s, %s, NOW())"
    db_cursor.execute(order_query, (user_id, total_price))
    order_id = db_cursor.lastrowid  # Получаем ID только что вставленного заказа

    # Вставляем каждый товар из корзины в таблицу order_items, связанной с orders
    order_item_query = "INSERT INTO order_items (order_id, product_name, product_price, quantity) VALUES (%s, %s, %s, %s)"
    for item in cart_items:
        db_cursor.execute(order_item_query, (order_id, item['product_name'], item['product_price'], item['quantity']))

    db.commit()  # Сохраняем изменения в базе данных
    logger.info(f"Заказ {order_id} успешно сохранен для пользователя {user_id}")

@bot.message_handler(func=lambda message: message.text == "Подтвердить заказ")
def handle_confirm_order(message):
    """Обработка подтверждения заказа"""
    logger.info(f"Пользователь {message.chat.id} подтвердил заказ")
    chat_id = message.chat.id  # Определяем chat_id для удобства
    cart_items = cart_manager.get_cart(chat_id)

    if not cart_items:
        bot.send_message(chat_id, "Ваша корзина пуста.")
        return

    # Получение данных пользователя
    user_info = user_manager.get_user_info_from_db(chat_id)
    fio = user_info.get('fio', 'Не указано')
    phone = user_info.get('phone', 'Не указан')
    address = user_info.get('address', 'Не указан')

    order_message = (
        f"Новый заказ от пользователя {chat_id}:\n"
        f"ФИО: {fio}\n"
        f"Телефон: {phone}\n"
        f"Адрес: {address}\n\n"
    )
    total_price = 0

    # Формирование сообщения для админа и подсчет общей суммы
    for item in cart_items:
        order_message += f"{item['product_name']} - {item['product_price']}₽ x{item['quantity']} = {item['total_price']}₽\n"
        total_price += item['total_price']

    order_message += f"\nИтого: {total_price}₽"

    # Отправка сообщения администратору
    try:
        bot.send_message(admin_chat_id, order_message)
        logger.info(f"Отправка сообщения администратору с ID {admin_chat_id}: {order_message}")
    except Exception as e:
        logger.error(f"Ошибка при отправке сообщения администратору: {e}")
        bot.send_message(chat_id, "Произошла ошибка при подтверждении заказа. Попробуйте позже.")
        return

    # Сохранение заказа в базу данных
    save_order(chat_id, cart_items, total_price)

    bot.send_message(chat_id, "Ваш заказ подтвержден. С вами свяжется менеджер для проведения оплаты заказа.")
    cart_manager.clear_cart(chat_id)
    user_manager.set_state(chat_id, 'main_menu_choose')
    main_menu(chat_id)

@bot.message_handler(func=lambda message: user_manager.get_state(message.chat.id) == 'order_history')
def handle_order_history(message):
    logger.info(f"Пользователь {message.chat.id} запросил историю заказов")
    chat_id = message.chat.id
    order_history = fetch_order_history(chat_id)

    if order_history:
        # Группируем заказы по order_id
        orders = {}
        for order in order_history:
            order_id = order['order_id']
            if order_id not in orders:
                orders[order_id] = {
                    'products': [],
                    'total_price': order['total_price'],
                    'order_date': order['order_date'],
                }
            # Добавляем продукт с его количеством
            product_info = f"{order['product_name']} х {order['quantity']}шт"
            orders[order_id]['products'].append(product_info)

        history_message = "📝 *Ваша история заказов:*\n\n"
        for order_id, details in orders.items():
            history_message += (f"*Заказ ID:* {order_id}\n"
                                f"*Продукты:*\n")
            for product in details['products']:
                history_message += f" - {product}\n"
            history_message += (f"*Сумма:* {details['total_price']}₽\n"
                                f"*Дата заказа:* {details['order_date'].strftime('%Y-%m-%d %H:%M')}\n\n")

        bot.send_message(chat_id, history_message, parse_mode="Markdown")
    else:
        bot.send_message(chat_id, "У вас нет заказов.")

    # Возвращаем в главное меню
    user_manager.set_state(chat_id, 'main_menu_choose')


def fetch_order_history(user_id):
    db_cursor = db.cursor(dictionary=True)
    query = """
        SELECT o.order_id, oi.product_name, oi.quantity, oi.product_price, oi.quantity * oi.product_price AS total_price, o.order_date
        FROM orders AS o
        JOIN order_items AS oi ON o.order_id = oi.order_id
        WHERE o.user_id = %s
        ORDER BY o.order_date DESC
    """
    db_cursor.execute(query, (user_id,))
    return db_cursor.fetchall()

@bot.message_handler(func=lambda message: user_manager.get_state(message.chat.id) == 'search')
def handle_search_start(message):
    """Инициализация поиска по каталогу."""
    logger.info(f"Пользователь {message.chat.id} запустил поиск по каталогу")
    bot.send_message(message.chat.id, "Введите название товара для поиска:")
    user_manager.set_state(message.chat.id, 'search_input')  # Устанавливаем новое состояние для ввода запроса

@bot.message_handler(func=lambda message: user_manager.get_state(message.chat.id) == 'search_input')
def handle_search_input(message):
    """Обработка ввода пользователя для поиска в каталоге."""
    search_query = message.text
    search_results = search_catalog_in_db(search_query)

    if not search_results:
        bot.send_message(message.chat.id, "Товары не найдены по запросу.")
        user_manager.set_state(message.chat.id, 'main_menu_choose')
        main_menu(message.chat.id)
        return

    # Отображаем первую страницу результатов поиска
    display_search_results(message.chat.id, search_results, page=0)

def search_catalog_in_db(search_query):
    """
    Функция выполняет поиск товаров в базе данных по названию, содержащему запрос.
    """
    # SQL-запрос для поиска в базе данных
    query = f"SELECT id, name, price FROM products WHERE name LIKE %s"
    cursor = db.cursor(dictionary=True)

    try:
        # Выполнение запроса и добавление символов `%` для поиска по подстроке
        cursor.execute(query, (f"%{search_query}%",))
        results = cursor.fetchall()
        return results
    except Exception as e:
        logger.error(f"Ошибка при выполнении поиска: {e}")
        return []
    finally:
        cursor.close()

def display_search_results(chat_id, search_results, page=0):
    """Отображение результатов поиска с пагинацией и возможностью перехода к товару."""
    total_results = len(search_results)
    start = page * PRODUCTS_PER_PAGE
    end = start + PRODUCTS_PER_PAGE
    results_page = search_results[start:end]

    # Формируем сообщение с результатами на текущей странице
    result_message = "Результаты поиска:\n"
    markup = InlineKeyboardMarkup()
    for idx, item in enumerate(results_page, start=start + 1):
        result_message += f"{idx}. {item['name']} - {item['price']}₽\n"
        markup.add(InlineKeyboardButton(f"{item['name']} - {item['price']}₽", callback_data=f"product_{item['id']}"))

    # Кнопки навигации по страницам
    if end < total_results:
        markup.add(InlineKeyboardButton("Следующая страница", callback_data=f"search_page_{page + 1}"))
    if page > 0:
        markup.add(InlineKeyboardButton("Предыдущая страница", callback_data=f"search_page_{page - 1}"))

    bot.send_message(chat_id, result_message, reply_markup=markup)
    user_manager.save_info(chat_id, search_results=search_results)

@bot.callback_query_handler(func=lambda call: call.data.startswith("search_page_"))
def handle_search_page(call):
    """Переход между страницами результатов поиска."""
    page = int(call.data.split('_')[2])
    search_results = user_manager.get_info(call.message.chat.id).get('search_results', [])

    if search_results:
        display_search_results(call.message.chat.id, search_results, page=page)
    else:
        bot.send_message(call.message.chat.id, "Ошибка при загрузке результатов поиска.")


# Обработка выбора "О Greenway"
@bot.message_handler(func=lambda message: message.text == "О Greenway")
def handle_about_greenway(message):
    user_manager.set_state(message.chat.id, 'about_company')  # Устанавливаем состояние

    # Список сообщений, которые будут отправлены подряд
    messages = [
        "Компания *Greenway* основана с целью 🤝 помочь людям заботиться об экологии.",
        "Мы предлагаем продукцию, которая снижает вредное воздействие на 🌿 окружающую среду.",
        "Наша продукция включает экотовары для 🏚 дома, 💄 косметику и многое другое.",
        "🤗 Поддерживая нас, вы поддерживаете экологически чистый образ жизни."
    ]

    # Отправка сообщений с паузой
    for msg in messages:
        bot.send_message(message.chat.id, msg, parse_mode="Markdown")
        time.sleep(1)  # Небольшая пауза между сообщениями (опционально)

    # Возвращение пользователя в главное меню
    user_manager.set_state(chat_id, 'main_menu_choose')
    main_menu(chat_id)

def check_connection(interval=30):
    """Периодически проверяет соединение и состояние пользователей."""
    while True:
        try:
            # Проверка соединения с сервером базы данных (например, MySQL)
            db.ping(reconnect=True, attempts=3, delay=5)

            # Проверка состояния каждого пользователя
            for chat_id in user_manager.states.keys():
                state = user_manager.get_state(chat_id)
                if not state or state == '':  # Если состояние отсутствует
                    return_to_main_menu(chat_id)

            time.sleep(interval)  # Задержка перед следующей проверкой

        except Exception as e:
            logger.error(f"Ошибка при проверке соединения: {e}")
            # Попробуем повторно подключиться к базе данных
            time.sleep(interval)

def return_to_main_menu(chat_id):
    # Переводит пользователя в главное меню с уведомлением
    logger.info(f"Возникли технические трудности у пользователя {message.chat.id}, он возвращен в главное меню")
    bot.send_message(chat_id, "Возникли технические трудности, вы возвращены в главное меню.")
    main_menu(chat_id)  # Переход в главное меню
    user_manager.set_state(chat_id, 'main_menu_choose')  # Сброс состояния пользователя

if __name__ == "__main__":
    # Запускаем поток для проверки состояния
    threading.Thread(target=check_connection, daemon=True).start()
    # Запуск основного процесса обработки сообщений
    bot.polling(none_stop=True)