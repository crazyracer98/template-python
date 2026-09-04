# Evolve Hero to support multiple powers (`powers: list[str]`)

## Status

Draft

## Goal

Evolve Hero's *current* shape from a single `superpower: str` to
`powers: list[str]` (one hero, multiple powers) at the existing unversioned
`/heroes` paths, and extend the two generic format-rendering modules
(`xml_codec.py`, `web_components.py`) to support a flat list-of-scalars
field so JSON, XML, and web-component CRUD stay in parity as the model
gains this shape.

This is step 1 of 2 toward introducing API/model versioning for Hero (see
`2026-09-hero-api-versioning.md`), but is deliberately self-contained and
independently mergeable: it does **not** touch versioning, deprecation, or
path prefixes. Land this first, fully green, before starting the versioning
plan — that plan wraps *this* shape as `/v2` and adds a `/v1` compatibility
layer that converts back down to the old single-`superpower` shape.

## Approach

### Data model

- `src/app/models/hero.py`: replace
  ```python
  superpower: Mapped[str] = mapped_column(nullable=False)
  ```
  with
  ```python
  powers: Mapped[list[str]] = mapped_column(postgresql.ARRAY(String), nullable=False)
  ```
  (`from sqlalchemy.dialects.postgresql import ARRAY`, `from sqlalchemy import String`
  — check existing imports in the file first, `Mapped`/`mapped_column` are
  already imported from `sqlalchemy.orm`).
- `src/app/repositories/memory.py`'s `InMemoryRepository` needs **no**
  change — it's dict-backed with no column typing, generic over `ModelT`.
- New Alembic revision, chained after the current head (`7dc8146fcf6c`).
  Generate the scaffold with:
  ```
  uv run alembic revision --autogenerate -m "convert hero superpower to powers list"
  ```
  Autogenerate will detect the column add/drop but **not** the data
  backfill — hand-edit the generated file to this shape:
  ```python
  def upgrade() -> None:
      op.add_column("heroes", sa.Column("powers", postgresql.ARRAY(sa.String()), nullable=True))
      op.execute("UPDATE heroes SET powers = ARRAY[superpower]")
      op.alter_column("heroes", "powers", nullable=False)
      op.drop_column("heroes", "superpower")

  def downgrade() -> None:
      op.add_column("heroes", sa.Column("superpower", sa.String(), nullable=True))
      op.execute("UPDATE heroes SET superpower = powers[1]")
      op.alter_column("heroes", "superpower", nullable=False)
      op.drop_column("heroes", "powers")
  ```
  Follow the existing `7dc8146fcf6c` revision's style for imports/structure.

### Views

