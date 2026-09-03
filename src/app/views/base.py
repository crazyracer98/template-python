"""Common base for views that convert to and from a SQLAlchemy ORM instance."""

from pydantic import BaseModel, ConfigDict


class ORMView(BaseModel):
    """Base for API-facing Pydantic models constructible from an ORM model instance.

    `from_attributes=True` is what lets app.crud.base.CRUDInterface build one of these
    straight from a SQLAlchemy model instance via `model_validate`, instead of a dict.
    """

    model_config = ConfigDict(from_attributes=True)
