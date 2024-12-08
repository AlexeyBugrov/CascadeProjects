import os
from pathlib import Path
import mimetypes
from datetime import datetime
from collections import defaultdict
import argparse
import PIL.Image
import cv2

class FolderAnalyzer:
    def __init__(self):
        self.mime_types = {
            'text': ['txt', 'md', 'rst', 'org'],
            'document': ['doc', 'docx', 'odt', 'pdf', 'rtf'],
            'spreadsheet': ['xls', 'xlsx', 'ods', 'csv'],
            'presentation': ['ppt', 'pptx', 'odp'],
            'image': ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'svg', 'webp'],
            'video': ['mp4', 'avi', 'mkv', 'mov', 'wmv'],
            'audio': ['mp3', 'wav', 'ogg', 'flac', 'm4a'],
            'archive': ['zip', 'rar', '7z', 'tar', 'gz'],
            'code': ['py', 'js', 'java', 'cpp', 'h', 'css', 'html', 'xml', 'json'],
        }

    def get_file_type(self, file_path: Path) -> str:
        """Определяет тип файла."""
        mime_type, _ = mimetypes.guess_type(str(file_path))
        if mime_type:
            main_type = mime_type.split('/')[0]
            if main_type == 'image':
                return 'image'
            elif main_type == 'video':
                return 'video'
            elif main_type == 'audio':
                return 'audio'
            elif main_type == 'text':
                return 'document'
            elif main_type == 'application':
                if 'pdf' in mime_type:
                    return 'document'
                elif 'spreadsheet' in mime_type or 'excel' in mime_type:
                    return 'spreadsheet'
                elif 'presentation' in mime_type or 'powerpoint' in mime_type:
                    return 'presentation'
                elif 'document' in mime_type or 'word' in mime_type:
                    return 'document'
                else:
                    return 'other'
        return 'other'

    def format_size(self, size_bytes: int) -> str:
        """Форматирует размер в байтах в человекочитаемый формат."""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.2f} TB"

    def get_file_details(self, file_path: Path) -> dict:
        """Получает детальную информацию о файле."""
        details = {
            'size': file_path.stat().st_size,
            'extension': file_path.suffix.lower(),
        }
        
        try:
            if self.get_file_type(file_path) == 'image':
                with PIL.Image.open(file_path) as img:
                    details['dimensions'] = f"{img.width}*{img.height}"
            elif self.get_file_type(file_path) == 'video':
                cap = cv2.VideoCapture(str(file_path))
                if cap.isOpened():
                    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                    codec = int(cap.get(cv2.CAP_PROP_FOURCC))
                    details['dimensions'] = f"{width}*{height}"
                    details['codec'] = ''.join([chr((codec >> 8 * i) & 0xFF) for i in range(4)])
                cap.release()
        except Exception as e:
            print(f"Ошибка при получении деталей файла {file_path}: {e}")
        
        return details

    def get_directory_total_size(self, path: Path) -> int:
        """Получает общий размер директории, включая все вложенные файлы."""
        total_size = 0
        for item in path.rglob('*'):
            if item.is_file():
                total_size += item.stat().st_size
        return total_size

    def get_directory_stats(self, path: Path) -> dict:
        """Собирает детальную статистику по директории."""
        stats = defaultdict(lambda: {
            'total_size': 0,
            'files_by_ext': defaultdict(lambda: {
                'count': 0,
                'size': 0,
                'dimensions': set(),
                'codecs': set()
            })
        })
        
        # Рекурсивно обходим все файлы в директории
        for item in path.rglob('*'):
            if item.is_file():
                file_type = self.get_file_type(item)
                details = self.get_file_details(item)
                ext = details['extension']
                
                stats[file_type]['total_size'] += details['size']
                stats[file_type]['files_by_ext'][ext]['count'] += 1
                stats[file_type]['files_by_ext'][ext]['size'] += details['size']
                
                if 'dimensions' in details:
                    stats[file_type]['files_by_ext'][ext]['dimensions'].add(details['dimensions'])
                if 'codec' in details:
                    stats[file_type]['files_by_ext'][ext]['codecs'].add(details['codec'])
        
        return stats

    def get_summary_stats(self, path: Path) -> dict:
        """Собирает сводную статистику по всей структуре."""
        summary = {
            'total_size': 0,
            'folders_count': 0,
            'files_count': 0,
            'types': defaultdict(lambda: {
                'count': 0,
                'size': 0,
                'extensions': defaultdict(lambda: {
                    'count': 0,
                    'size': 0
                })
            })
        }
        
        # Подсчитываем папки
        for _ in path.rglob('*'):
            if _.is_dir():
                summary['folders_count'] += 1
        
        # Подсчитываем файлы и их размеры
        for item in path.rglob('*'):
            if item.is_file():
                file_type = self.get_file_type(item)
                size = item.stat().st_size
                ext = item.suffix.lower()
                
                summary['total_size'] += size
                summary['files_count'] += 1
                summary['types'][file_type]['count'] += 1
                summary['types'][file_type]['size'] += size
                summary['types'][file_type]['extensions'][ext]['count'] += 1
                summary['types'][file_type]['extensions'][ext]['size'] += size
        
        return summary

    def format_dimensions(self, dimensions: set, max_dims: int = 5) -> str:
        """Форматирует список размеров изображений."""
        if not dimensions:
            return ""
        
        dims_list = sorted(dimensions)
        if len(dims_list) <= max_dims:
            return f"({', '.join(dims_list)})"
        
        return f"({dims_list[0]}, ... {dims_list[-1]})"

    def generate_tree(self, directory: Path, max_depth: int = 0, current_depth: int = 0) -> list:
        """Генерирует древовидную структуру папок с детальной статистикой."""
        tree = []
        prefix_last = "└── "
        prefix_middle = "├── "
        prefix_indent = "│   "
        prefix_empty = "    "

        def add_directory(path: Path, prefix: str = "", level: int = 0) -> list:
            if max_depth > 0 and level >= max_depth:
                return []

            entries = sorted(path.iterdir(), key=lambda x: (not x.is_dir(), x.name))
            entries = [e for e in entries if e.is_dir() or not e.name.startswith('.')]
            
            result = []
            for i, entry in enumerate(entries):
                is_last = i == len(entries) - 1
                current_prefix = prefix_last if is_last else prefix_middle
                
                if entry.is_dir():
                    stats = self.get_directory_stats(entry)
                    if stats:
                        # Добавляем имя директории с префиксом текущего уровня
                        stats_str = self.format_directory_stats(stats, True)
                        result.append(f"{prefix}{current_prefix}{entry.name} {stats_str}")
                        
                        # Добавляем статистику файлов с правильным отступом
                        detailed_stats = self.format_directory_stats(stats)
                        if detailed_stats:
                            # Используем тот же отступ для всех уровней
                            indented_stats = detailed_stats.replace("│      ", f"{prefix}{prefix_indent}")
                            result.append(indented_stats)
                        
                        # Рекурсивно добавляем содержимое директории
                        next_prefix = prefix + (prefix_indent if not is_last else prefix_empty)
                        result.extend(add_directory(entry, next_prefix, level + 1))
            
            return result

        # Добавляем корневую директорию
        root_stats = self.get_directory_stats(directory)
        if root_stats:
            root_stats_str = self.format_directory_stats(root_stats, True)
            tree.append(f"{directory.name} {root_stats_str}")
            
            # Добавляем статистику корневой директории
            detailed_stats = self.format_directory_stats(root_stats)
            if detailed_stats:
                tree.append(detailed_stats)
            
            # Добавляем поддиректории
            if max_depth == 0 or current_depth < max_depth:
                tree.extend(add_directory(directory, "", current_depth))
        
        return [line.rstrip() for line in tree if line.strip()]

    def format_directory_stats(self, stats: dict, is_root: bool = False) -> str:
        """Форматирует детальную статистику директории."""
        if not stats:
            return ""
        
        if is_root:
            total_size = sum(s['total_size'] for s in stats.values())
            return f"[folder] ({self.format_size(total_size)})"
        
        parts = []
        for file_type, type_stats in sorted(stats.items()):
            ext_parts = []
            for ext, ext_stats in sorted(type_stats['files_by_ext'].items()):
                if ext_stats['count'] > 0:
                    ext_info = [f"{ext_stats['count']} - *{ext}"]
                    
                    if ext_stats['dimensions']:
                        ext_info.append(self.format_dimensions(ext_stats['dimensions']))
                    
                    if ext_stats['codecs']:
                        codecs = sorted(ext_stats['codecs'])
                        ext_info.append(f"; {', '.join(codecs)}")
                    
                    ext_info.append(f"({self.format_size(ext_stats['size'])})")
                    ext_parts.append(' '.join(ext_info))
            
            if ext_parts:
                parts.append(f"{file_type.capitalize()}: {', '.join(ext_parts)}")
        
        if not parts:
            return ""
            
        # Форматируем с правильными отступами для текущего уровня
        result = []
        for i, part in enumerate(parts):
            prefix = '└── ' if i == len(parts) - 1 else '├── '
            result.append(f"│      {prefix}{part}")
        return '\n'.join(result)

    def generate_folder_tree(self, directory: Path, max_depth: int = 0, current_depth: int = 0) -> list:
        """Генерирует краткое дерево структуры папок без детальной информации."""
        tree = []
        prefix_last = "└── "
        prefix_middle = "├── "
        prefix_indent = "│   "
        prefix_empty = "    "

        def add_directory(path: Path, prefix: str = "", level: int = 0) -> list:
            if max_depth > 0 and level >= max_depth:
                return []

            entries = sorted([e for e in path.iterdir() if e.is_dir() and not e.name.startswith('.')])
            result = []
            
            for i, entry in enumerate(entries):
                is_last = i == len(entries) - 1
                current_prefix = prefix_last if is_last else prefix_middle
                
                # Добавляем только имя директории и её размер
                total_size = self.get_directory_total_size(entry)
                result.append(f"{prefix}{current_prefix}{entry.name} ({self.format_size(total_size)})")
                
                # Рекурсивно добавляем поддиректории
                next_prefix = prefix + (prefix_indent if not is_last else prefix_empty)
                result.extend(add_directory(entry, next_prefix, level + 1))
            
            return result

        # Добавляем корневую директорию
        total_size = self.get_directory_total_size(directory)
        tree.append(f"{directory.name} ({self.format_size(total_size)})")
        if max_depth == 0 or current_depth < max_depth:
            tree.extend(add_directory(directory, "", current_depth))
        
        return tree

    def generate_report(self, directory: Path, max_depth: int = 0) -> str:
        """Генерирует markdown-отчет.
        
        Args:
            directory (Path): Путь к анализируемой директории
            max_depth (int, optional): Максимальная глубина анализа.
                0 (по умолчанию) - полный анализ всех уровней вложенности
                1 - только первый уровень вложенности
                2 - первый и второй уровни, и т.д.
        """
        summary_stats = self.get_summary_stats(directory)
        
        report = [
            f"# [{directory.name}](\"{directory.absolute()}\")",
            f"\nОтчет сгенерирован: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"Глубина анализа: {max_depth if max_depth > 0 else 'Полная'}\n",
            "## Сводная информация\n",
            f"- Общий размер: {self.format_size(summary_stats['total_size'])}",
            f"- Количество папок: {summary_stats['folders_count']}",
            f"- Количество файлов: {summary_stats['files_count']}\n",
            "### Распределение по типам файлов:\n"
        ]
        
        # Добавляем информацию по каждому типу файлов
        for file_type, type_stats in sorted(summary_stats['types'].items()):
            report.append(f"**{file_type.capitalize()}**:")
            report.append(f"- Всего файлов: {type_stats['count']}")
            report.append(f"- Общий размер: {self.format_size(type_stats['size'])}")
            
            if type_stats['extensions']:
                report.append("- Расширения:")
                for ext, ext_stats in sorted(type_stats['extensions'].items()):
                    report.append(f"  - {ext}: {ext_stats['count']} файлов ({self.format_size(ext_stats['size'])})")
            report.append("")
        
        # Добавляем краткое дерево структуры
        report.extend([
            "## Структура папок\n",
            "```",
            *self.generate_folder_tree(directory, max_depth),
            "```\n",
            "## Детальная структура\n",
            "```",
            *self.generate_tree(directory, max_depth),
            "```\n"
        ])
        
        return '\n'.join(report)

