#!/bin/sh
set -eu
export PYTHONNOUSERSITE=1
export PYTHONDONTWRITEBYTECODE=1
export DJANGO_SETTINGS_MODULE=sapl.settings
cd /var/interlegis/sapl
exec /usr/bin/python3 -s -m gunicorn sapl.wsgi:application   --bind 127.0.0.1:8000 --workers 3 --worker-class gthread --threads 4   --timeout 300 --max-requests 1500 --max-requests-jitter 100   --access-logfile /var/log/sapl/access.log --error-logfile /var/log/sapl/error.log
