import datetime as dt
import logging

from celery import shared_task
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.utils import timezone

from .emails import (
    meeting_cancellation_template,
    meeting_confirmation_template,
    meeting_reminder_template,
    meeting_reschedule_template,
    organizer_notification_template,
)
from .models import Meeting

logger = logging.getLogger("meeting")


def _send_email(*, subject: str, html_body: str, to: list[str]) -> None:
    recipients = [address for address in dict.fromkeys(to) if address]
    if not recipients:
        logger.warning("No recipients for email %r; skipping send", subject)
        return

    message = EmailMultiAlternatives(
        subject=subject,
        body=html_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=recipients,
    )
    message.attach_alternative(html_body, "text/html")
    message.send(fail_silently=False)


def _organizer_email() -> str:
    return settings.GOOGLE_ADMIN_EMAIL or settings.DEFAULT_FROM_EMAIL


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_confirmation_email_task(self, meeting_id: str) -> None:
    """Sends the visitor's booking confirmation and a separate organizer
    notification. Both reference the same Google Calendar event/Meet link
    already created by MeetingService.book_meeting -- no calendar event is
    created here, this task only sends email."""
    try:
        meeting = Meeting.objects.get(id=meeting_id)
    except Meeting.DoesNotExist:
        logger.warning("Meeting %s no longer exists; skipping confirmation email", meeting_id)
        return

    failure: Exception | None = None

    try:
        _send_email(
            subject=f"Meeting Confirmed: {meeting.title}",
            html_body=meeting_confirmation_template(meeting),
            to=[meeting.visitor_email],
        )
    except Exception as exc:
        logger.exception("Failed to send visitor confirmation email for meeting %s", meeting_id)
        failure = exc

    try:
        _send_email(
            subject=f"New Meeting Booked - {meeting.visitor_name}",
            html_body=organizer_notification_template(meeting),
            to=[_organizer_email()],
        )
    except Exception as exc:
        logger.exception("Failed to send organizer notification email for meeting %s", meeting_id)
        failure = failure or exc

    if failure is not None:
        raise self.retry(exc=failure)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_reschedule_email_task(self, meeting_id: str, old_start_iso: str, old_end_iso: str) -> None:
    try:
        meeting = Meeting.objects.get(id=meeting_id)
    except Meeting.DoesNotExist:
        logger.warning("Meeting %s no longer exists; skipping reschedule email", meeting_id)
        return

    try:
        _send_email(
            subject=f"Meeting Rescheduled: {meeting.title}",
            html_body=meeting_reschedule_template(meeting, old_start_iso, old_end_iso),
            to=[meeting.visitor_email, settings.GOOGLE_ADMIN_EMAIL],
        )
    except Exception as exc:
        logger.exception("Failed to send reschedule email for meeting %s", meeting_id)
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_cancellation_email_task(self, meeting_id: str) -> None:
    try:
        meeting = Meeting.objects.get(id=meeting_id)
    except Meeting.DoesNotExist:
        logger.warning("Meeting %s no longer exists; skipping cancellation email", meeting_id)
        return

    try:
        _send_email(
            subject=f"Meeting Cancelled: {meeting.title}",
            html_body=meeting_cancellation_template(meeting),
            to=[meeting.visitor_email, settings.GOOGLE_ADMIN_EMAIL],
        )
    except Exception as exc:
        logger.exception("Failed to send cancellation email for meeting %s", meeting_id)
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_reminder_email_task(self, meeting_id: str) -> None:
    try:
        meeting = Meeting.objects.get(id=meeting_id)
    except Meeting.DoesNotExist:
        logger.warning("Meeting %s no longer exists; skipping reminder email", meeting_id)
        return

    try:
        _send_email(
            subject=f"Reminder: {meeting.title}",
            html_body=meeting_reminder_template(meeting),
            to=[meeting.visitor_email, settings.GOOGLE_ADMIN_EMAIL],
        )
    except Exception as exc:
        logger.exception("Failed to send reminder email for meeting %s", meeting_id)
        raise self.retry(exc=exc)
    else:
        Meeting.objects.filter(id=meeting_id).update(reminder_sent=True)


@shared_task
def dispatch_due_reminders() -> int:
    """Celery beat entry point (runs every few minutes): finds meetings entering
    the reminder window and queues one reminder email task per meeting."""
    now = timezone.now()
    lead = dt.timedelta(minutes=settings.MEETING_REMINDER_LEAD_MINUTES)
    window_start = now + lead - dt.timedelta(minutes=5)
    window_end = now + lead

    due_meetings = Meeting.objects.filter(
        status__in=Meeting.ACTIVE_STATUSES,
        reminder_sent=False,
        start_time__gte=window_start,
        start_time__lte=window_end,
    )

    count = 0
    for meeting in due_meetings:
        send_reminder_email_task.delay(str(meeting.id))
        count += 1

    if count:
        logger.info("Queued %s meeting reminder email(s)", count)
    return count
