"""ASGI entry point: HTTP and websockets through one application.

Django is loaded before anything else imports a model - the routing module
reaches consumers, which reach models, and importing those before the app
registry is ready fails in a way that reads like a circular import.
"""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'goldride_project.settings')

django_asgi_app = get_asgi_application()

from channels.routing import ProtocolTypeRouter, URLRouter  # noqa: E402
from channels.security.websocket import AllowedHostsOriginValidator  # noqa: E402

from chat.auth import TokenAuthMiddleware  # noqa: E402
from chat.routing import websocket_urlpatterns  # noqa: E402

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    # Origin checking is not optional. A websocket is exempt from the
    # same-origin policy, so without this any page on the internet could open
    # a socket to us carrying the visitor's session and read their
    # conversation. It reuses ALLOWED_HOSTS, which is already correct.
    "websocket": AllowedHostsOriginValidator(
        TokenAuthMiddleware(URLRouter(websocket_urlpatterns))
    ),
})
