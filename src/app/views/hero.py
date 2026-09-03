"""Pydantic view models for the Hero resource."""

from pydantic import Field

from app.views.base import ORMView


class HeroBase(ORMView):
    """Fields shared by every Hero view."""

    name: str = Field(min_length=1, max_length=200)
    superpower: str = Field(min_length=1, max_length=200)


class HeroCreate(HeroBase):
    """Fields accepted when creating a Hero."""


class HeroUpdate(ORMView):
    """Fields accepted when partially updating a Hero -- all optional."""

    name: str | None = Field(default=None, min_length=1, max_length=200)
    superpower: str | None = Field(default=None, min_length=1, max_length=200)


class Hero(HeroBase):
    """A Hero as returned by the API, including its assigned id."""

    id: int
