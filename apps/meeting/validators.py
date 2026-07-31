import datetime as dt
from zoneinfo import ZoneInfo

from django.conf import settings
from django.utils import timezone

from .exceptions import DuplicateBookingError, InvalidSlotError
from .models import Meeting


def get_meeting_timezone() -> ZoneInfo:
    """The business timezone meetings are scheduled in (independent of Django's TIME_ZONE)."""
    return ZoneInfo(settings.MEETING_TIMEZONE)


def get_working_days() -> set[int]:
    """Weekdays meetings may be booked on. Monday=0 ... Sunday=6, matching `date.weekday()`."""
    return {int(day) for day in settings.MEETING_WORKING_DAYS.split(",") if day.strip() != ""}


def get_working_hours() -> tuple[dt.time, dt.time]:
    start = dt.datetime.strptime(settings.MEETING_WORKING_HOURS_START, "%H:%M").time()
    end = dt.datetime.strptime(settings.MEETING_WORKING_HOURS_END, "%H:%M").time()
    return start, end


def validate_slot_duration(start: dt.datetime, end: dt.datetime) -> None:
    if end <= start:
        raise InvalidSlotError("The end time must be after the start time.")
    duration_minutes = (end - start).total_seconds() / 60
    expected = settings.MEETING_SLOT_DURATION_MINUTES
    if int(duration_minutes) != int(expected):
        raise InvalidSlotError(f"Meetings must be exactly {expected} minutes long.")


def validate_not_in_past(start: dt.datetime) -> None:
    now = timezone.now()
    if start <= now:
        raise InvalidSlotError("Cannot book a meeting in the past.")

    min_notice = dt.timedelta(minutes=settings.MEETING_MIN_NOTICE_MINUTES)
    if start < now + min_notice:
        raise InvalidSlotError(
            f"Meetings must be booked at least {settings.MEETING_MIN_NOTICE_MINUTES} minutes in advance."
        )


def validate_within_advance_window(start: dt.datetime) -> None:
    now = timezone.now()
    max_advance = dt.timedelta(days=settings.MEETING_MAX_ADVANCE_DAYS)
    if start > now + max_advance:
        raise InvalidSlotError(
            f"Meetings cannot be booked more than {settings.MEETING_MAX_ADVANCE_DAYS} days in advance."
        )


def validate_working_hours(start: dt.datetime, end: dt.datetime) -> None:
    business_tz = get_meeting_timezone()
    local_start = start.astimezone(business_tz)
    local_end = end.astimezone(business_tz)

    if local_start.weekday() not in get_working_days():
        raise InvalidSlotError("Meetings cannot be booked on non-working days.")

    if local_start.date() != local_end.date():
        raise InvalidSlotError("Meetings cannot span multiple days.")

    working_start, working_end = get_working_hours()
    if local_start.time() < working_start or local_end.time() > working_end:
        raise InvalidSlotError(
            f"Meetings can only be booked between {working_start.strftime('%H:%M')} "
            f"and {working_end.strftime('%H:%M')} ({settings.MEETING_TIMEZONE})."
        )


def validate_no_duplicate_booking(
    visitor_email: str, start: dt.datetime, end: dt.datetime, exclude_id=None
) -> None:
    overlapping = Meeting.objects.filter(
        visitor_email__iexact=visitor_email,
        status__in=Meeting.ACTIVE_STATUSES,
        start_time__lt=end,
        end_time__gt=start,
    )
    if exclude_id is not None:
        overlapping = overlapping.exclude(id=exclude_id)
    if overlapping.exists():
        raise DuplicateBookingError(
            "You already have a meeting booked that overlaps with this time slot."
        )


def validate_no_internal_conflict(start: dt.datetime, end: dt.datetime, exclude_id=None) -> None:
    """Guards against double-booking the single admin calendar, regardless of visitor."""
    overlapping = Meeting.objects.filter(
        status__in=Meeting.ACTIVE_STATUSES,
        start_time__lt=end,
        end_time__gt=start,
    )
    if exclude_id is not None:
        overlapping = overlapping.exclude(id=exclude_id)
    if overlapping.exists():
        raise DuplicateBookingError(
            "This time slot has just been booked by someone else. Please choose another slot."
        )


def validate_meeting_slot(
    *, visitor_email: str, start: dt.datetime, end: dt.datetime, exclude_id=None
) -> None:
    """Runs every business-rule validation for a candidate slot except the Google Calendar check."""
    validate_slot_duration(start, end)
    validate_not_in_past(start)
    validate_within_advance_window(start)
    validate_working_hours(start, end)
    validate_no_duplicate_booking(visitor_email, start, end, exclude_id=exclude_id)
    validate_no_internal_conflict(start, end, exclude_id=exclude_id)
