"""SQLAlchemy model for the shared, cross-resource revision history log.

One table for every resource that opts into revision history (keyed by
`resource`+`record_id`), not a table per resource -- matches Archivable/
Draftable/etc.'s "purely additive, nothing resource-specific" shape. See
app.interfaces.base.RevisionSink for the opt-in CRUDInterface hook that writes
into this table.
"""

from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import IdentifiedBase


class Revision(IdentifiedBase):
    """One append-only log entry: who changed what record of what resource, and how."""

    __tablename__ = "revisions"

    resource: Mapped[str] = mapped_column(index=True)
    record_id: Mapped[int] = mapped_column(index=True)
    action: Mapped[str]
    snapshot: Mapped[dict[str, object]] = mapped_column(postgresql.JSONB)
    actor: Mapped[str]
