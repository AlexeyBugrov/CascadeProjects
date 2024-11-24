from telegram.ext import Updater, MessageHandler, Filters, CallbackContext
from telegram import Update
import logging
from typing import List, Dict
import pandas as pd
import sys

from config import TELEGRAM_BOT_TOKEN, OPENAI_API_KEY, PICKLE_FILE_PATH
from utils import process_message_with_chatgpt, create_news_entry, save_to_pickle, load_from_pickle, verify_telegram_token, verify_openai_key

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Глобальный список для хранения обработанных новостей
news_data: List[Dict] = []

def handle_message(update: Update, context: CallbackContext):
    """
    Обработчик входящих сообщений от Telegram
    """
    try:
        message = update.message.text
        chat_id = update.message.chat_id
        source = f"{update.message.chat.title if update.message.chat.title else 'Private Chat'}"
        
        # Обработка сообщения через ChatGPT
        chatgpt_response = process_message_with_chatgpt(message, OPENAI_API_KEY)
        
        if chatgpt_response:
            # Создание записи новости
            news_entry = create_news_entry(message, source, chatgpt_response)
            news_data.append(news_entry)
            
            # Сохранение данных
            save_to_pickle(news_data, PICKLE_FILE_PATH)
            
            # Отправка подтверждения
            response_text = f"✅ Новость обработана:\nКомпания: {chatgpt_response['company_name']}\n" \
                          f"Тикер: {chatgpt_response['ticker']}\n" \
                          f"Влияние: {chatgpt_response['impact_score']}"
            context.bot.send_message(chat_id=chat_id, text=response_text)
        
        else:
            context.bot.send_message(
                chat_id=chat_id,
                text="❌ Произошла ошибка при обработке сообщения."
            )
            
    except Exception as e:
        logger.error(f"Ошибка при обработке сообщения: {str(e)}")
        context.bot.send_message(
            chat_id=chat_id,
            text="❌ Произошла ошибка при обработке сообщения."
        )

def main():
    """
    Основная функция для запуска бота
    """
    try:
        # Проверка токенов перед запуском
        logger.info("Проверка токенов...")
        
        if not verify_telegram_token(TELEGRAM_BOT_TOKEN):
            logger.error("Неверный токен Telegram. Проверьте значение TELEGRAM_BOT_TOKEN в config.py")
            sys.exit(1)
            
        if not verify_openai_key(OPENAI_API_KEY):
            logger.error("Неверный ключ OpenAI API. Проверьте значение OPENAI_API_KEY в config.py")
            sys.exit(1)
            
        logger.info("Проверка токенов успешно завершена")
        
        # Загрузка существующих данных, если есть
        global news_data
        existing_data = load_from_pickle(PICKLE_FILE_PATH)
        if not existing_data.empty:
            news_data = existing_data.to_dict('records')
        
        # Инициализация бота
        updater = Updater(TELEGRAM_BOT_TOKEN)
        dp = updater.dispatcher
        
        # Добавление обработчика сообщений
        dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))
        
        # Запуск бота
        logger.info("Бот запущен и готов к работе")
        updater.start_polling()
        updater.idle()
        
    except Exception as e:
        logger.error(f"Ошибка при запуске бота: {str(e)}")
        sys.exit(1)

if __name__ == '__main__':
    main()