- `src/app/views/hero.py`: in `HeroBase`, `HeroCreate`, and `Hero`, replace
  `superpower: str = Field(min_length=1, max_length=200)` with
  `powers: list[str] = Field(min_length=1)` (non-empty list; add an
  element-level length constraint too if it reads cleanly, e.g.
  `Annotated[list[Annotated[str, Field(min_length=1, max_length=200)]], Field(min_length=1)]`
  — use judgement on verbosity vs. today's existing constraint style). In
  `HeroUpdate`, `powers: list[str] | None = Field(default=None, min_length=1)`.

### XML codec — generalize to flat lists of scalars

`src/app/xml_codec.py` currently documents and only supports scalar fields.
Extend both directions:

- `to_xml`: for each field, if the dumped value is a `list`, emit one child
  element per item sharing the tag name, instead of stringifying the whole
  list:
  ```python
  def to_xml(model: BaseModel, root_tag: str) -> str:
      """Render a flat Pydantic model as XML: one child element per scalar
      field, one repeated child element per item of a list field."""
      root = Element(root_tag)
      for field, value in model.model_dump(mode="json").items():
          items = value if isinstance(value, list) else [value]
          for item in items:
              child = SubElement(root, field)
              child.text = str(item)
      return tostring(root, encoding="unicode")
  ```
- `from_xml`: group repeated child elements by tag before validating, and
  use the target schema's field annotation to decide whether a tag should
  become a list or collapse to a scalar (needed so a list field with
  exactly one XML element still validates as `list[str]`, not `str`):
  ```python
  from typing import get_origin

  def from_xml[ModelT: BaseModel](body: bytes, schema: type[ModelT]) -> ModelT:
      """Parse an XML document (repeated elements group into a list field,
      single elements stay scalar) into the given model."""
      root = fromstring(body)  # noqa: S314
      grouped: dict[str, list[str | None]] = {}
      for child in root:
          grouped.setdefault(child.tag, []).append(child.text)
      data: dict[str, str | None | list[str | None]] = {}
      for tag, values in grouped.items():
          field = schema.model_fields.get(tag)
          is_list_field = field is not None and get_origin(field.annotation) is list
          data[tag] = values if is_list_field else values[-1]
      return schema.model_validate(data)
  ```
- Update the module docstring: fields may be scalars *or* flat lists of
  scalars — nested models are still unsupported.

### Web components — generalize `render_crud_component_js`

- `src/app/web_components.py`: `render_crud_form` needs **no** change — it
  just renders one `<input>` per field name; comma-separated-string→list
  parsing for a list field belongs in the resource-specific route handler
  (see `heroes_web.py` below), not in this generic template function.
- `render_crud_component_js` gains an optional parameter:
  ```python
  def render_crud_component_js(
      resource: str, api_base: str, fields: Sequence[str], *, list_fields: Sequence[str] = ()
  ) -> str:
  ```
  Use it in the generated JS so:
  - the `{Resource}List` table `.join(", ")`s a `list_fields` value instead
    of relying on default array-to-string coercion for display, and
  - the `{Resource}Form` submit handler splits a `list_fields` entry's raw
    form value on `,` (trimming whitespace) into an array before
    `JSON.stringify`-ing the payload.
  Keep both functions fully generic (parameterized, not Hero-specific) —
  this mirrors how `fields` is already just a parameter, not a Hero-only
  concept.

### Controller wiring

- `src/app/controllers/heroes_web.py`: `_FIELDS = ("name", "powers")`; pass
  `list_fields=("powers",)` into the `render_crud_component_js` call.
  `submit_hero_form`'s `Form()`-bound handler currently takes
  `superpower: Annotated[str, Form()]` directly — change it to accept the
  raw comma-separated string and split it into a list before constructing
  `HeroCreate(name=name, powers=[p.strip() for p in powers.split(",") if p.strip()])`.
- `src/app/controllers/heroes_xml.py`: no route-body changes needed — it
  already goes through `to_xml`/`from_xml` generically; only its imported
  `HeroCreate`/`HeroUpdate` view shapes change (automatically, from the
  views edit above).
- `src/app/controllers/heroes.py`: no route-body changes needed (JSON
  serialization is Pydantic's own, handles `list[str]` natively) — only
  its imported view shapes change.

### Tests

- Update `superpower` → `powers` (and single string → list) across:
  `tests/unit/controllers/test_heroes.py`,
  `tests/unit/controllers/test_heroes_xml.py`,
  `tests/unit/controllers/test_heroes_web.py`,
  `tests/integration/controllers/test_heroes.py`,
  `tests/e2e/test_heroes_e2e.py`, `tests/e2e/test_heroes_xml_e2e.py`,
  `tests/e2e/test_heroes_web_e2e.py`.
- Extend `tests/unit/test_xml_codec.py` with: a model with a `list[str]`
  field round-trips through `to_xml`/`from_xml`; a list field with exactly
  one element still round-trips as a list (not collapsed to scalar); mixed
  scalar + list fields on the same model.
- Extend `tests/unit/test_web_components.py` with: `render_crud_component_js`
  called with `list_fields` produces JS containing the split/join logic
  (string-contains assertions are fine, this module has no JS test runner).

## Verification

Run and show actual output for:
```
uv run ruff check
uv run ruff format --check
uv run mypy --strict
uv run lint-imports
uv run pytest
uv run pytest tests/e2e
```
Manually exercise `/heroes/form` in a browser (or via the Playwright suite)
to confirm the comma-separated `powers` input round-trips correctly through
create → list display.

## Open questions

None currently — if the element-level `Field` constraint verbosity for
`powers: list[str]` turns out to read poorly against this repo's existing
style, simplify it and note the deviation here before merging.
