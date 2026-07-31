import datetime as dt

from django.utils import timezone

from apps.meeting.validators import get_meeting_timezone


def next_business_datetime(days_ahead: int = 1, hour: int = 10) -> dt.datetime:
    """Returns an aware datetime (in the configured MEETING_TIMEZONE) that is
    guaranteed to fall on a Mon-Fri business day, `days_ahead` or more days in
    the future, at the given local hour."""
    business_tz = get_meeting_timezone()
    candidate = timezone.now().astimezone(business_tz) + dt.timedelta(days=days_ahead)
    while candidate.weekday() > 4:
        candidate += dt.timedelta(days=1)
    return candidate.replace(hour=hour, minute=0, second=0, microsecond=0)


def next_weekend_datetime(days_ahead: int = 1, hour: int = 10) -> dt.datetime:
    """Returns an aware datetime (in the configured MEETING_TIMEZONE) that is
    guaranteed to fall on a Sat/Sun, `days_ahead` or more days in the future,
    at the given local hour."""
    business_tz = get_meeting_timezone()
    candidate = timezone.now().astimezone(business_tz) + dt.timedelta(days=days_ahead)
    while candidate.weekday() <= 4:
        candidate += dt.timedelta(days=1)
    return candidate.replace(hour=hour, minute=0, second=0, microsecond=0)
