import datetime as dt

from django.test import TestCase

from apps.meeting.exceptions import DuplicateBookingError, InvalidSlotError
from apps.meeting.models import Meeting
from apps.meeting.validators import (
    validate_meeting_slot,
    validate_no_duplicate_booking,
    validate_no_internal_conflict,
    validate_not_in_past,
    validate_slot_duration,
    validate_within_advance_window,
    validate_working_hours,
)

from .helpers import next_business_datetime, next_weekend_datetime


class SlotDurationValidatorTests(TestCase):
    def test_rejects_end_before_start(self):
        start = next_business_datetime()
        with self.assertRaises(InvalidSlotError):
            validate_slot_duration(start, start - dt.timedelta(minutes=30))

    def test_rejects_wrong_duration(self):
        start = next_business_datetime()
        with self.assertRaises(InvalidSlotError):
            validate_slot_duration(start, start + dt.timedelta(minutes=45))

    def test_accepts_configured_duration(self):
        start = next_business_datetime()
        validate_slot_duration(start, start + dt.timedelta(minutes=30))  # no exception


class PastAndAdvanceWindowValidatorTests(TestCase):
    def test_rejects_time_in_the_past(self):
        with self.assertRaises(InvalidSlotError):
            validate_not_in_past(dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=1))

    def test_rejects_time_within_minimum_notice(self):
        with self.assertRaises(InvalidSlotError):
            validate_not_in_past(dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=5))

    def test_rejects_time_beyond_max_advance(self):
        with self.assertRaises(InvalidSlotError):
            validate_within_advance_window(dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=365))

    def test_accepts_time_within_window(self):
        start = next_business_datetime()
        validate_not_in_past(start)
        validate_within_advance_window(start)  # no exception


class WorkingHoursValidatorTests(TestCase):
    def test_rejects_weekend(self):
        start = next_weekend_datetime()
        with self.assertRaises(InvalidSlotError):
            validate_working_hours(start, start + dt.timedelta(minutes=30))

    def test_rejects_before_working_hours(self):
        start = next_business_datetime(hour=6)
        with self.assertRaises(InvalidSlotError):
            validate_working_hours(start, start + dt.timedelta(minutes=30))

    def test_rejects_after_working_hours(self):
        start = next_business_datetime(hour=23)
        with self.assertRaises(InvalidSlotError):
            validate_working_hours(start, start + dt.timedelta(minutes=30))

    def test_accepts_within_working_hours(self):
        start = next_business_datetime(hour=10)
        validate_working_hours(start, start + dt.timedelta(minutes=30))  # no exception


class DuplicateAndConflictValidatorTests(TestCase):
    def setUp(self):
        self.start = next_business_datetime()
        self.end = self.start + dt.timedelta(minutes=30)
        self.existing = Meeting.objects.create(
            visitor_name="Existing Visitor",
            visitor_email="existing@example.com",
            title="Existing Meeting",
            start_time=self.start,
            end_time=self.end,
        )

    def test_rejects_duplicate_booking_for_same_visitor(self):
        with self.assertRaises(DuplicateBookingError):
            validate_no_duplicate_booking("existing@example.com", self.start, self.end)

    def test_ignores_excluded_meeting_for_duplicate_check(self):
        validate_no_duplicate_booking(
            "existing@example.com", self.start, self.end, exclude_id=self.existing.id
        )  # no exception

    def test_rejects_internal_conflict_for_different_visitor(self):
        with self.assertRaises(DuplicateBookingError):
            validate_no_internal_conflict(self.start, self.end)

    def test_full_validation_rejects_overlapping_slot(self):
        with self.assertRaises(DuplicateBookingError):
            validate_meeting_slot(
                visitor_email="new-visitor@example.com", start=self.start, end=self.end
            )
