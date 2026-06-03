import os
from celery import Celery
from celery.schedules import crontab

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("student_platform")
app.config_from_object("django.conf:settings", namespace="CELERY")

# Настройка Celery Beat (расписание)
app.conf.beat_schedule = {
    'send-push-notifications-morning': {
        'task': 'learning.tasks.send_push_notifications',
        'schedule': crontab(hour=10, minute=0),  # Каждый день в 10:00
        'kwargs': {'times_of_day': 'morning'},
    },
    'send-push-notifications-evening': {
        'task': 'learning.tasks.send_push_notifications',
        'schedule': crontab(hour=21, minute=0),
        'kwargs': {'times_of_day': 'evening'},
    },
}

app.autodiscover_tasks()
