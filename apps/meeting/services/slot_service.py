import datetime as dt
import logging
from typing import Optional

from django.conf import settings
from django.utils import timezone

from ..models import Meeting
from ..validators import get_meeting_timezone, get_working_days, get_working_hours
from .google_calendar_service import GoogleCalendarService

logger = logging.getLogger("meeting")


class SlotService:
    """Computes bookable slots for a given day by combining working-hours rules,
    already-booked meetings in the database, and the admin's live Google Calendar
    free/busy data."""

    def __init__(self, calendar_service: Optional[GoogleCalendarService] = None) -> None:
        self._calendar_service = calendar_service or GoogleCalendarService()

    def _day_bounds(self, day: dt.date) -> tuple[dt.datetime, dt.datetime]:
        business_tz = get_meeting_timezone()
        working_start, working_end = get_working_hours()
        start = dt.datetime.combine(day, working_start, tzinfo=business_tz)
        end = dt.datetime.combine(day, working_end, tzinfo=business_tz)
        return start, end

    def _candidate_slots(self, day: dt.date) -> list[tuple[dt.datetime, dt.datetime]]:
        if day.weekday() not in get_working_days():
            return []

        day_start, day_end = self._day_bounds(day)
        slot_length = dt.timedelta(minutes=settings.MEETING_SLOT_DURATION_MINUTES)
        step = slot_length + dt.timedelta(minutes=settings.MEETING_BUFFER_MINUTES)

        slots = []
        cursor = day_start
        while cursor + slot_length <= day_end:
            slots.append((cursor, cursor + slot_length))
            cursor += step
        return slots

    @staticmethod
    def _overlaps_any(start: dt.datetime, end: dt.datetime, periods) -> bool:
        for busy_start, busy_end in periods:
            if start < busy_end and end > busy_start:
                return True
        return False

    def get_available_slots(self, day: dt.date) -> list[dict]:
        """Best-effort listing for the public slots endpoint: degrades to DB-only
        availability if Google Calendar is unreachable, rather than failing the page."""
        now = timezone.now()
        min_notice = dt.timedelta(minutes=settings.MEETING_MIN_NOTICE_MINUTES)
        candidates = [s for s in self._candidate_slots(day) if s[0] >= now + min_notice]
        if not candidates:
            return []

        window_start, window_end = candidates[0][0], candidates[-1][1]

        booked = list(
            Meeting.objects.filter(
                status__in=Meeting.ACTIVE_STATUSES,
                start_time__lt=window_end,
                end_time__gt=window_start,
            ).values_list("start_time", "end_time")
        )

        busy_periods = list(booked)
        try:
            busy_periods += self._calendar_service.get_busy_periods(window_start, window_end)
        except Exception:
            logger.exception(
                "Falling back to DB-only availability for %s due to a Google Calendar error", day
            )

        return [
            {"start_time": slot_start, "end_time": slot_end}
            for slot_start, slot_end in candidates
            if not self._overlaps_any(slot_start, slot_end, busy_periods)
        ]

    def is_slot_available(
        self, start: dt.datetime, end: dt.datetime, exclude_meeting_id=None
    ) -> bool:
        """Authoritative check used at booking time. Unlike `get_available_slots`,
        this does NOT swallow Google Calendar errors -- a booking must not be
        confirmed if we can't verify the admin's calendar is actually free."""
        db_conflict = Meeting.objects.filter(
            status__in=Meeting.ACTIVE_STATUSES,
            start_time__lt=end,
            end_time__gt=start,
        )
        if exclude_meeting_id is not None:
            db_conflict = db_conflict.exclude(id=exclude_meeting_id)
        if db_conflict.exists():
            return False

        busy_periods = self._calendar_service.get_busy_periods(start, end)
        return not self._overlaps_any(start, end, busy_periods)
