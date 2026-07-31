import datetime as dt
import logging

from django.conf import settings
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Meeting
from .permissions import IsMeetingStaffOrTokenOwner
from .serializers import (
    AvailableSlotQuerySerializer,
    MeetingBookingSerializer,
    MeetingCancelSerializer,
    MeetingListQuerySerializer,
    MeetingRescheduleSerializer,
    MeetingSerializer,
    SlotSerializer,
)
from .services.meeting_service import MeetingService

logger = logging.getLogger("meeting")


class MeetingPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


def _get_meeting_for_request(request, view, meeting_id) -> Meeting:
    """Fetches a meeting and enforces object-level permissions (staff or token owner)."""
    meeting = get_object_or_404(Meeting, id=meeting_id)
    view.check_object_permissions(request, meeting)
    return meeting


class AvailableSlotsView(APIView):
    """GET /api/meetings/slots/?date=YYYY-MM-DD

    Public endpoint: returns the bookable slots for a given day, filtered by
    working hours, existing DB bookings, and the admin's live Google Calendar.
    """

    permission_classes = [AllowAny]

    def get(self, request):
        query = AvailableSlotQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        target_date = query.validated_data["date"]

        service = MeetingService()
        slots = service.get_available_slots(target_date)

        return Response(
            {
                "date": target_date,
                "timezone": settings.MEETING_TIMEZONE,
                "slot_duration_minutes": settings.MEETING_SLOT_DURATION_MINUTES,
                "slots": SlotSerializer(slots, many=True).data,
            },
            status=status.HTTP_200_OK,
        )


class BookMeetingView(APIView):
    """POST /api/meetings/book/

    Public endpoint: books a meeting, creates the Google Calendar event with a
    Meet link, invites both parties, and queues a confirmation email.
    """

    permission_classes = [AllowAny]

    def post(self, request):
        serializer = MeetingBookingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        slot_duration = dt.timedelta(minutes=settings.MEETING_SLOT_DURATION_MINUTES)
        start_time = data["start_time"]
        end_time = start_time + slot_duration

        created_by = request.user if request.user and request.user.is_authenticated else None

        meeting = MeetingService().book_meeting(
            visitor_name=data["visitor_name"],
            visitor_email=data["visitor_email"],
            visitor_phone=data.get("visitor_phone", ""),
            start_time=start_time,
            end_time=end_time,
            agenda=data.get("agenda", ""),
            created_by=created_by,
        )
        return Response(MeetingSerializer(meeting).data, status=status.HTTP_201_CREATED)


class MeetingListView(APIView):
    """GET /api/meetings/ (staff only)

    Lists meetings with optional filters: status, visitor_email, date_from, date_to.
    """

    permission_classes = [IsAdminUser]

    def get(self, request):
        query = MeetingListQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        filters = query.validated_data

        meetings = Meeting.objects.all()
        if "status" in filters:
            meetings = meetings.filter(status=filters["status"])
        if "visitor_email" in filters:
            meetings = meetings.filter(visitor_email__iexact=filters["visitor_email"])
        if "date_from" in filters:
            meetings = meetings.filter(start_time__date__gte=filters["date_from"])
        if "date_to" in filters:
            meetings = meetings.filter(start_time__date__lte=filters["date_to"])

        paginator = MeetingPagination()
        page = paginator.paginate_queryset(meetings, request, view=self)
        serializer = MeetingSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


class MeetingDetailView(APIView):
    """GET /api/meetings/<id>/ (staff, or the visitor via `?token=<public_token>`)"""

    permission_classes = [IsMeetingStaffOrTokenOwner]

    def get(self, request, id):
        meeting = _get_meeting_for_request(request, self, id)
        return Response(MeetingSerializer(meeting).data, status=status.HTTP_200_OK)


class MeetingRescheduleView(APIView):
    """PATCH /api/meetings/<id>/reschedule/ (staff, or the visitor via `?token=<public_token>`)"""

    permission_classes = [IsMeetingStaffOrTokenOwner]

    def patch(self, request, id):
        meeting = _get_meeting_for_request(request, self, id)

        serializer = MeetingRescheduleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        slot_duration = dt.timedelta(minutes=settings.MEETING_SLOT_DURATION_MINUTES)
        new_start_time = data["start_time"]
        new_end_time = new_start_time + slot_duration

        meeting = MeetingService().reschedule_meeting(
            meeting,
            new_start_time=new_start_time,
            new_end_time=new_end_time,
            reason=data.get("reason", ""),
        )
        return Response(MeetingSerializer(meeting).data, status=status.HTTP_200_OK)


class MeetingCancelView(APIView):
    """POST /api/meetings/<id>/cancel/ (staff, or the visitor via `?token=<public_token>`)"""

    permission_classes = [IsMeetingStaffOrTokenOwner]

    def post(self, request, id):
        meeting = _get_meeting_for_request(request, self, id)

        serializer = MeetingCancelSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        cancelled_by = (
            Meeting.CANCELLED_BY_ADMIN
            if request.user and request.user.is_authenticated and request.user.is_staff
            else Meeting.CANCELLED_BY_VISITOR
        )

        meeting = MeetingService().cancel_meeting(
            meeting, reason=data.get("reason", ""), cancelled_by=cancelled_by
        )
        return Response(MeetingSerializer(meeting).data, status=status.HTTP_200_OK)
