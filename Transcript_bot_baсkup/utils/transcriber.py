import whisper
from openai import OpenAI
from config import (
    OPENAI_API_KEY, WHISPER_LOCAL_MODEL, WHISPER_CLOUD_MODEL,
    CHAT_MODEL, USE_LOCAL_WHISPER,
    ANALYSIS_TEMPERATURE, NOTES_TEMPERATURE, NOTES_MAX_TOKENS,
    NOTES_PRESENCE_PENALTY, NOTES_FREQUENCY_PENALTY,
    MEETING_PROMPT, COURSE_PROMPT_HEADER, COURSE_PROMPT, COURSE_CONTENT_PROMPT,
    CONTENT_ANALYSIS_PROMPT, COURSE_CONTENT_FORMAT
)

class Transcriber:
    def __init__(self):
        self.client = OpenAI(api_key=OPENAI_API_KEY)
        if USE_LOCAL_WHISPER:
            self.local_model = whisper.load_model(WHISPER_LOCAL_MODEL)

    async def transcribe_with_local_whisper(self, audio_path):
        """Transcribe audio using local Whisper model"""
        try:
            result = self.local_model.transcribe(audio_path)
            return result["text"]
        except Exception as e:
            raise Exception(f"Error during local transcription: {str(e)}")

    def transcribe_with_cloud_whisper(self, audio_path):
        """Transcribe audio using OpenAI Whisper API"""
        try:
            with open(audio_path, "rb") as audio_file:
                transcript = self.client.audio.transcriptions.create(
                    model=WHISPER_CLOUD_MODEL,
                    file=audio_file,
                    response_format="text"
                )
            return transcript
        except Exception as e:
            raise Exception(f"Error during cloud transcription: {str(e)}")

    def transcribe_with_whisper(self, audio_path):
        """Transcribe audio using selected Whisper model (local or cloud)"""
        if USE_LOCAL_WHISPER:
            return self.transcribe_with_local_whisper(audio_path)
        else:
            return self.transcribe_with_cloud_whisper(audio_path)

    def analyze_content_type(self, transcript):
        """Analyze transcript to determine content type using OpenAI"""
        try:
            response = self.client.chat.completions.create(
                model=CHAT_MODEL,
                messages=[
                    {"role": "system", "content": CONTENT_ANALYSIS_PROMPT},
                    {"role": "user", "content": transcript[:1000]}  # Send first 1000 chars for analysis
                ],
                temperature=ANALYSIS_TEMPERATURE
            )
            return response.choices[0].message.content.strip().lower()
        except Exception as e:
            raise Exception(f"Error during content type analysis: {str(e)}")

    def generate_notes(self, transcript, content_type, audio_info):
        """Generate structured notes using OpenAI"""
        try:
            # Форматируем заголовок
            header = COURSE_PROMPT_HEADER.format(
                title=audio_info.get('title', 'Без названия'),
                channel=audio_info.get('channel', 'Неизвестный автор'),
                duration=audio_info.get('duration_str', 'Неизвестно'),
                process_date=audio_info.get('process_date', 'Неизвестно'),
                video_url=audio_info.get('video_url', 'N/A'),
                original_description=audio_info.get('original_description', 'Описание недоступно')
            )

            # Анализируем тип контента если не указан
            if not content_type:
                content_type = self.analyze_content_type(transcript)

            # Генерируем заметки в зависимости от типа контента
            if content_type == "meeting":
                notes_response = self.client.chat.completions.create(
                    model=CHAT_MODEL,
                    messages=[
                        {"role": "system", "content": MEETING_PROMPT},
                        {"role": "user", "content": transcript}
                    ],
                    temperature=NOTES_TEMPERATURE,
                    max_tokens=NOTES_MAX_TOKENS,
                    presence_penalty=NOTES_PRESENCE_PENALTY,
                    frequency_penalty=NOTES_FREQUENCY_PENALTY
                )
            else:
                # Для курсов и других типов контента
                notes_response = self.client.chat.completions.create(
                    model=CHAT_MODEL,
                    messages=[
                        {"role": "system", "content": COURSE_PROMPT},
                        {"role": "user", "content": transcript}
                    ],
                    temperature=NOTES_TEMPERATURE,
                    max_tokens=NOTES_MAX_TOKENS,
                    presence_penalty=NOTES_PRESENCE_PENALTY,
                    frequency_penalty=NOTES_FREQUENCY_PENALTY
                )

            notes = notes_response.choices[0].message.content
            return f"{header}\n\n{notes}"

        except Exception as e:
            raise Exception(f"Error generating notes: {str(e)}")
