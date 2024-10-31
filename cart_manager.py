from typing import List, Dict, Any

class CartManager:
    def __init__(self):
        self.cart: Dict[int, List[Dict[str, Any]]] = {}

    def add_to_cart(self, chat_id: int, product_id: int, product_name: str, product_price: float, quantity: int):
        if chat_id not in self.cart:
            self.cart[chat_id] = []
        # Проверяем, если товар уже в корзине, обновляем количество
        for item in self.cart[chat_id]:
            if item['product_id'] == product_id:
                item['quantity'] += quantity
                item['total_price'] = item['quantity'] * item['product_price']
                return
        # Если товара еще нет в корзине, добавляем его
        self.cart[chat_id].append({
            'product_id': product_id,
            'product_name': product_name,
            'product_price': product_price,
            'quantity': quantity,
            'total_price': product_price * quantity
        })

    def get_cart(self, chat_id: int) -> List[Dict[str, Any]]:
        return self.cart.get(chat_id, [])

    def clear_cart(self, chat_id: int):
        if chat_id in self.cart:
            del self.cart[chat_id]

    def update_item_quantity(self, chat_id: int, item_index: int, new_quantity: int):
        """Обновляет количество указанного товара в корзине пользователя."""
        if chat_id in self.cart and 0 <= item_index < len(self.cart[chat_id]):
            self.cart[chat_id][item_index]['quantity'] = new_quantity
            # Пересчитываем общую цену за товар с учетом нового количества
            self.cart[chat_id][item_index]['total_price'] = self.cart[chat_id][item_index]['product_price'] * new_quantity

    def remove_item(self, chat_id: int, item_index: int):
        """Удаляет указанный товар из корзины пользователя."""
        if chat_id in self.cart and 0 <= item_index < len(self.cart[chat_id]):
            del self.cart[chat_id][item_index]