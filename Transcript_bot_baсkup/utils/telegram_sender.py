import telegram
from telegram import Update, Bot
import config
import logging
from utils.pdf_converter import PDFConverter
import os
import asyncio
import aiofiles

logger = logging.getLogger(__name__)

class TelegramSender:
    def __init__(self, transcript_bot_token, obsimatic_bot_token, group_chat_id=None):
        """Initialize TelegramSender with bot tokens"""
        self.logger = logging.getLogger(__name__)
        
        # Инициализация ботов с увеличенным таймаутом
        self.transcript_bot = telegram.Bot(token=transcript_bot_token, request=telegram.request.HTTPXRequest(
            connection_pool_size=8,
            read_timeout=30,
            write_timeout=30,
            connect_timeout=30,
            pool_timeout=30
        ))
        self.obsimatic_bot = telegram.Bot(token=obsimatic_bot_token, request=telegram.request.HTTPXRequest(
            connection_pool_size=8,
            read_timeout=30,
            write_timeout=30,
            connect_timeout=30,
            pool_timeout=30
        ))
        self.group_chat_id = group_chat_id
        self.pdf_converter = PDFConverter()
        
    async def _ensure_bots(self):
        """Проверяет и при необходимости инициализирует ботов"""
        if config.DEBUG_MODE:
            if self.transcript_bot is None and config.TRANSCRIPT_BOT_TOKEN:
                self.transcript_bot = telegram.Bot(token=config.TRANSCRIPT_BOT_TOKEN)
                logger.info("TranscriptAI bot initialized")
        else:
            self.transcript_bot = None

    def _escape_markdown(self, text: str) -> str:
        """Escape Markdown special characters"""
        if not text:
            return ""
            
        # Экранируем все специальные символы Markdown V2
        escape_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '!', '.', '\\']
        
        # Сначала экранируем обратный слэш, чтобы не экранировать уже экранированные символы
        text = text.replace('\\', '\\\\')
        
        for char in escape_chars:
            if char != '\\':  # Пропускаем обратный слэш, так как уже обработали
                text = text.replace(char, f'\\{char}')
        
        return text

    async def send_long_message(self, update: Update, text: str, send_to_user=True):
        """
        Отправляет длинное сообщение, разбивая его на части при необходимости.
        
        Args:
            update (Update): Объект обновления Telegram
            text (str): Текст для отправки
            send_to_user (bool): Отправлять ли сообщение пользователю (по умолчанию True)
        """
        MAX_MESSAGE_LENGTH = 4096  # Максимальная длина сообщения в Telegram
        PART_HEADER_LENGTH = 20    # Примерная длина заголовка с номером части
        EFFECTIVE_LENGTH = MAX_MESSAGE_LENGTH - PART_HEADER_LENGTH
        
        try:
            # Разбиваем текст на части, учитывая переносы строк
            parts = []
            current_part = ""
            
            for line in text.split('\n'):
                if len(current_part + line + '\n') > EFFECTIVE_LENGTH:
                    if current_part:
                        parts.append(current_part.strip())
                        current_part = line + '\n'
                    else:
                        # Если строка слишком длинная, разбиваем ее
                        while line:
                            parts.append(line[:EFFECTIVE_LENGTH])
                            line = line[EFFECTIVE_LENGTH:]
                else:
                    current_part += line + '\n'
            
            if current_part:
                parts.append(current_part.strip())
            
            total_parts = len(parts)
            
            # Отправляем каждую часть
            for i, part in enumerate(parts, 1):
                try:
                    # Формируем сообщение
                    message_text = part
                    if total_parts > 1:
                        message_text = f"[Часть {i}/{total_parts}]\n{part}"
                    
                    # Пробуем отправить с Markdown
                    try:
                        await update.message.reply_text(
                            text=message_text,
                            parse_mode='Markdown'
                        )
                    except Exception as md_error:
                        self.logger.warning(f"Failed to send with Markdown: {str(md_error)}")
                        # Пробуем отправить без форматирования
                        try:
                            await update.message.reply_text(message_text)
                        except Exception as plain_error:
                            self.logger.error(f"Failed to send message part {i}/{total_parts}: {str(plain_error)}")
                            continue
                    
                    await asyncio.sleep(1)  # Пауза между отправкой частей
                    
                except Exception as e:
                    self.logger.error(f"Error sending part {i}/{total_parts}: {str(e)}")
                    continue
            
        except Exception as e:
            self.logger.error(f"Error sending messages: {str(e)}")
            raise Exception(f"Error sending messages: {str(e)}")

    def _split_text(self, text: str, max_length: int = 4000) -> list:
        """Split text into chunks of maximum length while preserving markdown structure"""
        if len(text) <= max_length:
            return [text]
        
        chunks = []
        current_chunk = []
        current_length = 0
        
        # Split by lines to preserve formatting
        lines = text.split('\n')
        
        for line in lines:
            if len(line) + current_length + 1 <= max_length:
                current_chunk.append(line)
                current_length += len(line) + 1  # +1 for newline
            else:
                # If current line is too long, split it
                if len(line) > max_length:
                    words = line.split(' ')
                    current_word = ''
                    for word in words:
                        if len(current_word) + len(word) + 1 <= max_length:
                            current_word = f"{current_word} {word}".strip()
                        else:
                            if current_chunk:  # Add current chunk if not empty
                                chunks.append('\n'.join(current_chunk))
                            chunks.append(current_word)
                            current_word = word
                            current_chunk = []
                            current_length = 0
                    if current_word:
                        current_chunk = [current_word]
                        current_length = len(current_word)
                else:
                    # Current line would make chunk too long, start new chunk
                    if current_chunk:
                        chunks.append('\n'.join(current_chunk))
                    current_chunk = [line]
                    current_length = len(line)
        
        # Add remaining chunk if any
        if current_chunk:
            chunks.append('\n'.join(current_chunk))
        
        return chunks

    async def send_notes(self, chat_id: int, notes: str, title: str = "Notes") -> None:
        """Send notes to chat with markdown formatting and as PDF"""
        try:
            # Convert chat_id to int if it's a string
            try:
                chat_id = int(chat_id)
            except (TypeError, ValueError):
                self.logger.error(f"Invalid chat_id: {chat_id}")
                raise ValueError(f"Invalid chat_id: {chat_id}")

            # Split notes into chunks
            chunks = self._split_text(notes)
            
            # Send each chunk
            for i, chunk in enumerate(chunks):
                # Add part number if multiple chunks
                part_prefix = f"Part {i+1}/{len(chunks)}\n\n" if len(chunks) > 1 else ""
                
                # Sanitize markdown for each chunk
                sanitized_chunk = self._escape_markdown(part_prefix + chunk)
                
                try:
                    await self.transcript_bot.send_message(
                        chat_id=chat_id,
                        text=sanitized_chunk,
                        parse_mode='MarkdownV2'
                    )
                except Exception as e:
                    self.logger.warning(f"Failed to send chunk {i+1} with Markdown: {str(e)}")
                    # Fallback to plain text if markdown fails
                    await self.transcript_bot.send_message(
                        chat_id=chat_id,
                        text=part_prefix + chunk,
                        parse_mode=None
                    )

            # Generate and send PDF
            try:
                pdf_path = self.pdf_converter.md_to_pdf(notes, title)
                
                try:
                    # Отправляем PDF в тот же чат, что и markdown
                    async with aiofiles.open(pdf_path, 'rb') as pdf_file:
                        pdf_data = await pdf_file.read()
                        await self.obsimatic_bot.send_document(
                            chat_id=chat_id,
                            document=pdf_data,
                            filename=f"{title}.pdf",
                            caption=f"Транскрипция: {title}"
                        )
                finally:
                    # Удаляем временный PDF файл
                    if os.path.exists(pdf_path):
                        os.remove(pdf_path)
            except Exception as e:
                self.logger.error(f"Error sending PDF: {str(e)}")
                raise
        except Exception as e:
            self.logger.error(f"Error in send_notes: {str(e)}")
            raise

    async def send_document(self, file_path: str, chat_id: int, update: Update):
        """Send a document to the specified chat"""
        try:
            async with aiofiles.open(file_path, 'rb') as doc:
                file_data = await doc.read()
                await self.transcript_bot.send_document(
                    chat_id=chat_id,
                    document=file_data,
                    filename=os.path.basename(file_path),
                    caption=f"Файл: {os.path.basename(file_path)}"
                )
        except Exception as e:
            logger.error(f"Error sending document: {str(e)}")
            await update.message.reply_text(f"Sorry, there was an error sending the document: {str(e)}")
            raise
