import yt_dlp

class YouTubeInfo:
    def __init__(self):
        self.ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': True,
        }

    def extract_video_info(self, url):
        """
        Извлекает информацию о видео с YouTube
        
        Args:
            url (str): URL видео на YouTube
            
        Returns:
            dict: Словарь с информацией о видео:
                - title: название видео
                - description: описание видео
                - duration: длительность в секундах
                - channel: название канала
                - upload_date: дата загрузки
        """
        try:
            with yt_dlp.YoutubeDL(self.ydl_opts) as ydl:
                # Получаем информацию о видео
                video_info = ydl.extract_info(url, download=False)
                
                # Формируем структурированный ответ
                info = {
                    'title': video_info.get('title', 'Название недоступно'),
                    'description': video_info.get('description', 'Описание недоступно'),
                    'duration': video_info.get('duration', 0),
                    'channel': video_info.get('uploader', 'Канал недоступен'),
                    'upload_date': video_info.get('upload_date', 'Дата недоступна')
                }
                
                # Форматируем длительность в читаемый вид
                if info['duration']:
                    minutes = info['duration'] // 60
                    seconds = info['duration'] % 60
                    info['duration_str'] = f"{minutes}:{seconds:02d}"
                else:
                    info['duration_str'] = "Длительность недоступна"
                
                # Форматируем дату
                if info['upload_date'] and info['upload_date'] != 'Дата недоступна':
                    year = info['upload_date'][:4]
                    month = info['upload_date'][4:6]
                    day = info['upload_date'][6:8]
                    info['upload_date'] = f"{day}.{month}.{year}"
                
                return info
                
        except Exception as e:
            return {
                'error': f"Ошибка при получении информации о видео: {str(e)}",
                'title': 'Ошибка',
                'description': 'Не удалось получить описание',
                'duration': 0,
                'duration_str': 'Недоступно',
                'channel': 'Недоступно',
                'upload_date': 'Недоступно'
            }

    def format_info_message(self, info):
        """
        Форматирует информацию о видео в читаемый текст с экранированием специальных символов
        
        Args:
            info (dict): Словарь с информацией о видео
            
        Returns:
            str: Отформатированный текст с информацией
        """
        def escape_markdown(text):
            """Экранирует специальные символы Markdown"""
            if not text:
                return ""
            # Экранируем специальные символы
            escape_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '=', '|', '{', '}', '!', '"']
            for char in escape_chars:
                text = text.replace(char, '\\' + char)
            # Удаляем множественные пробелы и невидимые символы
            text = ' '.join(text.split())
            # Ограничиваем только базовыми символами Unicode
            text = ''.join(char for char in text if ord(char) < 65536)
            return text

        # Экранируем все поля
        safe_title = escape_markdown(info['title'])
        safe_channel = escape_markdown(info['channel'])
        safe_duration = escape_markdown(info['duration_str'])
        safe_date = escape_markdown(info['upload_date'])
        
        # Обрабатываем описание отдельно
        description = info['description'][:500]
        if len(info['description']) > 500:
            description += "..."
        safe_description = escape_markdown(description)
        
        # Формируем сообщение с экранированными значениями
        message = f"""📹 *{safe_title}*

📺 *Канал:* {safe_channel}
⏱ *Длительность:* {safe_duration}
📅 *Дата загрузки:* {safe_date}

📝 *Описание:*
{safe_description}"""

        return message
