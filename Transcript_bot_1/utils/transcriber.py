import os
import logging
import whisper
import torch

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Transcriber:
    def __init__(self, model_size: str = 'base', language: str = 'ru'):
        """
        Инициализация транскрайбера
        
        :param model_size: Размер модели Whisper ('tiny', 'base', 'small', 'medium', 'large')
        :param language: Язык транскрибации
        """
        try:
            # Проверяем доступность CUDA
            self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
            logger.info(f"Используется устройство: {self.device}")
            
            # Загружаем модель Whisper
            logger.info(f"Загрузка модели Whisper: {model_size}")
            self.model = whisper.load_model(model_size).to(self.device)
            
            # Параметры транскрибации
            self.language = language
        except Exception as e:
            logger.error(f"Ошибка инициализации Whisper: {e}")
            raise

    def transcribe(self, audio_path: str) -> str:
        """
        Транскрибация аудиофайла
        
        :param audio_path: Путь к аудиофайлу
        :return: Текст транскрибации
        """
        try:
            # Проверяем существование файла
            if not os.path.exists(audio_path):
                raise FileNotFoundError(f"Файл не найден: {audio_path}")
            
            # Проверяем размер файла
            file_size = os.path.getsize(audio_path)
            max_file_size = 50 * 1024 * 1024  # 50 МБ
            
            if file_size > max_file_size:
                raise ValueError(f"Файл слишком большой. Максимальный размер: {max_file_size/1024/1024} МБ")
            
            # Выполняем транскрибацию
            logger.info(f"Начало транскрибации файла: {audio_path}")
            result = self.model.transcribe(
                audio_path, 
                language=self.language,
                fp16=self.device == 'cuda'  # Используем FP16 только на CUDA
            )
            
            # Извлекаем текст
            transcription_text = result['text'].strip()
            
            # Проверяем, что текст не пустой
            if not transcription_text:
                logger.warning("Транскрибация не содержит текста")
                return "Не удалось распознать текст"
            
            logger.info(f"Транскрибация завершена. Длина текста: {len(transcription_text)} символов")
            return transcription_text
        
        except Exception as e:
            logger.error(f"Ошибка при транскрибации: {e}", exc_info=True)
            raise
