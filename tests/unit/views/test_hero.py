"""Unit test: Hero views validate input and convert from an ORM-shaped object."""

from dataclasses import dataclass

import pytest
from pydantic import ValidationError

from app.views.hero import Hero, HeroCreate, HeroUpdate


@dataclass
class _FakeORMHero:
    """Stand-in for a SQLAlchemy Hero instance -- just needs matching attributes."""

    id: int
    name: str
    superpower: str


def test_hero_create_accepts_valid_fields() -> None:
    """HeroCreate accepts a name and superpower within the length bounds."""
    hero = HeroCreate(name="Spider-Man", superpower="Wall-crawling")
    assert hero.name == "Spider-Man"


def test_hero_create_rejects_empty_name() -> None:
    """HeroCreate rejects an empty name."""
    with pytest.raises(ValidationError):
        HeroCreate(name="", superpower="Flight")


def test_hero_update_allows_all_fields_omitted() -> None:
    """HeroUpdate accepts an empty payload -- every field is optional."""
    update = HeroUpdate()
    assert update.name is None
    assert update.superpower is None


def test_hero_converts_from_orm_instance() -> None:
    """Hero.model_validate builds a view straight from an ORM-shaped object."""
    orm_hero = _FakeORMHero(id=1, name="Batman", superpower="Detective skills")
    hero = Hero.model_validate(orm_hero)
    assert hero == Hero(id=1, name="Batman", superpower="Detective skills")
