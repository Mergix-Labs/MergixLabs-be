import logging
from http.cookies import SimpleCookie
from urllib.parse import parse_qs

from channels.middleware import BaseMiddleware
from channels.db import database_sync_to_async
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.tokens import AccessToken

logger = logging.getLogger("samaira_ai")

User = get_user_model()


@database_sync_to_async
def get_user(user_id):
    try:
        return User.objects.get(id=user_id)
    except User.DoesNotExist:
        return AnonymousUser()


def _extract_token(scope):
    """Return a JWT string from ?token= query param or the access cookie."""
    query_string = scope.get("query_string", b"").decode()
    params = parse_qs(query_string)
    token = params.get("token", [None])[0]
    if token:
        return token

    # Fall back to the simplejwt cookie — the browser sends HttpOnly cookies
    # on WebSocket upgrades even when JS cannot read them.
    cookie_name = getattr(settings, "SIMPLE_JWT", {}).get("AUTH_COOKIE", "access")
    raw_cookie = dict(scope.get("headers", [])).get(b"cookie", b"").decode("latin-1")
    if raw_cookie:
        jar = SimpleCookie()
        jar.load(raw_cookie)
        morsel = jar.get(cookie_name)
        if morsel:
            return morsel.value

    return None


class JWTAuthMiddleware(BaseMiddleware):

    async def __call__(self, scope, receive, send):

        scope["user"] = AnonymousUser()

        try:
            token = _extract_token(scope)
            if token:
                access_token = AccessToken(token)
                user_id = access_token["user_id"]
                user = await get_user(user_id)
                scope["user"] = user
                if not user.is_authenticated:
                    logger.warning("WS auth: user_id=%s not found in DB", user_id)
            else:
                logger.warning("WS auth: no token found in query string or cookie")
        except Exception as exc:
            logger.warning("WS auth failed: %s", exc)
            scope["user"] = AnonymousUser()

        return await super().__call__(scope, receive, send)