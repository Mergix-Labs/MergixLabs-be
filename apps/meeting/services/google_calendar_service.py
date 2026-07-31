import datetime as dt
import logging

from django.conf import settings
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from ..exceptions import GoogleCalendarError

logger = logging.getLogger("meeting")


class GoogleCalendarService:
    """
    Thin wrapper around the Google Calendar API v3.

    Authenticates as the admin's Google account via a long-lived OAuth refresh
    token (env-configured, see README). A service account is intentionally NOT
    used here: service accounts cannot invite attendees or generate Google
    Meet links unless Workspace domain-wide delegation is enabled, which most
    single-user setups don't have.
    """

    _SCOPES = ["https://www.googleapis.com/auth/calendar"]

    def __init__(self) -> None:
        self._service = None

    def _get_credentials(self) -> Credentials:
        required = {
            "GOOGLE_CLIENT_ID": settings.GOOGLE_CLIENT_ID,
            "GOOGLE_CLIENT_SECRET": settings.GOOGLE_CLIENT_SECRET,
            "GOOGLE_REFRESH_TOKEN": settings.GOOGLE_REFRESH_TOKEN,
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise GoogleCalendarError(
                f"Google Calendar integration is not configured. Missing: {', '.join(missing)}."
            )

        credentials = Credentials(
            token=None,
            refresh_token=settings.GOOGLE_REFRESH_TOKEN,
            token_uri=settings.GOOGLE_TOKEN_URI,
            client_id=settings.GOOGLE_CLIENT_ID,
            client_secret=settings.GOOGLE_CLIENT_SECRET,
            scopes=self._SCOPES,
        )
        try:
            credentials.refresh(Request())
        except Exception as exc:
            logger.exception("Failed to refresh Google OAuth credentials")
            raise GoogleCalendarError("Could not authenticate with Google Calendar.") from exc
        return credentials

    def _get_service(self):
        if self._service is None:
            credentials = self._get_credentials()
            self._service = build("calendar", "v3", credentials=credentials, cache_discovery=False)
        return self._service

    def get_busy_periods(
        self, time_min: dt.datetime, time_max: dt.datetime
    ) -> list[tuple[dt.datetime, dt.datetime]]:
        """Queries the admin calendar's free/busy data for the given window."""
        service = self._get_service()
        body = {
            "timeMin": time_min.isoformat(),
            "timeMax": time_max.isoformat(),
            "items": [{"id": settings.GOOGLE_CALENDAR_ID}],
        }
        try:
            response = service.freebusy().query(body=body).execute()
        except HttpError as exc:
            logger.exception("Google Calendar freebusy query failed")
            raise GoogleCalendarError("Could not check calendar availability.") from exc

        calendar_data = response.get("calendars", {}).get(settings.GOOGLE_CALENDAR_ID, {})
        busy_periods = []
        for period in calendar_data.get("busy", []):
            busy_periods.append(
                (dt.datetime.fromisoformat(period["start"]), dt.datetime.fromisoformat(period["end"]))
            )
        return busy_periods

    def create_event(
        self,
        *,
        summary: str,
        description: str,
        start: dt.datetime,
        end: dt.datetime,
        timezone_name: str,
        visitor_email: str,
        visitor_name: str,
        organizer_email: str,
    ) -> dict:
        """Creates the calendar event with a Google Meet link and emails invites to both parties."""
        service = self._get_service()
        event_body = {
            "summary": summary,
            "description": description,
            "start": {"dateTime": start.isoformat(), "timeZone": timezone_name},
            "end": {"dateTime": end.isoformat(), "timeZone": timezone_name},
            "attendees": [
                {"email": visitor_email, "displayName": visitor_name},
                {"email": organizer_email},
            ],
            "conferenceData": {
                "createRequest": {
                    "requestId": f"meet-{int(start.timestamp())}-{abs(hash(visitor_email))}",
                    "conferenceSolutionKey": {"type": "hangoutsMeet"},
                }
            },
            "reminders": {"useDefault": True},
        }
        try:
            event = (
                service.events()
                .insert(
                    calendarId=settings.GOOGLE_CALENDAR_ID,
                    body=event_body,
                    conferenceDataVersion=1,
                    sendUpdates="all",
                )
                .execute()
            )
        except HttpError as exc:
            logger.exception("Failed to create Google Calendar event")
            raise GoogleCalendarError("Could not create the calendar event.") from exc
        return event

    def update_event_time(
        self, event_id: str, *, start: dt.datetime, end: dt.datetime, timezone_name: str
    ) -> dict:
        """Patches an existing event's start/end time (used for reschedules) and re-notifies attendees."""
        service = self._get_service()
        try:
            event = (
                service.events()
                .patch(
                    calendarId=settings.GOOGLE_CALENDAR_ID,
                    eventId=event_id,
                    body={
                        "start": {"dateTime": start.isoformat(), "timeZone": timezone_name},
                        "end": {"dateTime": end.isoformat(), "timeZone": timezone_name},
                    },
                    conferenceDataVersion=1,
                    sendUpdates="all",
                )
                .execute()
            )
        except HttpError as exc:
            logger.exception("Failed to reschedule Google Calendar event %s", event_id)
            raise GoogleCalendarError("Could not update the calendar event.") from exc
        return event

    def delete_event(self, event_id: str) -> None:
        """Deletes the event and notifies attendees of the cancellation."""
        service = self._get_service()
        try:
            service.events().delete(
                calendarId=settings.GOOGLE_CALENDAR_ID,
                eventId=event_id,
                sendUpdates="all",
            ).execute()
        except HttpError as exc:
            if exc.resp.status in (404, 410):
                logger.warning("Google Calendar event %s was already deleted", event_id)
                return
            logger.exception("Failed to delete Google Calendar event %s", event_id)
            raise GoogleCalendarError("Could not cancel the calendar event.") from exc
