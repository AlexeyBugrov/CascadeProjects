#!/bin/bash

# Remove the cron job
crontab -l | grep -v "TranscriptAI_bot" | crontab -

echo "Cron job removed successfully!"
