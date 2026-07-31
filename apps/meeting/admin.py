from django.contrib import admin, messages
from django.utils.html import format_html
from unfold.admin import ModelAdmin

from .models import Meeting
from .services.meeting_service import MeetingService


@admin.register(Meeting)
class MeetingAdmin(ModelAdmin):
    list_display = (
        "visitor_name",
        "visitor_email",
        "start_time",
        "end_time",
        "status",
        "reschedule_count",
        "meet_link_display",
        "created_at",
    )
    list_filter = ("status", "cancelled_by", "start_time")
    search_fields = (
        "visitor_name",
        "visitor_email",
        "visitor_phone",
        "google_event_id",
        "id",
        "public_token",
    )
    date_hierarchy = "start_time"
    ordering = ("-start_time",)
    actions = ["mark_completed", "cancel_selected"]

    readonly_fields = (
        "id",
        "public_token",
        "google_event_id",
        "google_meet_link",
        "google_event_link",
        "reschedule_count",
        "cancelled_at",
        "created_at",
        "updated_at",
    )

    fieldsets = (
        ("Visitor", {"fields": ("visitor_name", "visitor_email", "visitor_phone")}),
        (
            "Schedule",
            {"fields": ("title", "agenda", "start_time", "end_time", "timezone", "status")},
        ),
        (
            "Google Calendar",
            {"fields": ("google_event_id", "google_meet_link", "google_event_link")},
        ),
        (
            "Lifecycle",
            {
                "fields": (
                    "rescheduled_from",
                    "reschedule_count",
                    "reminder_sent",
                    "cancelled_at",
                    "cancellation_reason",
                    "cancelled_by",
                )
            },
        ),
        ("Metadata", {"fields": ("id", "public_token", "created_by", "created_at", "updated_at")}),
    )

    @admin.display(description="Meet Link")
    def meet_link_display(self, obj: Meeting):
        if not obj.google_meet_link:
            return "-"
        return format_html('<a href="{}" target="_blank">Join</a>', obj.google_meet_link)

    @admin.action(description="Mark selected meetings as completed")
    def mark_completed(self, request, queryset):
        updated = queryset.filter(status__in=Meeting.ACTIVE_STATUSES).update(
            status=Meeting.STATUS_COMPLETED
        )
        self.message_user(request, f"{updated} meeting(s) marked as completed.")

    @admin.action(description="Cancel selected meetings (also cancels the Google Calendar event)")
    def cancel_selected(self, request, queryset):
        service = MeetingService()
        cancelled = 0
        for meeting in queryset.filter(status__in=Meeting.ACTIVE_STATUSES):
            try:
                service.cancel_meeting(
                    meeting, reason="Cancelled by admin", cancelled_by=Meeting.CANCELLED_BY_ADMIN
                )
                cancelled += 1
            except Exception as exc:  # surfaced to the admin instead of a 500 page
                self.message_user(
                    request, f"Failed to cancel meeting {meeting.id}: {exc}", level=messages.ERROR
                )
        if cancelled:
            self.message_user(request, f"{cancelled} meeting(s) cancelled.")
