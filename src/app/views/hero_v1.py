"""Deprecated v1 Hero view (single superpower) and its converters to/from v2."""

from pydantic import Field

from app.views.base import IXDTFDatetime, ORMView
from app.views.hero import Hero, HeroCreate, HeroUpdate


class HeroV1Base(ORMView):
    """Fields shared by every v1 Hero view."""

    name: str = Field(min_length=1, max_length=200)
    superpower: str = Field(min_length=1, max_length=200)


class HeroV1Create(HeroV1Base):
    """Fields accepted when creating a Hero via the deprecated v1 shape."""


class HeroV1Update(ORMView):
    """Fields accepted when partially updating a Hero via the deprecated v1 shape."""

    name: str | None = Field(default=None, min_length=1, max_length=200)
    superpower: str | None = Field(default=None, min_length=1, max_length=200)


class HeroV1(HeroV1Base):
    """A Hero as returned by the deprecated v1 API."""

    id: int
    created_at: IXDTFDatetime
    updated_at: IXDTFDatetime


def hero_to_v1(hero: Hero) -> HeroV1:
    """Convert a current (v2) Hero down to the deprecated v1 shape.

    v1 can only represent one power; the first entry in `powers` is treated
    as the primary power. Lossy but deliberate: v1 clients keep working,
    but never see more than one power even if v2 has several.
    """
    return HeroV1(
        id=hero.id,
        name=hero.name,
        superpower=hero.powers[0],
        created_at=hero.created_at,
        updated_at=hero.updated_at,
    )


def hero_v1_create_to_v2(payload: HeroV1Create) -> HeroCreate:
    """Convert a v1 create payload up to the current (v2) shape."""
    return HeroCreate(name=payload.name, powers=[payload.superpower])


def hero_v1_update_to_v2(payload: HeroV1Update) -> HeroUpdate:
    """Convert a v1 update payload up to the current (v2) shape.

    Only maps `superpower` -> `powers` when it was actually supplied -- an
    unset v1 field must stay unset in v2, not overwrite existing powers
    with a single-element list.
    """
    data = payload.model_dump(exclude_unset=True)
    if "superpower" in data:
        data["powers"] = [data.pop("superpower")]
    return HeroUpdate.model_validate(data)
