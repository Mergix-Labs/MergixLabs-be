import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class Meeting(models.Model):
    """A scheduled call between a website visitor and the admin, backed by a Google Calendar event."""

    STATUS_SCHEDULED = "scheduled"
    STATUS_RESCHEDULED = "rescheduled"
    STATUS_CANCELLED = "cancelled"
    STATUS_COMPLETED = "completed"

    STATUS_CHOICES = [
        (STATUS_SCHEDULED, "Scheduled"),
        (STATUS_RESCHEDULED, "Rescheduled"),
        (STATUS_CANCELLED, "Cancelled"),
        (STATUS_COMPLETED, "Completed"),
    ]

    # Statuses under which a meeting still occupies a slot on the calendar.
    ACTIVE_STATUSES = (STATUS_SCHEDULED, STATUS_RESCHEDULED)

    CANCELLED_BY_VISITOR = "visitor"
    CANCELLED_BY_ADMIN = "admin"
    CANCELLED_BY_CHOICES = [
        (CANCELLED_BY_VISITOR, "Visitor"),
        (CANCELLED_BY_ADMIN, "Admin"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    # Capability token mailed to the visitor so they can view/reschedule/cancel without an account.
    public_token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, db_index=True)

    visitor_name = models.CharField(max_length=150)
    visitor_email = models.EmailField(db_index=True)
    visitor_phone = models.CharField(max_length=32, blank=True)

    title = models.CharField(max_length=255)
    agenda = models.TextField(blank=True)

    start_time = models.DateTimeField(db_index=True)
    end_time = models.DateTimeField()
    timezone = models.CharField(max_length=64, default="UTC")

    status = models.CharField(
        max_length=16, choices=STATUS_CHOICES, default=STATUS_SCHEDULED, db_index=True
    )

    google_event_id = models.CharField(max_length=255, blank=True)
    google_meet_link = models.URLField(blank=True)
    google_event_link = models.URLField(blank=True)

    rescheduled_from = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="rescheduled_to",
    )
    reschedule_count = models.PositiveIntegerField(default=0)

    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancellation_reason = models.CharField(max_length=255, blank=True)
    cancelled_by = models.CharField(max_length=16, choices=CANCELLED_BY_CHOICES, blank=True)

    reminder_sent = models.BooleanField(default=False)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_meetings",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-start_time"]
        indexes = [
            models.Index(fields=["start_time", "end_time", "status"]),
            models.Index(fields=["visitor_email", "start_time"]),
        ]

    def __str__(self) -> str:
        return f"{self.visitor_name} <{self.visitor_email}> @ {self.start_time.isoformat()}"

    @property
    def is_active(self) -> bool:
        return self.status in self.ACTIVE_STATUSES

    @property
    def is_upcoming(self) -> bool:
        return self.is_active and self.start_time > timezone.now()
