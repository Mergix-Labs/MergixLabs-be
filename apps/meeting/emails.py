import datetime as dt
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.template.loader import render_to_string
from django.utils import timezone


def _meeting_local_times(meeting) -> tuple[dt.datetime, dt.datetime]:
    """Resolves start/end times in the meeting's own configured timezone,
    independent of whatever timezone is currently active for the process."""
    try:
        tz = ZoneInfo(meeting.timezone or "UTC")
    except ZoneInfoNotFoundError:
        tz = dt.timezone.utc
    return meeting.start_time.astimezone(tz), meeting.end_time.astimezone(tz)


def _meeting_email_context(meeting) -> dict:
    start_local, end_local = _meeting_local_times(meeting)
    return {
        "meeting": meeting,
        "visitor_name": meeting.visitor_name,
        "visitor_email": meeting.visitor_email,
        "visitor_phone": meeting.visitor_phone,
        "title": meeting.title,
        "date": start_local.strftime("%A, %d %B %Y"),
        "time": f"{start_local.strftime('%I:%M %p')} - {end_local.strftime('%I:%M %p')}",
        "timezone": meeting.timezone,
        "agenda": meeting.agenda,
        "google_meet_link": meeting.google_meet_link,
        "google_event_link": meeting.google_event_link,
        "meeting_id": meeting.id,
        "public_token": meeting.public_token,
    }


def _format_range(start: dt.datetime, end: dt.datetime) -> str:
    local_start = timezone.localtime(start)
    local_end = timezone.localtime(end)
    return f"{local_start.strftime('%A, %d %B %Y, %I:%M %p')} - {local_end.strftime('%I:%M %p %Z')}"


def _meet_button(meeting) -> str:
    if not meeting.google_meet_link:
        return ""
    return f'<a class="button" href="{meeting.google_meet_link}">Join Google Meet</a>'


def _base_wrapper(heading: str, body_html: str) -> str:
    return f"""
    <html>
    <head>
    <style>
    .container{{width:100%;padding:10px;background-color:#f1f1f1;}}
    .content{{width:50%;margin:0 auto;padding:20px;background-color:white;border-radius:8px;}}
    .meta{{color:#555;margin:4px 0;}}
    .button{{display:inline-block;padding:10px 18px;background-color:#7c3aed;color:white;
             text-decoration:none;border-radius:6px;margin-top:12px;}}
    </style>
    </head>
    <body>
    <div class="container">
        <div class="content">
            <h1>{heading}</h1>
            {body_html}
        </div>
    </div>
    </body>
    </html>
    """


def meeting_confirmation_template(meeting) -> str:
    return render_to_string("meeting/emails/visitor_confirmation.html", _meeting_email_context(meeting))


def organizer_notification_template(meeting) -> str:
    return render_to_string("meeting/emails/organizer_notification.html", _meeting_email_context(meeting))


def meeting_reminder_template(meeting) -> str:
    body = f"""
    <p>Hi {meeting.visitor_name},</p>
    <p>This is a reminder that your meeting is coming up soon.</p>
    <p class="meta"><strong>When:</strong> {_format_range(meeting.start_time, meeting.end_time)}</p>
    {_meet_button(meeting)}
    """
    return _base_wrapper("Meeting Reminder", body)


def meeting_reschedule_template(meeting, old_start_iso: str, old_end_iso: str) -> str:
    old_start = dt.datetime.fromisoformat(old_start_iso)
    old_end = dt.datetime.fromisoformat(old_end_iso)
    body = f"""
    <p>Hi {meeting.visitor_name},</p>
    <p>Your meeting has been rescheduled.</p>
    <p class="meta"><strong>Previous time:</strong> {_format_range(old_start, old_end)}</p>
    <p class="meta"><strong>New time:</strong> {_format_range(meeting.start_time, meeting.end_time)}</p>
    {_meet_button(meeting)}
    """
    return _base_wrapper("Meeting Rescheduled", body)


def meeting_cancellation_template(meeting) -> str:
    body = f"""
    <p>Hi {meeting.visitor_name},</p>
    <p>Your meeting scheduled for {_format_range(meeting.start_time, meeting.end_time)} has been cancelled.</p>
    <p class="meta"><strong>Reason:</strong> {meeting.cancellation_reason or 'Not specified'}</p>
    <p>Feel free to book a new slot whenever it's convenient for you.</p>
    """
    return _base_wrapper("Meeting Cancelled", body)
