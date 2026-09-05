"""Pydantic view for the shared revision-history log (app.models.revision.Revision)."""

from typing import Any

from app.views.base import IXDTFDatetime, ORMView


class RevisionView(ORMView):
    """One revision-log entry, as returned by a resource's `GET <prefix>/revisions` route."""

    id: int
    resource: str
    record_id: int
    action: str
    snapshot: dict[str, Any]
    actor: str
    created_at: IXDTFDatetime
