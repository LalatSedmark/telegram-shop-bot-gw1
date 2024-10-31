from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
import pandas as pd
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time

# Настройка опций Chrome
options = Options()
options.add_argument("--disable-notifications")
options.add_argument("--disable-geolocation")
options.add_argument("--disable-popup-blocking")

# Запускаем Chrome с заданными опциями
service = Service(ChromeDriverManager().install())
driver = webdriver.Chrome(service=service, options=options)

# Открываем страницу каталога
catalog_url = 'https://greenwayglobal.com/shop/accessories'
driver.get(catalog_url)

# Добавьте небольшую задержку для завершения загрузки страницы
time.sleep(5)

# Ищем ссылки на товары на странице
product_elements = []  # Инициализация переменной
try:
    product_elements = WebDriverWait(driver, 10).until(
        EC.presence_of_all_elements_located((By.CLASS_NAME, 'productItem__name')))  # Измените класс на правильный
    print("Элементы продуктов загружены.")
except Exception as e:
    print(f"Ошибка при поиске элементов продуктов: {e}")

# Проверяем, были ли найдены элементы
if not product_elements:
    print("Не удалось найти элементы продуктов. Завершение программы.")
    driver.quit()
    exit()

# Сохраняем ссылки на товары
product_links = []
base_url = 'https://greenwayglobal.com'
for element in product_elements:
    link = element.get_attribute('href')
    if link:
        # Проверяем, если ссылка относительная, добавляем базовый URL
        full_link = base_url + link if link.startswith('/') else link
        product_links.append(full_link)
    else:
        print(f"Элемент не имеет ссылки: {element}")

print(f"Найдено {len(product_links)} товаров.")

# Список для хранения данных
data = []

# Парсим каждую страницу товара
for product_url in product_links:
    driver.get(product_url)

    # Явное ожидание для загрузки страницы товара
    try:
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CLASS_NAME, 'productInfo__title')))

        # Парсим название
        title = driver.find_element(By.CLASS_NAME, 'productInfo__title').text

        # Парсим цену
        price = driver.find_element(By.CLASS_NAME, 'productPrice__price').text

        # Парсим описание
        description = driver.find_element(By.CLASS_NAME, 'productInfo__description').text

        # Парсим ссылку на изображение
        try:
            image_element = driver.find_element(By.CLASS_NAME, 'vue-lb-modal-image')
            image_url = image_element.get_attribute('src')

            # Если атрибут 'src' пуст, попробуем взять 'data-src'
            if not image_url:
                image_url = image_element.get_attribute('data-src')
        except Exception as e:
            print(f"Ошибка при парсинге изображения: {e}")

        # Добавляем данные в список
        data.append({
            'Название': title,
            'Цена': price,
            'Описание': description,
            'Ссылка на фото': image_url
        })

    except Exception as e:
        print(f"Ошибка на странице {product_url}: {e}")

# Закрываем браузер
driver.quit()

# Сохраняем данные в Excel
df = pd.DataFrame(data)
df.to_excel('products_selenium.xlsx', index=False)

print("Данные успешно сохранены в файл products_selenium.xlsx")