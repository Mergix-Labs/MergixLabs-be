#!/bin/sh
set -e

echo "Applying database migrations..."
python manage.py migrate --noinput

echo "Creating superuser if it doesn't exist..."

python manage.py shell <<EOF
from django.contrib.auth import get_user_model
import os
import traceback

User = get_user_model()

email = os.environ.get("DJANGO_SUPERUSER_EMAIL")
password = os.environ.get("DJANGO_SUPERUSER_PASSWORD")
full_name = os.environ.get("DJANGO_SUPERUSER_FULL_NAME", "Admin")

try:
    if email and password:
        if not User.objects.filter(email=email).exists():
            User.objects.create_superuser(
                email=email,
                password=password,
                full_name=full_name,
            )
            print("✅ Superuser created.")
        else:
            print("ℹ️ Superuser already exists.")
    else:
        print("⚠️ DJANGO_SUPERUSER_EMAIL or DJANGO_SUPERUSER_PASSWORD is missing.")
except Exception:
    traceback.print_exc()
EOF

echo "Collecting static files..."
python manage.py collectstatic --noinput

echo "Starting Gunicorn..."
exec gunicorn core.wsgi:application -c gunicorn.conf.py