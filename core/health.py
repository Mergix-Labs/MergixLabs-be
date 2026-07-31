from django.http import JsonResponse


def health_check(request):
    """Liveness probe for Render's health check -- deliberately does not touch
    the database/Redis/Celery, so a downstream blip doesn't restart the web dyno."""
    return JsonResponse({"status": "ok"})
