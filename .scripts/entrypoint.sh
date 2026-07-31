#!/bin/sh
set -e

echo "Applying database migrations..."
python manage.py migrate --noinput

echo "Creating superuser if it doesn't exist..."

python manage.py shell <<EOF
from django.contrib.auth import get_user_model
import os

User = get_user_model()

email = os.environ.get("DJANGO_SUPERUSER_EMAIL")
password = os.environ.get("DJANGO_SUPERUSER_PASSWORD")
full_name = os.environ.get("DJANGO_SUPERUSER_FULL_NAME", "Admin")

if email and password:
    user, created = User.objects.get_or_create(
        email=email,
        defaults={"full_name": full_name},
    )

    user.full_name = full_name
    user.is_staff = True
    user.is_superuser = True
    user.is_active = True
    user.set_password(password)
    user.save()

    if created:
        print("✅ Superuser created.")
    else:
        print("✅ Existing user updated.")

    print(
        f"staff={user.is_staff}, "
        f"superuser={user.is_superuser}, "
        f"active={user.is_active}"
    )
EOF
echo "Collecting static files..."
python manage.py collectstatic --noinput

echo "Starting Gunicorn..."
exec gunicorn core.wsgi:application -c gunicorn.conf.py