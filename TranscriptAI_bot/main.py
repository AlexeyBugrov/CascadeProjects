import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, JobQueue
from utils.audio_processor import AudioProcessor
from utils.transcriber import Transcriber
from utils.telegram_sender import TelegramSender
from utils.youtube_info import YouTubeInfo
import config
import aiohttp
import time
from typing import Optional, Dict, Any
import aiofiles
from telegram.constants import ChatAction
from utils.pdf_converter import generate_pdf
import signal
import asyncio
import sys
import re
import yt_dlp
from datetime import datetime, timedelta

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Initialize processors
audio_processor = AudioProcessor(temp_dir=config.TEMP_DIRECTORY)
youtube_info = YouTubeInfo()
transcriber = Transcriber()
telegram_sender = TelegramSender(
    transcript_bot_token=config.TRANSCRIPT_BOT_TOKEN,
    obsimatic_bot_token=config.OBSIMATIC_BOT_TOKEN,
    group_chat_id=config.GROUP_CHAT_ID
)

MAX_VIDEO_SIZE_MB = config.REGULAR_SIZE_LIMIT_MB
MAX_AUDIO_SIZE_MB = config.REGULAR_SIZE_LIMIT_MB

# Global variable to track shutdown state
is_shutting_down = False

async def shutdown(signal_type, loop, application):
    """Cleanup and shutdown the bot gracefully"""
    global is_shutting_down
    
    if is_shutting_down:
        return
        
    is_shutting_down = True
    
    logger.info(f"\nReceived signal {signal_type.name}...")
    logger.info("Cleaning up resources...")
    
    # Clean up temp directories
    try:
        if os.path.exists(config.TEMP_DIRECTORY):
            for file in os.listdir(config.TEMP_DIRECTORY):
                file_path = os.path.join(config.TEMP_DIRECTORY, file)
                try:
                    if os.path.isfile(file_path):
                        os.unlink(file_path)
                except Exception as e:
                    logger.error(f"Error deleting {file_path}: {e}")
    except Exception as e:
        logger.error(f"Error cleaning temp directory: {e}")

    # Stop the application
    try:
        logger.info("Stopping the bot...")
        await application.stop()
        await application.shutdown()
    except Exception as e:
        logger.error(f"Error stopping application: {e}")

    # Cancel all running tasks
    tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    for task in tasks:
        task.cancel()
    
    logger.info(f"Cancelling {len(tasks)} outstanding tasks...")
    await asyncio.gather(*tasks, return_exceptions=True)
    
    loop.stop()
    logger.info("Shutdown complete!")

def handle_exception(loop, context):
    """Handle exceptions in the event loop"""
    msg = context.get("exception", context["message"])
    logger.error(f"Caught exception: {msg}")
    logger.info("Shutting down...")
    asyncio.create_task(shutdown(signal.SIGINT, loop, application))

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message when the command /start is issued."""
    chat_id = update.effective_chat.id
    logger.info(f"Received /start command from chat_id: {chat_id}")
    
    welcome_message = """
Welcome to TranscriptAI Bot! 🎥 ➡️ 📝

I can help you transcribe video content and create structured notes. You can:
1. Send me a YouTube link
2. Upload a video file directly

I'll process the content and send you back organized notes in Markdown format!
    """
    await update.message.reply_text(welcome_message)
    
    # Проверяем статус Premium
    is_premium = await check_bot_premium(context)
    if is_premium:
        await update.message.reply_text(
            "🌟 У бота есть Telegram Premium!\n"
            "Максимальный размер файла: 2GB"
        )
    else:
        await update.message.reply_text(
            "ℹ️ Бот работает без Telegram Premium.\n"
            "Максимальный размер файла: 20MB"
        )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message when the command /help is issued."""
    help_text = f"""
Available commands:
/start - Start the bot
/help - Show this help message

To transcribe content:
- Send a YouTube link
- Upload a video file (max {MAX_VIDEO_SIZE_MB}MB)

File size limits:
• Video files: up to {MAX_VIDEO_SIZE_MB}MB
• Extracted audio: up to {MAX_AUDIO_SIZE_MB}MB

The bot will:
1. Process the video
2. Extract audio
3. Transcribe the content
4. Analyze the type (meeting/course)
5. Generate structured notes
6. Send the results to ObsiMatic bot

Note: If your video is too large, try:
• Compressing the video
• Using a YouTube link instead
• Trimming the video to a shorter duration
    """
    await update.message.reply_text(help_text)

