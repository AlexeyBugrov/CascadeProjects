# Системные импорты
import os
import sys
import logging
import traceback
import subprocess
import uuid
import atexit
import platform
import re
import time
import requests

# Telegram импорты
from telegram import Update
from telegram.ext import (
    Application, 
    CommandHandler, 
    MessageHandler, 
    CallbackContext
)

# Локальные импорты
from utils.media_processor import MediaProcessor
from utils.transcriber import Transcriber
from config import (
    TRANSCRIPT_BOT_TOKEN, 
    TEMP_DIR, 
    OUTPUT_DIR, 
    FFMPEG_PATH
)

# Настройка логирования
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot_debug.log', encoding='utf-8', mode='w'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Ensure directories exist
TEMP_DIR = "temp"
OUTPUT_DIR = "output"
os.makedirs(TEMP_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Логирование версий библиотек
def log_library_versions():
    """Логирование версий используемых библиотек"""
    try:
        import whisper
        import torch
        import yt_dlp
        import openai
        
        logger.info("🔍 Версии библиотек:")
        logger.info(f"   Python: {sys.version}")
        logger.info(f"   Whisper: {whisper.__version__}")
        logger.info(f"   PyTorch: {torch.__version__}")
        logger.info(f"   yt-dlp: {yt_dlp.version.__version__}")
        logger.info(f"   OpenAI: {openai.__version__}")
    except Exception as e:
        logger.error(f"❌ Ошибка при логировании версий библиотек: {e}")
        logger.error(traceback.format_exc())

# Диагностика окружения
def log_system_environment():
    """Подробная диагностика системного окружения"""
    logger.info("🖥️ Системная диагностика:")
    logger.info(f"   ОС: {sys.platform}")
    logger.info(f"   Кодировка файловой системы: {sys.getfilesystemencoding()}")
    logger.info(f"   Текущая директория: {os.getcwd()}")
    logger.info(f"   Путь Python: {sys.executable}")
    
    # Проверка доступности CUDA
    try:
        import torch
        logger.info(f"   CUDA доступен: {torch.cuda.is_available()}")
        if torch.cuda.is_available():
            logger.info(f"   Устройство CUDA: {torch.cuda.get_device_name(0)}")
    except Exception as e:
        logger.warning(f"   Ошибка проверки CUDA: {e}")

def check_ffmpeg_installation():
    """
    Расширенная проверка установки FFmpeg
    """
    try:
        # Путь к FFmpeg
        ffmpeg_dir = os.path.join(os.getcwd(), 'ffmpeg', 'bin')
        ffmpeg_path = os.path.join(ffmpeg_dir, 'ffmpeg.exe')
        ffprobe_path = os.path.join(ffmpeg_dir, 'ffprobe.exe')
        
        logger.info(f"🔍 Проверка FFmpeg:")
        logger.info(f"   Путь к FFmpeg: {ffmpeg_path}")
        logger.info(f"   Путь к FFprobe: {ffprobe_path}")
        
        # Проверка существования файлов с подробной диагностикой
        def check_file_exists(path):
            if not os.path.exists(path):
                logger.error(f"❌ Файл не найден: {path}")
                logger.error(f"   Содержимое директории: {os.listdir(os.path.dirname(path))}")
                return False
            return True
        
        if not (check_file_exists(ffmpeg_path) and check_file_exists(ffprobe_path)):
            raise FileNotFoundError("FFmpeg или FFprobe не найдены")
        
        # Проверка версии с расширенной диагностикой
        try:
            result = subprocess.run(
                [ffmpeg_path, '-version'], 
                capture_output=True, 
                text=True, 
                check=True
            )
            logger.info(f"✅ Версия FFmpeg:\n{result.stdout}")
        except subprocess.CalledProcessError as e:
            logger.error(f"❌ Ошибка при проверке версии FFmpeg: {e}")
            logger.error(f"   Stderr: {e.stderr}")
            raise
        
        return ffmpeg_dir
    
    except Exception as e:
        logger.error(f"❌ Критическая ошибка при проверке FFmpeg: {e}")
        logger.error(traceback.format_exc())
        raise

def main():
    """Основная функция запуска бота с расширенной диагностикой"""
    try:
        # Логирование системной информации
        log_system_environment()
        log_library_versions()
        
        # Проверка FFmpeg перед стартом
        ffmpeg_location = check_ffmpeg_installation()
        
        # Инициализация MediaProcessor с корректным путем к FFmpeg
        media_processor = MediaProcessor(TEMP_DIR, ffmpeg_location=ffmpeg_location)
        transcriber = Transcriber(TRANSCRIPT_BOT_TOKEN)
        
        # Создание временных директорий с логированием
        os.makedirs(TEMP_DIR, exist_ok=True)
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        logger.info(f"✅ Временная директория: {TEMP_DIR}")
        logger.info(f"✅ Директория вывода: {OUTPUT_DIR}")
        
        # Инициализация бота
        application = Application.builder().token(TRANSCRIPT_BOT_TOKEN).build()
        
        # Регистрация обработчиков
        application.add_handler(CommandHandler('start', start_command))
        application.add_handler(CommandHandler('help', help_command))
        application.add_handler(MessageHandler(filters.Document | filters.Video | filters.Audio, process_audio_file))
        application.add_handler(MessageHandler(filters.TEXT, handle_message))
        
        # Регистрация обработчика завершения
        atexit.register(cleanup_temp_files)
        
        logger.info("🤖 Бот TranscriptAI запущен")
        application.run_polling(drop_pending_updates=True)
    
    except Exception as e:
        logger.critical(f"❌ Критическая ошибка при запуске бота: {e}")
        logger.critical(traceback.format_exc())
        print(f"Ошибка: {e}")
        print(traceback.format_exc())
        sys.exit(1)

def is_valid_youtube_url(url: str) -> bool:
    """Проверка валидности YouTube ссылки"""
    youtube_patterns = [
        r'(https?://)?(www\.)?(youtube|youtu|youtube-nocookie)\.(com|be)/(watch\?v=|embed/|v/|.+\?v=)?([^&=%\?]{11})',
        r'youtu\.be/([^&=%\?]{11})'
    ]
    
    for pattern in youtube_patterns:
        if re.match(pattern, url):
            return True
    return False

async def start_command(update: Update, context: CallbackContext) -> None:
    """Обработчик команды /start"""
    user = update.effective_user
    welcome_message = (
        f"Привет, {user.mention_markdown_v2()}\\! 👋\n\n"
        "Я бот для транскрибации и анализа аудио/видео контента 🎧🤖\n\n"
        "Что я умею:\n"
        "• Транскрибировать аудио и видео файлы\n"
        "• Генерировать структурированные заметки\n"
        "• Анализировать содержимое медиафайлов\n\n"
        "Просто отправь мне файл или ссылку на YouTube\\!"
    )
    await update.message.reply_markdown_v2(welcome_message)

async def help_command(update: Update, context: CallbackContext) -> None:
    """Обработчик команды /help"""
    help_message = (
        "*Помощь по использованию бота:*\n\n"
        "• Отправьте аудио или видео файл для транскрибации\n"
        "• Можно прислать ссылку на YouTube видео\n"
        "• Поддерживаются форматы: MP3, MP4, WAV, WEBM и другие\n\n"
        "*Команды:*\n"
        "/start \\- начать работу с ботом\n"
        "/help \\- показать справку"
    )
    await update.message.reply_markdown_v2(help_message)

async def handle_message(update: Update, context: CallbackContext) -> None:
    """Обработчик входящих сообщений"""
    message = update.message
    
    if not message:
        await update.message.reply_text("❌ Не удалось обработать сообщение")
        return
    
    # Проверяем текстовое сообщение
    if message.text:
        # Проверка на YouTube ссылку
        if is_valid_youtube_url(message.text):
            await handle_youtube_link(update, context)
        else:
            await message.reply_text(
                "🤔 Отправьте, пожалуйста, файл или корректную ссылку на YouTube"
            )
    # Проверяем медиафайлы
    elif message.document or message.video or message.audio:
        await process_audio_file(update, context)
    else:
        await message.reply_text(
            "❓ Я не могу обработать этот тип сообщения. Отправьте аудио/видео файл или ссылку на YouTube"
        )

async def process_audio_file(update: Update, context: CallbackContext) -> None:
    """Обработка аудио/видео файла"""
    try:
        # Получаем файл
        if update.message.document:
            file = update.message.document
        elif update.message.video:
            file = update.message.video
        elif update.message.audio:
            file = update.message.audio
        else:
            await update.message.reply_text("❌ Неподдерживаемый тип файла")
            return
        
        # Проверяем размер файла
        if file.file_size > 50 * 1024 * 1024:  # 50 МБ
            await update.message.reply_text("❌ Файл слишком большой. Максимальный размер - 50 МБ")
            return
        
        # Логируем информацию о файле
        logger.info(f"Получен файл: {file.file_name}, размер: {file.file_size} байт")
        
        # Отправляем сообщение о начале обработки
        processing_msg = await update.message.reply_text("🔄 Начинаю обработку файла...")
        
        # Скачиваем файл
        file_path = os.path.join(TEMP_DIR, f"{uuid.uuid4()}_{file.file_name}")
        file_obj = await file.get_file()
        await file_obj.download_to_drive(file_path)
        
        # Проверяем расширение файла
        file_extension = os.path.splitext(file_path)[1].lower()
        supported_extensions = ['.mp3', '.wav', '.mp4', '.avi', '.webm']
        
        if file_extension not in supported_extensions:
            os.remove(file_path)
            await processing_msg.delete()
            await update.message.reply_text(f"❌ Неподдерживаемый формат файла: {file_extension}")
            return
        
        # Инициализируем процессоры
        media_processor = MediaProcessor(TEMP_DIR)
        transcriber = Transcriber()
        
        # Конвертируем файл в подходящий формат
        converted_file = media_processor.convert_to_wav(file_path)
        
        # Транскрибируем
        transcription_result = transcriber.transcribe(converted_file)
        
        # Формируем ответ
        if transcription_result:
            # Отправляем текст транскрипции
            await update.message.reply_text(f"📝 Транскрипция:\n{transcription_result}")
            
            # Сохраняем транскрипцию в файл
            output_file = os.path.join(OUTPUT_DIR, f"{uuid.uuid4()}_transcript.txt")
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(transcription_result)
            
            logger.info(f"Транскрипция сохранена: {output_file}")
        else:
            await update.message.reply_text("❌ Не удалось транскрибировать файл")
        
        # Удаляем временные файлы
        os.remove(file_path)
        os.remove(converted_file)
        
        # Удаляем сообщение о процессинге
        await processing_msg.delete()
    
    except Exception as e:
        logger.error(f"Ошибка при обработке файла: {e}", exc_info=True)
        await update.message.reply_text(f"❌ Критическая ошибка при обработке файла: {e}")
        # Логируем полный стек вызова
        traceback.print_exc()

async def handle_youtube_link(update: Update, context: CallbackContext) -> None:
    """Обработка YouTube ссылки"""
    try:
        url = update.message.text
        
        # Проверяем валидность ссылки
        if not is_valid_youtube_url(url):
            await update.message.reply_text("❌ Некорректная ссылка на YouTube")
            return
        
        # Логируем ссылку
        logger.info(f"Получена YouTube ссылка: {url}")
        
        # Отправляем сообщение о начале обработки
        processing_msg = await update.message.reply_text("🔄 Начинаю загрузку и обработку видео...")
        
        # Инициализируем процессоры
        media_processor = MediaProcessor(TEMP_DIR)
        transcriber = Transcriber()
        
        # Скачиваем видео
        try:
            video_path = media_processor.download_youtube_video(url)
        except Exception as download_error:
            logger.error(f"Ошибка загрузки видео: {download_error}", exc_info=True)
            await processing_msg.delete()
            await update.message.reply_text(f"❌ Не удалось загрузить видео: {download_error}")
            return
        
        # Проверяем длительность видео
        video_duration = media_processor.get_video_duration(video_path)
        max_duration = 600  # 10 минут
        
        if video_duration > max_duration:
            os.remove(video_path)
            await processing_msg.delete()
            await update.message.reply_text(f"❌ Видео слишком длинное. Максимальная длительность - {max_duration/60} минут")
            return
        
        # Извлекаем аудио
        audio_path = media_processor.extract_audio(video_path)
        
        # Транскрибируем
        transcription_result = transcriber.transcribe(audio_path)
        
        # Формируем ответ
        if transcription_result:
            # Отправляем текст транскрипции
            await update.message.reply_text(f"📝 Транскрипция:\n{transcription_result}")
            
            # Сохраняем транскрипцию в файл
            output_file = os.path.join(OUTPUT_DIR, f"{uuid.uuid4()}_youtube_transcript.txt")
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(transcription_result)
            
            logger.info(f"Транскрипция YouTube видео сохранена: {output_file}")
        else:
            await update.message.reply_text("❌ Не удалось транскрибировать видео")
        
        # Очищаем временные файлы
        os.remove(video_path)
        os.remove(audio_path)
        
        # Удаляем сообщение о процессинге
        await processing_msg.delete()
    
    except Exception as e:
        logger.error(f"Ошибка при обработке YouTube ссылки: {e}", exc_info=True)
        await update.message.reply_text(f"❌ Критическая ошибка при обработке ссылки: {e}")
        # Логируем полный стек вызова
        traceback.print_exc()

async def send_to_obsimatic(notes_path: str):
    """Send notes to ObsiMatic bot"""
    try:
        with open(notes_path, 'rb') as f:
            files = {'document': f}
            response = requests.post(
                f'https://api.telegram.org/bot{OBSIMATIC_BOT_TOKEN}/sendDocument',
                data={'chat_id': '@ObsiMatic'},
                files=files
            )
            response.raise_for_status()
    except Exception as e:
        logger.error(f"Error sending to ObsiMatic: {str(e)}")
        raise

async def cleanup_temp_files(audio_path: str):
    """Очистка временных файлов"""
    try:
        # Получаем директорию файла
        temp_dir = os.path.dirname(audio_path)
        
        # Логируем начало очистки
        logger.info(f"🧹 Начинаем очистку временных файлов в директории: {temp_dir}")
        
        # Получаем список всех файлов
        files_to_remove = []
        for filename in os.listdir(temp_dir):
            file_path = os.path.join(temp_dir, filename)
            
            # Проверяем, что это файл
            if os.path.isfile(file_path):
                # Удаляем файлы старше 1 часа
                file_age = time.time() - os.path.getctime(file_path)
                if file_age > 3600:  # 1 час в секундах
                    files_to_remove.append(file_path)
        
        # Удаляем файлы
        for file_path in files_to_remove:
            try:
                os.remove(file_path)
                logger.info(f"🗑️ Удален файл: {file_path}")
            except Exception as remove_error:
                logger.error(f"❌ Ошибка при удалении файла {file_path}: {remove_error}")
        
        logger.info(f"✅ Очистка временных файлов завершена. Удалено файлов: {len(files_to_remove)}")
    
    except Exception as e:
        logger.error(f"❌ Ошибка при очистке временных файлов: {str(e)}")

def cleanup_on_exit():
    """Очистка всех временных файлов при завершении работы бота"""
    try:
        temp_dir = TEMP_DIR
        logger.info(f"🧹 Полная очистка временной директории: {temp_dir}")
        
        # Удаляем все файлы в директории
        for filename in os.listdir(temp_dir):
            file_path = os.path.join(temp_dir, filename)
            try:
                if os.path.isfile(file_path):
                    os.remove(file_path)
                    logger.info(f"🗑️ Удален файл: {file_path}")
            except Exception as remove_error:
                logger.error(f"❌ Ошибка при удалении файла {file_path}: {remove_error}")
        
        logger.info("✅ Полная очистка временной директории завершена")
    
    except Exception as e:
        logger.error(f"❌ Ошибка при полной очистке: {str(e)}")

# Регистрируем обработчик очистки при завершении
import atexit
atexit.register(cleanup_on_exit)

if __name__ == '__main__':
    try:
        # Инициализация логирования
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        # Запуск основной функции
        main()
    except Exception as e:
        logger.critical(f"Критическая ошибка при запуске: {e}")
        logger.critical(traceback.format_exc())
        print(f"Ошибка: {e}")
        print(traceback.format_exc())
