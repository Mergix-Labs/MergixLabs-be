# MergixLabs Django Template

## Overview
Django template that will be used by the backend team as a base structure for upcoming projects


## Features
- Enhanced Admin Panel (better version of the default admin panel)
- Django REST Framework setup
- Simple JWT token authentication using DRF
- APIs for login, signup, and token refresh
- Configuration for environment variables
- Deploys to [Render](https://render.com) via `render.yaml` (web + Celery worker + Celery beat + Redis + Postgres)


## Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/MergixLabs/django-template
   cd MergixLabs-django-template
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

## Celery Setup

### Start the Celery Worker
To start the Celery worker, use the following command:

```bash
celery -A core worker --loglevel=info -P eventlet
```

### Why Use Eventlet with Celery?
Eventlet provides greater concurrency compared to the prefork method, allowing you to manage multiple tasks simultaneously without the need for non-blocking code.

On Render, the worker and beat schedule run as their own Background Worker services (`mergixlabs-celery-worker`, `mergixlabs-celery-beat` in `render.yaml`) — they are not started manually.

## Example of Running a Celery Task

You can run a Celery task within a Django view as follows:

```python
from django.http import JsonResponse
from .tasks import myprint  # Ensure to import your task

def run_celery_task(request):
    # 1st method: Using delay
    myprint.delay()  # args can be passed as well, but not objects
    # Syntax: task_name.delay(arg1, arg2, ...)

    # 2nd method: Using apply_async
    myprint.apply_async()  # args can be passed as well, but not objects
    # Syntax: task_name.apply_async(args=[arg1, arg2], kwargs={'key': value}, options={})

    return JsonResponse({'status': 'success'})
```
## Deploying to Render

This project deploys to [Render](https://render.com) as a Docker-based Blueprint (`render.yaml`), replacing the old EC2/SSH/GitHub Actions flow. Render builds directly from GitHub — no SSH keys, no deploy workflow file needed.

**One-time setup:**
1. Push this repo to GitHub (already done if you're reading this on `main`/`staging`).
2. In the Render dashboard: **New > Blueprint**, point it at this repo. Render reads `render.yaml` and provisions:
   - `mergixlabs-be` (web, Gunicorn/WSGI, `Dockerfile`, Persistent Disk mounted at `/app/media`)
   - `mergixlabs-celery-worker` and `mergixlabs-celery-beat` (Background Workers, same image, different `dockerCommand`)
   - `mergixlabs-redis` (Celery broker/result backend)
   - `mergixlabs-db` (managed Postgres, wired to `DATABASE_URL` automatically)
3. Fill in the env vars marked `sync: false` in `render.yaml` (secrets: email/Mailjet/Google/Pinecone/Gemini credentials, `ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS`, `CSRF_TRUSTED_ORIGINS`, `FRONTEND_URL`, `SENTRY_DSN`) in the Render dashboard for each service. See `.env.example` for what every variable does.
4. Deploy. Render's build → pre-deploy → start pipeline for the web service is: build the Docker image → run `preDeployCommand` (`migrate`) → start the container (`.scripts/entrypoint.sh`: `collectstatic` then `gunicorn`) → poll `/health/` until it responds before routing traffic.

**Ongoing deploys:** every push to the branch Render is tracking triggers `autoDeploy` automatically — no manual step.

**Known limitation:** media (`apps.fintech_ai` document uploads) lives on a Persistent Disk attached only to the web service. Render disks can't be shared across services, so the Celery worker's `ingest_document_task` cannot read a file the web service just wrote. This was an explicit, accepted tradeoff when picking a disk over S3 for media — if that pipeline needs to work in production, move `STORAGES["default"]` back to `storages.backends.s3boto3.S3Boto3Storage` (`django-storages`/`boto3`, both removed from `requirements.txt`, would need re-adding) so both services read/write the same object store.

**Local development:** `docker compose up --build` (see `docker-compose.yml`) runs Postgres, Redis, web, worker, and beat together for local parity. Render does not read this file at all — it's purely a local convenience.

## APIs
This template includes APIs for:
- **Login**: Authenticate users and issue JWT tokens.
- **Signup**: Register new users.
- **Refresh Token**: Obtain new tokens using refresh tokens.
- **Meeting Scheduling** (`/api/v1/meetings/`): Google Calendar-backed slot lookup, booking, reschedule, and cancellation. See [apps/meeting/README.md](apps/meeting/README.md) for setup and API details.

## Environment Variables
Copy `.env.example` to `.env` and fill in the values for local development. `.env.example` documents every environment variable the project reads, grouped by area (Django core, database, JWT/cookies, email, Mailjet, Google Calendar, meeting scheduling, Pinecone/Gemini, Celery/Redis, Sentry). On Render, the same variables are set per-service via `render.yaml`.

## Media Storage
User-uploaded files (e.g. `apps.fintech_ai` knowledge documents) are stored on local disk via `MEDIA_ROOT`/`MEDIA_URL`. In production on Render this is a Persistent Disk mounted at `/app/media` on the web service only — see the "Deploying to Render" section above for the resulting limitation with the Celery-based document ingestion pipeline.

## Contributing
Feel free to contribute to this project by forking the repository and submitting a pull request.


## Contact
For any questions or feedback, please reach out to [aman@mergixlabs-.com].
