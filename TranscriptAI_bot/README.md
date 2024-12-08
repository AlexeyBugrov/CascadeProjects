# TranscriptAI Bot

Telegram бот для транскрибации голосовых и видео сообщений с генерацией структурированных заметок и интеграцией в Obsidian.

## Возможности

- Транскрибация голосовых и видео сообщений с помощью OpenAI Whisper (локальный или облачный)
- Поддержка YouTube видео через ссылки
- Автоматическое определение типа контента (встреча/курс)
- Генерация структурированных заметок в формате Markdown с временными метками
- Автоматическое разбиение на логические разделы
- Интеграция с Obsidian через ObsiMatic бот
- Поддержка Telegram Premium (увеличенные лимиты на размер файлов)
- Оптимизация аудио под ограничения размера
- Умное форматирование сообщений с поддержкой Markdown

### Поддерживаемые форматы
- Видео: mp4, avi, mov, webm, mkv, wmv, flv
- Аудио: mp3, wav, m4a, ogg, aac, wma, flac

### Лимиты на размер файлов
- Обычный бот: до 20MB
- Telegram Premium: до 2GB

## Установка

1. Клонируйте репозиторий:
```bash
git clone https://github.com/yourusername/TranscriptAI_bot.git
cd TranscriptAI_bot
```

2. Установите зависимости:
```bash
pip install -r requirements.txt
```

3. Создайте файл .env с необходимыми переменными окружения:
```env
TRANSCRIPT_BOT_TOKEN=your_transcript_bot_token
OBSIMATIC_BOT_TOKEN=your_obsimatic_bot_token
OPENAI_API_KEY=your_openai_api_key
GROUP_CHAT_ID=your_group_chat_id
OBSIMATIC_BOT_USERNAME=your_obsimatic_bot_username
```

## Конфигурация

### Основные настройки (config.py)
```python
# Режим отладки
DEBUG_MODE = True    # Включает расширенное логирование

# Настройки отправки сообщений
SEND_TO_GROUP = True          # Отправка сообщений в группу
SEND_TO_OBSIMATIC_BOT = True # Отправка сообщений ObsiMatic боту
GENERATE_PDF = True          # Генерация PDF версии заметок

# Настройки Whisper
USE_LOCAL_WHISPER = False     # Использовать локальную версию Whisper
WHISPER_LOCAL_MODEL = "base"  # Модель для локального Whisper
WHISPER_CLOUD_MODEL = "whisper-1"  # Модель для облачного Whisper

# Настройки генерации
CHAT_MODEL = "gpt-4"         # Модель для анализа и генерации заметок
```

## Структура проекта
```
TranscriptAI_bot/
├── main.py             # Основной файл бота
├── config.py           # Конфигурация и системные промпты
├── requirements.txt    # Зависимости проекта
├── .env               # Переменные окружения
├── README.md          # Документация
└── utils/
    ├── audio_processor.py    # Обработка аудио/видео
    ├── youtube_info.py       # Работа с YouTube
    ├── transcriber.py        # Транскрибация и генерация заметок
    ├── telegram_sender.py    # Отправка сообщений
    └── pdf_converter.py      # Конвертация в PDF
```

## Формат заметок

Бот генерирует структурированные заметки следующего формата:

1. **Метаданные**
   - Название
   - Канал/Автор
   - Длительность
   - Дата обработки
   - Ссылка на источник (для YouTube)

2. **Содержание**
   - Логические разделы с временными метками (MM:SS-MM:SS)
   - Краткое описание каждого раздела

3. **Конспект**
   - Основные темы и подтемы
   - Ключевые моменты
   - Цитаты и важные мысли

## Требования к системе

- Python 3.8+
- FFmpeg (для обработки аудио/видео)
- Достаточно свободного места для временных файлов
- Доступ к API OpenAI

## Лицензия

MIT License
