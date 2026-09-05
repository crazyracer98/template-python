"""SQLAlchemy model for the Hero resource -- the example CRUD app's data."""

from sqlalchemy import String
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import IdentifiedBase


class Hero(IdentifiedBase):
    """A hero row in the `heroes` table, owned by the caller (`owner_id`) who created it."""

    __tablename__ = "heroes"

    name: Mapped[str] = mapped_column(nullable=False)
    powers: Mapped[list[str]] = mapped_column(postgresql.ARRAY(String), nullable=False)
    owner_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
