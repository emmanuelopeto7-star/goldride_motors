"""Turning a pasted video link into something an iframe can use.

Sellers paste whatever the share button gave them - a watch URL, a youtu.be
short link, a Vimeo page, usually with tracking parameters attached. None of
those render in an embed. Rather than ask staff to hand-convert them, the link
is parsed once here and the player URL is derived on the way out.

Only YouTube and Vimeo are accepted. An arbitrary URL in an iframe on a page
that also carries a sign-in session is not a feature worth having.
"""

import re
from urllib.parse import parse_qs, urlparse

from django.core.exceptions import ValidationError

YOUTUBE_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be"}
VIMEO_HOSTS = {"vimeo.com", "www.vimeo.com", "player.vimeo.com"}

# Conservative: YouTube ids are 11 characters of an alphabet that has never
# widened, Vimeo ids are numeric. Anything else is a malformed paste.
YOUTUBE_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")
VIMEO_ID = re.compile(r"^\d+$")


def parse_video_url(url):
    """Return (provider, video_id), or (None, None) if this is not a video we
    can embed. Never raises - callers decide whether that is an error."""
    if not url:
        return None, None

    parts = urlparse(url.strip())
    host = parts.netloc.lower()
    segments = [segment for segment in parts.path.split("/") if segment]

    if host in YOUTUBE_HOSTS:
        if host == "youtu.be":
            candidate = segments[0] if segments else ""
        elif segments and segments[0] in ("embed", "shorts", "v"):
            candidate = segments[1] if len(segments) > 1 else ""
        else:
            candidate = parse_qs(parts.query).get("v", [""])[0]
        if YOUTUBE_ID.match(candidate):
            return "youtube", candidate
        return None, None

    if host in VIMEO_HOSTS:
        # player.vimeo.com/video/123 and vimeo.com/123 both end in the id.
        candidate = segments[-1] if segments else ""
        if VIMEO_ID.match(candidate):
            return "vimeo", candidate
        return None, None

    return None, None


def embed_url(url):
    """The player URL for a link, or "" when there is nothing to play."""
    provider, video_id = parse_video_url(url)
    if provider == "youtube":
        return f"https://www.youtube.com/embed/{video_id}"
    if provider == "vimeo":
        return f"https://player.vimeo.com/video/{video_id}"
    return ""


def validate_video_url(value):
    """Model-level guard, so a bad link is refused at the point it is entered
    rather than rendering as an empty box on the detail page."""
    if not value:
        return
    provider, _ = parse_video_url(value)
    if provider is None:
        raise ValidationError(
            "Paste a YouTube or Vimeo link - for example "
            "https://youtu.be/dQw4w9WgXcQ or https://vimeo.com/123456789."
        )
