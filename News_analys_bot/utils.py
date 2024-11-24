import openai
import pandas as pd
from datetime import datetime
import pickle
from typing import Dict, List, Union
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def process_message_with_chatgpt(message: str, api_key: str) -> Dict[str, Union[str, int]]:
    """
    Обработка сообщения с помощью ChatGPT для извлечения необходимой информации
    
    Args:
        message (str): Текст сообщения для анализа
        api_key (str): API ключ для OpenAI
        
    Returns:
        Dict: Словарь с извлеченной информацией
    """
    try:
        openai.api_key = api_key
        
        prompt = f"""Проанализируй следующую новость и выдели:
        1. Тикер компании
        2. Название компании
        3. Краткую сводку новости
        4. Оценку влияния на котировки по шкале от -2 до 2, где:
           -2: крайне негативно
           -1: негативно
           0: нейтрально
           1: позитивно
           2: крайне позитивно
        
        Новость: {message}
        
        Формат ответа должен быть в JSON:
        {{
            "ticker": "тикер",
            "company_name": "название компании",
            "summary": "краткая сводка",
            "impact_score": число от -2 до 2
        }}
        """
        
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3
        )
        
        # Извлекаем JSON из ответа
        import json
        result = json.loads(response.choices[0].message.content)
        return result
    
    except Exception as e:
        logger.error(f"Ошибка при обработке сообщения через ChatGPT: {str(e)}")
        return None

def create_news_entry(message: str, source: str, chatgpt_response: Dict) -> Dict:
    """
    Создание записи новости с полной информацией
    
    Args:
        message (str): Исходное сообщение
        source (str): Источник сообщения
        chatgpt_response (Dict): Обработанный ответ от ChatGPT
        
    Returns:
        Dict: Полная запись новости
    """
    return {
        'timestamp': datetime.now().isoformat(),
        'source': source,
        'original_message': message,
        'ticker': chatgpt_response.get('ticker'),
        'company_name': chatgpt_response.get('company_name'),
        'summary': chatgpt_response.get('summary'),
        'impact_score': chatgpt_response.get('impact_score')
    }

def save_to_pickle(data: List[Dict], filepath: str):
    """
    Сохранение данных в pickle файл
    
    Args:
        data (List[Dict]): Список записей для сохранения
        filepath (str): Путь к файлу для сохранения
    """
    try:
        df = pd.DataFrame(data)
        with open(filepath, 'wb') as f:
            pickle.dump(df, f)
        logger.info(f"Данные успешно сохранены в {filepath}")
    except Exception as e:
        logger.error(f"Ошибка при сохранении данных: {str(e)}")

def load_from_pickle(filepath: str) -> pd.DataFrame:
    """
    Загрузка данных из pickle файла
    
    Args:
        filepath (str): Путь к файлу для загрузки
        
    Returns:
        pd.DataFrame: Загруженные данные
    """
    try:
        with open(filepath, 'rb') as f:
            return pickle.load(f)
    except Exception as e:
        logger.error(f"Ошибка при загрузке данных: {str(e)}")
        return pd.DataFrame()

def verify_telegram_token(token: str) -> bool:
    """
    Проверка валидности токена Telegram
    
    Args:
        token (str): Токен для проверки
        
    Returns:
        bool: True если токен валидный, False если нет
    """
    try:
        from telegram.ext import Updater
        updater = Updater(token)
        bot_info = updater.bot.get_me()
        logger.info(f"Успешное подключение к боту: {bot_info.first_name} (@{bot_info.username})")
        return True
    except Exception as e:
        logger.error(f"Ошибка проверки токена Telegram: {str(e)}")
        return False

def verify_openai_key(api_key: str) -> bool:
    """
    Проверка валидности ключа OpenAI
    
    Args:
        api_key (str): Ключ API для проверки
        
    Returns:
        bool: True если ключ валидный, False если нет
    """
    try:
        import openai
        openai.api_key = api_key
        # Пробуем сделать тестовый запрос
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": "Test message"}],
            max_tokens=5
        )
        logger.info("Успешное подключение к OpenAI API")
        return True
    except Exception as e:
        logger.error(f"Ошибка проверки ключа OpenAI: {str(e)}")
        return False
