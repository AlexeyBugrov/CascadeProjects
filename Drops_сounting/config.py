# Параметры для обработки изображения
DARK_MODE_SETTINGS = {
    # Параметры CLAHE
    'CLAHE': {
        'CLIP_LIMIT': 1.5,      # Ограничение контраста (меньше = меньше шума)
        'TILE_SIZE': (3, 3)     # Размер сетки (меньше = более локальный контраст)
    },
    
    # Параметры билатерального фильтра
    'BILATERAL': {
        'DIAMETER': 3,          # Диаметр окрестности каждого пикселя
        'SIGMA_COLOR': 20,      # Фильтр по цвету
        'SIGMA_SPACE': 20       # Фильтр по расстоянию
    },
    
    # Параметры бинаризации
    'THRESHOLD': {
        'WINDOW_SIZE': 5,       # Размер окна (меньше = более детальная бинаризация)
        'C': -1                 # Константа (отрицательная для светлых капель)
    },
    
    # Параметры морфологических операций
    'MORPHOLOGY': {
        'KERNEL_SIZE': (2, 2),  # Размер ядра для морфологических операций
        'ITERATIONS': 1         # Количество итераций
    },
    
    # Параметры фильтрации капель
    'DROPLET_FILTER': {
        'MIN_AREA': 1,          # Минимальная площадь капли
        'MAX_AREA': 150,        # Максимальная площадь капли
        'MIN_CIRCULARITY': 0.09,# Минимальная округлость
        'MIN_INTENSITY_DIFF': 0.2  # Минимальная разница яркости с фоном
    },
    
    # Параметры разделения слипшихся капель
    'WATERSHED': {
        'DIST_TRANSFORM_SIZE': 5,    # Размер ядра для distance transform
        'THRESHOLD_RATIO': 0.3       # Порог для выделения центров капель (0-1)
    }
}

# Параметры для светлого режима
LIGHT_MODE_SETTINGS = {
    # Параметры CLAHE
    'CLAHE': {
        'CLIP_LIMIT': 0.8,      # Увеличен для лучшего контраста
        'TILE_SIZE': (10, 10)     # Для локального контраста
    },
    
    # Параметры билатерального фильтра
    'BILATERAL': {
        'DIAMETER': 3,          # Возвращаем прежнее значение
        'SIGMA_COLOR': 30,      
        'SIGMA_SPACE': 30       
    },
    
    # Параметры бинаризации
    'THRESHOLD': {
        'WINDOW_SIZE': 5,       # Возвращаем прежнее значение
        'C': 1                  # Возвращаем прежнее значение
    },
    
    # Параметры морфологических операций
    'MORPHOLOGY': {
        'KERNEL_SIZE': (2, 2),  # Оставляем маленький размер ядра
        'ITERATIONS': 1         # Возвращаем одну итерацию
    },
    
    # Параметры фильтрации капель
    'DROPLET_FILTER': {
        'MIN_AREA': 2,          # Для маленьких капель
        'MAX_AREA': 500,        # Для крупных капель
        'MIN_CIRCULARITY': 0.01, # Для менее круглых капель
        'MIN_INTENSITY_DIFF': 0.05  # Для капель с меньшим контрастом
    },
    
    # Параметры разделения слипшихся капель
    'WATERSHED': {
        'DIST_TRANSFORM_SIZE': 5,    # Возвращаем прежнее значение
        'THRESHOLD_RATIO': 0.25      # Немного уменьшаем для лучшего разделения
    }
}

# Параметры визуализации
VISUALIZATION_SETTINGS = {
    'FIGURE_SIZE': (15, 6),
    'HIST_SIZE': (8, 4),
    'CONTOUR_COLOR': (0, 255, 0),
    'CONTOUR_THICKNESS': 1
}

# Пути к файлам
FILE_SETTINGS = {
    'IMAGE_PATH': "D:\Obsidian_storage\second_mind\Проекты\ИИ\Hekuma (пробирки)\Данные для анализа 25.11.2024\датасет -20241122_RASP\max\Product00006470_Good\selected_regions\20241202_003212\work\work_1.png",
    # 'IMAGE_PATH': "D:\Obsidian_storage\second_mind\Проекты\ИИ\Hekuma (пробирки)\Данные для анализа 25.11.2024\датасет -20241122_RASP\max\Product00006470_Good\Alg02.bmp",
    'OUTPUT_DIR': 'results'
}

# Пути для отладки
DEBUG_PATHS = {
    'OUTPUT_DIR': r"D:\CascadeProjects\Drops_сounting\results",
    'SAVE_DEBUG_IMAGES': True,  # Флаг для сохранения промежуточных изображений (d_*.* и l_*.*)
    'DEBUG_STEPS': [            # Этапы обработки для сохранения
        'original',
        'gray',
        'enhanced',
        'blurred',
        'binary',
        'morphed',
        'result',
        'combined_debug'
    ]
}

# Пути к тестовым изображениям
TEST_IMAGES = {
    'DARK_REGION': r"D:\CascadeProjects\Drops_сounting\results\dark_regions\dark_region.png",
    'LIGHT_REGION': r"D:\CascadeProjects\Drops_сounting\results\light_regions\light_region.png"
}
# TEST_IMAGES = {
#     'DARK_REGION': r"D:\Obsidian_storage\second_mind\Проекты\ИИ\Hekuma (пробирки)\Данные для анализа 25.11.2024\датасет -20241122_RASP\max\Product00006470_Good\regions\dark\region_1.png",
#     'LIGHT_REGION': r"D:\Obsidian_storage\second_mind\Проекты\ИИ\Hekuma (пробирки)\Данные для анализа 25.11.2024\датасет -20241122_RASP\max\Product00006470_Good\regions\light\region_0.png"
# }
