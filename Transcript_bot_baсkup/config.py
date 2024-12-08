import os
import sys
import platform
from pathlib import Path
from dotenv import load_dotenv

# Загрузка переменных окружения
load_dotenv()

# Определение операционной системы
SYSTEM_NAME = platform.system().lower()
IS_WINDOWS = SYSTEM_NAME == 'windows'
IS_LINUX = SYSTEM_NAME == 'linux'
IS_MACOS = SYSTEM_NAME == 'darwin'

# Определение базовой директории (где находится main.py)
BASE_DIR = Path(os.path.dirname(os.path.abspath(sys.argv[0]))).resolve()

# Настройка путей в зависимости от ОС
if IS_WINDOWS:
    # Windows-специфичные пути
    FFMPEG_PATH = BASE_DIR / 'ffmpeg' / 'bin'
    FFMPEG_EXECUTABLE = FFMPEG_PATH / 'ffmpeg.exe'
    FFPROBE_EXECUTABLE = FFMPEG_PATH / 'ffprobe.exe'
    WKHTMLTOPDF_PATH = r'C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe'
    PANDOC_PATH = r'C:\Users\{}\AppData\Local\Pandoc\pandoc.exe'.format(os.getenv('USERNAME'))
elif IS_LINUX:
    # Linux-специфичные пути
    FFMPEG_PATH = Path('/usr/bin')
    FFMPEG_EXECUTABLE = FFMPEG_PATH / 'ffmpeg'
    FFPROBE_EXECUTABLE = FFMPEG_PATH / 'ffprobe'
    WKHTMLTOPDF_PATH = '/usr/bin/wkhtmltopdf'
    PANDOC_PATH = '/usr/bin/pandoc'
else:
    # MacOS или другие ОС
    FFMPEG_PATH = Path('/usr/local/bin')
    FFMPEG_EXECUTABLE = FFMPEG_PATH / 'ffmpeg'
    FFPROBE_EXECUTABLE = FFMPEG_PATH / 'ffprobe'
    WKHTMLTOPDF_PATH = '/usr/bin/wkhtmltopdf'
    PANDOC_PATH = '/usr/local/bin/pandoc'

# Настройки для PDF
PDF_MARGIN = '1.5cm'
PDF_FONT = 'Arial'
PDF_PAGE_SIZE = 'A4'
PDF_DPI = '300'

# Создание необходимых директорий
TEMP_DIRECTORY = BASE_DIR / "temp"
PROCESSED_DIRECTORY = BASE_DIR / "processed"
LOG_DIRECTORY = BASE_DIR / "logs"
PDF_TEMPLATE_DIR = BASE_DIR / "templates"
PDF_OUTPUT_DIR = PROCESSED_DIRECTORY / "pdf"

