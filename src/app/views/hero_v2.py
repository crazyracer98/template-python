"""Pydantic view models for the current (v2) Hero resource."""

from typing import Annotated

from pydantic import Field

from app.views.base import IXDTFDatetime, ORMView

Power = Annotated[str, Field(min_length=1, max_length=200)]


class HeroV2Base(ORMView):
    """Fields shared by every Hero view."""

    name: str = Field(min_length=1, max_length=200)
    powers: Annotated[list[Power], Field(min_length=1)]


class HeroV2Create(HeroV2Base):
    """Fields accepted when creating a Hero."""


class HeroV2Update(ORMView):
    """Fields accepted when partially updating a Hero -- all optional."""

    name: str | None = Field(default=None, min_length=1, max_length=200)
    powers: Annotated[list[Power], Field(min_length=1)] | None = None


class HeroV2(HeroV2Base):
    """A Hero as returned by the API, including its assigned id and owner."""

    id: int
    owner_id: str
    created_at: IXDTFDatetime
    updated_at: IXDTFDatetime
