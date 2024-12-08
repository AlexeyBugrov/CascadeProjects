import os
import shutil
import subprocess
import mimetypes
import pandas as pd
from pathlib import Path
from tqdm import tqdm
from typing import Dict, List, Tuple

class MDConverter:
    def __init__(self, base_prefix: str = None):
        """
        Инициализация конвертера.
        
        Args:
            base_prefix (str): Базовый путь, который будет удален из относительных путей
                             (например, "D:\\Obsidian_storage\\second_mind\\")
        """
        self.base_prefix = base_prefix
        self.image_counter = 1  # Глобальный счетчик для всех изображений
        self.supported_extensions = {
            'document': [
                # Microsoft Office
                '.doc', '.docx', '.rtf',
                # OpenOffice/LibreOffice
                '.odt', '.fodt',
                # Другие текстовые форматы
                '.txt', '.markdown', '.rst', '.org',
                '.tex', '.latex', '.ltx',
                # Электронные книги
                '.epub', '.fb2'
            ],
            'spreadsheet': [
                # Microsoft Office
                '.xls', '.xlsx',
                # OpenOffice/LibreOffice
                '.ods', '.fods'
            ],
            'presentation': [
                # Microsoft Office
                '.ppt', '.pptx',
                # OpenOffice/LibreOffice
                '.odp', '.fodp'
            ],
            'pdf': ['.pdf'],
            'web': [
                '.html', '.htm', '.xhtml',
                '.xml', '.opml'
            ]
        }
        self.stats = {
            'total_files': 0,
            'successful_conversions': 0,
            'failed_conversions': 0,
            'errors': []
        }

    def is_supported_file(self, file_path: Path) -> bool:
        """Проверяет, поддерживается ли формат файла."""
        # Игнорируем .md файлы
        if file_path.suffix.lower() == '.md':
            return False
            
        return any(file_path.suffix.lower() in exts 
                  for exts in self.supported_extensions.values())

    def create_source_docs_folder(self, base_dir: Path) -> Path:
        """Создает папку Source_Docs если она не существует."""
        source_docs = base_dir / 'Source_Docs'
        source_docs.mkdir(parents=True, exist_ok=True)
        return source_docs

    def create_attachments_folder(self, source_docs: Path) -> Path:
        """Создает папку Attachments в Source_Docs если она не существует."""
        attachments = source_docs / 'Attachments'
        attachments.mkdir(parents=True, exist_ok=True)
        return attachments

    def create_file_attachments_folder(self, attachments: Path, original_file: Path) -> Path:
        """Создает подпапку для файла в папке Attachments если она не существует."""
        file_attachments = attachments / original_file.stem
        file_attachments.mkdir(parents=True, exist_ok=True)
        print(f"Создана папка для вложений: {file_attachments}")  # Отладочный вывод
        return file_attachments

    def get_pandoc_format(self, file_path: Path) -> str:
        """Определяет формат входного файла для Pandoc."""
        ext = file_path.suffix.lower()
        format_map = {
            # Microsoft Office форматы
            '.docx': 'docx',
            '.doc': 'doc',
            '.xlsx': 'xlsx',
            '.xls': 'xls',
            '.pptx': 'pptx',
            '.ppt': 'ppt',
            # OpenOffice/LibreOffice форматы
            '.odt': 'odt',
            '.fodt': 'odt',
            '.ods': 'ods',
            '.fods': 'ods',
            '.odp': 'odp',
            '.fodp': 'odp',
            # Текстовые форматы
            '.md': 'markdown',
            '.markdown': 'markdown',
            '.rst': 'rst',
            '.org': 'org',
            '.tex': 'latex',
            '.latex': 'latex',
            '.ltx': 'latex',
            '.txt': 'text',
            # Веб-форматы
            '.html': 'html',
            '.htm': 'html',
            '.xhtml': 'html',
            '.xml': 'xml',
            '.opml': 'opml',
            # Другие форматы
            '.pdf': 'pdf',
            '.epub': 'epub',
            '.fb2': 'fb2'
        }
        return format_map.get(ext, 'text')

    def get_pandoc_params(self, file_path: Path) -> list:
        """Возвращает специфические параметры Pandoc для разных типов файлов."""
        ext = file_path.suffix.lower()
        base_params = [
            '--wrap=none',  # Отключаем перенос строк
            '--extract-media=./',  # Извлекаем медиафайлы
            '--standalone'  # Создаем автономный документ
        ]
        
        # Параметры для офисных документов
        if ext in ['.xlsx', '.xls', '.ods', '.fods']:
            return base_params + [
                '--read=csv',
                '--columns=100'  # Увеличиваем ширину столбцов
            ]
        # Параметры для текстовых документов
        elif ext in ['.docx', '.doc', '.odt', '.fodt']:
            return base_params + [
                '--track-changes=accept',  # Принимаем все изменения
                '--wrap=none'
            ]
        # Параметры для PDF
        elif ext == '.pdf':
            return base_params + [
                '--pdf-engine=xelatex'  # Используем xelatex для лучшей поддержки Unicode
            ]
        # Параметры для презентаций
        elif ext in ['.ppt', '.pptx', '.odp', '.fodp']:
            return base_params + [
                '--slide-level=2'  # Уровень вложенности слайдов
            ]
        # Параметры для электронных книг
        elif ext in ['.epub', '.fb2']:
            return base_params + [
                '--toc',  # Добавляем оглавление
                '--toc-depth=3'  # Глубина оглавления
            ]
        return base_params

    def get_relative_path(self, file_path: Path, base_path: Path = None) -> str:
        """
        Получает относительный путь от базового пути.
        Если указан base_prefix, удаляет его из пути.
        """
        try:
            # Сначала получаем путь относительно base_path
            if base_path:
                rel_path = Path(str(file_path).replace('\\', '/')).relative_to(base_path)
            else:
                rel_path = file_path

            # Преобразуем путь в строку и нормализуем слеши
            path_str = str(rel_path).replace('\\', '/')
            
            # Если указан base_prefix, удаляем его из пути
            if self.base_prefix:
                prefix = self.base_prefix.replace('\\', '/')
                if prefix.endswith('/'):
                    prefix = prefix[:-1]
                if path_str.startswith(prefix):
                    path_str = path_str[len(prefix):].lstrip('/')

            return path_str
        except ValueError:
            # Если не удалось получить относительный путь, возвращаем полный
            return str(file_path).replace('\\', '/')

    def process_markdown_content(self, content: str, current_dir: Path, base_dir: Path, original_file: Path) -> str:
        """Обрабатывает содержимое markdown файла для корректировки путей к изображениям."""
        import re
        
        # Создаем папки для файлов только если есть изображения
        source_docs = None
        attachments = None
        file_attachments = None
        
        def ensure_folders():
            """Создает необходимые папки при первом обращении к ним."""
            nonlocal source_docs, attachments, file_attachments
            if source_docs is None:
                source_docs = self.create_source_docs_folder(current_dir)
                attachments = self.create_attachments_folder(source_docs)
                file_attachments = self.create_file_attachments_folder(attachments, original_file)
            return file_attachments

        def process_image(img_path: str, style: str = None) -> str:
            """Обрабатывает путь к изображению и возвращает markdown-ссылку."""
            try:
                # Убираем экранирование и начальные ./
                img_path = img_path.replace('\\', '/').replace('./', '')
                
                # Очищаем путь от дополнительных параметров
                img_path = re.sub(r'{[^}]*}', '', img_path).strip()
                
                # Проверяем различные варианты путей к файлу
                possible_paths = [
                    current_dir / 'media' / img_path,  # Путь в подпапке media
                    current_dir / img_path,            # Прямой путь
                    Path(img_path),                    # Абсолютный путь
                ]
                
                # Ищем существующий файл
                full_path = None
                for path in possible_paths:
                    if path.exists() and path.is_file():
                        full_path = path
                        break
                
                if full_path:
                    # Создаем папки только если нашли изображение
                    file_attachments_dir = ensure_folders()
                    
                    # Генерируем имя файла с номером из глобального счетчика
                    suffix = full_path.suffix
                    new_img_name = f"Attachment {self.image_counter}{suffix}"
                    self.image_counter += 1
                    
                    # Копируем изображение в подпапку файла
                    new_img_path = file_attachments_dir / new_img_name
                    shutil.copy2(full_path, new_img_path)
                    
                    # Формируем относительный путь от базовой директории
                    rel_path = self.get_relative_path(current_dir, base_dir)
                    
                    # Формируем путь к изображению
                    attachment_path = f"{rel_path}/Source_Docs/Attachments/{original_file.stem}/{new_img_name}"
                    attachment_path = re.sub(r'/+', '/', attachment_path)  # Убираем двойные слеши
                    attachment_path = attachment_path.strip('/')  # Убираем начальные и конечные слеши
                    
                    # Добавляем размеры изображения, если они были
                    if style:
                        width_match = re.search(r'width=([0-9.]+in)', style)
                        height_match = re.search(r'height=([0-9.]+in)', style)
                        if width_match or height_match:
                            # Конвертируем дюймы в пиксели (приблизительно 96 DPI)
                            width = int(float(width_match.group(1)) * 96) if width_match else None
                            height = int(float(height_match.group(1)) * 96) if height_match else None
                            
                            # Формируем HTML-тег изображения
                            img_attributes = []
                            if width:
                                img_attributes.append(f'width="{width}"')
                            if height:
                                img_attributes.append(f'height="{height}"')
                            
                            return f'<img src="{attachment_path}" {" ".join(img_attributes)} />'
                    
                    return f"![](<{attachment_path}>)"
                
                # Если это уже существующая ссылка с путем к Source_Docs
                if 'Source_Docs/Attachments' in img_path:
                    return f"![](<{img_path}>)"
                
                # Логируем, что изображение не найдено
                print(f"Изображение не найдено: {img_path} в {current_dir}")
                return f"![Изображение не найдено: {img_path}]()"
                
            except Exception as e:
                print(f"Ошибка при обработке изображения {img_path}: {str(e)}")
                return f"![Ошибка обработки изображения: {img_path}]()"

        def replace_html_img(match):
            """Заменяет HTML-теги img на markdown-ссылки."""
            src = re.search(r'src="([^"]+)"', match.group(0))
            style = re.search(r'style="([^"]+)"', match.group(0))
            
            if src:
                return process_image(src.group(1), style.group(1) if style else None)
            return match.group(0)

        def replace_markdown_img(match):
            """Заменяет markdown-ссылки на изображения."""
            alt_text = match.group(1) or ""
            img_path = match.group(2)
            style = None
            
            # Извлекаем стиль, если он есть (поддержка обоих форматов)
            style_match = re.search(r'{([^}]+)}', match.group(0))
            if style_match:
                style = style_match.group(1)
                # Преобразуем формат width=6.46in в width="6.46in"
                style = re.sub(r'width=([0-9.]+in)', r'width="\1"', style)
                style = re.sub(r'height=([0-9.]+in)', r'height="\1"', style)
            
            return process_image(img_path, style)

        # Заменяем HTML-теги img
        content = re.sub(r'<img[^>]+>', replace_html_img, content)
        
        # Заменяем markdown-ссылки на изображения (с учетом стилей)
        content = re.sub(r'!\[(.*?)\](?:\(([^)]+)\))(?:{[^}]*})?', replace_markdown_img, content)
        
        return content

    def convert_file(self, file_path: Path, base_dir: Path) -> bool:
        """Конвертирует файл в markdown."""
        try:
            print(f"\nПроверка файла: {file_path}")
            print(f"Существует: {file_path.exists()}")
            print(f"Абсолютный путь: {file_path.absolute()}")
            
            if not file_path.exists():
                self.stats['failed_conversions'] += 1
                self.stats['errors'].append((str(file_path), "[WinError 2] Не удается найти указанный файл"))
                return False

            # Создаем папки для файлов
            source_docs = self.create_source_docs_folder(base_dir)
            
            # Получаем формат файла для pandoc
            input_format = self.get_pandoc_format(file_path)
            
            # Формируем имя выходного файла
            output_file = source_docs / f"{file_path.stem}.md"
            
            # Получаем параметры для pandoc
            pandoc_params = self.get_pandoc_params(file_path)
            
            # Формируем команду для pandoc
            command = [
                'pandoc',
                str(file_path),
                '-f', input_format,
                '-t', 'markdown',
                '-o', str(output_file)
            ] + pandoc_params
            
            print(f"Выполняется команда: {' '.join(command)}")
            
            # Выполняем конвертацию
            result = subprocess.run(command, capture_output=True, text=True)
            
            if result.returncode == 0:
                self.stats['successful_conversions'] += 1
                return True
            else:
                self.stats['failed_conversions'] += 1
                error_msg = f"Pandoc error: {result.stderr.strip()}"
                self.stats['errors'].append((str(file_path), error_msg))
                return False
                
        except Exception as e:
            self.stats['failed_conversions'] += 1
            error_msg = f"Exception: {str(e)}"
            self.stats['errors'].append((str(file_path), error_msg))
            return False

    def process_directory(self, directory: Path):
        """Обрабатывает все файлы в директории."""
        try:
            print(f"\nОбработка директории: {directory}")
            print(f"Существует: {directory.exists()}")
            print(f"Абсолютный путь: {directory.absolute()}")
            
            # Получаем список всех файлов в директории
            files = [f for f in directory.rglob('*') if f.is_file() and self.is_supported_file(f)]
            print(f"\nНайдено файлов для конвертации: {len(files)}")
            for f in files:
                print(f"- {f}")
                
            self.stats['total_files'] = len(files)
            
            # Обрабатываем каждый файл
            for file_path in tqdm(files, desc="Конвертация файлов"):
                self.convert_file(file_path, directory)
                
        except Exception as e:
            print(f"Ошибка при обработке директории: {e}")

    def print_statistics(self):
        """Выводит статистику конвертации."""
        print("\n=== Статистика конвертации ===")
        print(f"Всего файлов обработано: {self.stats['total_files']}")
        print(f"Успешно сконвертировано: {self.stats['successful_conversions']}")
        print(f"Не удалось сконвертировать: {self.stats['failed_conversions']}")
        
        if self.stats['errors']:
            print("\nОшибки при конвертации:")
            for file_path, error in self.stats['errors']:
                print(f"\nФайл: {file_path}")
                print(f"Ошибка: {error}")

def main():
    import sys
    if len(sys.argv) != 2 and len(sys.argv) != 3:
        print("Использование: python md_converter.py <путь_к_директории> [базовый_префикс]")
        sys.exit(1)

    directory = Path(sys.argv[1])
    if not directory.exists() or not directory.is_dir():
        print("Указанная директория не существует!")
        sys.exit(1)

    # Получаем базовый префикс из аргументов или конфигурации
    base_prefix = None
    if len(sys.argv) == 3:
        base_prefix = sys.argv[2]
    else:
        # Можно добавить чтение из конфигурационного файла
        config_file = Path(__file__).parent / 'config.ini'
        if config_file.exists():
            import configparser
            config = configparser.ConfigParser()
            config.read(config_file)
            if 'Paths' in config and 'base_prefix' in config['Paths']:
                base_prefix = config['Paths']['base_prefix']

    converter = MDConverter(base_prefix)
    converter.process_directory(directory)
    converter.print_statistics()

if __name__ == "__main__":
    main()