def extract_youtube_url(text: str) -> str:
    """Извлекает URL YouTube из текста"""
    # Паттерны для различных форматов YouTube URL
    youtube_patterns = [
        r'(?:https?:\/\/)?(?:www\.)?(?:youtube\.com|youtu\.be)\/(?:watch\?v=)?([^\s&]+)',
        r'(?:https?:\/\/)?(?:www\.)?youtube\.com\/shorts\/([^\s&]+)'
    ]
    
    for pattern in youtube_patterns:
        matches = re.finditer(pattern, text)
        for match in matches:
            # Возвращаем полный URL
            full_match = match.group(0)
            if 'youtu.be' in full_match:
                return f'https://youtube.com/watch?v={match.group(1)}'
            return full_match
    
    return None

async def process_youtube_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process YouTube link and generate transcript"""
    try:
        message_text = update.message.text
        youtube_url = extract_youtube_url(message_text)
        
        if not youtube_url:
            await update.message.reply_text("❌ Не удалось найти корректную ссылку на YouTube видео в сообщении")
            return
        
        await update.message.reply_text("Processing YouTube video... 🎥")
        
        # Get video info
        try:
            video_info = await get_video_info(youtube_url)
            info_message = format_video_info(video_info)
            await update.message.reply_text(info_message)
        except Exception as e:
            logger.error(f"Error getting video info: {str(e)}")
            await update.message.reply_text("📹 Ошибка\n\n"
                                          "📺 Канал: Недоступно\n"
                                          "⏱ Длительность: Недоступно\n"
                                          "📅 Дата загрузки: Недоступно\n\n"
                                          "📝 Описание:\n"
                                          "Не удалось получить описание")
        
        # Download and process
        audio_path = await download_youtube_audio(youtube_url)
        if audio_path and os.path.exists(audio_path):
            await process_audio_file(update, context, audio_path, is_youtube=True)
        else:
            raise Exception("Failed to download audio")
            
    except Exception as e:
        error_message = f"YouTube download error: {str(e)}"
        logger.error(f"Error processing YouTube link: {error_message}")
        await update.message.reply_text(f"Sorry, there was an error processing the YouTube link: {error_message}")

async def download_youtube_audio(url: str) -> str:
    """Download YouTube video and extract audio"""
    try:
        output_template = os.path.join(config.TEMP_DIRECTORY, '%(id)s.%(ext)s')
        ydl_opts = {
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'outtmpl': output_template,
            'quiet': True,
            'no_warnings': True
        }
        
        async with aiofiles.tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_path = temp_file.name
            
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            audio_path = ydl.prepare_filename(info).rsplit('.', 1)[0] + '.mp3'
            
        return audio_path
        
    except Exception as e:
        logger.error(f"Error downloading YouTube audio: {str(e)}")
        raise

async def get_video_info(url: str) -> dict:
    """Get YouTube video information"""
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': True
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(url, download=False)
            return {
                'title': info.get('title', 'Недоступно'),
                'channel': info.get('uploader', 'Недоступно'),
                'duration': str(timedelta(seconds=info.get('duration', 0))),
                'upload_date': datetime.strptime(
                    str(info.get('upload_date', '20240101')), '%Y%m%d'
                ).strftime('%d.%m.%Y'),
                'description': info.get('description', 'Не удалось получить описание')
            }
        except Exception as e:
            logger.error(f"Error extracting video info: {str(e)}")
            raise

def format_video_info(info: dict) -> str:
    """Format video information for display"""
    return (
        f"📹 {info['title']}\n\n"
        f"📺 Канал: {info['channel']}\n"
        f"⏱ Длительность: {info['duration']}\n"
        f"📅 Дата загрузки: {info['upload_date']}\n\n"
        f"📝 Описание:\n{info['description']}"
    )

async def process_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process uploaded video files."""
    video_path = None
    compressed_path = None
    audio_path = None
    
    try:
        chat_id = update.message.chat_id
        
        # Проверяем размер файла
        file_size_mb = update.message.video.file_size / (1024 * 1024)  # Convert to MB
        
        if file_size_mb > config.TELEGRAM_SIZE_LIMIT_MB:
            message = (
                f"❌ Видео слишком большое ({file_size_mb:.1f}MB).\n\n"
                f"Из-за ограничений Telegram Bot API я могу обрабатывать файлы только до {config.TELEGRAM_SIZE_LIMIT_MB}MB.\n\n"
                "Пожалуйста, воспользуйтесь одним из этих способов:\n\n"
                "1️⃣ Загрузите видео на YouTube и отправьте мне ссылку (рекомендуется)\n\n"
                "2️⃣ Сожмите видео с помощью онлайн-сервисов:\n"
                "• Clideo - https://clideo.com/compress-video\n"
                "• FreeConvert - https://www.freeconvert.com/video-compressor\n"
                "• 8mb.video - https://8mb.video\n\n"
                "3️⃣ Разделите видео на части поменьше\n\n"
                "4️⃣ Запишите видео с меньшим качеством\n\n"
                "Рекомендуемые настройки для сжатия:\n"
                "• Разрешение: 720p\n"
                "• Битрейт видео: 1000-1500 kbps\n"
                "• Аудио: 128 kbps, стерео\n"
                "• Формат: MP4 (H.264)"
            )
            await update.message.reply_text(message)
            return
            
        await update.message.reply_text("Обработка видео файла... 🎥")
        
        # Download file
        file = await context.bot.get_file(update.message.video.file_id)
        video_path = os.path.join(config.TEMP_DIRECTORY, f"video_{update.message.video.file_id}")
        await file.download_to_drive(video_path)
        
        # Extract audio and process
        audio_path = audio_processor.extract_audio(video_path)
        
        # Проверяем размер аудио файла
        audio_size_mb = os.path.getsize(audio_path) / (1024 * 1024)  # Convert to MB
        if audio_size_mb > MAX_AUDIO_SIZE_MB:
            raise Exception(
                f"Извлеченное аудио слишком большое ({audio_size_mb:.1f}MB). "
                f"Максимально допустимый размер {MAX_AUDIO_SIZE_MB}MB. "
                "Попробуйте использовать видео меньшей длительности или качествa."
            )
        
        await process_audio_file(update, context, audio_path)
        
    except Exception as e:
        logger.error(f"Error processing video: {str(e)}")
        await update.message.reply_text(f"Извините, произошла ошибка при обработке видео: {str(e)}")
    finally:
        # Cleanup
        for path in [video_path, compressed_path, audio_path]:
            if path and os.path.exists(path):
                try:
                    os.remove(path)
                except Exception as e:
                    logger.error(f"Error cleaning up file {path}: {str(e)}")

