"""SQLAlchemy model for the Hero resource -- the example CRUD app's data."""

from sqlalchemy import String
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import IdentifiedBase
from app.models.mixins import Archivable, Draftable, Lockable, Schedulable


class Hero(IdentifiedBase, Archivable, Draftable, Schedulable, Lockable):
    """A hero row in the `heroes` table, owned by the caller (`owner_id`) who created it.

    Worked example of every record-lifecycle mixin (see app.models.mixins) --
    `name`/`powers` are nullable (rather than the original `nullable=False`) so a
    draft can be created with either or both omitted; see app/README.md's "Example
    CRUD resource: Hero".
    """

    __tablename__ = "heroes"

    name: Mapped[str | None] = mapped_column(nullable=True)
    powers: Mapped[list[str] | None] = mapped_column(postgresql.ARRAY(String), nullable=True)
    owner_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