def main():
    parser = argparse.ArgumentParser(description='Анализ структуры папок и файлов')
    parser.add_argument('directory', help='Путь к анализируемой папке')
    parser.add_argument('-o', '--output', help='Путь для сохранения отчета')
    parser.add_argument('-d', '--depth', type=int, default=0, 
                       help='Глубина анализа (0 - полный анализ)')
    parser.add_argument('--debug', action='store_true',
                       help='Сохранять копию отчета в папку скрипта')
    args = parser.parse_args()

    try:
        directory = Path(args.directory)
        if not directory.exists():
            print(f"Ошибка: Папка {directory} не существует")
            return

        analyzer = FolderAnalyzer()
        report = analyzer.generate_report(directory, args.depth)

        # Определяем имя выходного файла
        if args.output:
            output_path = Path(args.output)
        else:
            output_path = directory / f"folder_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"

        # Сохраняем отчет в целевую папку
        output_path.write_text(report, encoding='utf-8')
        print(f"Отчет сохранен в: {output_path}")

        # В режиме отладки сохраняем копию в папку скрипта
        if args.debug:
            script_dir = Path(__file__).parent
            debug_path = script_dir / f"debug_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
            debug_path.write_text(report, encoding='utf-8')
            print(f"Отладочная копия сохранена в: {debug_path}")

    except Exception as e:
        print(f"Ошибка при анализе папки: {e}")

if __name__ == '__main__':
    main()
