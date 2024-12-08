#!/bin/bash

# Get the absolute path of the script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

# Add the bot to crontab to run at system startup
(crontab -l 2>/dev/null; echo "@reboot cd ${SCRIPT_DIR} && python3 main.py >> ${SCRIPT_DIR}/bot.log 2>&1") | crontab -

echo "Bot has been added to crontab and will start automatically on system startup."