# Создание директорий если они не существуют
for directory in [TEMP_DIRECTORY, PROCESSED_DIRECTORY, LOG_DIRECTORY, 
                 PDF_TEMPLATE_DIR, PDF_OUTPUT_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

# Токены из .env файла
TRANSCRIPT_BOT_TOKEN = os.getenv('TRANSCRIPT_BOT_TOKEN')    # Бот для приема команд и аудио
OBSIMATIC_BOT_TOKEN = os.getenv('OBSIMATIC_BOT_TOKEN')     # Бот для отправки заметок
GROUP_CHAT_ID = os.getenv('GROUP_CHAT_ID')                 # ID группы для коммуникации между ботами
OBSIMATIC_BOT_USERNAME = os.getenv('OBSIMATIC_BOT_USERNAME')  # Username ObsiMatic бота (без @)
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')              # API ключ OpenAI

# Настройки отладки
DEBUG_MODE = True    # Режим отладки с отправкой в OBSIMATIC_BOT
SEND_TO_GROUP = True  # Отправлять ли сообщения в группу для логирования
SEND_TO_OBSIMATIC_BOT = False  # Отправлять ли сообщения напрямую в ObsiMatic бот

# Настройки Whisper
WHISPER_LOCAL_MODEL = "base"         # Локальная модель whisper
WHISPER_CLOUD_MODEL = "whisper-1"    # Облачная модель whisper через OpenAI API
USE_LOCAL_WHISPER = False           # True для локальной модели, False для облачной

# Настройки OpenAI моделей
CHAT_MODEL = "gpt-4o-mini"               # Модель для анализа и генерации заметок
CHAT_TEMPERATURE = 0.7             # Температура для генерации текста
ANALYSIS_TEMPERATURE = 0.3         # Температура для анализа контента

# Настройки генерации
GENERATE_PDF = True                # Генерировать ли PDF версию заметок
MARKDOWN_ENABLED = True            # Использовать ли markdown форматирование

# Ограничения Telegram API
TELEGRAM_SIZE_LIMIT_MB = 20        # Базовое ограничение Telegram Bot API
TELEGRAM_PREMIUM_SIZE_LIMIT_MB = 4096  # Максимальный размер для Telegram Premium (4GB)
REGULAR_SIZE_LIMIT_MB = 20         # Лимит для обычных пользователей
PREMIUM_SIZE_LIMIT_MB = 2048       # Лимит для премиум пользователей (2GB)

# Динамические лимиты (будут обновляться в зависимости от Premium статуса)
MAX_VIDEO_SIZE_MB = REGULAR_SIZE_LIMIT_MB
MAX_AUDIO_SIZE_MB = REGULAR_SIZE_LIMIT_MB

# Лимиты в байтах для внутренней обработки
DEFAULT_SIZE_LIMIT = REGULAR_SIZE_LIMIT_MB * 1024 * 1024       # Для обычных пользователей
PREMIUM_SIZE_LIMIT = PREMIUM_SIZE_LIMIT_MB * 1024 * 1024       # Для премиум пользователей

# Поддерживаемые форматы файлов
VIDEO_FORMATS = ['.mp4', '.avi', '.mov', '.webm', '.mkv', '.wmv', '.flv']
AUDIO_FORMATS = ['.mp3', '.wav', '.m4a', '.ogg', '.aac', '.wma', '.flac']
SUPPORTED_FORMATS = VIDEO_FORMATS + AUDIO_FORMATS

# Настройки логирования
LOG_FILE = LOG_DIRECTORY / 'bot.log'
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
LOG_LEVEL = 'INFO'

# Настройки обработки файлов
MAX_CHUNK_SIZE = 25 * 1024 * 1024  # 25MB для разбиения больших файлов

# Рекомендуемые форматы для сжатия
RECOMMENDED_AUDIO_FORMATS = {
    'mp3': '128k',  # Рекомендуемый битрейт для MP3
    'ogg': '96k',   # Рекомендуемый битрейт для OGG
    'm4a': '128k',  # Рекомендуемый битрейт для M4A
}

# Преобразование путей в абсолютные строки
TEMP_DIRECTORY = str(TEMP_DIRECTORY.absolute())
PROCESSED_DIRECTORY = str(PROCESSED_DIRECTORY.absolute())
LOG_DIRECTORY = str(LOG_DIRECTORY.absolute())
LOG_FILE = str(LOG_FILE.absolute())
PDF_TEMPLATE_DIR = str(PDF_TEMPLATE_DIR.absolute())
PDF_OUTPUT_DIR = str(PDF_OUTPUT_DIR.absolute())
FFMPEG_PATH = str(FFMPEG_PATH.absolute())
FFMPEG_EXECUTABLE = str(FFMPEG_EXECUTABLE.absolute())
FFPROBE_EXECUTABLE = str(FFPROBE_EXECUTABLE.absolute())

# Сообщения бота
START_MESSAGE = """
👋 Привет! Я бот для транскрибации голосовых и видео сообщений.

Отправьте мне:
🎤 Голосовое сообщение
🎥 Видео сообщение
🔗 Ссылку на YouTube видео

И я создам для вас текстовую расшифровку!
"""

HELP_MESSAGE = """
🤖 Я могу помочь вам с транскрибацией:

📝 Поддерживаемые форматы:
- Голосовые сообщения
- Видео сообщения
- YouTube видео

📊 Ограничения:
- Обычные пользователи: до 20MB
- Premium пользователи: до 2GB

❓ Нужна помощь? Напишите в поддержку.
"""

# Настройки анализа контента
CONTENT_ANALYSIS_PROMPT = """Analyze the following transcript and determine if it's a Zoom meeting/phone call or a lesson/course. Respond with either 'meeting' or 'course'."""

# Generation Parameters
NOTES_TEMPERATURE = 0.7
NOTES_MAX_TOKENS = 16384
NOTES_PRESENCE_PENALTY = 0.3
NOTES_FREQUENCY_PENALTY = 0.3

# System Prompts
MEETING_PROMPT = """Analyze the meeting transcript and create a structured summary with the following:
                 1. Title (inferred from content)
                 2. List of participants
                 3. Main topics discussed
                 4. Key decisions and action items
                 5. Summary of the meeting
                 Format the output in Markdown. Language: russian."""

COURSE_CONTENT_PROMPT = '''Проанализируй транскрипцию и создай подробное содержание в следующем формате:
1. Раздели контент на логические разделы с временными метками
2. Для каждого раздела укажи:
   - Номер и название раздела
   - Временной интервал в формате MM:SS-MM:SS
   - Краткое описание содержания (2-3 предложения)
3. Используй формат времени: 0:00-1:30, 1:30-2:45 и т.д.
4. Сделай описания информативными и полезными
'''

COURSE_PROMPT_HEADER = """# {title}

## Метаданные
- **Автор:** {channel}
- **Длительность:** {duration}
- **Дата обработки:** {process_date}
- **Ссылка:** {video_url}

**Описание:**
{original_description}

---
"""

COURSE_CONTENT_FORMAT = '''### {section_number}. {section_title}
**{start_time}-{end_time}**
{description}
'''

COURSE_PROMPT = """Ты - эксперт по созданию структурированных конспектов. 
Твоя задача - создать подробный, хорошо организованный конспект на основе транскрипции.

Раздел "Конспект" - это ОСНОВНОЙ раздел. Вот как его нужно оформлять:

1. Структура и форматирование:
   - Используй подзаголовки третьего уровня (###) для основных тем
   - Каждая тема должна быть на новой строке
   - Используй маркированные списки для подтем (-)
   - Используй вложенные списки для деталей (  *)
   - Выделяй ключевые термины жирным (**термин**)

2. Содержание каждой темы:
   ### Название темы
   - Основная мысль или концепция
     * Подробное объяснение
     * Определения важных терминов
     * Примеры и иллюстрации
   - Связи с другими темами
     * Как эта тема связана с предыдущей
     * Как она связана с последующей

3. Логическая структура:
   - Начинай с общего обзора темы
   - Переходи к конкретным концепциям
   - Завершай практическим применением
   - Добавляй связки между темами

4. Обязательные элементы:
   - Вступление (общий обзор)
   - Основные концепции и их объяснения
   - Примеры и применение
   - Связи между темами
   - Краткие выводы по каждой теме

5. Оформление текста:
   - Используй короткие, четкие предложения
   - Разделяй длинные абзацы на пункты
   - Добавляй пробелы между разделами
   - Сохраняй единый стиль форматирования

Общие правила для всех разделов:
1. Строго следуй структуре разделов
2. Используй точное форматирование markdown
3. Сохраняй отступы и структуру списков
4. Не добавляй лишних переносов строк
5. Делай каждый раздел информативным
6. Используй маркированные списки и нумерацию как в шаблоне
7. Выделяй важные термины жирным (**термин**)

На основе транскрипции создай подробный конспект. 
Строго следуй этой структуре и форматированию:

## Содержание
Проанализируй транскрипцию и создай подробное содержание в следующем формате:
1. Раздели контент на логические разделы с временными метками
2. Для каждого раздела укажи:
   - Номер и название раздела
   - Временной интервал в формате MM:SS-MM:SS
   - Краткое описание содержания (2-3 предложения)
3. Используй формат времени: 0:00-1:30, 1:30-2:45 и т.д.
4. Сделай описания информативными и полезными

## Конспект
Создай подробный конспект основного содержания. Обязательно включи:
1. Основные темы и подтемы
2. Ключевые моменты и их объяснения
3. Важные детали и нюансы
4. Логические связи между частями

Используй подзаголовки третьего уровня (###) для структурирования.

## Основные идеи
Выдели 3-5 ключевых идей. Для каждой:

1. **Идея**: [четкая формулировка]
   - **Значимость**: [объяснение важности]
   - **Контекст**: [связь с общей темой]

## Ключевые концепции
Список основных терминов и концепций:

1. **[Термин]**
   - **Определение**: [четкое определение]
   - **Важность**: [почему это важно]
   - **Применение**: [как используется]

## Практические примеры
Конкретные примеры из материала:

1. **Пример**: [название/краткое описание]
   - **Ситуация**: [описание контекста]
   - **Применение**: [как иллюстрирует концепцию]
   - **Выводы**: [что можно извлечь]

## Заключение
Структурированное заключение:

1. **Итоги**: [основные результаты]
2. **Выводы**: [главные заключения]
3. **Рекомендации**: [практические советы]
4. **Следующие шаги**: [что делать дальше]

## Полезные ссылки
Структурированный список ресурсов:

1. **Упомянутые источники**:
   - [список источников из материала]

2. **Рекомендуемые материалы**:
   - [дополнительные ресурсы]

3. **Связанные темы**:
   - [темы для дальнейшего изучения]

Транскрипция:
{transcript}"""

# Templates for Obsidian notes
MEETING_TEMPLATE = """# {title}

## Metadata
- Date: {date}
- Time: {time}
- Type: {meeting_type}

## File Information
- Filename: {filename}
- Duration: {duration}
- Audio Channels: {channels}
{additional_info}

## Participants
{participants}

## Summary
{summary}

## Action Items
{action_items}

## Debug Information
### Detailed Transcript
{transcript}
"""

COURSE_TEMPLATE = """# {title}

## Metadata
- Type: {content_type}
- Date: {date}

## Course Information
- Filename: {filename}
- Duration: {duration}
- Audio Channels: {channels}
{additional_info}

## Video Information
- Video URL: {video_url}
- Original Description:
{original_description}

## Summary
{summary}

## Table of Contents
{contents}

## Sections
{sections}

## Debug Information
### Detailed Transcript
{transcript}
"""
