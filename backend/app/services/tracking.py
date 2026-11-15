"""Tracking pixel helpers.

Note: many mail clients (Apple Mail, Gmail's image proxy) pre-fetch images, so an
"open" can be a false positive. Consider telling recipients you use read receipts.
"""
from ..config import settings
from ..models import TrackedEmail

# 1x1 transparent GIF
PIXEL_GIF = (b"GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff!\xf9\x04\x01\x00\x00\x00\x00,"
             b"\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;")


def pixel_url(token: str) -> str:
    return f"{settings.public_base_url}/api/track/{token}.gif"


def html_snippet(token: str) -> str:
    return f'<img src="{pixel_url(token)}" width="1" height="1" alt="" style="display:none" />'


def to_out(t: TrackedEmail) -> dict:
    return {
        "id": t.id, "token": t.token, "job_id": t.job_id, "recipient": t.recipient,
        "open_count": t.open_count, "first_opened_at": t.first_opened_at,
        "last_opened_at": t.last_opened_at,
        "pixel_url": pixel_url(t.token), "html_snippet": html_snippet(t.token),
    }
