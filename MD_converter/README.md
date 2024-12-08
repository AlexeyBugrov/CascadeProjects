# MD Converter

Скрипт для конвертации различных форматов документов в Markdown формат.

## Поддерживаемые форматы

### Текстовые документы
- Microsoft Office (doc, docx, rtf)
- OpenOffice/LibreOffice (odt, fodt)
- Текстовые форматы (txt, rst, org)
- LaTeX (tex, latex, ltx)
- Электронные книги (epub, fb2)

### Таблицы
- Microsoft Excel (xls, xlsx)
- OpenOffice/LibreOffice Calc (ods, fods)

### Презентации
- Microsoft PowerPoint (ppt, pptx)
- OpenOffice/LibreOffice Impress (odp, fodp)

### Другие форматы
- PDF файлы
- Веб-страницы (html, htm, xhtml)
- XML документы (xml, opml)

## Требования
- Python 3.8+
- Pandoc (должен быть установлен в системе)
- Зависимости из requirements.txt

## Установка
1. Установите Pandoc с официального сайта: https://pandoc.org/installing.html
2. Установите зависимости Python:
```bash
pip install -r requirements.txt
```

## Использование
```bash
python md_converter.py path/to/directory
```

Скрипт:
1. Рекурсивно обрабатывает все файлы в указанной директории
2. Создает папку Source_Docs в каждой директории, где есть поддерживаемые файлы
3. Конвертирует файлы в Markdown формат
4. Сохраняет изображения в папке Source_Docs/Attachments
5. Перемещает исходные файлы в папку Source_Docs
6. Выводит статистику конвертации
