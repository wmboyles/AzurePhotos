#!/bin/sh
set -e

echo "----- Custom startup: ensuring ffmpeg is installed -----"

if ! command -v ffmpeg >/dev/null 2>&1; then
    echo "Installing ffmpeg..."
    apt-get update
    apt-get install -y ffmpeg
else
    echo "ffmpeg already installed."
fi

echo "----- Starting Flask app with gunicorn command -----"

# This should be the default command for startup.
# See: https://learn.microsoft.com/en-us/azure/app-service/configure-language-python#container-startup-process
gunicorn --bind=0.0.0.0 --timeout 600 app:app