async def process_audio_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает аудио сообщения (аудио файлы и голосовые сообщения)"""
    chat_id = update.effective_chat.id
    logger.info(f"Processing audio message from chat_id: {chat_id}")
    
    audio_path = None
    processed_path = None
    
    try:
        # Определяем тип сообщения (аудио файл или голосовое сообщение)
        if update.message.audio:
            file_obj = update.message.audio
            file_type = "аудио файл"
        elif update.message.voice:
            file_obj = update.message.voice
            file_type = "голосовое сообщение"
        else:
            await update.message.reply_text("Неподдерживаемый тип аудио сообщения")
            return
        
        # Проверяем размер файла
        file_size_mb = file_obj.file_size / (1024 * 1024)
        file_name = getattr(file_obj, 'file_name', 'Голосовое сообщение')
        logger.info(f"Получен {file_type} '{file_name}', размер: {file_size_mb:.1f}MB")
        
        if file_size_mb > config.TELEGRAM_SIZE_LIMIT_MB:
            # Формируем рекомендации по сжатию
            format_recommendations = "\n".join([
                f"• {fmt.upper()}: используйте битрейт {bitrate} для оптимального качества"
                for fmt, bitrate in config.RECOMMENDED_AUDIO_FORMATS.items()
            ])
            
            message = (
                f"❌ {file_type.capitalize()} слишком большой ({file_size_mb:.1f}MB).\n"
                f"Telegram Bot API ограничивает размер файла до {config.TELEGRAM_SIZE_LIMIT_MB}MB.\n\n"
                "Пожалуйста:\n"
                "1️⃣ Сожмите аудио в один из рекомендуемых форматов:\n"
                f"{format_recommendations}\n\n"
                "2️⃣ Используйте онлайн-сервисы для сжатия:\n"
                "• Online Audio Converter - https://online-audio-converter.com/\n"
                "• Audio Online Convert - https://audio.online-convert.com/\n\n"
                "3️⃣ Или разделите длинную аудиозапись на части по 19MB\n\n"
                "❗️ Это ограничение Telegram Bot API, которое нельзя обойти."
            )
            await update.message.reply_text(message)
            return
        
        await update.message.reply_text(f"Обработка {file_type}... 🎵")
        
        # Загружаем файл
        try:
            audio_path = os.path.join(config.TEMP_DIRECTORY, f"audio_{file_obj.file_id}")
            file = await context.bot.get_file(file_obj.file_id)
            await file.download_to_drive(audio_path)
            logger.info("Загрузка файла успешна")
        except Exception as download_error:
            error_message = str(download_error)
            logger.error(f"Ошибка при загрузке файла: {error_message}")
            
            if "File is too big" in error_message:
                await update.message.reply_text(
                    f"❌ Не удалось загрузить файл размером {file_size_mb:.1f}MB.\n"
                    f"Telegram ограничивает размер файла до {config.TELEGRAM_SIZE_LIMIT_MB}MB.\n"
                    "Пожалуйста, сожмите файл или разделите его на части."
                )
            else:
                await update.message.reply_text(
                    f"❌ Произошла ошибка при загрузке файла:\n{error_message}"
                )
            return
        
        # Проверяем успешность загрузки
        if os.path.exists(audio_path):
            actual_size_mb = os.path.getsize(audio_path) / (1024 * 1024)
            logger.info(f"Файл успешно загружен, размер: {actual_size_mb:.1f}MB")
            
            # Обрабатываем аудио
            processed_path = audio_processor.process_audio_message(audio_path)
            logger.info("Аудио успешно обработано")
            
            # Транскрибируем
            await process_audio_file(update, context, processed_path)
        else:
            raise Exception("Файл не был загружен")
        
    except Exception as e:
        error_message = str(e)
        logger.error(f"Финальная ошибка: {error_message}")
        await update.message.reply_text(
            f"Извините, произошла ошибка при обработке аудио:\n{error_message}"
        )
    finally:
        # Очистка
        for path in [audio_path, processed_path]:
            if path and os.path.exists(path):
                try:
                    os.remove(path)
                    logger.info(f"Удален временный файл: {path}")
                except Exception as e:
                    logger.error(f"Ошибка при очистке файла {path}: {str(e)}")

def get_file_creation_time(file_path: str) -> str:
    """Получает время создания файла в формате DD-MM-YYYY HH-mm-ss"""
    try:
        # Для Windows используем время создания
        if os.name == 'nt':
            timestamp = os.path.getctime(file_path)
        # Для Unix-подобных систем используем время последнего изменения
        else:
            timestamp = os.path.getmtime(file_path)
        
        return datetime.fromtimestamp(timestamp).strftime("%d-%m-%Y %H-%M-%S")
    except Exception as e:
        logger.error(f"Error getting file creation time: {str(e)}")
        return datetime.now().strftime("%d-%m-%Y %H-%M-%S")

async def process_audio_file(update: Update, context: ContextTypes.DEFAULT_TYPE, audio_path, is_youtube=False):
    """Process audio file and generate notes"""
    temp_files = [audio_path]  # Keep track of files to clean up
    try:
        # Получаем время создания файла
        file_timestamp = get_file_creation_time(audio_path)
        
        if not is_youtube:
            audio_info = {
                'title': f'Audio Note ({file_timestamp})',
                'video_url': 'N/A',
                'channel': 'Local Audio',
                'duration': 'N/A',
                'process_date': time.strftime("%d.%m.%Y"),
                'original_description': 'No description available'
            }
        else:
            # Get video info
            try:
                video_info = await get_video_info(extract_youtube_url(update.message.text))
                audio_info = {
                    'title': f'{video_info["title"]} ({file_timestamp})',
                    'video_url': extract_youtube_url(update.message.text),
                    'channel': video_info['channel'],
                    'duration': video_info['duration'],
                    'process_date': time.strftime("%d.%m.%Y"),
                    'original_description': video_info['description']
                }
            except Exception as e:
                logger.error(f"Error getting video info: {str(e)}")
                audio_info = {
                    'title': f'Audio Note ({file_timestamp})',
                    'video_url': 'N/A',
                    'channel': 'Unknown',
                    'duration': 'N/A',
                    'process_date': time.strftime("%d.%m.%Y"),
                    'original_description': 'No description available'
                }

        # Оптимизируем аудио файл перед транскрибацией
        try:
            optimized_audio_path, optimization_info = audio_processor.optimize_audio_file(
                input_path=audio_path, 
                output_path=f"{audio_path}_optimized.mp3", 
                target_size_mb=20.0
            )
            
            # Заменяем оригинальный путь на оптимизированный
            temp_files.append(optimized_audio_path)
            audio_path = optimized_audio_path
            
            logger.info(f"Audio optimized successfully: {optimized_audio_path}")
            logger.info(f"Optimization details: {optimization_info}")
        except Exception as e:
            logger.error(f"Audio optimization failed: {e}")
            # В случае ошибки оптимизации используем оригинальный файл
        
        # Транскрибируем аудио
        await update.message.reply_text("Transcribing audio... 🎯")
        transcript = transcriber.transcribe_with_whisper(audio_path)

        # Анализируем тип контента
        content_type = transcriber.analyze_content_type(transcript)

        # Генерируем заметки
        await update.message.reply_text("Generating notes... 📝")
        notes = transcriber.generate_notes(transcript, content_type, audio_info)

        # Отправляем заметки
        await update.message.reply_text("Sending notes... 📤")
        await telegram_sender.send_notes(
            chat_id=update.effective_chat.id,
            notes=notes,
            title=audio_info.get('title', 'Notes')
        )

        # Генерируем PDF
        await update.message.reply_text("Generating PDF... 📄")
        pdf_path = generate_pdf(notes, title=audio_info.get('title', 'Notes').replace('/', '_'))
        temp_files.append(pdf_path)
        
        # Отправляем PDF
        await update.message.reply_text("Sending PDF... 📎")
        await telegram_sender.send_document(pdf_path, update.effective_chat.id, update)

        await update.message.reply_text("Done! 🎉")

    except Exception as e:
        logging.error(f"Error processing audio: {str(e)}")
        await update.message.reply_text(f"Sorry, an error occurred while processing the audio: {str(e)}")
    finally:
        # Clean up all temporary files
        cleanup_files(temp_files)

def cleanup_files(file_paths):
    """Clean up temporary files"""
    for path in file_paths:
        if path and os.path.exists(path):
            try:
                os.remove(path)
                logger.info(f"Cleaned up file: {path}")
            except Exception as e:
                logger.error(f"Error cleaning up file {path}: {str(e)}")

async def download_large_file(file_id: str, bot_token: str, destination: str, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """
    Загружает большой файл напрямую через multipart/form-data.
    
    Args:
        file_id: ID файла в Telegram
        bot_token: Токен бота
        destination: Путь для сохранения файла
        context: Контекст бота для получения информации о файле
    
    Returns:
        bool: True если загрузка успешна, False в противном случае
    """
    try:
        # Используем python-telegram-bot для получения информации о файле
        logger.info(f"Получаем информацию о файле с ID: {file_id}")
        file = await context.bot.get_file(file_id)
        file_path = file.file_path
        logger.info(f"Получен путь к файлу: {file_path}")
        
        # Загружаем файл напрямую
        download_url = f"https://api.telegram.org/file/bot{bot_token}/{file_path}"
        logger.info(f"Загружаем файл с URL: {download_url}")
        
        async with aiohttp.ClientSession() as session:
            async with session.get(download_url, timeout=aiohttp.ClientTimeout(total=300)) as response:
                if response.status == 200:
                    total_size = int(response.headers.get('content-length', 0))
                    bytes_downloaded = 0
                    
                    with open(destination, 'wb') as f:
                        async for chunk in response.content.iter_chunked(8192):
                            if chunk:
                                f.write(chunk)
                                bytes_downloaded += len(chunk)
                                progress = (bytes_downloaded / total_size) * 100 if total_size else 0
                                if total_size and bytes_downloaded % (1024 * 1024) == 0:  # Логируем каждый МБ
                                    logger.info(f"Загружено: {bytes_downloaded/(1024*1024):.1f}MB ({progress:.1f}%)")
                    
                    logger.info(f"Файл успешно загружен: {destination}")
                    return True
                else:
                    response_text = await response.text()
                    logger.error(f"Ошибка загрузки файла: HTTP {response.status}, {response_text}")
                    return False
                    
    except Exception as e:
        logger.error(f"Ошибка при загрузке файла: {str(e)}")
        return False

async def check_bot_premium(context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Проверяет, имеет ли бот Premium статус"""
    try:
        bot_info = await context.bot.get_me()
        is_premium = getattr(bot_info, 'is_premium', False)
        logger.info(f"Bot Premium status: {is_premium}")
        return is_premium
    except Exception as e:
        logger.error(f"Error checking bot premium status: {e}")
        return False

