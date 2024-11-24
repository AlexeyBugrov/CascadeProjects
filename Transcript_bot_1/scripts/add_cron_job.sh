#!/bin/bash

# Get the absolute path of the script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Create virtual environment if it doesn't exist
if [ ! -d "$PROJECT_DIR/venv" ]; then
    python -m venv "$PROJECT_DIR/venv"
fi

# Create the cron job
(crontab -l 2>/dev/null; echo "@reboot cd $PROJECT_DIR && $PROJECT_DIR/venv/bin/python main.py >> $PROJECT_DIR/bot.log 2>&1") | crontab -

echo "Cron job added successfully!"
