import datetime as dt

from django.conf import settings
from django.utils import timezone
from rest_framework import serializers

from .models import Meeting
from .validators import get_meeting_timezone


class AvailableSlotQuerySerializer(serializers.Serializer):
    date = serializers.DateField()

    def validate_date(self, value: dt.date) -> dt.date:
        today = timezone.now().astimezone(get_meeting_timezone()).date()
        max_date = today + dt.timedelta(days=settings.MEETING_MAX_ADVANCE_DAYS)
        if value < today:
            raise serializers.ValidationError("Cannot fetch slots for a past date.")
        if value > max_date:
            raise serializers.ValidationError(
                f"Slots can only be viewed up to {settings.MEETING_MAX_ADVANCE_DAYS} days in advance."
            )
        return value


class SlotSerializer(serializers.Serializer):
    start_time = serializers.DateTimeField()
    end_time = serializers.DateTimeField()


class MeetingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Meeting
        fields = [
            "id",
            "public_token",
            "visitor_name",
            "visitor_email",
            "visitor_phone",
            "title",
            "agenda",
            "start_time",
            "end_time",
            "timezone",
            "status",
            "google_meet_link",
            "google_event_link",
            "reschedule_count",
            "cancelled_at",
            "cancellation_reason",
            "cancelled_by",
            "reminder_sent",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class MeetingBookingSerializer(serializers.Serializer):
    visitor_name = serializers.CharField(max_length=150)
    visitor_email = serializers.EmailField()
    visitor_phone = serializers.CharField(max_length=32, required=False, allow_blank=True, default="")
    start_time = serializers.DateTimeField()
    agenda = serializers.CharField(required=False, allow_blank=True, max_length=2000, default="")


class MeetingRescheduleSerializer(serializers.Serializer):
    start_time = serializers.DateTimeField()
    reason = serializers.CharField(required=False, allow_blank=True, max_length=255, default="")


class MeetingCancelSerializer(serializers.Serializer):
    reason = serializers.CharField(required=False, allow_blank=True, max_length=255, default="")


class MeetingListQuerySerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=Meeting.STATUS_CHOICES, required=False)
    visitor_email = serializers.EmailField(required=False)
    date_from = serializers.DateField(required=False)
    date_to = serializers.DateField(required=False)
