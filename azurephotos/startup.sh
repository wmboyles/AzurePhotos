#!/bin/sh
set -e

echo "----- Custom startup: ensuring ffmpeg is installed -----"

if ! command -v ffmpeg >/dev/null 2>&1; then
    chmod +x $APP_PATH/bin/ffmpeg-7.0.2-amd64-static/ffmpeg
    chmod +x $APP_PATH/bin/ffmpeg-7.0.2-amd64-static/ffprobe
    export PATH="$APP_PATH/bin:$PATH"
else
    echo "ffmpeg already installed."
fi

ffmpeg -version

echo "----- Starting Flask app with gunicorn command -----"

# This should be the default command for startup.
# See: https://learn.microsoft.com/en-us/azure/app-service/configure-language-python#container-startup-process
gunicorn --bind=0.0.0.0 --timeout 600 app:app
