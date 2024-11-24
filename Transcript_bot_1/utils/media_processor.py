import os
import yt_dlp
import logging
import asyncio
import re
from pathlib import Path
import time
import transliterate
import subprocess
import datetime
import traceback

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MediaProcessor:
    def __init__(self, temp_dir: str, ffmpeg_location: str = None):
        self.temp_dir = temp_dir
        os.makedirs(temp_dir, exist_ok=True)
        
        # Проверяем наличие ffmpeg
        if ffmpeg_location:
            self.ffmpeg_location = ffmpeg_location
            print(f"✅ FFmpeg location set manually: {ffmpeg_location}")
        else:
            ffmpeg_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'ffmpeg', 'bin')
            if os.path.exists(os.path.join(ffmpeg_path, 'ffmpeg.exe')):
                print(f"✅ FFmpeg found and working correctly at: {os.path.join(ffmpeg_path, 'ffmpeg.exe')}")
                self.ffmpeg_location = ffmpeg_path
            else:
                raise Exception("❌ FFmpeg not found. Please ensure ffmpeg is installed in the ffmpeg/bin directory or provide a custom path.")

    def _sanitize_filename(self, filename: str) -> str:
        """Очистка имени файла от недопустимых символов"""
        # Транслитерация кириллических символов
        filename = self._transliterate(filename)
        
        # Заменяем пробелы и удаляем все спецсимволы
        import re
        filename = re.sub(r'[^\w\-_\.]', '_', filename)
        
        # Заменяем несколько подряд идущих символов на один
        filename = re.sub(r'(_)\1+', r'\1', filename)
        
        # Убираем точки в конце
        filename = filename.rstrip('.')
        
        # Ограничиваем длину
        if len(filename) > 200:
            name, ext = os.path.splitext(filename)
            filename = name[:196] + ext
        
        # Если имя файла пустое после очистки, генерируем случайное
        if not filename:
            filename = f"file_{int(time.time())}.txt"
        
        return filename

    def _transliterate(self, text: str) -> str:
        """Транслитерация кириллических символов"""
        try:
            return transliterate.translit(text, 'ru', reversed=True)
        except Exception:
            # Если библиотека не работает, используем простую замену
            translit_map = {
                'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 
                'е': 'e', 'ё': 'yo', 'ж': 'zh', 'з': 'z', 'и': 'i', 
                'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm', 'н': 'n', 
                'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 
                'у': 'u', 'ф': 'f', 'х': 'kh', 'ц': 'ts', 'ч': 'ch', 
                'ш': 'sh', 'щ': 'shch', 'ъ': '', 'ы': 'y', 'ь': '', 
                'э': 'e', 'ю': 'yu', 'я': 'ya'
            }
            logger.warning(f"Не удалось использовать transliterate. Используется простая транслитерация.")
            return ''.join(translit_map.get(char.lower(), char) for char in text)

    async def _wait_for_file_access(self, file_path: str, timeout: int = 10, mode: str = 'ab') -> bool:
        """
        Ожидание освобождения файла с расширенной диагностикой
        
        :param file_path: Путь к файлу
        :param timeout: Максимальное время ожидания
        :param mode: Режим открытия файла
        :return: True, если файл доступен, иначе False
        """
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                # Проверяем существование файла
                if not os.path.exists(file_path):
                    logger.info(f"Файл не существует: {file_path}")
                    return True
                
                # Получаем информацию о файле
                file_stat = os.stat(file_path)
                
                # Пробуем открыть файл
                with open(file_path, mode):
                    logger.debug(f"Файл успешно открыт: {file_path}")
                    return True
            except PermissionError:
                logger.warning(f"Нет доступа к файлу: {file_path}")
            except OSError as e:
                logger.warning(f"Ошибка доступа к файлу {file_path}: {e}")
            
            await asyncio.sleep(0.5)
        
        logger.error(f"Не удалось получить доступ к файлу за {timeout} секунд: {file_path}")
        return False

    async def _safe_remove_file(self, file_path: str) -> bool:
        """
        Безопасное удаление файла с расширенной диагностикой
        
        :param file_path: Путь к файлу для удаления
        :return: True, если файл успешно удален, иначе False
        """
        if not os.path.exists(file_path):
            logger.info(f"Файл не существует, удаление не требуется: {file_path}")
            return True
        
        try:
            # Проверяем права доступа к файлу
            if not os.access(file_path, os.W_OK):
                logger.warning(f"Нет прав на запись файла: {file_path}")
                return False
            
            # Ждем, пока файл освободится
            if not await self._wait_for_file_access(file_path, mode='r'):
                logger.error(f"Не удалось получить доступ к файлу для удаления: {file_path}")
                return False
            
            # Получаем информацию о файле перед удалением
            file_stat = os.stat(file_path)
            logger.info(f"Удаление файла: {file_path}")
            logger.info(f"  Размер: {file_stat.st_size} байт")
            logger.info(f"  Время создания: {file_stat.st_ctime}")
            
            os.remove(file_path)
            logger.info(f"Файл успешно удален: {file_path}")
            return True
        except Exception as e:
            logger.error(f"Критическая ошибка при удалении файла {file_path}: {str(e)}")
            return False

    async def download_youtube_video(self, url: str) -> str:
        """Скачивание видео с YouTube"""
        temp_video_file = None
        temp_audio_file = None
        
        try:
            # Устанавливаем путь к ffmpeg
            os.environ['PATH'] += os.pathsep + os.path.dirname(self.ffmpeg_location)
            
            # Сначала получаем информацию о видео для определения имени файла
            info_opts = {
                'quiet': False,
                'no_warnings': False,
                'extract_flat': False,
                'ffmpeg_location': os.path.join(self.ffmpeg_location, 'ffmpeg.exe')
            }
            
            with yt_dlp.YoutubeDL(info_opts) as ydl:
                info_dict = ydl.extract_info(url, download=False)
                if not info_dict:
                    raise Exception("Не удалось получить информацию о видео")
                
                # Используем только временную метку для имени файла
                timestamp = int(time.time())
                
                # Создаем полные абсолютные пути к файлам
                temp_video_file = os.path.abspath(os.path.join(self.temp_dir, f"video_{timestamp}.webm"))
                temp_audio_file = os.path.abspath(os.path.join(self.temp_dir, f"audio_{timestamp}.wav"))
                
                # Очищаем старые файлы, если они существуют
                await self._safe_remove_file(temp_video_file)
                await self._safe_remove_file(temp_audio_file)
                
                # Настройки для скачивания с расширенной конфигурацией
                ydl_opts = {
                    'format': 'bestaudio/best',
                    'outtmpl': temp_video_file,
                    'nocheckcertificate': True,
                    'geo_bypass': True,
                    'geo_bypass_country': 'US',
                    'extractor_retries': 10,
                    'retries': 10,
                    'fragment_retries': 10,
                    'quiet': False,
                    'no_warnings': False,
                    'verbose': True,
                    'keepvideo': True,  # Не удалять исходный файл
                    'ffmpeg_location': os.path.join(self.ffmpeg_location, 'ffmpeg.exe'),
                    'postprocessors': [{
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': 'wav',
                        'preferredquality': '192',
                    }]
                }
                
                # Скачиваем видео с расширенной обработкой
                logger.info(f"Начинаем скачивание в файл: {temp_video_file}")
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([url])
                
                # Расширенная проверка файла
                logger.info(f"Проверяем файл: {temp_video_file}")
                
                # Проверяем существование файлов с полными путями
                if not os.path.exists(temp_video_file):
                    logger.error(f"❌ Файл не найден: {temp_video_file}")
                    logger.error(f"Содержимое директории {self.temp_dir}:")
                    for filename in os.listdir(self.temp_dir):
                        logger.error(f"- {filename}")
                    raise Exception("Файл не был создан после скачивания")
                
                file_size = os.path.getsize(temp_video_file)
                logger.info(f"✅ Размер файла: {file_size} байт")
                
                # Проверка размера файла (ограничение Whisper - 25 МБ)
                max_file_size = 25 * 1024 * 1024  # 25 МБ
                if file_size > max_file_size:
                    logger.error(f"❌ Файл слишком большой: {file_size} байт (макс. 25 МБ)")
                    raise ValueError(f"Размер файла превышает 25 МБ: {file_size} байт")
                
                if file_size == 0:
                    raise Exception("Скачанный файл пуст")
                
                # Если файл уже в формате webm, сохраняем его без конвертации
                if temp_video_file.lower().endswith('.webm'):
                    return temp_video_file
                
                # Конвертируем в WAV с более подробной обработкой ошибок
                logger.info("Конвертируем в WAV...")
                ffmpeg_path = os.path.join(self.ffmpeg_location, 'ffmpeg.exe')
                ffmpeg_cmd = [
                    f'"{ffmpeg_path}"',
                    '-y',  # Перезаписывать файлы
                    '-i', f'"{temp_video_file}"',
                    '-vn',  # Убираем видео
                    '-acodec', 'pcm_s16le',  # Кодек для WAV
                    '-ar', '44100',  # Частота дискретизации
                    '-ac', '1',  # Моно канал
                    f'"{temp_audio_file}"'
                ]
                
                process = await asyncio.create_subprocess_shell(
                    ' '.join(ffmpeg_cmd),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                
                stdout, stderr = await process.communicate()
                
                if process.returncode != 0:
                    error_message = stderr.decode(errors='ignore')
                    logger.error(f"❌ FFmpeg завершился с ошибкой: {error_message}")
                    raise Exception(f"FFmpeg завершился с ошибкой: {error_message}")
                
                # Финальная проверка WAВ файла
                if not os.path.exists(temp_audio_file):
                    raise Exception("WAV файл не был создан")
                
                wav_size = os.path.getsize(temp_audio_file)
                logger.info(f"✅ Размер WAV файла: {wav_size} байт")
                
                if wav_size == 0:
                    raise Exception("Созданный WAV файл пуст")
                
                return temp_audio_file
        
        except Exception as e:
            logger.error(f"❌ Ошибка при скачивании видео: {str(e)}")
            
            # Очищаем временные файлы в случае ошибки
            if temp_video_file and os.path.exists(temp_video_file):
                await self._safe_remove_file(temp_video_file)
            if temp_audio_file and os.path.exists(temp_audio_file):
                await self._safe_remove_file(temp_audio_file)
            
            raise

    async def extract_audio(self, video_path: str) -> str:
        """
        Извлечение аудио с расширенной диагностикой
        Поддерживает прямое копирование для webm
        """
        logger.debug(f"🎬 Начало извлечения аудио из файла: {video_path}")
        
        try:
            # Создаем временную директорию, если не существует
            temp_dir = os.path.join(os.getcwd(), 'temp')
            os.makedirs(temp_dir, exist_ok=True)
            
            # Генерируем уникальное имя для аудиофайла
            file_name = os.path.splitext(os.path.basename(video_path))[0]
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # Проверяем расширение исходного файла
            file_ext = os.path.splitext(video_path)[1].lower()
            
            # Определяем пути к FFmpeg и FFprobe
            ffmpeg_path = os.path.join(self.ffmpeg_location, 'ffmpeg.exe')
            ffprobe_path = os.path.join(self.ffmpeg_location, 'ffprobe.exe')
            
            logger.debug(f"🔍 Пути к утилитам:")
            logger.debug(f"FFmpeg: {ffmpeg_path}")
            logger.debug(f"FFprobe: {ffprobe_path}")
            
            # Проверяем существование утилит
            if not os.path.exists(ffmpeg_path):
                raise FileNotFoundError(f"FFmpeg не найден: {ffmpeg_path}")
            if not os.path.exists(ffprobe_path):
                raise FileNotFoundError(f"FFprobe не найден: {ffprobe_path}")
            
            # Если webm, пробуем сохранить как есть
            if file_ext == '.webm':
                logger.debug("🌐 Обнаружен webm файл, пробуем сохранить напрямую")
                
                # Проверка кодеков в webm
                ffprobe_cmd = [
                    ffprobe_path, 
                    '-v', 'quiet', 
                    '-print_format', 'json', 
                    '-show_streams', 
                    video_path
                ]
                
                logger.debug(f"🚀 Команда FFprobe: {' '.join(ffprobe_cmd)}")
                
                try:
                    ffprobe_output = subprocess.check_output(ffprobe_cmd, universal_newlines=True)
                    logger.debug(f"🔊 Информация FFprobe: {ffprobe_output}")
                except subprocess.CalledProcessError as e:
                    logger.error(f"❌ Ошибка FFprobe: {e}")
                    logger.error(f"Stderr: {e.stderr}")
                
                # Генерируем путь для аудио
                temp_audio_file = os.path.join(temp_dir, f"{file_name}_{timestamp}.wav")
                
                # Копируем аудиопоток
                ffmpeg_cmd = [
                    ffmpeg_path, 
                    '-i', video_path, 
                    '-vn',  # Только аудио
                    '-acodec', 'pcm_s16le',  # WAV кодек
                    '-ar', '44100',  # Частота дискретизации
                    '-ac', '1',  # Моно канал
                    temp_audio_file
                ]
                
                logger.debug(f"🚀 Команда FFmpeg: {' '.join(ffmpeg_cmd)}")
                
                try:
                    subprocess.run(ffmpeg_cmd, check=True, capture_output=True, text=True)
                except subprocess.CalledProcessError as e:
                    logger.error(f"❌ Ошибка FFmpeg: {e}")
                    logger.error(f"Stderr: {e.stderr}")
                    raise
                
                logger.debug(f"✅ Аудио извлечено в: {temp_audio_file}")
                return temp_audio_file
            
            # Для других форматов - стандартная конвертация
            temp_audio_file = os.path.join(temp_dir, f"{file_name}_{timestamp}.wav")
            
            ffmpeg_cmd = [
                ffmpeg_path,
                '-y',  # Перезаписывать файлы
                '-i', video_path,
                '-vn',  # Убираем видео
                '-acodec', 'pcm_s16le',  # Кодек для WAV
                '-ar', '44100',  # Частота дискретизации
                '-ac', '1',  # Моно канал
                temp_audio_file
            ]
            
            logger.debug(f"🚀 Команда FFmpeg: {' '.join(ffmpeg_cmd)}")
            
            try:
                subprocess.run(ffmpeg_cmd, check=True, capture_output=True, text=True)
            except subprocess.CalledProcessError as e:
                logger.error(f"❌ Ошибка FFmpeg: {e}")
                logger.error(f"Stderr: {e.stderr}")
                raise
            
            logger.debug(f"✅ Аудио извлечено в: {temp_audio_file}")
            return temp_audio_file
        
        except Exception as e:
            logger.error(f"❌ Ошибка извлечения аудио: {e}")
            logger.error(traceback.format_exc())
            raise

    async def get_video_info(self, url: str) -> dict:
        """Получение информации о видео"""
        try:
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'extract_flat': True
            }
            
            loop = asyncio.get_event_loop()
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = await loop.run_in_executor(None, ydl.extract_info, url, False)
                
            return {
                'title': info.get('title', 'Unknown'),
                'duration': info.get('duration', 0),
                'channel': info.get('uploader', 'Unknown'),
                'upload_date': info.get('upload_date', 'Unknown')
            }
            
        except Exception as e:
            logger.error(f"Ошибка при получении информации о видео: {str(e)}")
            raise

    async def cleanup_temp_files(self):
        """Очистка временных файлов"""
        try:
            for file in os.listdir(self.temp_dir):
                file_path = os.path.join(self.temp_dir, file)
                try:
                    if os.path.isfile(file_path):
                        os.unlink(file_path)
                except Exception as e:
                    logger.error(f"Ошибка при удалении файла {file_path}: {str(e)}")
        except Exception as e:
            logger.error(f"Ошибка при очистке временных файлов: {str(e)}")
            raise

    def convert_to_wav(self, file_path: str, target_sample_rate: int = 16000) -> str:
        """
        Конвертация аудио/видео файла в WAV формат с указанной частотой дискретизации
        
        :param file_path: Путь к исходному файлу
        :param target_sample_rate: Целевая частота дискретизации (по умолчанию 16000 для Whisper)
        :return: Путь к конвертированному WAV файлу
        """
        try:
            # Генерируем имя для выходного файла
            output_filename = f"converted_{int(time.time())}.wav"
            output_path = os.path.join(self.temp_dir, output_filename)
            
            # Полный путь к FFmpeg
            ffmpeg_exe = os.path.join(self.ffmpeg_location, 'ffmpeg.exe')
            
            # Команда FFmpeg для конвертации
            ffmpeg_command = [
                ffmpeg_exe, 
                '-i', file_path,  # Входной файл
                '-vn',            # Отключаем видео
                '-acodec', 'pcm_s16le',  # Кодек для WAV
                '-ar', str(target_sample_rate),  # Частота дискретизации
                '-ac', '1',       # Моно канал
                output_path
            ]
            
            # Выполняем конвертацию
            result = subprocess.run(
                ffmpeg_command, 
                capture_output=True, 
                text=True, 
                timeout=300  # Таймаут 5 минут
            )
            
            # Проверяем результат
            if result.returncode != 0:
                logger.error(f"Ошибка конвертации: {result.stderr}")
                raise Exception(f"Не удалось конвертировать файл: {result.stderr}")
            
            # Проверяем, что файл создался
            if not os.path.exists(output_path):
                raise Exception("Файл после конвертации не был создан")
            
            logger.info(f"Файл успешно конвертирован: {output_path}")
            return output_path
        
        except subprocess.TimeoutExpired:
            logger.error("Превышено время конвертации файла")
            raise Exception("Превышено время конвертации файла")
        except Exception as e:
            logger.error(f"Ошибка при конвертации файла: {e}")
            raise

    def extract_audio(self, video_path: str) -> str:
        """
        Извлечение аудио из видео файла
        
        :param video_path: Путь к видео файлу
        :return: Путь к извлеченному аудио файлу
        """
        try:
            # Генерируем имя для выходного файла
            output_filename = f"extracted_audio_{int(time.time())}.wav"
            output_path = os.path.join(self.temp_dir, output_filename)
            
            # Полный путь к FFmpeg
            ffmpeg_exe = os.path.join(self.ffmpeg_location, 'ffmpeg.exe')
            
            # Команда FFmpeg для извлечения аудио
            ffmpeg_command = [
                ffmpeg_exe, 
                '-i', video_path,  # Входной файл
                '-vn',             # Отключаем видео
                '-acodec', 'pcm_s16le',  # Кодек для WAV
                '-ar', '16000',    # Частота дискретизации
                '-ac', '1',        # Моно канал
                output_path
            ]
            
            # Выполняем извлечение аудио
            result = subprocess.run(
                ffmpeg_command, 
                capture_output=True, 
                text=True, 
                timeout=300  # Таймаут 5 минут
            )
            
            # Проверяем результат
            if result.returncode != 0:
                logger.error(f"Ошибка извлечения аудио: {result.stderr}")
                raise Exception(f"Не удалось извлечь аудио: {result.stderr}")
            
            # Проверяем, что файл создался
            if not os.path.exists(output_path):
                raise Exception("Файл аудио после извлечения не был создан")
            
            logger.info(f"Аудио успешно извлечено: {output_path}")
            return output_path
        
        except subprocess.TimeoutExpired:
            logger.error("Превышено время извлечения аудио")
            raise Exception("Превышено время извлечения аудио")
        except Exception as e:
            logger.error(f"Ошибка при извлечении аудио: {e}")
            raise

    def get_video_duration(self, video_path: str) -> float:
        """
        Получение длительности видео файла
        
        :param video_path: Путь к видео файлу
        :return: Длительность видео в секундах
        """
        try:
            # Полный путь к FFprobe
            ffprobe_exe = os.path.join(self.ffmpeg_location, 'ffprobe.exe')
            
            # Команда FFprobe для получения длительности
            ffprobe_command = [
                ffprobe_exe,
                '-v', 'error',
                '-show_entries', 'format=duration',
                '-of', 'default=noprint_wrappers=1:nokey=1',
                video_path
            ]
            
            # Выполняем команду
            result = subprocess.run(
                ffprobe_command, 
                capture_output=True, 
                text=True, 
                timeout=30  # Таймаут 30 секунд
            )
            
            # Проверяем результат
            if result.returncode != 0:
                logger.error(f"Ошибка получения длительности: {result.stderr}")
                raise Exception(f"Не удалось получить длительность видео: {result.stderr}")
            
            # Парсим длительность
            duration = float(result.stdout.strip())
            
            logger.info(f"Длительность видео: {duration} секунд")
            return duration
        
        except subprocess.TimeoutExpired:
            logger.error("Превышено время получения длительности видео")
            raise Exception("Превышено время получения длительности видео")
        except Exception as e:
            logger.error(f"Ошибка при получении длительности видео: {e}")
            raise
