"""Unit test: the sunset() dependency sets Sunset/Deprecation/Link headers."""

from datetime import UTC, datetime

from fastapi import Response

from app.http_headers import sunset


def test_sunset_sets_deprecation_and_sunset_headers() -> None:
    """sunset() without a link sets Deprecation/Sunset but no Link header."""
    response = Response()
    sunset(datetime(2027, 1, 1, tzinfo=UTC))(response)
    assert response.headers["Deprecation"] == "true"
    assert response.headers["Sunset"] == "Fri, 01 Jan 2027 00:00:00 GMT"
    assert "Link" not in response.headers


def test_sunset_sets_link_header_when_given() -> None:
    """sunset(..., link=...) also sets a Link header with rel="sunset"."""
    response = Response()
    sunset(datetime(2027, 1, 1, tzinfo=UTC), link="/heroes")(response)
    assert response.headers["Link"] == '</heroes>; rel="sunset"'