async def update_size_limits(context: ContextTypes.DEFAULT_TYPE):
    """Обновляет лимиты размера файлов на основе Premium статуса бота"""
    try:
        bot_info = await context.bot.get_me()
        is_premium = bot_info.is_premium if hasattr(bot_info, 'is_premium') else False
        
        # Устанавливаем значения по умолчанию
        config.TELEGRAM_SIZE_LIMIT_MB = config.TELEGRAM_SIZE_LIMIT_MB or 25
        config.TELEGRAM_PREMIUM_SIZE_LIMIT_MB = config.TELEGRAM_PREMIUM_SIZE_LIMIT_MB or 2048
        
        # Обновляем лимиты на основе Premium статуса
        size_limit = config.TELEGRAM_PREMIUM_SIZE_LIMIT_MB if is_premium else config.TELEGRAM_SIZE_LIMIT_MB
        
        config.MAX_VIDEO_SIZE_MB = size_limit
        config.MAX_AUDIO_SIZE_MB = size_limit
        config.TELEGRAM_SIZE_LIMIT_MB = size_limit
        
        logger.info(f"Updated size limits - Premium: {is_premium}, "
                   f"Video: {config.MAX_VIDEO_SIZE_MB}MB, "
                   f"Audio: {config.MAX_AUDIO_SIZE_MB}MB")
    except Exception as e:
        logger.error(f"Error updating size limits: {str(e)}")
        # Устанавливаем безопасные значения по умолчанию в случае ошибки
        config.MAX_VIDEO_SIZE_MB = 25
        config.MAX_AUDIO_SIZE_MB = 25
        config.TELEGRAM_SIZE_LIMIT_MB = 25

