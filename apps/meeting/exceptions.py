from rest_framework import status
from rest_framework.exceptions import APIException


class MeetingBaseException(APIException):
    """Base class for all meeting-domain errors surfaced to the API layer."""

    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Unable to process the meeting request."
    default_code = "meeting_error"

    def __init__(self, detail=None, code=None):
        super().__init__(detail=detail or self.default_detail, code=code or self.default_code)


class InvalidSlotError(MeetingBaseException):
    """Raised when a requested slot violates a business rule (working hours, past date, etc.)."""

    default_detail = "The selected time slot is invalid."
    default_code = "invalid_slot"


class SlotUnavailableError(MeetingBaseException):
    """Raised when a slot is already occupied on the admin's Google Calendar."""

    status_code = status.HTTP_409_CONFLICT
    default_detail = "The selected time slot is no longer available."
    default_code = "slot_unavailable"


class DuplicateBookingError(MeetingBaseException):
    """Raised when the visitor or the internal schedule already has an overlapping booking."""

    status_code = status.HTTP_409_CONFLICT
    default_detail = "A meeting is already booked for this email at an overlapping time."
    default_code = "duplicate_booking"


class MeetingNotModifiableError(MeetingBaseException):
    """Raised when trying to reschedule/cancel a meeting that is not in an active state."""

    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "This meeting can no longer be modified."
    default_code = "meeting_not_modifiable"


class GoogleCalendarError(MeetingBaseException):
    """Raised when the Google Calendar API cannot be reached or returns an error."""

    status_code = status.HTTP_502_BAD_GATEWAY
    default_detail = "Could not communicate with Google Calendar. Please try again shortly."
    default_code = "google_calendar_error"
