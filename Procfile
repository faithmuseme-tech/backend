web: python manage.py migrate && python manage.py create_superadmin && python manage.py collectstatic --noinput && gunicorn config.wsgi:application --bind 0.0.0.0:$PORT
