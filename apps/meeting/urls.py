from django.urls import path

from .views import (
    AvailableSlotsView,
    BookMeetingView,
    MeetingCancelView,
    MeetingDetailView,
    MeetingListView,
    MeetingRescheduleView,
)

app_name = "meeting"

urlpatterns = [
    path("slots/", AvailableSlotsView.as_view(), name="meeting-slots"),
    path("book/", BookMeetingView.as_view(), name="meeting-book"),
    path("", MeetingListView.as_view(), name="meeting-list"),
    path("<uuid:id>/", MeetingDetailView.as_view(), name="meeting-detail"),
    path("<uuid:id>/reschedule/", MeetingRescheduleView.as_view(), name="meeting-reschedule"),
    path("<uuid:id>/cancel/", MeetingCancelView.as_view(), name="meeting-cancel"),
]