def check_requirements():
    """Проверяет наличие всех необходимых Python пакетов"""
    logger = logging.getLogger(__name__)
    
    logger.info("\n📦 Проверка Python пакетов:")
    missing_packages = []
    outdated_packages = []
    
    required_packages = {
        'python-telegram-bot': '20.6',
        'openai': '0.28.0',
        'python-dotenv': '1.0.0',
        'aiofiles': '23.2.1',
        'aiohttp': '3.8.5',
        'pydub': '0.25.1',
        'markdown': '3.4.4',
        'Markdown': '3.4.4',
        'whisper': '1.1.10',
        'torch': '2.0.1',
        'numpy': '1.24.3',
        'pandas': '2.0.3',
        'psutil': '5.9.5',
        'wmi': '1.5.1'
    }
    
    import pkg_resources
    
    for package, required_version in required_packages.items():
        try:
            installed = pkg_resources.get_distribution(package)
            installed_version = installed.version
            required_version_parsed = pkg_resources.parse_version(required_version)
            installed_version_parsed = pkg_resources.parse_version(installed_version)
            
            if installed_version_parsed >= required_version_parsed:
                logger.info(f"✅ {package:<20} установлен {installed_version:<10} (мин. {required_version})")
            else:
                logger.info(f"⚠️ {package:<20} установлен {installed_version:<10} (требуется {required_version})")
                outdated_packages.append(f"{package}>={required_version}")
        except pkg_resources.DistributionNotFound:
            logger.info(f"❌ {package:<20} не установлен              (требуется {required_version})")
            missing_packages.append(f"{package}>={required_version}")
    
    if missing_packages or outdated_packages:
        logger.warning("\n⚠️ Необходимые действия:")
        
        if missing_packages:
            install_cmd = "pip install " + " ".join(missing_packages)
            logger.warning("\n📥 Установка отсутствующих пакетов:")
            logger.warning(f"  └─ {install_cmd}")
        
        if outdated_packages:
            upgrade_cmd = "pip install --upgrade " + " ".join(outdated_packages)
            logger.warning("\n⬆️ Обновление устаревших пакетов:")
            logger.warning(f"  └─ {upgrade_cmd}")
        
        return False
    
    logger.info("\n✅ Все пакеты установлены и соответствуют требуемым версиям")
    return True

