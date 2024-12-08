import os
import math
import subprocess
from moviepy.editor import VideoFileClip
from pydub import AudioSegment
import yt_dlp
from datetime import datetime
from config import FFMPEG_PATH, FFMPEG_EXECUTABLE, FFPROBE_EXECUTABLE
import logging

class AudioProcessor:
    def __init__(self, temp_dir):
        self.temp_dir = temp_dir
        if not os.path.exists(temp_dir):
            os.makedirs(temp_dir)
        
        # Настройка путей для FFmpeg
        os.environ["PATH"] = FFMPEG_PATH + os.pathsep + os.environ.get("PATH", "")

    def calculate_target_bitrate(self, duration: float, target_size_mb: float, channels: int) -> int:
        """
        Рассчитывает оптимальный битрейт для достижения целевого размера файла.
        
        Args:
            duration: Длительность аудио в секундах
            target_size_mb: Целевой размер файла в мегабайтах
            channels: Количество аудио каналов
        
        Returns:
            Оптимальный битрейт в kbps, округленный до ближайшего меньшего числа, кратного 8
        """
        # Конвертируем размер в биты
        target_size_bits = target_size_mb * 8 * 1024 * 1024
        
        # Рассчитываем битрейт
        bitrate = (target_size_bits / (duration * channels * 1024))
        
        # Округляем до ближайшего меньшего числа, кратного 8
        return math.floor(bitrate / 8) * 8

    def optimize_audio_file(self, input_path: str, output_path: str, target_size_mb: float = 20.0) -> tuple[str, dict]:
        """
        Оптимизирует аудио файл для достижения целевого размера с сохранением максимального качества.
        Использует поэтапное снижение качества для достижения целевого размера.
        
        Args:
            input_path: Путь к входному файлу
            output_path: Путь для сохранения оптимизированного файла
            target_size_mb: Целевой размер файла в мегабайтах
        
        Returns:
            Кортеж из пути к оптимизированному файлу и словаря с информацией о конвертации
        """
        duration = self.get_audio_duration(input_path)
        temp_path = output_path + ".temp.mp3"
        
        # Начальные параметры
        channels = 2  # начинаем со стерео
        min_bitrate = 16  # минимально допустимый битрейт
        max_bitrate = 192  # максимальный битрейт
        current_bitrate = max_bitrate
        
        optimization_steps = []
        
        while True:
            # Шаг 1: Пробуем с текущими параметрами
            command = [
                FFMPEG_EXECUTABLE,
                '-i', input_path,
                '-acodec', 'libmp3lame',
                '-ac', str(channels),
                '-ar', '16000',
                '-b:a', f'{current_bitrate}k',
                '-y',
                temp_path
            ]
            
            process = subprocess.run(command, capture_output=True, text=True)
            if process.returncode != 0:
                raise Exception(f"FFmpeg conversion error: {process.stderr}")
            
            # Проверяем результат
            actual_size = os.path.getsize(temp_path) / (1024 * 1024)
            
            optimization_steps.append({
                'step': len(optimization_steps) + 1,
                'channels': channels,
                'bitrate': current_bitrate,
                'size_mb': actual_size
            })
            
            if actual_size <= target_size_mb:
                # Цель достигнута
                os.rename(temp_path, output_path)
                return output_path, {
                    'final_size_mb': actual_size,
                    'channels': channels,
                    'bitrate': current_bitrate,
                    'duration': duration,
                    'optimization_steps': optimization_steps
                }
            
            # Рассчитываем следующий битрейт
            next_bitrate = self.calculate_target_bitrate(duration, target_size_mb, channels)
            
            if next_bitrate >= min_bitrate:
                # Шаг 2: Пробуем снизить битрейт
                current_bitrate = max(min_bitrate, next_bitrate)
            elif channels > 1:
                # Шаг 3: Если битрейт уже минимальный, снижаем количество каналов
                channels = 1
                current_bitrate = self.calculate_target_bitrate(duration, target_size_mb, channels)
                current_bitrate = max(min_bitrate, min(max_bitrate, current_bitrate))
            else:
                # Если все методы испробованы, возвращаем лучший возможный результат
                os.rename(temp_path, output_path)
                return output_path, {
                    'final_size_mb': actual_size,
                    'channels': channels,
                    'bitrate': current_bitrate,
                    'duration': duration,
                    'optimization_steps': optimization_steps,
                    'warning': 'Could not achieve target size while maintaining minimum quality'
                }

    def get_audio_duration(self, file_path: str) -> float:
        """Получает длительность аудио/видео файла в секундах."""
        command = [
            FFPROBE_EXECUTABLE,
            '-v', 'error',
            '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            file_path
        ]
        
        try:
            result = subprocess.run(command, capture_output=True, text=True)
            return float(result.stdout.strip())
        except Exception as e:
            raise Exception(f"Ошибка при получении длительности файла: {str(e)}")

    def process_audio_file(self, input_path: str, output_path: str, target_size_mb: float = 24) -> str:
        """
        Обрабатывает аудио файл с учетом ограничения размера.
        """
        try:
            # Получаем длительность
            duration = self.get_audio_duration(input_path)
            
            # Рассчитываем оптимальный битрейт
            bitrate = self.calculate_target_bitrate(duration, target_size_mb, 2)
            
            print(f"Обработка аудио: длительность={duration:.1f}с, битрейт={bitrate}kbps")
            
            # Конвертируем с рассчитанным битрейтом
            command = [
                FFMPEG_EXECUTABLE,
                '-i', input_path,
                '-acodec', 'libmp3lame',    # MP3 кодек
                '-ac', '2',                 # стерео
                '-ar', '24000',             # 24kHz (хорошо для речи)
                '-b:a', f'{bitrate}k',      # рассчитанный битрейт
                '-y',                       # перезаписать если существует
                output_path
            ]
            
            process = subprocess.run(command, capture_output=True, text=True)
            
            if process.returncode != 0:
                raise Exception(f"Ошибка FFmpeg: {process.stderr}")
            
            return output_path
            
        except Exception as e:
            if os.path.exists(output_path):
                os.remove(output_path)
            raise Exception(f"Ошибка обработки аудио: {str(e)}")

    def download_youtube_video(self, url):
        """Download YouTube video and extract audio"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        temp_output = os.path.join(self.temp_dir, f"yt_{timestamp}_temp.m4a")
        final_output = os.path.join(self.temp_dir, f"yt_{timestamp}.mp3")
        
        try:
            # Сначала скачиваем в m4a (лучшее качество)
            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': temp_output,
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'm4a',
                }],
                'ffmpeg_location': FFMPEG_PATH,
                'socket_timeout': 30,
                'retries': 3,
                'fragment_retries': 3,
                'ignoreerrors': True,
                'quiet': False,
                'no_warnings': False,
            }
            
            # Получаем информацию о видео
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                if not info:
                    raise Exception("Failed to extract video information")

                # Загружаем видео
                error_code = ydl.download([url])
                if error_code != 0:
                    raise Exception("Failed to download video")
                
                if not os.path.exists(temp_output):
                    raise Exception("Download completed but file not found")
            
            # Конвертируем в mp3 с оптимальными параметрами
            command = [
                FFMPEG_EXECUTABLE,
                '-i', temp_output,
                '-acodec', 'libmp3lame',    # MP3 кодек
                '-ac', '2',                 # стерео (лучше для распознавания речи)
                '-ar', '24000',             # 24kHz (хорошее качество для речи)
                '-b:a', '128k',             # 128kbps битрейт (баланс качества и размера)
                '-y',                       # перезаписать если существует
                final_output
            ]
            
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            stdout, stderr = process.communicate()
            
            if process.returncode != 0:
                raise Exception(f"FFmpeg conversion error: {stderr.decode()}")
            
            # Проверяем размер файла (должен быть меньше 25 MB)
            file_size = os.path.getsize(final_output) / (1024 * 1024)  # в MB
            if file_size > 24:  # оставляем небольшой запас
                # Если файл слишком большой, пересжимаем с меньшим битрейтом
                command[9] = '64k'  # уменьшаем битрейт до 64kbps
                process = subprocess.Popen(
                    command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
                stdout, stderr = process.communicate()
                
                if process.returncode != 0:
                    raise Exception(f"FFmpeg recompression error: {stderr.decode()}")
            
            # Удаляем временный файл
            if os.path.exists(temp_output):
                os.remove(temp_output)
            
            # Возвращаем путь к файлу и информацию о видео
            return final_output, {
                'title': info.get('title', 'Unknown'),
                'channel': info.get('uploader', 'Unknown'),
                'duration': str(datetime.fromtimestamp(info.get('duration', 0)).strftime('%H:%M:%S')),
                'upload_date': info.get('upload_date', 'Unknown'),
                'video_url': url,
                'original_description': info.get('description', 'No description available'),
                'process_date': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            
        except Exception as e:
            # Очищаем временные файлы при ошибке
            for file in [temp_output, final_output]:
                if os.path.exists(file):
                    os.remove(file)
            raise Exception(f"YouTube download error: {str(e)}")

    def extract_audio(self, video_path):
        """Extract audio from video file and return path to audio file"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        temp_path = os.path.join(self.temp_dir, f"audio_{timestamp}_temp.mp3")
        final_path = os.path.join(self.temp_dir, f"audio_{timestamp}.mp3")
        
        try:
            # Сначала извлекаем аудио с хорошим качеством
            command = [
                FFMPEG_EXECUTABLE,
                '-i', video_path,
                '-vn',                   # отключаем видео
                '-acodec', 'libmp3lame', # MP3 кодек
                '-ac', '2',              # стерео
                '-ar', '24000',          # 24kHz
                '-b:a', '192k',          # начальное хорошее качество
                '-y',                    # перезаписать если существует
                temp_path
            ]
            
            process = subprocess.run(command, capture_output=True, text=True)
            
            if process.returncode != 0:
                raise Exception(f"Ошибка FFmpeg: {process.stderr}")
            
            # Проверяем размер файла
            file_size = os.path.getsize(temp_path) / (1024 * 1024)  # в MB
            
            if file_size > 24:
                print(f"Размер аудио ({file_size:.1f}MB) превышает лимит. Выполняется сжатие...")
                self.process_audio_file(temp_path, final_path)
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                return final_path
            else:
                return temp_path
                
        except Exception as e:
            # Очищаем временные файлы при ошибке
            for path in [temp_path, final_path]:
                if os.path.exists(path):
                    os.remove(path)
            raise Exception(f"Ошибка извлечения аудио: {str(e)}")

    def process_audio_message(self, audio_file_path: str) -> str:
        """
        Обрабатывает аудио сообщение: оптимизирует размер и качество.
        
        Args:
            audio_file_path: Путь к входному аудио файлу
            
        Returns:
            Путь к обработанному файлу
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = os.path.join(self.temp_dir, f"processed_{timestamp}.mp3")
        
        try:
            # Получаем размер исходного файла
            file_size = os.path.getsize(audio_file_path) / (1024 * 1024)  # в MB
            
            if file_size > 20:
                # Если файл большой, используем оптимизацию
                output_path, conversion_info = self.optimize_audio_file(
                    audio_file_path, 
                    output_path,
                    target_size_mb=20.0
                )
                logging.info(f"Audio optimization results: {conversion_info}")
                return output_path
            
            # Для небольших файлов используем базовые параметры
            command = [
                FFMPEG_EXECUTABLE,
                '-i', audio_file_path,
                '-acodec', 'libmp3lame',
                '-ac', '1',                 # начинаем сразу с моно для маленьких файлов
                '-ar', '16000',
                '-b:a', '32k',              # базовый битрейт для небольших файлов
                '-y',
                output_path
            ]
            
            process = subprocess.run(command, capture_output=True, text=True)
            if process.returncode != 0:
                raise Exception(f"FFmpeg conversion error: {process.stderr}")
            
            return output_path
            
        except Exception as e:
            raise Exception(f"Ошибка обработки аудио сообщения: {str(e)}")

    def cleanup_temp_files(self, max_age_hours=24):
        """Clean up old temporary files"""
        try:
            current_time = datetime.now()
            for file in os.listdir(self.temp_dir):
                file_path = os.path.join(self.temp_dir, file)
                if os.path.isfile(file_path):
                    file_time = datetime.fromtimestamp(os.path.getctime(file_path))
                    age = current_time - file_time
                    if age.total_seconds() > max_age_hours * 3600:
                        try:
                            os.remove(file_path)
                        except Exception as e:
                            logging.warning(f"Failed to remove old file {file_path}: {str(e)}")
        except Exception as e:
            logging.warning(f"Error during cleanup: {str(e)}")
