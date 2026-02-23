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
