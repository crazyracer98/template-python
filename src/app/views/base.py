"""Common base for views that convert to and from a SQLAlchemy ORM instance."""

from datetime import UTC, datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, PlainSerializer


class ORMView(BaseModel):
    """Base for API-facing Pydantic models constructible from an ORM model instance.

    `from_attributes=True` is what lets app.interfaces.base.CRUDInterface build one of these
    straight from a SQLAlchemy model instance via `model_validate`, instead of a dict.
    """

    model_config = ConfigDict(from_attributes=True)


def _to_ixdtf(value: datetime) -> str:
    """Format a datetime as an RFC 9557 IXDTF string with a bracketed zone suffix.

    Every timestamp this app stores is UTC (see app.models.base.IdentifiedBase), so
    the suffix is always the fixed `[UTC]` zone name rather than a per-value lookup.
    """
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z") + "[UTC]"


IXDTFDatetime = Annotated[datetime, PlainSerializer(_to_ixdtf, return_type=str)]
