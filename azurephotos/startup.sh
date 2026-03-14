#!/bin/sh
set -e

echo "----- Starting Flask app with gunicorn command -----"

# This should be the default command for startup.
# See: https://learn.microsoft.com/en-us/azure/app-service/configure-language-python#container-startup-process
gunicorn --bind=0.0.0.0 --timeout 600 app:app
