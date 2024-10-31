from typing import Dict, Any
import logging

logging.basicConfig(level=logging.INFO)

class UserManager:
    def __init__(self, cursor, db):
        self.cursor = cursor
        self.db = db
        self.states: Dict[int, str] = {}
        self.info: Dict[int, Dict[str, Any]] = {}
        self.edit_items: Dict[int, int] = {}

    def get_user_info_from_db(self, chat_id: int) -> Dict[str, Any]:
        """Получение информации о пользователе из базы данных"""
        logging.info(f"Получение данных для пользователя {chat_id}")
        try:
            self.cursor.execute("SELECT fio, phone, address FROM users WHERE telegram_id = %s", (chat_id,))
            result = self.cursor.fetchone()
            logging.info(f"Данные пользователя {chat_id}: {result}")
            if result:
                fio, phone, address = result
                return {'fio': fio, 'phone': phone, 'address': address}
        except Exception as e:
            logging.error(f"Ошибка при запросе данных пользователя: {e}")
        return {}

    def save_user_to_db(self, chat_id: int, fio: str = None, phone: str = None, address: str = None):
        """Сохранение или обновление информации о пользователе в базе данных"""
        try:
            self.cursor.execute("SELECT user_id FROM users WHERE telegram_id = %s", (chat_id,))
            user = self.cursor.fetchone()

            if user:
                self.cursor.execute(""" 
                    UPDATE users
                    SET fio = %s, phone = %s, address = %s
                    WHERE telegram_id = %s
                """, (fio, phone, address, chat_id))
            else:
                self.cursor.execute(""" 
                    INSERT INTO users (telegram_id, fio, phone, address)
                    VALUES (%s, %s, %s, %s)
                """, (chat_id, fio, phone, address))

            self.db.commit()
        except Exception as e:
            logging.error(f"Ошибка при сохранении данных пользователя: {e}")

    def set_state(self, chat_id: int, state: str):
        self.states[chat_id] = state

    def get_state(self, chat_id: int) -> str:
        return self.states.get(chat_id, '')

    def save_info(self, chat_id: int, **kwargs):
        """Сохранение произвольной информации о пользователе."""
        if chat_id not in self.info:
            self.info[chat_id] = {}
        self.info[chat_id].update(kwargs)

    def get_info(self, chat_id: int) -> Dict[str, Any]:
        return self.info.get(chat_id, {})

    def set_edit_item(self, chat_id: int, item_index: int):
        """Сохраняет индекс товара, который пользователь редактирует"""
        self.edit_items[chat_id] = item_index

    def get_edit_item(self, chat_id: int) -> int:
        """Получает индекс товара, который пользователь редактирует"""
        return self.edit_items.get(chat_id, None)

    def clear_edit_item(self, chat_id: int):
        """Очищает информацию о редактируемом товаре"""
        if chat_id in self.edit_items:
            del self.edit_items[chat_id]

    def get_all_users(self):
        """Возвращает всех пользователей из базы данных."""
        users = []
        try:
            self.cursor.execute("SELECT telegram_id FROM users")
            results = self.cursor.fetchall()
            logging.info("Получены данные всех пользователей.")
            for row in results:
                users.append(row[0])  # Предполагаем, что telegram_id — это первый элемент в строке
        except Exception as e:
            logging.error(f"Ошибка при получении всех пользователей: {e}")
        return users

    def get_all_user_ids(self):
        """Возвращает список всех идентификаторов пользователей."""
        return self.get_all_users()  # Теперь этот метод корректен
