import datetime as dt
from unittest.mock import patch

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.meeting.models import Meeting
from apps.meeting.services.google_calendar_service import GoogleCalendarService
from apps.users.models import CustomUser

from .helpers import next_business_datetime


def _fake_event(event_id="evt_1"):
    return {
        "id": event_id,
        "hangoutLink": "https://meet.google.com/xyz-abcd-efg",
        "htmlLink": "https://calendar.google.com/event?eid=xyz",
    }


@patch.object(GoogleCalendarService, "get_busy_periods", return_value=[])
@patch.object(GoogleCalendarService, "create_event", return_value=_fake_event())
class MeetingAPITests(APITestCase):
    def test_slots_endpoint_returns_available_slots(self, _create_event, _get_busy):
        target_date = next_business_datetime(days_ahead=2).date()
        url = reverse("meeting:meeting-slots")

        response = self.client.get(url, {"date": target_date.isoformat()})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreater(len(response.data["slots"]), 0)

    def test_slots_endpoint_rejects_past_date(self, _create_event, _get_busy):
        past_date = (next_business_datetime() - dt.timedelta(days=30)).date()
        url = reverse("meeting:meeting-slots")

        response = self.client.get(url, {"date": past_date.isoformat()})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_book_meeting_creates_scheduled_meeting(self, _create_event, _get_busy):
        start = next_business_datetime(days_ahead=2)
        url = reverse("meeting:meeting-book")

        response = self.client.post(
            url,
            {
                "visitor_name": "Jane Doe",
                "visitor_email": "jane@example.com",
                "start_time": start.isoformat(),
                "agenda": "Product demo",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["status"], Meeting.STATUS_SCHEDULED)
        self.assertTrue(response.data["google_meet_link"])
        self.assertTrue(Meeting.objects.filter(visitor_email="jane@example.com").exists())

    def test_book_meeting_rejects_past_time(self, _create_event, _get_busy):
        past = next_business_datetime() - dt.timedelta(days=10)
        url = reverse("meeting:meeting-book")

        response = self.client.post(
            url,
            {"visitor_name": "Jane Doe", "visitor_email": "jane@example.com", "start_time": past.isoformat()},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_book_meeting_rejects_duplicate_slot(self, _create_event, _get_busy):
        start = next_business_datetime(days_ahead=2)
        Meeting.objects.create(
            visitor_name="Existing",
            visitor_email="existing@example.com",
            title="Existing meeting",
            start_time=start,
            end_time=start + dt.timedelta(minutes=30),
        )
        url = reverse("meeting:meeting-book")

        response = self.client.post(
            url,
            {"visitor_name": "New Visitor", "visitor_email": "new@example.com", "start_time": start.isoformat()},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)

    def test_list_meetings_requires_staff(self, _create_event, _get_busy):
        url = reverse("meeting:meeting-list")
        response = self.client.get(url)
        self.assertIn(response.status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN))

    def test_staff_can_list_meetings(self, _create_event, _get_busy):
        staff_user = CustomUser.objects.create_user(
            email="admin@example.com", password="password123", full_name="Admin"
        )
        staff_user.is_staff = True
        staff_user.save(update_fields=["is_staff"])

        start = next_business_datetime(days_ahead=2)
        Meeting.objects.create(
            visitor_name="Jane Doe",
            visitor_email="jane@example.com",
            title="Meeting",
            start_time=start,
            end_time=start + dt.timedelta(minutes=30),
        )

        self.client.force_authenticate(user=staff_user)
        url = reverse("meeting:meeting-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)

    def test_visitor_cannot_access_detail_without_token(self, _create_event, _get_busy):
        start = next_business_datetime(days_ahead=2)
        meeting = Meeting.objects.create(
            visitor_name="Jane Doe",
            visitor_email="jane@example.com",
            title="Meeting",
            start_time=start,
            end_time=start + dt.timedelta(minutes=30),
        )
        url = reverse("meeting:meeting-detail", args=[meeting.id])

        response = self.client.get(url)

        # No credentials were sent at all, so DRF's JWTAuthentication reports
        # NotAuthenticated (401) rather than PermissionDenied (403).
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_visitor_can_access_detail_with_public_token(self, _create_event, _get_busy):
        start = next_business_datetime(days_ahead=2)
        meeting = Meeting.objects.create(
            visitor_name="Jane Doe",
            visitor_email="jane@example.com",
            title="Meeting",
            start_time=start,
            end_time=start + dt.timedelta(minutes=30),
        )
        url = reverse("meeting:meeting-detail", args=[meeting.id])

        response = self.client.get(url, {"token": str(meeting.public_token)})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["visitor_email"], "jane@example.com")

    @patch.object(GoogleCalendarService, "delete_event")
    def test_visitor_can_cancel_with_public_token(self, mock_delete_event, _create_event, _get_busy):
        start = next_business_datetime(days_ahead=2)
        meeting = Meeting.objects.create(
            visitor_name="Jane Doe",
            visitor_email="jane@example.com",
            title="Meeting",
            start_time=start,
            end_time=start + dt.timedelta(minutes=30),
            google_event_id="evt_1",
        )
        url = reverse("meeting:meeting-cancel", args=[meeting.id])

        response = self.client.post(
            f"{url}?token={meeting.public_token}", {"reason": "no longer needed"}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        meeting.refresh_from_db()
        self.assertEqual(meeting.status, Meeting.STATUS_CANCELLED)
        mock_delete_event.assert_called_once_with("evt_1")

    @patch.object(GoogleCalendarService, "update_event_time")
    def test_visitor_can_reschedule_with_public_token(self, mock_update_event, _create_event, _get_busy):
        start = next_business_datetime(days_ahead=2)
        meeting = Meeting.objects.create(
            visitor_name="Jane Doe",
            visitor_email="jane@example.com",
            title="Meeting",
            start_time=start,
            end_time=start + dt.timedelta(minutes=30),
            google_event_id="evt_1",
        )
        new_start = next_business_datetime(days_ahead=4)
        url = reverse("meeting:meeting-reschedule", args=[meeting.id])

        response = self.client.patch(
            f"{url}?token={meeting.public_token}",
            {"start_time": new_start.isoformat()},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        meeting.refresh_from_db()
        self.assertEqual(meeting.status, Meeting.STATUS_RESCHEDULED)
        self.assertEqual(meeting.start_time, new_start)
        mock_update_event.assert_called_once()
