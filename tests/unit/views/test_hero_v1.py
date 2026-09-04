"""Unit test: the deprecated v1 Hero view and its converters to/from v2."""

from datetime import UTC, datetime

from app.views.hero import Hero, HeroUpdate
from app.views.hero_v1 import (
    HeroV1Create,
    HeroV1Update,
    hero_to_v1,
    hero_v1_create_to_v2,
    hero_v1_update_to_v2,
)

_NOW = datetime(2026, 1, 1, tzinfo=UTC)


def test_hero_to_v1_uses_only_the_first_power() -> None:
    """hero_to_v1 on a multi-power Hero returns only the first power as `superpower`."""
    hero = Hero(
        id=1,
        name="Storm",
        powers=["Weather control", "Flight"],
        created_at=_NOW,
        updated_at=_NOW,
    )
    v1 = hero_to_v1(hero)
    assert v1.superpower == "Weather control"


def test_hero_v1_create_to_v2_wraps_superpower_in_a_list() -> None:
    """hero_v1_create_to_v2 wraps the single `superpower` into a one-element `powers` list."""
    v2 = hero_v1_create_to_v2(HeroV1Create(name="Batman", superpower="Detective skills"))
    assert v2.name == "Batman"
    assert v2.powers == ["Detective skills"]


def test_hero_v1_update_to_v2_maps_superpower_when_set() -> None:
    """hero_v1_update_to_v2 maps a supplied `superpower` to a one-element `powers` list."""
    v2 = hero_v1_update_to_v2(HeroV1Update(superpower="Web-slinging"))
    assert v2 == HeroUpdate(powers=["Web-slinging"])


def test_hero_v1_update_to_v2_leaves_powers_unset_when_superpower_omitted() -> None:
    """An unset v1 `superpower` stays unset in v2, not an overwrite with an empty/None value."""
    v2 = hero_v1_update_to_v2(HeroV1Update(name="Batman"))
    assert v2.model_dump(exclude_unset=True) == {"name": "Batman"}
