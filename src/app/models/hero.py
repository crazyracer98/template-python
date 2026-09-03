"""SQLAlchemy model for the Hero resource -- the example CRUD app's data."""

from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import IdentifiedBase


class Hero(IdentifiedBase):
    """A hero row in the `heroes` table."""

    __tablename__ = "heroes"

    name: Mapped[str] = mapped_column(nullable=False)
    superpower: Mapped[str] = mapped_column(nullable=False)
