#!/bin/sh
set -e

echo "Applying database migrations..."
python manage.py migrate --noinput

echo "Creating superuser if it doesn't exist..."

echo "Collecting static files..."
python manage.py collectstatic --noinput

echo "Starting Gunicorn..."
exec gunicorn core.wsgi:application -c gunicorn.conf.py