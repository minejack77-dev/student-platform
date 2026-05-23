from celery import shared_task
from django.utils import timezone
from webpush import send_user_notification


@shared_task
def send_test_reminders():
    from learning.models import GroupTopicSchedule

    tomorrow = timezone.localdate() + timezone.timedelta(days=1)

    entries = GroupTopicSchedule.objects.filter(
        scheduled_for=tomorrow,
    ).select_related("topic", "group").prefetch_related("group__students__user")

    for entry in entries:
        for student in entry.group.students.all():
            payload = {
                "head": "Upcoming test tomorrow",
                "body": f"You have a test on {entry.topic.title} tomorrow.",
            }
            send_user_notification(user=student.user, payload=payload, ttl=86400)
