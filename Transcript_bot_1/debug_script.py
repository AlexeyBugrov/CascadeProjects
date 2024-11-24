import sys
import os
import platform
import subprocess
import logging

# Настройка логирования
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('system_debug.log', encoding='utf-8', mode='w'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

def check_system_environment():
    """Полная диагностика системного окружения"""
    logger.info("🔍 Системная диагностика")
    
    # Базовая информация о системе
    logger.info(f"ОС: {platform.platform()}")
    logger.info(f"Python версия: {sys.version}")
    logger.info(f"Архитектура: {platform.architecture()[0]}")
    logger.info(f"Текущий путь: {os.getcwd()}")
    logger.info(f"Путь Python: {sys.executable}")
    
    # Проверка установленных библиотек
    def check_library(name):
        try:
            __import__(name)
            logger.info(f"✅ {name} установлена")
            return True
        except ImportError:
            logger.warning(f"❌ {name} не установлена")
            return False
    
    libraries = [
        'torch', 'whisper', 'openai', 'yt_dlp', 
        'telegram', 'soundfile', 'numpy', 'scipy'
    ]
    
    for lib in libraries:
        check_library(lib)
    
    # Проверка FFmpeg
    try:
        result = subprocess.run(['ffmpeg', '-version'], 
                                capture_output=True, 
                                text=True, 
                                check=True)
        logger.info(f"FFmpeg версия:\n{result.stdout}")
    except Exception as e:
        logger.error(f"Ошибка проверки FFmpeg: {e}")
    
    # Проверка CUDA (для PyTorch)
    try:
        import torch
        logger.info(f"CUDA доступен: {torch.cuda.is_available()}")
        if torch.cuda.is_available():
            logger.info(f"CUDA устройство: {torch.cuda.get_device_name(0)}")
    except Exception as e:
        logger.warning(f"Ошибка проверки CUDA: {e}")

def check_telegram_bot_config():
    """Проверка конфигурации Telegram бота"""
    try:
        from config import TRANSCRIPT_BOT_TOKEN
        logger.info("✅ Токен Telegram бота загружен")
    except Exception as e:
        logger.error(f"❌ Ошибка загрузки токена: {e}")

def check_openai_config():
    """Проверка конфигурации OpenAI"""
    try:
        from config import OPENAI_API_KEY
        logger.info("✅ API ключ OpenAI загружен")
    except Exception as e:
        logger.error(f"❌ Ошибка загрузки ключа OpenAI: {e}")

def main():
    """Основная функция диагностики"""
    check_system_environment()
    check_telegram_bot_config()
    check_openai_config()

if __name__ == '__main__':
    main()
