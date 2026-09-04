"""RFC 8594 Sunset header support, paired with the (draft) Deprecation header.

A reusable FastAPI dependency any route can opt into to advertise that it will
stop being available at a given time -- see app.controllers.protected for the
applied example.
"""

from collections.abc import Callable
from datetime import datetime
from email.utils import format_datetime

from fastapi import Response


def sunset(at: datetime, *, link: str | None = None) -> Callable[[Response], None]:
    """Build a dependency that sets Sunset/Deprecation (and optionally Link) headers.

    `at` is rendered as an RFC 7231 HTTP-date via the stdlib, per RFC 8594's Sunset
    header format (an HTTP-date, not an IXDTF/ISO 8601 timestamp).
    """

    def _dependency(response: Response) -> None:
        response.headers["Deprecation"] = "true"
        response.headers["Sunset"] = format_datetime(at, usegmt=True)
        if link is not None:
            response.headers["Link"] = f'<{link}>; rel="sunset"'

    return _dependency
