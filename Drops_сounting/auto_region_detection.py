import cv2
import numpy as np
from pathlib import Path
from dark_region_detection import detect_dark_droplets
from light_region_detection import detect_light_droplets
from config import DEBUG_PATHS, FILE_SETTINGS
import matplotlib.pyplot as plt
from scipy.ndimage import gaussian_filter1d
from scipy.signal import find_peaks

def create_output_dirs():
    """Create necessary output directories"""
    output_dir = Path(DEBUG_PATHS['OUTPUT_DIR'])
    dark_dir = output_dir / 'dark_regions'
    light_dir = output_dir / 'light_regions'
    
    for dir_path in [output_dir, dark_dir, light_dir]:
        dir_path.mkdir(parents=True, exist_ok=True)
    
    return dark_dir, light_dir

def split_regions(image_path):
    """
    Разделяет изображение на светлые и темные области
    """
    # Загрузка изображения
    image = cv2.imdecode(np.fromfile(str(image_path), dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError(f"Failed to load image: {image_path}")
    
    # Конвертация в оттенки серого
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    
    # Применяем размытие для уменьшения шума
    blurred = cv2.GaussianBlur(gray, (21, 21), 0)
    
    # Применяем OTSU пороговую обработку для получения базовой маски
    _, base_mask = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    
    # Применяем морфологические операции для улучшения маски
    kernel = np.ones((25, 25), np.uint8)
    mask = cv2.morphologyEx(base_mask, cv2.MORPH_CLOSE, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    
    # Находим контуры регионов
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    # Создаем маски для светлых и темных областей
    height, width = gray.shape
    light_mask = np.zeros((height, width), dtype=np.uint8)
    dark_mask = np.zeros((height, width), dtype=np.uint8)
    
    for contour in contours:
        # Создаем маску для текущего контура
        region_mask = np.zeros((height, width), dtype=np.uint8)
        cv2.drawContours(region_mask, [contour], -1, 255, -1)
        
        # Вычисляем среднюю интенсивность в регионе
        mean_intensity = cv2.mean(gray, mask=region_mask)[0]
        
        # Анализируем гистограмму региона для определения типа
        hist = cv2.calcHist([gray], [0], region_mask, [256], [0, 256])
        hist_normalized = hist.ravel() / hist.sum()
        
        # Вычисляем пики гистограммы
        peaks = find_histogram_peaks(hist_normalized)
        
        # Определяем тип региона на основе нескольких критериев
        is_light = False
        if mean_intensity > 128:  # Базовый порог
            if len(peaks) >= 2:
                # Если есть несколько пиков, проверяем их распределение
                main_peak = max(peaks)
                if main_peak > 160:  # Основной пик должен быть в светлой области
                    is_light = True
            else:
                # Если один пик, используем более строгий порог
                is_light = mean_intensity > 160
        
        # Добавляем регион к соответствующей маске
        if is_light:
            light_mask = cv2.bitwise_or(light_mask, region_mask)
        else:
            dark_mask = cv2.bitwise_or(dark_mask, region_mask)
    
    # Применяем дополнительную обработку для уточнения границ
    kernel_refine = np.ones((5, 5), np.uint8)
    light_mask = cv2.erode(light_mask, kernel_refine, iterations=2)
    dark_mask = cv2.erode(dark_mask, kernel_refine, iterations=2)
    
    # Сохраняем маски для отладки
    if DEBUG_PATHS['SAVE_DEBUG_IMAGES']:
        output_dir = Path(DEBUG_PATHS['OUTPUT_DIR'])
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Сохраняем маски
        cv2.imwrite(str(output_dir / 'light_mask.png'), light_mask)
        cv2.imwrite(str(output_dir / 'dark_mask.png'), dark_mask)
        
        # Создаем визуализацию разделения
        visualization = np.zeros((height, width, 3), dtype=np.uint8)
        visualization[light_mask > 0] = [0, 255, 0]  # Зеленый для светлых областей
        visualization[dark_mask > 0] = [0, 0, 255]   # Красный для темных областей
        cv2.imwrite(str(output_dir / 'region_split.png'), visualization)
    
    return light_mask, dark_mask

def find_histogram_peaks(hist, min_distance=20, threshold_rel=0.2):
    """
    Находит значимые пики в гистограмме
    """
    # Сглаживаем гистограмму
    smoothed = gaussian_filter1d(hist, sigma=2)
    
    # Находим локальные максимумы
    peaks = find_peaks(smoothed, distance=min_distance, height=threshold_rel*np.max(smoothed))[0]
    
    return peaks

def filter_contours_by_mask(contours, mask):
    """
    Фильтрует контуры, оставляя только те, что находятся внутри маски
    """
    filtered_contours = []
    
    for contour in contours:
        # Создаем маску для контура
        contour_mask = np.zeros_like(mask)
        cv2.drawContours(contour_mask, [contour], -1, 255, -1)
        
        # Проверяем перекрытие с основной маской
        overlap = cv2.bitwise_and(contour_mask, mask)
        overlap_ratio = np.sum(overlap) / np.sum(contour_mask)
        
        # Если контур в основном находится внутри маски, сохраняем его
        if overlap_ratio > 0.7:  # Контур должен быть как минимум на 70% внутри маски
            filtered_contours.append(contour)
    
    return filtered_contours

def process_image(image_path):
    """
    Обрабатывает изображение, автоматически разделяя его на регионы
    """
    try:
        # Создаем output_dir
        output_dir = Path(DEBUG_PATHS['OUTPUT_DIR'])
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Загружаем изображение
        image = cv2.imdecode(np.fromfile(str(image_path), dtype=np.uint8), cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError(f"Failed to load image: {image_path}")
        
        # Разделяем изображение на регионы
        light_mask, dark_mask = split_regions(image_path)
        
        print("Обработка светлых областей...")
        light_contours = detect_light_droplets(image_path, debug=True, return_contours=True)
        if light_contours is None:
            light_contours = []
        
        print("Обработка темных областей...")
        dark_contours = detect_dark_droplets(image_path, debug=True, return_contours=True)
        if dark_contours is None:
            dark_contours = []
        
        # Фильтруем контуры по маскам
        light_filtered = filter_contours_by_mask(light_contours, light_mask)
        dark_filtered = filter_contours_by_mask(dark_contours, dark_mask)
        
        print(f"\nРезультаты анализа:")
        print(f"Найдено капель в светлой области: {len(light_filtered)}")
        print(f"Найдено капель в темной области: {len(dark_filtered)}")
        print(f"Всего капель: {len(light_filtered) + len(dark_filtered)}")
        
        # Создаем финальную визуализацию
        create_visualization(image, dark_mask, light_mask, dark_filtered, light_filtered, output_dir)
        print(f"\nВизуализация сохранена в: {output_dir / 'final_visualization.png'}")
        
        return light_filtered, dark_filtered
        
    except Exception as e:
        print(f"Ошибка при обработке изображения: {str(e)}")
        import traceback
        traceback.print_exc()
        return [], []

def save_masked_image(image, mask, output_path):
    """Save image with applied mask"""
    masked = cv2.bitwise_and(image, image, mask=mask)
    # Save using numpy to handle paths with non-ASCII characters
    is_success, buffer = cv2.imencode(".png", masked)
    if is_success:
        buffer.tofile(str(output_path))
    return masked

def create_visualization(image, dark_mask, light_mask, dark_contours, light_contours, output_dir):
    """Create final visualization with all detected droplets"""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Создаем копию изображения для визуализации
    visualization = image.copy()
    
    # Рисуем контуры капель разными цветами
    cv2.drawContours(visualization, dark_contours, -1, (0, 0, 255), 2)  # Красный для темных областей
    cv2.drawContours(visualization, light_contours, -1, (0, 255, 0), 2)  # Зеленый для светлых областей
    
    # Создаем полупрозрачные маски
    overlay = visualization.copy()
    overlay[dark_mask > 0] = (0, 0, 128)   # Темно-красный для темных областей
    overlay[light_mask > 0] = (0, 128, 0)   # Темно-зеленый для светлых областей
    
    # Смешиваем изображения
    cv2.addWeighted(overlay, 0.3, visualization, 0.7, 0, visualization)
    
    # Добавляем текст с количеством капель
    font = cv2.FONT_HERSHEY_SIMPLEX
    cv2.putText(visualization, f'Dark droplets: {len(dark_contours)}', 
                (10, 30), font, 1, (0, 0, 255), 2)
    cv2.putText(visualization, f'Light droplets: {len(light_contours)}', 
                (10, 70), font, 1, (0, 255, 0), 2)
    cv2.putText(visualization, f'Total: {len(dark_contours) + len(light_contours)}', 
                (10, 110), font, 1, (255, 255, 255), 2)
    
    # Сохраняем результат
    cv2.imwrite(str(output_dir / 'final_visualization.png'), visualization)

def auto_detect_regions(image_path):
    """
    Automatically detect dark and light regions in the image
    Returns masks for dark and light regions
    """
    # Read image using numpy to handle paths with non-ASCII characters
    image = cv2.imdecode(np.fromfile(str(image_path), dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError(f"Failed to load image: {image_path}")
    
    # Convert to grayscale
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    
    # Apply Gaussian blur to reduce noise
    blurred = cv2.GaussianBlur(gray, (21, 21), 0)
    
    # Use Otsu's method to find optimal threshold
    _, binary = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    
    # Create masks for dark and light regions
    dark_mask = (binary == 0).astype(np.uint8) * 255
    light_mask = (binary == 255).astype(np.uint8) * 255
    
    # Apply morphological operations to clean up the masks
    kernel = np.ones((50, 50), np.uint8)
    dark_mask = cv2.morphologyEx(dark_mask, cv2.MORPH_CLOSE, kernel)
    dark_mask = cv2.morphologyEx(dark_mask, cv2.MORPH_OPEN, kernel)
    light_mask = cv2.morphologyEx(light_mask, cv2.MORPH_CLOSE, kernel)
    light_mask = cv2.morphologyEx(light_mask, cv2.MORPH_OPEN, kernel)
    
    return dark_mask, light_mask

if __name__ == "__main__":
    # Test image path
    image_path = Path(FILE_SETTINGS['IMAGE_PATH']).resolve()
    
    try:
        # Исправляем путь, добавляя недостающую косую черту
        corrected_path = str(FILE_SETTINGS['IMAGE_PATH']).replace('selected_regions41202_003212', 'selected_regions\\41202_003212')
        image_path = Path(corrected_path).resolve()
        
        # Проверяем наличие файла изображения
        if not image_path.exists():
            raise FileNotFoundError(f"No such file or directory: '{image_path}'")

        # Создаем output_dir
        output_dir = Path(DEBUG_PATHS['OUTPUT_DIR'])
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Обрабатываем изображение
        light_contours, dark_contours = process_image(image_path)
        
        print("\nИтоговые результаты:")
        print(f"Капли в светлой области: {len(light_contours)}")
        print(f"Капли в темной области: {len(dark_contours)}")
        print(f"Всего капель: {len(light_contours) + len(dark_contours)}")
        print(f"\nВизуализация сохранена в: {output_dir / 'final_visualization.png'}")
        
    except Exception as e:
        print(f"Ошибка обработки изображения: {str(e)}")
        import traceback
        traceback.print_exc()
