import datetime as dt
import logging
from typing import Optional

from django.conf import settings
from django.db import connection, transaction
from django.utils import timezone

from ..exceptions import GoogleCalendarError, MeetingNotModifiableError, SlotUnavailableError
from ..models import Meeting
from ..tasks import (
    send_cancellation_email_task,
    send_confirmation_email_task,
    send_reschedule_email_task,
)
from ..validators import validate_meeting_slot
from .google_calendar_service import GoogleCalendarService
from .slot_service import SlotService

logger = logging.getLogger("meeting")


class MeetingService:
    """Orchestrates booking/reschedule/cancel flows: validation, Google Calendar
    sync, persistence, and dispatching notification emails via Celery."""

    def __init__(
        self,
        calendar_service: Optional[GoogleCalendarService] = None,
        slot_service: Optional[SlotService] = None,
    ) -> None:
        self._calendar_service = calendar_service or GoogleCalendarService()
        self._slot_service = slot_service or SlotService(self._calendar_service)

    def get_available_slots(self, day: dt.date) -> list[dict]:
        return self._slot_service.get_available_slots(day)

    @staticmethod
    def _lock_slot(start_time: dt.datetime) -> None:
        """Serializes concurrent booking attempts for the same slot using a Postgres
        advisory lock scoped to the transaction. No-op on backends without support
        (e.g. SQLite in local dev/tests) -- the DB overlap check still applies there,
        it's just not race-proof under true concurrency."""
        if connection.vendor != "postgresql":
            return
        lock_key = int(start_time.timestamp())
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_xact_lock(%s)", [lock_key])

    @transaction.atomic
    def book_meeting(
        self,
        *,
        visitor_name: str,
        visitor_email: str,
        visitor_phone: str,
        start_time: dt.datetime,
        end_time: dt.datetime,
        agenda: str,
        created_by=None,
    ) -> Meeting:
        self._lock_slot(start_time)

        validate_meeting_slot(visitor_email=visitor_email, start=start_time, end=end_time)

        if not self._slot_service.is_slot_available(start_time, end_time):
            raise SlotUnavailableError()

        title = f"{settings.MEETING_DEFAULT_TITLE_PREFIX} {visitor_name}".strip()
        meeting = Meeting.objects.create(
            visitor_name=visitor_name,
            visitor_email=visitor_email,
            visitor_phone=visitor_phone or "",
            title=title,
            agenda=agenda or "",
            start_time=start_time,
            end_time=end_time,
            timezone=settings.MEETING_TIMEZONE,
            created_by=created_by,
        )

        try:
            event = self._calendar_service.create_event(
                summary=title,
                description=agenda or "",
                start=start_time,
                end=end_time,
                timezone_name=settings.MEETING_TIMEZONE,
                visitor_email=visitor_email,
                visitor_name=visitor_name,
                organizer_email=settings.GOOGLE_ADMIN_EMAIL,
            )
        except GoogleCalendarError:
            # Roll back the DB row too -- don't leave an orphaned meeting with no calendar event.
            meeting.delete()
            raise

        meeting.google_event_id = event.get("id", "")
        meeting.google_meet_link = event.get("hangoutLink", "")
        meeting.google_event_link = event.get("htmlLink", "")
        meeting.save(update_fields=["google_event_id", "google_meet_link", "google_event_link"])

        transaction.on_commit(lambda: send_confirmation_email_task.delay(str(meeting.id)))

        return meeting

    @transaction.atomic
    def reschedule_meeting(
        self,
        meeting: Meeting,
        *,
        new_start_time: dt.datetime,
        new_end_time: dt.datetime,
        reason: str = "",
    ) -> Meeting:
        if not meeting.is_active:
            raise MeetingNotModifiableError("Only scheduled meetings can be rescheduled.")

        self._lock_slot(new_start_time)

        validate_meeting_slot(
            visitor_email=meeting.visitor_email,
            start=new_start_time,
            end=new_end_time,
            exclude_id=meeting.id,
        )

        if not self._slot_service.is_slot_available(
            new_start_time, new_end_time, exclude_meeting_id=meeting.id
        ):
            raise SlotUnavailableError()

        old_start, old_end = meeting.start_time, meeting.end_time

        if meeting.google_event_id:
            self._calendar_service.update_event_time(
                meeting.google_event_id,
                start=new_start_time,
                end=new_end_time,
                timezone_name=settings.MEETING_TIMEZONE,
            )

        meeting.start_time = new_start_time
        meeting.end_time = new_end_time
        meeting.status = Meeting.STATUS_RESCHEDULED
        meeting.reschedule_count += 1
        meeting.reminder_sent = False
        meeting.save(
            update_fields=["start_time", "end_time", "status", "reschedule_count", "reminder_sent"]
        )

        transaction.on_commit(
            lambda: send_reschedule_email_task.delay(
                str(meeting.id), old_start.isoformat(), old_end.isoformat()
            )
        )

        return meeting

    @transaction.atomic
    def cancel_meeting(
        self,
        meeting: Meeting,
        *,
        reason: str = "",
        cancelled_by: str = Meeting.CANCELLED_BY_VISITOR,
    ) -> Meeting:
        if not meeting.is_active:
            raise MeetingNotModifiableError("This meeting is already cancelled.")

        if meeting.google_event_id:
            self._calendar_service.delete_event(meeting.google_event_id)

        meeting.status = Meeting.STATUS_CANCELLED
        meeting.cancelled_at = timezone.now()
        meeting.cancellation_reason = reason or ""
        meeting.cancelled_by = cancelled_by
        meeting.save(update_fields=["status", "cancelled_at", "cancellation_reason", "cancelled_by"])

        transaction.on_commit(lambda: send_cancellation_email_task.delay(str(meeting.id)))

        return meeting
