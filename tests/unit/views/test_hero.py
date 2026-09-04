"""Unit test: Hero views validate input and convert from an ORM-shaped object."""

from dataclasses import dataclass
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.views.hero import Hero, HeroCreate, HeroUpdate

_NOW = datetime(2026, 1, 1, tzinfo=UTC)


@dataclass
class _FakeORMHero:
    """Stand-in for a SQLAlchemy Hero instance -- just needs matching attributes."""

    id: int
    name: str
    powers: list[str]
    created_at: datetime
    updated_at: datetime


def test_hero_create_accepts_valid_fields() -> None:
    """HeroCreate accepts a name and powers within the length bounds."""
    hero = HeroCreate(name="Spider-Man", powers=["Wall-crawling"])
    assert hero.name == "Spider-Man"


def test_hero_create_rejects_empty_name() -> None:
    """HeroCreate rejects an empty name."""
    with pytest.raises(ValidationError):
        HeroCreate(name="", powers=["Flight"])


def test_hero_create_rejects_empty_powers() -> None:
    """HeroCreate rejects an empty powers list."""
    with pytest.raises(ValidationError):
        HeroCreate(name="Nobody", powers=[])


def test_hero_update_allows_all_fields_omitted() -> None:
    """HeroUpdate accepts an empty payload -- every field is optional."""
    update = HeroUpdate()
    assert update.name is None
    assert update.powers is None


def test_hero_converts_from_orm_instance() -> None:
    """Hero.model_validate builds a view straight from an ORM-shaped object."""
    orm_hero = _FakeORMHero(
        id=1, name="Batman", powers=["Detective skills"], created_at=_NOW, updated_at=_NOW
    )
    hero = Hero.model_validate(orm_hero)
    assert hero.id == 1
    assert hero.name == "Batman"


def test_hero_serializes_timestamps_as_ixdtf() -> None:
    """Hero's created_at/updated_at serialize as RFC 9557 IXDTF strings."""
    hero = Hero(id=1, name="Batman", powers=["Detective skills"], created_at=_NOW, updated_at=_NOW)
    assert hero.model_dump(mode="json")["created_at"] == "2026-01-01T00:00:00Z[UTC]"
