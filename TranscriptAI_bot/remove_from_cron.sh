#!/bin/bash

# Remove the bot from crontab
crontab -l | grep -v "python3 main.py" | crontab -

echo "Bot has been removed from crontab."
