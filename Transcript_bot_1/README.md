# TranscriptAI Bot

Telegram bot that transcribes video content and generates structured Obsidian notes.

## Features

- Accepts video files and YouTube links
- Extracts audio and detects audio channels
- Transcribes using Whisper
- Classifies content type (meeting/course)
- Generates structured Markdown notes
- Automatically sends notes to ObsiMatic bot

## Prerequisites

- Python 3.8+
- FFmpeg
- Telegram Bot Token
- OpenAI API Key

## Installation

1. Clone the repository
2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Configure the bot:
- Update tokens in `config.py`
- Ensure directories in `config.py` exist

## Usage

1. Start the bot:
```bash
python main.py
```

2. In Telegram:
- Send `/start` to begin
- Send a video file or YouTube link
- Wait for processing
- Receive confirmation when notes are sent to ObsiMatic

## Automatic Startup

To run the bot automatically on system startup:

1. Make scripts executable:
```bash
chmod +x scripts/add_cron_job.sh
chmod +x scripts/remove_cron_job.sh
```

2. Add to cron:
```bash
./scripts/add_cron_job.sh
```

To remove from cron:
```bash
./scripts/remove_cron_job.sh
```

## Project Structure

```
TranscriptAI_bot/
├── main.py              # Main bot code
├── config.py            # Configuration and credentials
├── requirements.txt     # Python dependencies
├── README.md           # This file
├── utils/
│   ├── media_processor.py  # Video/audio processing
│   └── transcriber.py      # Transcription and AI processing
├── scripts/
│   ├── add_cron_job.sh    # Add bot to cron
│   └── remove_cron_job.sh # Remove bot from cron
├── temp/               # Temporary files
└── output/            # Generated notes
```

## Error Handling

The bot includes comprehensive error handling:
- File download issues
- Transcription failures
- API errors
- File system errors

All errors are logged to `bot.log`.
