from celery import shared_task
from django.utils import timezone
from accounts.push import send_user_push
import logging
from accounts.models import Student
from django.db.models import Count, Q

logger = logging.getLogger(__name__)

@shared_task
def send_test_reminders():
    from learning.models import GroupTopicSchedule

    today = timezone.localdate()

    entries = GroupTopicSchedule.objects.filter(
        scheduled_for=today,
    ).select_related("topic", "group").prefetch_related("group__students__user")

    for entry in entries:
        for student in entry.group.students.all():
            payload = {
                "head": "Upcoming test tomorrow",
                "body": f"You have a test on {entry.topic.title} tomorrow.",
            }
            send_user_push_task.delay(student.user_id, payload, 86400)

@shared_task
def send_push_notifications(times_of_day='morning'):

    today = timezone.localdate()

    students = Student.objects.filter(
        groups__topic_schedule_entries__scheduled_for=today
    ).annotate(
        tests_count=Count(
            'groups__topic_schedule_entries',
            filter=Q(groups__topic_schedule_entries__scheduled_for=today)
        )
    ).select_related('user')

    for student in students:
        count = student.tests_count
        
        if count == 1:
            head = "Today you have a test!"
            if times_of_day == 'morning':
                body = f"{count} task has been assigned for today. Stay disciplined and keep moving forward."
            else:
                body = f"You still have tasks left to complete. Today's assignment: {count} task."
        else:
            head = "Today you have several tests!"
            if times_of_day == 'morning':
                body = f"{count} tasks have been assigned for today. Stay disciplined and keep moving forward."
            else:
                body = f"You still have tasks left to complete. Today's assignment: {count} tasks."

        try:
            send_user_push_task.delay(student.user_id, {"head": head, "body": body}, 86400)
        except Exception as e:
            logger.error("Failed to queue push for user_id=%s", student.user_id)

@shared_task(soft_time_limit=25, time_limit=30, expires=60)
def send_user_push_task(user_id, payload, ttl=60):
    from accounts.models import User
    user = User.objects.filter(pk=user_id, is_active=True).first()
    if user:
        send_user_push(user=user, payload=payload, ttl=ttl)
