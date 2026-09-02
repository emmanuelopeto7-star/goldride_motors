"""Authenticating a websocket.

A websocket cannot carry an Authorization header from the browser - the API
simply has no way to set one. The two ways left are the query string and the
`Sec-WebSocket-Protocol` header, and this prefers the header: query strings
end up in proxy logs, and a DRF token never expires, so one logged is one
leaked for good.

The query string is still accepted, because tooling and tests reach for it
first and refusing would cost more than it protects. It is the fallback, not
the route the frontend takes.
"""

from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from django.contrib.auth.models import AnonymousUser
from rest_framework.authtoken.models import Token


@database_sync_to_async
def _user_for(key):
    try:
        return Token.objects.select_related("user").get(key=key).user
    except Token.DoesNotExist:
        return AnonymousUser()


def token_from_scope(scope):
    """The header first, the query string second."""
    for name, value in scope.get("headers", []):
        if name == b"sec-websocket-protocol":
            offered = [part.strip() for part in value.decode().split(",")]
            if len(offered) >= 2 and offered[0] == "token":
                return offered[1], True

    query = parse_qs(scope.get("query_string", b"").decode())
    key = (query.get("token") or [None])[0]
    return key, False


class TokenAuthMiddleware(BaseMiddleware):
    async def __call__(self, scope, receive, send):
        key, via_header = token_from_scope(scope)
        scope["user"] = await _user_for(key) if key else AnonymousUser()
        # The consumer echoes this back on accept: a browser that offered a
        # subprotocol expects one of its own back.
        scope["token_subprotocol"] = via_header
        return await super().__call__(scope, receive, send)
