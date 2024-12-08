import cv2
import numpy as np
from pathlib import Path
from dark_region_detection import detect_dark_droplets
from light_region_detection import detect_light_droplets
from config import TEST_IMAGES

def calculate_density(contours, image_shape):
    """
    Рассчитывает плотность капель на единицу площади
    """
    total_area = image_shape[0] * image_shape[1]  # Общая площадь изображения в пикселях
    droplet_count = len(contours)
    density = droplet_count / total_area
    return density, droplet_count

def compare_densities():
    """
    Сравнивает плотности капель между темной и светлой сценами
    """
    # Получаем пути к изображениям из конфига
    dark_image_path = Path(TEST_IMAGES['DARK_REGION'])
    light_image_path = Path(TEST_IMAGES['LIGHT_REGION'])
    
    if not dark_image_path.exists() or not light_image_path.exists():
        print("Ошибка: Проверьте пути к изображениям в config.py")
        return None
    
    print(f"\nАнализ изображений:")
    print(f"Темная сцена: {dark_image_path.name}")
    print(f"Светлая сцена: {light_image_path.name}")
    
    # Получаем контуры для темной сцены
    dark_contours = detect_dark_droplets(dark_image_path)
    dark_image = cv2.imdecode(np.fromfile(str(dark_image_path), dtype=np.uint8), cv2.IMREAD_COLOR)
    dark_density, dark_count = calculate_density(dark_contours, dark_image.shape[:2])
    
    # Получаем контуры для светлой сцены
    light_contours = detect_light_droplets(light_image_path)
    light_image = cv2.imdecode(np.fromfile(str(light_image_path), dtype=np.uint8), cv2.IMREAD_COLOR)
    light_density, light_count = calculate_density(light_contours, light_image.shape[:2])
    
    # Рассчитываем отношение плотностей
    density_ratio = light_density / dark_density if dark_density > 0 else float('inf')
    
    print("\nАнализ плотности капель:")
    print(f"Темная сцена:")
    print(f"- Количество капель: {dark_count}")
    print(f"- Размер изображения: {dark_image.shape[1]}x{dark_image.shape[0]} пикселей")
    print(f"- Плотность: {dark_density:.8f} капель/пиксель")
    print(f"- Плотность: {dark_density * 1_000_000:.2f} капель/млн пикселей")
    
    print(f"\nСветлая сцена:")
    print(f"- Количество капель: {light_count}")
    print(f"- Размер изображения: {light_image.shape[1]}x{light_image.shape[0]} пикселей")
    print(f"- Плотность: {light_density:.8f} капель/пиксель")
    print(f"- Плотность: {light_density * 1_000_000:.2f} капель/млн пикселей")
    
    print(f"\nОтношение плотностей (светлая/темная): {density_ratio:.2f}")
    
    return {
        'dark': {
            'count': dark_count,
            'density': dark_density,
            'density_per_million': dark_density * 1_000_000,
            'image_size': dark_image.shape[:2]
        },
        'light': {
            'count': light_count,
            'density': light_density,
            'density_per_million': light_density * 1_000_000,
            'image_size': light_image.shape[:2]
        },
        'ratio': density_ratio
    }

if __name__ == "__main__":
    compare_densities()