def get_system_info():
    """Получает информацию о системе"""
    import platform
    import psutil
    import locale
    
    logger = logging.getLogger(__name__)
    
    logger.info("\n💻 Системная информация:")
    
    # Основная информация о системе
    system = platform.system()
    release = platform.release()
    version = platform.version()
    machine = platform.machine()
    processor = platform.processor()
    
    # Информация о Python
    python_implementation = platform.python_implementation()
    python_build = platform.python_build()
    
    # Информация о памяти
    memory = psutil.virtual_memory()
    
    # Информация о CPU
    cpu_count = psutil.cpu_count()
    cpu_freq = psutil.cpu_freq()
    
    # Информация о локали
    system_locale = locale.getpreferredencoding()
    
    # Вывод информации
    logger.info(f"🖥️ ОС: {system} {release}")
    logger.info(f"📝 Версия ОС: {version}")
    logger.info(f"🔧 Архитектура: {machine}")
    logger.info(f"⚙️ Процессор: {processor}")
    logger.info(f"🧮 Количество ядер CPU: {cpu_count}")
    if cpu_freq:
        logger.info(f"⚡ Частота CPU: {cpu_freq.current:.2f} MHz")
    
    logger.info(f"🐍 Python реализация: {python_implementation}")
    logger.info(f"🔨 Python сборка: {python_build[0]} {python_build[1]}")
    
    logger.info(f"💾 Оперативная память:")
    logger.info(f"  └─ Всего: {memory.total / (1024**3):.2f} GB")
    logger.info(f"  └─ Доступно: {memory.available / (1024**3):.2f} GB")
    logger.info(f"  └─ Использовано: {memory.percent}%")
    
    logger.info(f"🌐 Системная кодировка: {system_locale}")
    
    # Получаем информацию о GPU
    get_gpu_info()

