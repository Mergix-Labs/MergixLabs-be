# Meeting Scheduling (`apps.meeting`)

Backend for booking calls between website visitors and the admin, with live
Google Calendar availability, automatic Google Meet link generation, calendar
invites, and Celery-driven notification emails. No frontend is included.

## Architecture

```
apps/meeting/
  models.py                       Meeting model
  validators.py                   Business-rule validation (working hours, notice, duplicates...)
  exceptions.py                   Typed API exceptions (400/409/502)
  permissions.py                  Staff-or-token object permission
  serializers.py                  Request/response (de)serialization
  services/
    google_calendar_service.py    Google Calendar API v3 wrapper (OAuth2 refresh token)
    slot_service.py               Available-slot computation (working hours + DB + Google freebusy)
    meeting_service.py            Orchestrates booking/reschedule/cancel end-to-end
  emails.py                       HTML email templates
  tasks.py                        Celery tasks: confirmation/reminder/reschedule/cancellation emails
  admin.py                        Django admin (Unfold) for meeting management
  views.py / urls.py              DRF APIViews and routing
  tests/                          Unit + API tests (Google Calendar is mocked)
```

Request flow for booking: `views.py` validates the request shape via
`serializers.py`, then delegates all business logic to
`services.meeting_service.MeetingService`, which runs `validators.py`,
calls `GoogleCalendarService` to create the event (Meet link + invites),
persists the `Meeting` row, and schedules a confirmation email via
`tasks.py` (fired from `transaction.on_commit` so it never races the DB
commit).

## API

All endpoints are namespaced under `/api/v1/meetings/`.

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/slots/?date=YYYY-MM-DD` | Public | Available slots for a day |
| POST | `/book/` | Public | Book a meeting |
| GET | `/` | Staff (JWT) | List/filter all meetings (paginated) |
| GET | `/<id>/` | Staff, or visitor with `?token=` | Meeting detail |
| PATCH | `/<id>/reschedule/` | Staff, or visitor with `?token=` | Reschedule to a new slot |
| POST | `/<id>/cancel/` | Staff, or visitor with `?token=` | Cancel |

Every `Meeting` has a `public_token` (a UUID, returned in the booking
response and mailed to the visitor). It acts as a capability token so a
visitor without an account can view/reschedule/cancel *their own* meeting by
appending `?token=<public_token>` -- staff use their JWT instead.

### GET `/api/v1/meetings/slots/?date=2026-08-03`

```json
{
  "date": "2026-08-03",
  "timezone": "Asia/Kolkata",
  "slot_duration_minutes": 30,
  "slots": [
    {"start_time": "2026-08-03T09:00:00+05:30", "end_time": "2026-08-03T09:30:00+05:30"},
    {"start_time": "2026-08-03T09:30:00+05:30", "end_time": "2026-08-03T10:00:00+05:30"}
  ]
}
```

### POST `/api/v1/meetings/book/`

Request:
```json
{
  "visitor_name": "Jane Doe",
  "visitor_email": "jane@example.com",
  "visitor_phone": "+1 555 0100",
  "start_time": "2026-08-03T09:30:00+05:30",
  "agenda": "Discuss the Q3 partnership proposal"
}
```

Response (`201 Created`): the full `Meeting` object, including
`google_meet_link`, `google_event_link`, and `public_token`.

Validation performed (returns `400`/`409` with a clear `detail` message on
failure): working hours, weekends, past/too-soon/too-far-out times, exact
slot duration, duplicate bookings for the same visitor, internal double
booking, and a live Google Calendar free/busy conflict check.

### PATCH `/api/v1/meetings/<id>/reschedule/`

```json
{"start_time": "2026-08-05T11:00:00+05:30", "reason": "Client asked to move it"}
```

### POST `/api/v1/meetings/<id>/cancel/`

```json
{"reason": "No longer needed"}
```

## Environment variables

See `settings.ini.sample` / `.env` for the full list. All Google credentials
are read from the environment -- nothing is hardcoded.

| Variable | Purpose |
|---|---|
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | OAuth2 client credentials |
| `GOOGLE_REFRESH_TOKEN` | Long-lived token for the admin's Google account |
| `GOOGLE_TOKEN_URI` | Defaults to `https://oauth2.googleapis.com/token` |
| `GOOGLE_CALENDAR_ID` | Calendar to read/write, e.g. `primary` or an email address |
| `GOOGLE_ADMIN_EMAIL` | Admin's email; added as an attendee and CC'd on notification emails |
| `MEETING_TIMEZONE` | Business timezone for working hours (independent of Django's `TIME_ZONE`) |
| `MEETING_WORKING_DAYS` | Comma-separated weekdays, Monday=0 (default `0,1,2,3,4`) |
| `MEETING_WORKING_HOURS_START` / `_END` | e.g. `09:00`, `18:00` |
| `MEETING_SLOT_DURATION_MINUTES` | Slot length (default 30) |
| `MEETING_BUFFER_MINUTES` | Gap between consecutive slots (default 0) |
| `MEETING_MIN_NOTICE_MINUTES` | Minimum lead time to book (default 60) |
| `MEETING_MAX_ADVANCE_DAYS` | How far ahead bookings are allowed (default 30) |
| `MEETING_REMINDER_LEAD_MINUTES` | How long before start to send the reminder email (default 60) |
| `EMAIL_*`, `DEFAULT_FROM_EMAIL` | SMTP settings for notification emails |

## Getting a Google OAuth refresh token

Service accounts are intentionally **not** used -- they cannot invite
attendees or generate Meet links without Google Workspace domain-wide
delegation, which most setups don't have. Instead, this integration
authenticates as the admin's own Google account via a refresh token:

1. In [Google Cloud Console](https://console.cloud.google.com/), create a
   project (or reuse one), enable the **Google Calendar API**, and create an
   **OAuth client ID** (type: Desktop app).
2. Run a one-time local script with the admin's Google account to obtain a
   refresh token (requires `pip install google-auth-oauthlib`, a dev-only
   dependency not needed at runtime):

   ```python
   from google_auth_oauthlib.flow import InstalledAppFlow

   flow = InstalledAppFlow.from_client_config(
       {
           "installed": {
               "client_id": "YOUR_CLIENT_ID",
               "client_secret": "YOUR_CLIENT_SECRET",
               "auth_uri": "https://accounts.google.com/o/oauth2/auth",
               "token_uri": "https://oauth2.googleapis.com/token",
               "redirect_uris": ["http://localhost"],
           }
       },
       scopes=["https://www.googleapis.com/auth/calendar"],
   )
   credentials = flow.run_local_server(port=0)
   print("GOOGLE_REFRESH_TOKEN=", credentials.refresh_token)
   ```
3. Sign in as the admin account when the browser opens, approve the
   Calendar scope, then copy the printed refresh token into
   `GOOGLE_REFRESH_TOKEN`. Set `GOOGLE_CLIENT_ID`/`GOOGLE_CLIENT_SECRET` from
   step 1 and `GOOGLE_CALENDAR_ID` to that account's calendar (`primary` is
   fine if it's the same account).

## Running the background workers

```bash
# Worker: processes confirmation/reminder/reschedule/cancellation emails
celery -A core worker -l info

# Beat: dispatches due reminder emails every 5 minutes (see core/celery.py)
celery -A core beat -l info
```

Both require Redis running and reachable at `CELERY_BROKER_URL`.

## Tests

```bash
python manage.py test apps.meeting
```

Google Calendar calls are mocked in every test (`unittest.mock.patch` on
`GoogleCalendarService`), so the suite runs offline with no real credentials.
