import os
import markdown
from datetime import datetime
import subprocess
import tempfile
import shutil
from pathlib import Path
from config import (
    WKHTMLTOPDF_PATH, PANDOC_PATH,
    PDF_MARGIN, PDF_FONT, PDF_PAGE_SIZE, PDF_DPI,
    TEMP_DIRECTORY
)

class PDFConverter:
    def __init__(self):
        self.temp_dir = TEMP_DIRECTORY
        if not os.path.exists(self.temp_dir):
            os.makedirs(self.temp_dir)
        
        # Проверяем наличие необходимых инструментов
        if not os.path.exists(WKHTMLTOPDF_PATH):
            raise Exception(f"wkhtmltopdf not found at {WKHTMLTOPDF_PATH}")
        if not os.path.exists(PANDOC_PATH):
            raise Exception(f"pandoc not found at {PANDOC_PATH}")

    def md_to_pdf(self, markdown_text, title):
        """Convert markdown to PDF using pandoc"""
        try:
            # Создаем временный MD файл
            with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False, encoding='utf-8') as temp_md:
                temp_md.write(markdown_text)
                temp_md_path = temp_md.name

            # Создаем временный HTML файл для стилей
            css = """
                body {
                    font-family: Arial, sans-serif;
                    font-size: 14pt;
                    line-height: 1.6;
                    margin: 1cm;
                    max-width: 21cm;
                    padding: 1cm;
                }
                h1 { 
                    font-size: 28pt; 
                    margin-bottom: 1em;
                    border-bottom: 2px solid #000;
                    padding-bottom: 0.2em;
                }
                h2 { 
                    font-size: 22pt; 
                    margin-top: 1.5em;
                    border-bottom: 1px solid #666;
                    padding-bottom: 0.2em;
                }
                h3 { 
                    font-size: 18pt; 
                }
                p {
                    margin: 0.8em 0;
                }
                a { 
                    color: #0066cc;
                    text-decoration: underline;
                }
                strong {
                    color: #000;
                }
                pre {
                    background-color: #f5f5f5;
                    padding: 1em;
                    border-radius: 5px;
                    overflow-x: auto;
                }
                code {
                    font-family: 'Courier New', Courier, monospace;
                    background-color: #f5f5f5;
                    padding: 0.2em 0.4em;
                    border-radius: 3px;
                }
                blockquote {
                    margin: 1em 0;
                    padding-left: 1em;
                    border-left: 4px solid #ddd;
                    color: #666;
                }
            """
            
            with tempfile.NamedTemporaryFile(mode='w', suffix='.css', delete=False, encoding='utf-8') as temp_css:
                temp_css.write(css)
                temp_css_path = temp_css.name

            # Генерируем имя для PDF
            safe_title = "".join(x for x in title if x.isalnum() or x in (' ', '-', '_')).rstrip()
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            pdf_path = os.path.join(self.temp_dir, f'{safe_title}_{timestamp}.pdf')

            # Конвертируем в PDF используя pandoc
            cmd = [
                PANDOC_PATH,
                temp_md_path,
                '-o', pdf_path,
                '--pdf-engine=' + WKHTMLTOPDF_PATH,
                '--variable', f'geometry:margin={PDF_MARGIN}',
                '--variable', f'mainfont:{PDF_FONT}',
                '--css', temp_css_path,
                '--standalone'
            ]

            # Добавляем параметры для wkhtmltopdf
            wk_options = [
                '--pdf-engine-opt=--margin-top', f'--pdf-engine-opt={PDF_MARGIN}',
                '--pdf-engine-opt=--margin-right', f'--pdf-engine-opt={PDF_MARGIN}',
                '--pdf-engine-opt=--margin-bottom', f'--pdf-engine-opt={PDF_MARGIN}',
                '--pdf-engine-opt=--margin-left', f'--pdf-engine-opt={PDF_MARGIN}',
                '--pdf-engine-opt=--page-size', f'--pdf-engine-opt={PDF_PAGE_SIZE}',
                '--pdf-engine-opt=--dpi', f'--pdf-engine-opt={PDF_DPI}'
            ]
            cmd.extend(wk_options)
            
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
            
            # Удаляем временные файлы
            os.unlink(temp_md_path)
            os.unlink(temp_css_path)

            if not os.path.exists(pdf_path):
                raise Exception(f"PDF file was not created at {pdf_path}")

            return pdf_path

        except subprocess.CalledProcessError as e:
            raise Exception(f"Error running pandoc: {e.stderr}")
        except Exception as e:
            raise Exception(f"Error converting markdown to PDF: {str(e)}")

def generate_pdf(markdown_text, title="Notes"):
    """Wrapper function to generate PDF from markdown text"""
    converter = PDFConverter()
    return converter.md_to_pdf(markdown_text, title)