def get_gpu_info():
    """Получает информацию о GPU"""
    logger = logging.getLogger(__name__)
    logger.info("\n🎮 Информация о GPU:")
    
    try:
        import torch
        if torch.cuda.is_available():
            logger.info("🟢 CUDA доступна")
            logger.info(f"  └─ CUDA версия: {torch.version.cuda}")
            logger.info(f"  └─ cuDNN версия: {torch.backends.cudnn.version() if torch.backends.cudnn.is_available() else 'недоступна'}")
            for i in range(torch.cuda.device_count()):
                gpu_props = torch.cuda.get_device_properties(i)
                logger.info(f"\n  GPU {i}: {gpu_props.name}")
                logger.info(f"  └─ Общая память: {gpu_props.total_memory / (1024**2):.2f} MB")
                logger.info(f"  └─ Количество SM: {gpu_props.multi_processor_count}")
                logger.info(f"  └─ Compute Capability: {gpu_props.major}.{gpu_props.minor}")
        else:
            logger.info("🔴 CUDA недоступна")
            
        # Проверяем поддержку MPS (для MacOS с Apple Silicon)
        if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            logger.info("🟢 MPS (Metal Performance Shaders) доступен")
        
    except Exception as e:
        logger.warning(f"❌ Ошибка при получении информации о CUDA: {str(e)}")
    
    # Получаем дополнительную информацию о GPU через WMI в Windows
    try:
        import wmi
        w = wmi.WMI()
        for gpu in w.Win32_VideoController():
            logger.info(f"\n📊 Системная информация о GPU:")
            logger.info(f"  └─ Название: {gpu.Name}")
            logger.info(f"  └─ Драйвер: {gpu.DriverVersion}")
            if gpu.AdapterRAM:
                gpu_ram = int(gpu.AdapterRAM) / (1024**3)  # Конвертируем в GB
                logger.info(f"  └─ Видеопамять: {gpu_ram:.2f} GB")
            logger.info(f"  └─ Разрешение: {gpu.CurrentHorizontalResolution}x{gpu.CurrentVerticalResolution}")
            logger.info(f"  └─ Частота обновления: {gpu.CurrentRefreshRate}Hz")
            
    except Exception as e:
        logger.debug(f"❌ Ошибка при получении системной информации о GPU: {str(e)}")

def check_environment():
    """Проверяет окружение и выводит важную информацию при старте бота"""
    logger = logging.getLogger(__name__)
    
    logger.info("🔍 Проверка окружения и конфигурации...")
    
    # Получение системной информации
    get_system_info()
    
    # Проверка Python версии
    python_version = sys.version.split()[0]
    logger.info(f"\n📌 Python версия: {python_version}")
    
    # Проверка requirements
    requirements_ok = check_requirements()
    if not requirements_ok:
        logger.warning("⚠️ Некоторые требуемые пакеты отсутствуют!")
    
    # Проверка необходимых зависимостей
    required_tools = {
        'FFmpeg': config.FFMPEG_EXECUTABLE,
        'FFprobe': config.FFPROBE_EXECUTABLE,
        'Pandoc': config.PANDOC_PATH,
        'wkhtmltopdf': config.WKHTMLTOPDF_PATH
    }
    
    logger.info("\n🛠 Проверка внешних инструментов:")
    for tool, path in required_tools.items():
        status = '✅' if os.path.exists(path) else '❌'
        logger.info(f"{status} {tool}: {path}")
    
    # Проверка токенов
    logger.info("\n🔑 Проверка токенов:")
    tokens = {
        'TRANSCRIPT_BOT_TOKEN': bool(config.TRANSCRIPT_BOT_TOKEN),
        'OBSIMATIC_BOT_TOKEN': bool(config.OBSIMATIC_BOT_TOKEN),
        'OPENAI_API_KEY': bool(config.OPENAI_API_KEY),
        'GROUP_CHAT_ID': bool(config.GROUP_CHAT_ID)
    }
    for token, exists in tokens.items():
        status = '✅' if exists else '❌'
        logger.info(f"{status} {token}")
    
    # Вывод важных настроек
    logger.info("\n⚙️ Настройки моделей:")
    logger.info(f"🤖 Whisper модель (локальная): {config.WHISPER_LOCAL_MODEL}")
    logger.info(f"🤖 Whisper модель (облачная): {config.WHISPER_CLOUD_MODEL}")
    logger.info(f"🔄 Использовать локальный Whisper: {config.USE_LOCAL_WHISPER}")
    logger.info(f"💭 Chat модель: {config.CHAT_MODEL}")
    
    logger.info("\n🎛 Настройки генерации:")
    logger.info(f"📝 Chat температура: {config.CHAT_TEMPERATURE}")
    logger.info(f"📊 Температура анализа: {config.ANALYSIS_TEMPERATURE}")
    logger.info(f"📄 Генерировать PDF: {config.GENERATE_PDF}")
    logger.info(f"✨ Markdown включен: {config.MARKDOWN_ENABLED}")
    
    logger.info("\n📊 Лимиты Telegram:")
    logger.info(f"📦 Базовый лимит: {config.TELEGRAM_SIZE_LIMIT_MB}MB")
    logger.info(f"💎 Premium лимит: {config.PREMIUM_SIZE_LIMIT_MB}MB")
    logger.info(f"🎥 Текущий лимит видео: {config.MAX_VIDEO_SIZE_MB}MB")
    logger.info(f"🔊 Текущий лимит аудио: {config.MAX_AUDIO_SIZE_MB}MB")
    
    logger.info("\n📁 Поддерживаемые форматы:")
    logger.info(f"🎥 Видео: {', '.join(config.VIDEO_FORMATS)}")
    logger.info(f"🔊 Аудио: {', '.join(config.AUDIO_FORMATS)}")
    
    logger.info("\n🔧 Режим отладки:")
    logger.info(f"🐛 Режим отладки: {config.DEBUG_MODE}")
    logger.info(f"📨 Отправка в группу: {config.SEND_TO_GROUP}")
    logger.info(f"🤖 Отправка в ObsiMatic бот: {config.SEND_TO_OBSIMATIC_BOT}")
    
    logger.info("\n📂 Рабочие директории:")
    logger.info(f"📌 База: {config.BASE_DIR}")
    logger.info(f"🗃 Временные файлы: {config.TEMP_DIRECTORY}")
    logger.info(f"📑 Обработанные файлы: {config.PROCESSED_DIRECTORY}")
    logger.info(f"📝 Логи: {config.LOG_DIRECTORY}")

