# Используем базовый образ Python
FROM python:3.9-slim

# Устанавливаем рабочую директорию
WORKDIR /app

# Копируем файлы бота в контейнер
COPY . /app

# Устанавливаем зависимости
RUN pip install -r requirements.txt

# Задаем переменные окружения
ENV TELEGRAM_TOKEN=${TELEGRAM_TOKEN}
ENV ADMIN_CHAT_ID=${ADMIN_CHAT_ID}
ENV MODERATOR_IDS=${MODERATOR_IDS}
ENV DB_HOST=${DB_HOST}
ENV DB_USER=${DB_USER}
ENV DB_PASSWORD=${DB_PASSWORD}
ENV DB_NAME=${DB_NAME}

# Запускаем бота
CMD ["python", "main.py"]