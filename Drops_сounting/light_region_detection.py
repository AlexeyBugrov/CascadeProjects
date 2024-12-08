from pathlib import Path
import cv2
import numpy as np
import matplotlib.pyplot as plt
from config import DEBUG_PATHS, LIGHT_MODE_SETTINGS

def save_debug_image(image, name, output_dir, prefix='l'):
    """Сохранение промежуточного результата обработки"""
    try:
        if isinstance(image, np.ndarray) and DEBUG_PATHS['SAVE_DEBUG_IMAGES']:
            # Создаем папку, если её нет
            output_dir = Path(output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # Создаем имя файла с префиксом
            filename = f"{prefix}_{name}.png"
            filepath = output_dir / filename
            
            # Проверяем тип изображения и конвертируем если нужно
            if len(image.shape) == 3 and image.shape[2] == 3:
                if name == 'result':  # Для финального результата сохраняем как RGB
                    image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
            elif len(image.shape) == 2:
                # Для полутоновых изображений убеждаемся, что они uint8
                image = image.astype(np.uint8)
            
            # Конвертируем путь в байты для cv2.imwrite
            filepath_str = str(filepath.absolute())
            
            # Используем imencode и запись в файл вместо imwrite
            is_success, im_buf_arr = cv2.imencode(".png", image)
            if is_success:
                im_buf_arr.tofile(filepath_str)
                print(f"Успешно сохранено изображение: {filename}")
                return True
            else:
                print(f"Ошибка при кодировании изображения: {filename}")
                print(f"Путь: {filepath_str}")
                return False
    except Exception as e:
        print(f"Ошибка при сохранении {name}: {str(e)}")
        print(f"Тип изображения: {type(image)}")
        print(f"Форма изображения: {image.shape if isinstance(image, np.ndarray) else 'не numpy array'}")
        return False
    return False

def visualize_steps(image_path, images, titles, valid_contours, output_dir):
    """
    Создает визуализацию всех этапов обработки с использованием matplotlib
    """
    if not DEBUG_PATHS['SAVE_DEBUG_IMAGES']:
        return
        
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
    
    # Сохраняем визуализацию
    output_path = str(output_dir / 'l_combined_debug.png')
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"Сохранена визуализация: l_combined_debug.png")
    plt.close()

def detect_light_droplets(image_path, debug=True, return_contours=False):
    """
    Детектирование темных капель на светлом фоне
    """
    # Создаем output_dir как Path объект
    output_dir = Path(DEBUG_PATHS['OUTPUT_DIR'])
    if debug:
        output_dir.mkdir(parents=True, exist_ok=True)
        print(f"Папка для сохранения: {output_dir}")

    # Загрузка изображения
    image = cv2.imdecode(np.fromfile(str(image_path), dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError(f"Failed to load image: {image_path}")
    
    # Сохраняем оригинальное изображение
    if debug:
        print(f"Оригинал: форма {image.shape}, тип {image.dtype}")
        save_debug_image(image.copy(), 'original', output_dir)
        print("Этап 1: Сохранен оригинал")

    # Конвертация в оттенки серого
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    if debug:
        print(f"Серое: форма {gray.shape}, тип {gray.dtype}")
        save_debug_image(gray.copy(), 'gray', output_dir)
        print("Этап 2: Сохранено изображение в градациях серого")

    # Применение CLAHE для улучшения контраста
    clahe = cv2.createCLAHE(
        clipLimit=LIGHT_MODE_SETTINGS['CLAHE']['CLIP_LIMIT'],
        tileGridSize=LIGHT_MODE_SETTINGS['CLAHE']['TILE_SIZE']
    )
    enhanced = clahe.apply(gray)
    if debug:
        print(f"Enhanced: форма {enhanced.shape}, тип {enhanced.dtype}")
        save_debug_image(enhanced.copy(), 'enhanced', output_dir)
        print("Этап 3: Сохранено улучшенное изображение")

    # Билатеральная фильтрация
    blurred = cv2.bilateralFilter(
        enhanced,
        LIGHT_MODE_SETTINGS['BILATERAL']['DIAMETER'],
        LIGHT_MODE_SETTINGS['BILATERAL']['SIGMA_COLOR'],
        LIGHT_MODE_SETTINGS['BILATERAL']['SIGMA_SPACE']
    )
    if debug:
        print(f"Blurred: форма {blurred.shape}, тип {blurred.dtype}")
        save_debug_image(blurred.copy(), 'blurred', output_dir)
        print("Этап 4: Сохранено сглаженное изображение")

    # Адаптивная бинаризация
    binary = cv2.adaptiveThreshold(
        blurred,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,
        LIGHT_MODE_SETTINGS['THRESHOLD']['WINDOW_SIZE'],
        LIGHT_MODE_SETTINGS['THRESHOLD']['C']
    )
    if debug:
        print(f"Binary: форма {binary.shape}, тип {binary.dtype}")
        save_debug_image(binary.copy(), 'binary', output_dir)
        print("Этап 5: Сохранено бинарное изображение")

    # Морфологические операции
    kernel = np.ones(LIGHT_MODE_SETTINGS['MORPHOLOGY']['KERNEL_SIZE'], np.uint8)
    morphed = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel, 
                             iterations=LIGHT_MODE_SETTINGS['MORPHOLOGY']['ITERATIONS'])
    morphed = cv2.morphologyEx(morphed, cv2.MORPH_CLOSE, kernel, 
                             iterations=LIGHT_MODE_SETTINGS['MORPHOLOGY']['ITERATIONS'])
    if debug:
        print(f"Morphed: форма {morphed.shape}, тип {morphed.dtype}")
        save_debug_image(morphed.copy(), 'morphed', output_dir)
        print("Этап 6: Сохранено морфологически обработанное изображение")

    # Находим контуры
    contours, _ = cv2.findContours(morphed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    # Фильтруем контуры
    valid_contours = []
    for contour in contours:
        area = cv2.contourArea(contour)
        if area < LIGHT_MODE_SETTINGS['DROPLET_FILTER']['MIN_AREA']:
            continue
        if area > LIGHT_MODE_SETTINGS['DROPLET_FILTER']['MAX_AREA']:
            continue
            
        perimeter = cv2.arcLength(contour, True)
        if perimeter == 0:
            continue
            
        circularity = 4 * np.pi * area / (perimeter * perimeter)
        if circularity < LIGHT_MODE_SETTINGS['DROPLET_FILTER']['MIN_CIRCULARITY']:
            continue
            
        valid_contours.append(contour)
    
    # Сохраняем результат
    if debug:
        result = image.copy()
        cv2.drawContours(result, valid_contours, -1, (0, 255, 0), 2)
        save_debug_image(result, 'result', output_dir)
        
        # Создаем визуализацию всех этапов
        images = [image, enhanced, blurred, binary, morphed, result]
        titles = ['Original', 'Enhanced', 'Blurred', 'Binary', 'Morphed', 'Result']
        visualize_steps(image_path, images, titles, valid_contours, output_dir)
        
        print(f"Найдено капель: {len(valid_contours)}")
        print("Результаты сохранены в папку 'results'")
    
    if return_contours:
        return valid_contours
    return len(valid_contours)

if __name__ == "__main__":
    from config import TEST_IMAGES
    detect_light_droplets(TEST_IMAGES['LIGHT_REGION'])
