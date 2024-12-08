import cv2
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
from config import DEBUG_PATHS, DARK_MODE_SETTINGS

def save_debug_image(image, name, output_dir, prefix='d'):
    """Сохранение промежуточного результата обработки"""
    if isinstance(image, np.ndarray):
        # Создаем имя файла с префиксом
        filename = f"{prefix}_{name}.png"
        filepath = output_dir / filename
        
        # Конвертируем в BGR если изображение RGB
        if len(image.shape) == 3 and image.shape[2] == 3:
            if name == 'result':  # Для финального результата сохраняем как RGB
                image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
        
        # Сохраняем изображение
        cv2.imwrite(str(filepath), image)
        return True
    return False

def create_debug_grid(images, titles, output_dir):
    """
    Создает сетку изображений 2x3 для визуализации этапов обработки
    """
    # Конвертируем все изображения в цветной формат BGR
    processed_images = []
    for img in images:
        if len(img.shape) == 2:  # Если изображение в оттенках серого
            img_bgr = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
        else:
            img_bgr = img.copy()
        processed_images.append(img_bgr)
    
    # Создаем сетку 2x3
    rows = 2
    cols = 3
    cell_height = processed_images[0].shape[0]
    cell_width = processed_images[0].shape[1]
    
    # Создаем пустое изображение для сетки
    grid = np.zeros((cell_height * rows, cell_width * cols, 3), dtype=np.uint8)
    
    # Заполняем сетку изображениями
    for idx, (img, title) in enumerate(zip(processed_images, titles)):
        i = idx // cols
        j = idx % cols
        
        # Копируем изображение в соответствующую ячейку сетки
        grid[i*cell_height:(i+1)*cell_height, 
             j*cell_width:(j+1)*cell_width] = img
        
        # Добавляем заголовок
        cv2.putText(grid, title, 
                   (j*cell_width + 10, i*cell_height + 30),
                   cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
    
    # Сохраняем результат
    cv2.imwrite(str(output_dir / 'debug_grid.png'), grid)
    return grid

def visualize_steps(image_path, images, titles, valid_contours, output_dir):
    """
    Создает визуализацию всех этапов обработки с использованием matplotlib
    """
    plt.style.use('dark_background')
    fig, axs = plt.subplots(2, 3, figsize=(15, 10))
    fig.suptitle(f'File: {Path(image_path).name}\nDetected droplets: {len(valid_contours)}', fontsize=10)
    
    # Новый порядок изображений:
    # Original | Result | Morphed
    # Enhanced | Blurred | Binary
    plot_order = [0, 5, 4, 1, 2, 3]  # Original, Result, Morphed, Enhanced, Blurred, Binary
    
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
        axs[i, j].axis('on')  # Показываем оси
    
    plt.tight_layout()
    plt.savefig(str(output_dir / 'd_combined_debug.png'), dpi=300, bbox_inches='tight')
    plt.close()

def detect_dark_droplets(image_path, debug=True, return_contours=False):
    """
    Детектирование светлых капель на темном фоне
    """
    output_dir = Path(DEBUG_PATHS['OUTPUT_DIR'])
    if debug:
        output_dir.mkdir(parents=True, exist_ok=True)

    # Загрузка изображения
    image = cv2.imdecode(np.fromfile(str(image_path), dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError(f"Failed to load image: {image_path}")
    
    if debug:
        save_debug_image(image, 'original', output_dir)
    
    # Преобразование в оттенки серого
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    if debug:
        save_debug_image(gray, 'gray', output_dir)
    
    # Применение CLAHE для улучшения локального контраста
    clahe = cv2.createCLAHE(
        clipLimit=DARK_MODE_SETTINGS['CLAHE']['CLIP_LIMIT'],
        tileGridSize=DARK_MODE_SETTINGS['CLAHE']['TILE_SIZE']
    )
    enhanced = clahe.apply(gray)
    enhanced = clahe.apply(enhanced)
    if debug:
        save_debug_image(enhanced, 'enhanced', output_dir)
    
    # Билатеральная фильтрация
    blurred = cv2.bilateralFilter(
        enhanced,
        d=DARK_MODE_SETTINGS['BILATERAL']['DIAMETER'],
        sigmaColor=DARK_MODE_SETTINGS['BILATERAL']['SIGMA_COLOR'],
        sigmaSpace=DARK_MODE_SETTINGS['BILATERAL']['SIGMA_SPACE']
    )
    if debug:
        save_debug_image(blurred, 'blurred', output_dir)
    
    # Локальная бинаризация
    binary = cv2.adaptiveThreshold(
        blurred,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        DARK_MODE_SETTINGS['THRESHOLD']['WINDOW_SIZE'],
        DARK_MODE_SETTINGS['THRESHOLD']['C']
    )
    if debug:
        save_debug_image(binary, 'binary', output_dir)
    
    # Морфологические операции
    kernel = np.ones(
        DARK_MODE_SETTINGS['MORPHOLOGY']['KERNEL_SIZE'],
        np.uint8
    )
    morphed = cv2.morphologyEx(
        binary,
        cv2.MORPH_OPEN,
        kernel,
        iterations=DARK_MODE_SETTINGS['MORPHOLOGY']['ITERATIONS']
    )
    
    if debug:
        save_debug_image(morphed, 'morphed', output_dir)
    
    # Находим контуры капель
    contours, _ = cv2.findContours(morphed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    # Фильтруем контуры по размеру
    valid_contours = []
    for contour in contours:
        area = cv2.contourArea(contour)
        if (DARK_MODE_SETTINGS['DROPLET_FILTER']['MIN_AREA'] <= area <= 
            DARK_MODE_SETTINGS['DROPLET_FILTER']['MAX_AREA']):
            valid_contours.append(contour)
    
    if debug:
        # Создаем копию оригинального изображения для отрисовки результата
        result_image = image.copy()
        cv2.drawContours(result_image, valid_contours, -1, (0, 255, 0), 1)
        
        # Создаем визуализацию всех этапов
        debug_images = [image, enhanced, blurred, binary, morphed, result_image]
        titles = ['Original', 'CLAHE Enhanced', 'Blurred', 
                 'Binary', 'Morphology', f'Result ({len(valid_contours)} droplets)']
        
        visualize_steps(image_path, debug_images, titles, valid_contours, output_dir)
        
    print(f"Найдено капель: {len(valid_contours)}")
    print("Результаты сохранены в папку 'results'")
    
    if return_contours:
        return valid_contours, len(valid_contours)
    return len(valid_contours)

if __name__ == "__main__":
    from config import TEST_IMAGES
    
    try:
        # Запуск детектирования
        contours = detect_dark_droplets(TEST_IMAGES['DARK_REGION'])
    except Exception as e:
        print(f"Ошибка: {str(e)}")
