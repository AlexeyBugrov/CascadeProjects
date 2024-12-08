import cv2
import numpy as np
from matplotlib import pyplot as plt
import os
from pathlib import Path
from config import (
    IMAGE_SETTINGS,
    MORPHOLOGY_SETTINGS,
    THRESHOLD_SETTINGS,
    VISUALIZATION_SETTINGS,
    FILE_SETTINGS,
    DROPLET_DETECTION
)

def normalize_path(path):
    """Преобразование пути в правильный формат для Python"""
    # Убираем кавычки, если они есть
    path = path.strip('"\'')
    # Заменяем обратные слеши на прямые
    path = path.replace('\\', '/')
    return path

def check_image_file():
    """Проверка наличия файла изображения"""
    # Нормализуем путь
    image_path = normalize_path(FILE_SETTINGS['IMAGE_PATH'])
    image_path = Path(image_path)
    
    if not image_path.is_file():
        raise FileNotFoundError(
            f"Файл изображения не найден: {image_path}\n"
            "Проверьте путь к файлу в настройках"
        )
    return str(image_path.absolute())

def detect_droplets():
    # Получаем активный режим и его параметры
    active_mode = DROPLET_DETECTION['ACTIVE_MODE']
    detection_params = DROPLET_DETECTION[active_mode]
    
    # Проверка и получение пути к изображению
    image_path = check_image_file()
    
    # Чтение изображения
    image = cv2.imdecode(
        np.fromfile(image_path, dtype=np.uint8),
        cv2.IMREAD_COLOR
    )
    
    if image is None:
        raise ValueError(
            f"Не удалось прочитать изображение: {image_path}\n"
            "Убедитесь, что файл является корректным изображением"
        )
    
    # Преобразование в оттенки серого
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    
    # Улучшение контраста с помощью CLAHE
    clahe = cv2.createCLAHE(
        clipLimit=IMAGE_SETTINGS['CLAHE_CLIP_LIMIT'],
        tileGridSize=IMAGE_SETTINGS['CLAHE_GRID_SIZE']
    )
    enhanced = clahe.apply(gray)
    
    # Билатеральная фильтрация для сохранения краев
    denoised = cv2.bilateralFilter(enhanced, 9, 75, 75)
    
    # Локальная адаптивная бинаризация
    binary = cv2.adaptiveThreshold(
        denoised,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,
        THRESHOLD_SETTINGS['BLOCK_SIZE'],
        THRESHOLD_SETTINGS['C']
    )
    
    # Морфологические операции
    kernel = np.ones(MORPHOLOGY_SETTINGS['KERNEL_SIZE'], np.uint8)
    
    # Открытие для удаления мелкого шума
    processed = cv2.morphologyEx(
        binary,
        cv2.MORPH_OPEN,
        kernel,
        iterations=MORPHOLOGY_SETTINGS['ITERATIONS']
    )
    
    # Закрытие для заполнения разрывов
    processed = cv2.morphologyEx(
        processed,
        cv2.MORPH_CLOSE,
        kernel,
        iterations=MORPHOLOGY_SETTINGS['ITERATIONS']
    )
    
    # Distance transform для разделения слипшихся капель
    dist_transform = cv2.distanceTransform(
        processed, 
        eval(detection_params['DISTANCE_TRANSFORM']['DIST_TYPE']), 
        detection_params['DISTANCE_TRANSFORM']['MASK_SIZE']
    )
    
    # Нормализация distance transform
    dist_transform = cv2.normalize(dist_transform, None, 0, 1.0, cv2.NORM_MINMAX)
    
    # Выделение уверенного переднего плана
    _, sure_fg = cv2.threshold(
        dist_transform, 
        detection_params['DISTANCE_TRANSFORM']['FOREGROUND_THRESHOLD'],
        255, 
        cv2.THRESH_BINARY
    )
    sure_fg = np.uint8(sure_fg)
    
    # Нахождение контуров
    contours, _ = cv2.findContours(
        sure_fg,
        cv2.RETR_EXTERNAL,
        cv2.CHAIN_APPROX_SIMPLE
    )
    
    # Фильтрация и подсчет капель
    valid_droplets = []
    for contour in contours:
        area = cv2.contourArea(contour)
        if IMAGE_SETTINGS['MIN_DROPLET_SIZE'] < area < IMAGE_SETTINGS['MAX_DROPLET_SIZE']:
            perimeter = cv2.arcLength(contour, True)
            if perimeter > 0:
                circularity = 4 * np.pi * area / (perimeter ** 2)
                if circularity > detection_params['CIRCULARITY_THRESHOLD']:
                    valid_droplets.append(contour)
    
    # Создание изображений с результатами
    result = image.copy()
    droplets_mask = np.zeros_like(gray)
    
    # Отрисовка контуров
    cv2.drawContours(
        result,
        valid_droplets,
        -1,
        VISUALIZATION_SETTINGS['CONTOUR_COLOR'],
        VISUALIZATION_SETTINGS['CONTOUR_THICKNESS']
    )
    
    # Создание маски с каплями
    cv2.drawContours(
        droplets_mask,
        valid_droplets,
        -1,
        (255),
        -1
    )
    
    return {
        'total_droplets': len(valid_droplets),
        'original_image': image,
        'result_image': result,
        'droplets_mask': droplets_mask,
        'binary_result': processed,
        'droplet_areas': [cv2.contourArea(c) for c in valid_droplets]
    }

def save_results(results):
    """Сохранение результатов обработки"""
    # Создаем директорию для результатов, если её нет
    output_dir = Path(FILE_SETTINGS['OUTPUT_DIR'])
    output_dir.mkdir(exist_ok=True)
    
    try:
        # Сохранение изображения с обнаруженными каплями
        cv2.imwrite(
            str(output_dir / 'detection_results.png'),
            results['result_image']
        )
        
        # Сохранение маски капель
        cv2.imwrite(
            str(output_dir / 'droplets_mask.png'),
            results['droplets_mask']
        )
        
        # Сохранение результата бинаризации
        cv2.imwrite(
            str(output_dir / 'binary_result.png'),
            results['binary_result']
        )
        
        # Построение и сохранение гистограммы размеров
        plt.figure(figsize=(10, 6))
        plt.hist(results['droplet_areas'], bins=50)
        plt.title('Распределение размеров капель')
        plt.xlabel('Площадь (пиксели)')
        plt.ylabel('Количество капель')
        plt.savefig(str(output_dir / 'size_distribution.png'))
        plt.close()
        
        print(f"Обнаружено капель: {results['total_droplets']}")
        print(f"Результаты сохранены в папку: {FILE_SETTINGS['OUTPUT_DIR']}")
        print("Сохраненные файлы:")
        print("- detection_results.png - изображение с обнаруженными каплями")
        print("- droplets_mask.png - маска капель (белые капли на черном фоне)")
        print("- binary_result.png - результат бинаризации")
        print("- size_distribution.png - распределение размеров капель")
        
    except Exception as e:
        print(f"Ошибка при сохранении результатов: {str(e)}")

if __name__ == "__main__":
    try:
        # Получение результатов обработки
        results = detect_droplets()
        # Сохранение результатов
        save_results(results)
    except Exception as e:
        print(f"Ошибка: {str(e)}")
