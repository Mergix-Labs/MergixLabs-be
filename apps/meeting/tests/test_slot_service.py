import datetime as dt
from unittest.mock import MagicMock

from django.test import TestCase

from apps.meeting.models import Meeting
from apps.meeting.services.slot_service import SlotService

from .helpers import next_business_datetime, next_weekend_datetime


class SlotServiceTests(TestCase):
    def setUp(self):
        self.calendar_service = MagicMock()
        self.calendar_service.get_busy_periods.return_value = []
        self.service = SlotService(calendar_service=self.calendar_service)

    def test_returns_no_slots_on_a_weekend(self):
        weekend_day = next_weekend_datetime().date()
        self.assertEqual(self.service.get_available_slots(weekend_day), [])

    def test_returns_candidate_slots_on_a_business_day(self):
        business_day = next_business_datetime(days_ahead=2).date()
        slots = self.service.get_available_slots(business_day)
        self.assertGreater(len(slots), 0)
        for slot in slots:
            self.assertEqual(
                (slot["end_time"] - slot["start_time"]).total_seconds() / 60, 30
            )

    def test_excludes_slots_already_booked_in_db(self):
        business_day = next_business_datetime(days_ahead=2, hour=10)
        Meeting.objects.create(
            visitor_name="Existing",
            visitor_email="existing@example.com",
            title="Existing meeting",
            start_time=business_day,
            end_time=business_day + dt.timedelta(minutes=30),
        )

        slots = self.service.get_available_slots(business_day.date())
        booked_starts = [s["start_time"] for s in slots]
        self.assertNotIn(business_day, booked_starts)

    def test_excludes_slots_busy_on_google_calendar(self):
        business_day = next_business_datetime(days_ahead=2, hour=11)
        self.calendar_service.get_busy_periods.return_value = [
            (business_day, business_day + dt.timedelta(minutes=30))
        ]

        slots = self.service.get_available_slots(business_day.date())
        booked_starts = [s["start_time"] for s in slots]
        self.assertNotIn(business_day, booked_starts)

    def test_degrades_to_db_only_when_google_calendar_errors(self):
        business_day = next_business_datetime(days_ahead=2).date()
        self.calendar_service.get_busy_periods.side_effect = Exception("network error")

        slots = self.service.get_available_slots(business_day)  # should not raise
        self.assertGreater(len(slots), 0)

    def test_is_slot_available_checks_db_and_google_calendar(self):
        start = next_business_datetime(days_ahead=2)
        end = start + dt.timedelta(minutes=30)

        self.assertTrue(self.service.is_slot_available(start, end))

        self.calendar_service.get_busy_periods.return_value = [(start, end)]
        self.assertFalse(self.service.is_slot_available(start, end))