async def main():
    """Start the bot."""
    global application
    
    try:
        # Create required directories
        os.makedirs(config.TEMP_DIRECTORY, exist_ok=True)
        os.makedirs(config.PROCESSED_DIRECTORY, exist_ok=True)
        
        logger.info("Initializing bot application...")
        application = Application.builder().token(config.TRANSCRIPT_BOT_TOKEN).build()

        # Add command handlers
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, process_youtube_link))
        application.add_handler(MessageHandler(filters.VIDEO, process_video))
        application.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, process_audio_message))
        logger.info("Added command handlers")

        # Initialize size limits
        application.job_queue.run_once(update_size_limits, 0)
        logger.info("Initialized size limits")
        
        # Start the bot
        logger.info("Starting bot...")
        await application.initialize()
        await application.start()
        
        # Start polling
        logger.info("Starting polling...")
        await application.updater.start_polling(allowed_updates=Update.ALL_TYPES)
        
        # Keep the application running
        logger.info("Bot is running. Press Ctrl+C to stop")
        
        # Create a future that never completes unless cancelled
        stop_signal = asyncio.Event()
        await stop_signal.wait()
        
    except Exception as e:
        logger.error(f"Error in main: {str(e)}", exc_info=True)
        raise
    finally:
        logger.info("Shutting down...")
        try:
            if application:
                await application.stop()
                await application.shutdown()
        except Exception as e:
            logger.error(f"Error during application shutdown: {str(e)}")

def signal_handler(signum, frame):
    """Handle shutdown signals"""
    logger.info(f"Received signal {signal.Signals(signum).name}")
    if application and application.is_running:
        logger.info("Stopping application...")
        # Create an event loop if one doesn't exist
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        async def stop_app():
            await application.stop()
            await application.shutdown()
        
        try:
            loop.run_until_complete(stop_app())
        except Exception as e:
            logger.error(f"Error during shutdown: {str(e)}")
        finally:
            loop.close()
    sys.exit(0)

if __name__ == '__main__':
    try:
        # Настройка логирования
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('bot.log', encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        
        logger = logging.getLogger(__name__)
        logger.info("Starting TranscriptAI bot...")
        
        # Проверка окружения и вывод информации
        check_environment()
        
        logger.info("Initializing bot application...")
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user (Ctrl+C). Goodbye!")
    except SystemExit:
        logger.info("Bot stopped by system exit. Goodbye!")
    except Exception as e:
        logger.error(f"Bot stopped due to error: {str(e)}", exc_info=True)
    finally:
        # Ensure we cleanup any remaining resources
        logger.info("Cleaning up...")
        try:
            if os.path.exists(config.TEMP_DIRECTORY):
                for file in os.listdir(config.TEMP_DIRECTORY):
                    file_path = os.path.join(config.TEMP_DIRECTORY, file)
                    try:
                        if os.path.isfile(file_path):
                            os.unlink(file_path)
                            logger.debug(f"Deleted temporary file: {file_path}")
                    except Exception as e:
                        logger.error(f"Error deleting {file_path}: {str(e)}")
        except Exception as e:
            logger.error(f"Error during final cleanup: {str(e)}")
        logger.info("Cleanup complete. Exiting.")
