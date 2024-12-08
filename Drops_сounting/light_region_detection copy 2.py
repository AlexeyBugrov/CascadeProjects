from pathlib import Path
import cv2
import numpy as np
import matplotlib.pyplot as plt
from config import DEBUG_PATHS, LIGHT_MODE_SETTINGS

def save_debug_image(image, name, output_dir, prefix='l'):
    """Сохранение промежуточного результата обработки"""
    if isinstance(image, np.ndarray):
        filename = f"{prefix}_{name}.png"
        filepath = output_dir / filename
        cv2.imwrite(str(filepath), image)
        return True
    return False

def visualize_steps(image_path, images, titles, valid_contours, output_dir):
    """
    Создает визуализацию всех этапов обработки с использованием matplotlib
    """
    plt.style.use('default')  # Используем светлый фон для светлой зоны
    fig, axs = plt.subplots(2, 3, figsize=(15, 10))
    fig.suptitle(f'File: {Path(image_path).name}\nDetected droplets: {len(valid_contours)}', fontsize=10)
    
    # Порядок изображений:
    # Original | Result | Morphed
    # Enhanced | Blurred | Binary
    plot_order = [0, 5, 4, 1, 2, 3]
    
    for idx, (img, title) in enumerate(zip([images[i] for i in plot_order], 
                                         [titles[i] for i in plot_order])):
        i = idx // 3
        j = idx % 3
        
        if len(img.shape) == 3:
            img_show = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        else:
            img_show = img
            
        axs[i, j].imshow(img_show, cmap='gray' if len(img.shape) == 2 else None)
        axs[i, j].set_title(title)
        axs[i, j].axis('on')
    
    plt.tight_layout()
    plt.savefig(str(output_dir / 'l_combined_debug.png'), dpi=300, bbox_inches='tight')
    plt.close()

def detect_light_droplets(image_path, debug=True, return_contours=False):
    """
    Детектирование темных капель на светлом фоне
    """
    output_dir = Path(DEBUG_PATHS['OUTPUT_DIR'])
    if debug:
        output_dir.mkdir(parents=True, exist_ok=True)

    # Загрузка изображения
    image = cv2.imdecode(np.fromfile(str(image_path), dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError(f"Failed to load image: {image_path}")
    
    # Конвертация в оттенки серого
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    
    # Применение CLAHE для улучшения контраста
    clahe = cv2.createCLAHE(
        clipLimit=LIGHT_MODE_SETTINGS['CLAHE']['CLIP_LIMIT'],
        tileGridSize=LIGHT_MODE_SETTINGS['CLAHE']['TILE_SIZE']
    )
    enhanced = clahe.apply(gray)
    
    # Билатеральная фильтрация
    blurred = cv2.bilateralFilter(
        enhanced,
        LIGHT_MODE_SETTINGS['BILATERAL']['DIAMETER'],
        LIGHT_MODE_SETTINGS['BILATERAL']['SIGMA_COLOR'],
        LIGHT_MODE_SETTINGS['BILATERAL']['SIGMA_SPACE']
    )
    
    # Адаптивная бинаризация
    binary = cv2.adaptiveThreshold(
        blurred,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,
        LIGHT_MODE_SETTINGS['THRESHOLD']['WINDOW_SIZE'],
        LIGHT_MODE_SETTINGS['THRESHOLD']['C']
    )
    
    # Морфологические операции
    kernel = np.ones(LIGHT_MODE_SETTINGS['MORPHOLOGY']['KERNEL_SIZE'], np.uint8)
    morphed = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel, 
                             iterations=LIGHT_MODE_SETTINGS['MORPHOLOGY']['ITERATIONS'])
    morphed = cv2.morphologyEx(morphed, cv2.MORPH_CLOSE, kernel, 
                             iterations=LIGHT_MODE_SETTINGS['MORPHOLOGY']['ITERATIONS'])
    
    # Находим контуры
    contours, _ = cv2.findContours(morphed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    # Фильтруем контуры
    valid_contours = []
    for contour in contours:
        area = cv2.contourArea(contour)
        if area < LIGHT_MODE_SETTINGS['DROPLET_FILTER']['MIN_AREA'] or \
           area > LIGHT_MODE_SETTINGS['DROPLET_FILTER']['MAX_AREA']:
            continue
            
        # Проверка округлости
        perimeter = cv2.arcLength(contour, True)
        if perimeter == 0:
            continue
        circularity = 4 * np.pi * area / (perimeter * perimeter)
        if circularity < LIGHT_MODE_SETTINGS['DROPLET_FILTER']['MIN_CIRCULARITY']:
            continue
            
        # Проверка разницы интенсивности
        mask = np.zeros_like(gray)
        cv2.drawContours(mask, [contour], -1, 255, -1)
        mean_intensity = cv2.mean(gray, mask=mask)[0]
        
        # Расширяем контур для получения фона
        dilated_mask = cv2.dilate(mask, kernel, iterations=2)
        bg_mask = cv2.subtract(dilated_mask, mask)
        bg_intensity = cv2.mean(gray, mask=bg_mask)[0]
        
        if abs(mean_intensity - bg_intensity) >= LIGHT_MODE_SETTINGS['DROPLET_FILTER']['MIN_INTENSITY_DIFF']:
            valid_contours.append(contour)
    
    if debug:
        # Сохраняем промежуточные результаты
        images = [image, enhanced, blurred, binary, morphed]
        titles = ['Original', 'Enhanced', 'Blurred', 'Binary', 'Morphed']
        
        # Создаем результирующее изображение
        result = image.copy()
        cv2.drawContours(result, valid_contours, -1, (0, 255, 0), 2)
        images.append(result)
        titles.append('Result')
        
        # Визуализируем этапы обработки
        visualize_steps(image_path, images, titles, valid_contours, output_dir)
    
    print(f"Найдено капель: {len(valid_contours)}")
    print("Результаты сохранены в папку 'results'")
    
    if return_contours:
        return valid_contours, len(valid_contours)
    return len(valid_contours)

if __name__ == "__main__":
    from config import TEST_IMAGES
    detect_light_droplets(TEST_IMAGES['LIGHT_REGION'])
