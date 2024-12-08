import os
import math
import argparse
from moviepy.editor import VideoFileClip, AudioFileClip
from typing import Optional

# Максимальный размер аудио файла в МБ
MAX_AUDIO_SIZE_MB = 20

def calculate_bitrate(audio_duration: float, target_size_mb: float) -> int:
    """
    Рассчитывает необходимый битрейт для достижения целевого размера файла.
    
    Args:
        audio_duration (float): Длительность аудио в секундах
        target_size_mb (float): Целевой размер файла в МБ
    
    Returns:
        int: Оптимальный битрейт в кbps
    """
    # Конвертируем размер в биты (1 MB = 8 * 1024 * 1024 бит)
    target_size_bits = target_size_mb * 8 * 1024 * 1024
    
    # Рассчитываем битрейт (bits/s)
    bitrate = math.floor(target_size_bits / audio_duration)
    
    # Конвертируем в kbps и округляем до ближайшего меньшего числа, кратного 32
    # (большинство кодеков MP3 работают лучше с битрейтами, кратными 32)
    kbps = math.floor((bitrate / 1024) / 32) * 32
    
    # Устанавливаем минимальный битрейт 32 kbps
    return max(32, kbps)

def compress_audio(input_path: str, output_path: str, target_size_mb: float) -> str:
    """
    Сжимает аудио файл до указанного размера.
    
    Args:
        input_path (str): Путь к входному аудио файлу
        output_path (str): Путь для сохранения сжатого файла
        target_size_mb (float): Целевой размер файла в МБ
    
    Returns:
        str: Путь к сжатому файлу
    """
    # Загружаем аудио
    audio = AudioFileClip(input_path)
    
    # Рассчитываем необходимый битрейт
    bitrate = calculate_bitrate(audio.duration, target_size_mb)
    print(f"      • Длительность: {audio.duration:.1f} сек")
    print(f"      • Целевой размер: {target_size_mb:.1f}MB")
    print(f"      • Расчетный битрейт: {bitrate}kbps")
    
    # Сохраняем с новым битрейтом
    audio.write_audiofile(output_path, bitrate=f"{bitrate}k")
    audio.close()
    
    final_size = get_file_size_mb(output_path)
    print(f"      • Фактический размер: {final_size:.1f}MB")
    
    return output_path

def get_file_size_mb(file_path: str) -> float:
    """Возвращает размер файла в МБ."""
    return os.path.getsize(file_path) / (1024 * 1024)

def extract_audio(input_path: str, output_path: Optional[str] = None, bitrate: str = "128k") -> str:
    """
    Извлекает или конвертирует аудио в формат MP3.
    Если входной файл - видео, извлекает из него аудио дорожку.
    Если входной файл - аудио, конвертирует его в MP3 если нужно.
    Если размер превышает MAX_AUDIO_SIZE_MB, файл автоматически сжимается.
    
    Args:
        input_path (str): Путь к входному файлу (видео или аудио)
        output_path (Optional[str]): Путь для сохранения MP3 файла. 
                                   Если не указан, создается рядом с входным файлом
        bitrate (str): Начальный битрейт аудио (по умолчанию "128k")
    
    Returns:
        str: Путь к созданному MP3 файлу
    
    Raises:
        FileNotFoundError: Если входной файл не найден
        ValueError: Если входной файл имеет неподдерживаемый формат
        Exception: При ошибках обработки
    """
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Файл не найден: {input_path}")
    
    # Проверяем расширение файла
    video_extensions = ['.mp4', '.avi', '.wmv', '.mkv', '.mov', '.flv']
    audio_extensions = ['.mp3', '.wav', '.m4a', '.aac', '.ogg', '.flac', '.wma']
    
    is_video = any(input_path.lower().endswith(ext) for ext in video_extensions)
    is_audio = any(input_path.lower().endswith(ext) for ext in audio_extensions)
    
    if not (is_video or is_audio):
        raise ValueError(
            f"Неподдерживаемый формат файла. Поддерживаются:\n"
            f"Видео: {', '.join(video_extensions)}\n"
            f"Аудио: {', '.join(audio_extensions)}"
        )
    
    try:
        # Если выходной путь не указан, создаем его рядом с входным файлом
        if output_path is None:
            output_path = os.path.splitext(input_path)[0] + '.mp3'
        
        # Создаем временный путь для исходного аудио
        temp_path = output_path + '.temp.mp3'
        
        # Создаем папку для выходного файла, если её нет
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        
        print(f"[1/4] Загрузка файла {input_path}...")
        initial_size = get_file_size_mb(input_path)
        print(f"      Размер исходного файла: {initial_size:.1f}MB")
        
        # Обрабатываем в зависимости от типа файла
        if is_video:
            print(f"[2/4] Извлечение аудио дорожки из видео...")
            with VideoFileClip(input_path) as video:
                audio = video.audio
                if audio is None:
                    raise ValueError("В видео файле отсутствует аудио дорожка")
                print(f"      Длительность: {video.duration:.1f} сек")
                print(f"      Начальный битрейт: {bitrate}")
                audio.write_audiofile(temp_path, bitrate=bitrate)
        else:
            print(f"[2/4] Обработка аудио файла...")
            with AudioFileClip(input_path) as audio:
                print(f"      Длительность: {audio.duration:.1f} сек")
                print(f"      Начальный битрейт: {bitrate}")
                audio.write_audiofile(temp_path, bitrate=bitrate)
        
        # Проверяем размер полученного файла
        audio_size = get_file_size_mb(temp_path)
        print(f"[3/4] Анализ аудио...")
        print(f"      Размер аудио: {audio_size:.1f}MB")
        
        if audio_size > MAX_AUDIO_SIZE_MB:
            print(f"      ⚠️ Размер превышает лимит в {MAX_AUDIO_SIZE_MB}MB")
            print(f"[4/4] Сжатие аудио до допустимого размера...")
            
            # Сжимаем до целевого размера
            compress_audio(temp_path, output_path, MAX_AUDIO_SIZE_MB)
            
            # Удаляем временный файл
            os.remove(temp_path)
        else:
            print(f"      ✓ Размер в пределах допустимого")
            print(f"[4/4] Финализация аудио файла...")
            # Если размер в пределах нормы, просто переименовываем временный файл
            os.replace(temp_path, output_path)
        
        final_size = get_file_size_mb(output_path)
        print("\n✅ Обработка завершена успешно!")
        print(f"   • Исходный размер: {initial_size:.1f}MB")
        print(f"   • Конечный размер: {final_size:.1f}MB")
        
        return output_path
        
    except Exception as e:
        # Очищаем временные файлы при ошибке
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise Exception(f"Ошибка при обработке файла: {str(e)}")

def main():
    parser = argparse.ArgumentParser(description="Извлечение или конвертация аудио в формат MP3")
    parser.add_argument("input_path", help="Путь к входному файлу (видео или аудио)")
    parser.add_argument("-o", "--output", help="Путь для сохранения MP3 файла (опционально)")
    parser.add_argument("-b", "--bitrate", default="128k", help="Начальный битрейт аудио (по умолчанию 128k)")
    
    args = parser.parse_args()
    
    try:
        output_path = extract_audio(args.input_path, args.output, args.bitrate)
        print(f"\nАудио успешно извлечено и сохранено в:\n{output_path}")
    except Exception as e:
        print(f"\nОшибка: {str(e)}")
        exit(1)

if __name__ == "__main__":
    main()
