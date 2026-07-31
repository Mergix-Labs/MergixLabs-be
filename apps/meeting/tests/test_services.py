import datetime as dt
from unittest.mock import MagicMock, patch

from django.test import TestCase

from apps.meeting.exceptions import DuplicateBookingError, InvalidSlotError, SlotUnavailableError
from apps.meeting.models import Meeting
from apps.meeting.services.meeting_service import MeetingService

from .helpers import next_business_datetime, next_weekend_datetime


def _fake_event(event_id="evt_123"):
    return {
        "id": event_id,
        "hangoutLink": "https://meet.google.com/abc-defg-hij",
        "htmlLink": "https://calendar.google.com/event?eid=abc",
    }


class MeetingServiceBookingTests(TestCase):
    def setUp(self):
        self.calendar_service = MagicMock()
        self.calendar_service.get_busy_periods.return_value = []
        self.calendar_service.create_event.return_value = _fake_event()
        self.service = MeetingService(calendar_service=self.calendar_service)

    def test_book_meeting_creates_meeting_and_syncs_calendar(self):
        start = next_business_datetime()
        end = start + dt.timedelta(minutes=30)

        with patch("apps.meeting.tasks.send_confirmation_email_task.delay") as mock_delay:
            with self.captureOnCommitCallbacks(execute=True):
                meeting = self.service.book_meeting(
                    visitor_name="Jane Doe",
                    visitor_email="jane@example.com",
                    visitor_phone="",
                    start_time=start,
                    end_time=end,
                    agenda="Discuss proposal",
                )

        self.assertEqual(meeting.status, Meeting.STATUS_SCHEDULED)
        self.assertEqual(meeting.google_event_id, "evt_123")
        self.assertEqual(meeting.google_meet_link, "https://meet.google.com/abc-defg-hij")
        mock_delay.assert_called_once_with(str(meeting.id))
        self.calendar_service.create_event.assert_called_once()

    def test_book_meeting_rejects_weekend_slot(self):
        start = next_weekend_datetime()
        end = start + dt.timedelta(minutes=30)

        with self.assertRaises(InvalidSlotError):
            self.service.book_meeting(
                visitor_name="Jane Doe",
                visitor_email="jane@example.com",
                visitor_phone="",
                start_time=start,
                end_time=end,
                agenda="",
            )
        self.calendar_service.create_event.assert_not_called()

    def test_book_meeting_rejects_duplicate_booking(self):
        start = next_business_datetime()
        end = start + dt.timedelta(minutes=30)
        Meeting.objects.create(
            visitor_name="Jane Doe",
            visitor_email="jane@example.com",
            title="Existing",
            start_time=start,
            end_time=end,
        )

        with self.assertRaises(DuplicateBookingError):
            self.service.book_meeting(
                visitor_name="Jane Doe",
                visitor_email="jane@example.com",
                visitor_phone="",
                start_time=start,
                end_time=end,
                agenda="",
            )

    def test_book_meeting_rejects_google_calendar_conflict(self):
        start = next_business_datetime()
        end = start + dt.timedelta(minutes=30)
        self.calendar_service.get_busy_periods.return_value = [(start, end)]

        with self.assertRaises(SlotUnavailableError):
            self.service.book_meeting(
                visitor_name="Jane Doe",
                visitor_email="jane@example.com",
                visitor_phone="",
                start_time=start,
                end_time=end,
                agenda="",
            )
        self.calendar_service.create_event.assert_not_called()

    def test_book_meeting_rolls_back_db_row_on_calendar_failure(self):
        from apps.meeting.exceptions import GoogleCalendarError

        start = next_business_datetime()
        end = start + dt.timedelta(minutes=30)
        self.calendar_service.create_event.side_effect = GoogleCalendarError("boom")

        with self.assertRaises(GoogleCalendarError):
            self.service.book_meeting(
                visitor_name="Jane Doe",
                visitor_email="jane@example.com",
                visitor_phone="",
                start_time=start,
                end_time=end,
                agenda="",
            )
        self.assertFalse(Meeting.objects.filter(visitor_email="jane@example.com").exists())


class MeetingServiceRescheduleAndCancelTests(TestCase):
    def setUp(self):
        self.calendar_service = MagicMock()
        self.calendar_service.get_busy_periods.return_value = []
        self.service = MeetingService(calendar_service=self.calendar_service)

        start = next_business_datetime()
        self.meeting = Meeting.objects.create(
            visitor_name="Jane Doe",
            visitor_email="jane@example.com",
            title="Meeting with Jane Doe",
            start_time=start,
            end_time=start + dt.timedelta(minutes=30),
            google_event_id="evt_123",
        )

    def test_reschedule_updates_time_and_syncs_calendar(self):
        new_start = next_business_datetime(days_ahead=2)
        new_end = new_start + dt.timedelta(minutes=30)

        with patch("apps.meeting.tasks.send_reschedule_email_task.delay") as mock_delay:
            with self.captureOnCommitCallbacks(execute=True):
                meeting = self.service.reschedule_meeting(
                    self.meeting, new_start_time=new_start, new_end_time=new_end
                )

        meeting.refresh_from_db()
        self.assertEqual(meeting.status, Meeting.STATUS_RESCHEDULED)
        self.assertEqual(meeting.start_time, new_start)
        self.assertEqual(meeting.reschedule_count, 1)
        self.calendar_service.update_event_time.assert_called_once()
        mock_delay.assert_called_once()

    def test_cancel_deletes_calendar_event_and_marks_cancelled(self):
        with patch("apps.meeting.tasks.send_cancellation_email_task.delay") as mock_delay:
            with self.captureOnCommitCallbacks(execute=True):
                meeting = self.service.cancel_meeting(self.meeting, reason="not needed anymore")

        meeting.refresh_from_db()
        self.assertEqual(meeting.status, Meeting.STATUS_CANCELLED)
        self.assertEqual(meeting.cancellation_reason, "not needed anymore")
        self.calendar_service.delete_event.assert_called_once_with("evt_123")
        mock_delay.assert_called_once()

    def test_cannot_cancel_an_already_cancelled_meeting(self):
        from apps.meeting.exceptions import MeetingNotModifiableError

        self.meeting.status = Meeting.STATUS_CANCELLED
        self.meeting.save(update_fields=["status"])

        with self.assertRaises(MeetingNotModifiableError):
            self.service.cancel_meeting(self.meeting)
