"""Unit test: build_json_router/build_xml_router/build_web_router's generic route wiring.

Exercises the three router factories directly against a minimal fake schema/model
pair, not tied to Hero -- mirrors how tests/unit/crud/test_compat.py tests
CompatCRUD generically.
"""

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Annotated, Any

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel, ConfigDict

from app.controllers import crud_actions
from app.controllers.crud_router import build_json_router, build_web_router, build_xml_router
from app.crud.base import CRUDInterface
from app.repositories.filtering import FilterClause, FilterOp, SortClause


@dataclass
class _GadgetRecord:
    """Stand-in for a persisted record, independent of any ORM."""

    id: int
    name: str
    tags: list[str]


class _Gadget(BaseModel):
    """View returned by the CRUD interface."""

    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    tags: list[str]


class _GadgetCreate(BaseModel):
    """View accepted when creating a gadget."""

    name: str
    tags: list[str]


class _GadgetUpdate(BaseModel):
    """View accepted when updating a gadget -- all optional."""

    name: str | None = None
    tags: list[str] | None = None


def _matches(record: _GadgetRecord, clause: FilterClause) -> bool:
    value = getattr(record, clause.field)
    if clause.op is FilterOp.EQ:
        return bool(value == clause.value)
    if clause.op is FilterOp.ICONTAINS:
        return str(clause.value).casefold() in str(value).casefold()
    if clause.op is FilterOp.IN:
        return value in clause.value
    raise NotImplementedError(clause.op)


class _FakeGadgetRepository:
    """In-memory Repository implementation, keyed by id."""

    def __init__(self) -> None:
        """Start with no records and the first id to hand out."""
        self._records: dict[int, _GadgetRecord] = {}
        self._next_id = 1

    def _matching(self, filters: Sequence[FilterClause]) -> list[_GadgetRecord]:
        return [r for r in self._records.values() if all(_matches(r, c) for c in filters)]

    async def get(self, record_id: int) -> _GadgetRecord | None:
        """Return the record with the given id, or None if it doesn't exist."""
        return self._records.get(record_id)

    async def list(
        self,
        *,
        skip: int = 0,
        limit: int = 100,
        filters: Sequence[FilterClause] = (),
        sort: Sequence[SortClause] = (),
    ) -> list[_GadgetRecord]:
        """Return up to `limit` matching records, skipping the first `skip`."""
        matching = self._matching(filters)
        for clause in reversed(sort):
            matching = sorted(
                matching, key=lambda r: getattr(r, clause.field), reverse=clause.descending
            )
        return matching[skip : skip + limit]

    async def count(self, *, filters: Sequence[FilterClause] = ()) -> int:
        """Return how many records match the given filters."""
        return len(self._matching(filters))

    async def create(self, data: dict[str, Any]) -> _GadgetRecord:
        """Create and return a new record from the given field values."""
        record = _GadgetRecord(id=self._next_id, **data)
        self._records[self._next_id] = record
        self._next_id += 1
        return record

    async def update(self, record_id: int, data: dict[str, Any]) -> _GadgetRecord | None:
        """Update the record with the given id and return it, or None if it doesn't exist."""
        record = self._records.get(record_id)
        if record is None:
            return None
        for field, value in data.items():
            setattr(record, field, value)
        return record

    async def delete(self, record_id: int) -> bool:
        """Delete the record with the given id; return whether it existed."""
        return self._records.pop(record_id, None) is not None

    async def update_many(
        self, *, filters: Sequence[FilterClause], data: dict[str, Any]
    ) -> Sequence[_GadgetRecord]:
        """Apply the given field values to every record matching the filters; return them."""
        matching = self._matching(filters)
        for record in matching:
            for field, value in data.items():
                setattr(record, field, value)
        return matching

    async def delete_many(self, *, filters: Sequence[FilterClause]) -> Sequence[_GadgetRecord]:
        """Delete every record matching the filters; return the records that were deleted."""
        matching = self._matching(filters)
        for record in matching:
            del self._records[record.id]
        return matching


def get_gadget_crud() -> CRUDInterface[_Gadget, _GadgetRecord]:
    """Build a CRUD interface for Gadget (always overridden per test, never called as-is)."""
    return CRUDInterface(schema=_Gadget, repository=_FakeGadgetRepository())


GadgetCRUD = Annotated[CRUDInterface[_Gadget, _GadgetRecord], Depends(get_gadget_crud)]

# No RBAC of its own to exercise here (see tests/unit/controllers/test_heroes.py for that) --
# a single always-succeeding dependency stands in for read/write/delete roles alike.
NoAuth = Depends(lambda: None)

app = FastAPI()
app.include_router(
    build_json_router(
        prefix="/gadgets",
        tags=["gadgets"],
        resource_label="Gadget",
        schema=_Gadget,
        create_schema=_GadgetCreate,
        update_schema=_GadgetUpdate,
        crud_dependency=GadgetCRUD,
        read_roles=NoAuth,
        write_roles=NoAuth,
        delete_roles=NoAuth,
    )
)
app.include_router(
    build_xml_router(
        prefix="/gadgets/xml",
        tags=["gadgets"],
        resource_label="Gadget",
        item_tag="gadget",
        list_tag="gadgets",
        schema=_Gadget,
        create_schema=_GadgetCreate,
        update_schema=_GadgetUpdate,
        crud_dependency=GadgetCRUD,
        read_roles=NoAuth,
        write_roles=NoAuth,
        delete_roles=NoAuth,
    )
)
app.include_router(
    build_web_router(
        prefix="/gadgets",
        tags=["gadgets"],
        resource="gadget",
        api_base="/gadgets",
        fields=("name", "tags"),
        create_schema=_GadgetCreate,
        crud_dependency=GadgetCRUD,
        read_roles=NoAuth,
        write_roles=NoAuth,
    )
)

client = TestClient(app)


def test_json_router_crud_lifecycle() -> None:
    """Create, list, get, update, and delete a record through the generated JSON routes."""
    # One repository instance shared across every request in this test -- FastAPI
    # calls the override afresh per request, so a per-call repository would silently
    # discard state between requests.
    repository = _FakeGadgetRepository()
    app.dependency_overrides[get_gadget_crud] = lambda: CRUDInterface(
        schema=_Gadget, repository=repository
    )
    try:
        create_response = client.post("/gadgets", json={"name": "Widget", "tags": ["a"]})
        assert create_response.status_code == 201
        gadget_id = create_response.json()["id"]

        list_response = client.get("/gadgets")
        assert list_response.status_code == 200
        assert len(list_response.json()) == 1

        get_response = client.get("/gadgets", params={"id": gadget_id})
        assert get_response.status_code == 200
        assert get_response.json()["name"] == "Widget"

        update_response = client.patch("/gadgets", params={"id": gadget_id}, json={"tags": ["b"]})
        assert update_response.status_code == 200
        assert update_response.json()["tags"] == ["b"]

        delete_response = client.delete("/gadgets", params={"id": gadget_id})
        assert delete_response.status_code == 204

        missing_response = client.get("/gadgets", params={"id": gadget_id})
        assert missing_response.status_code == 404
    finally:
        del app.dependency_overrides[get_gadget_crud]


def test_json_router_get_missing_returns_404() -> None:
    """GET /gadgets?id= for a nonexistent id returns 404."""
    app.dependency_overrides[get_gadget_crud] = lambda: CRUDInterface(
        schema=_Gadget, repository=_FakeGadgetRepository()
    )
    try:
        response = client.get("/gadgets", params={"id": 999})
    finally:
        del app.dependency_overrides[get_gadget_crud]
    assert response.status_code == 404


def test_json_router_update_missing_returns_404() -> None:
    """PATCH /gadgets?id= for a nonexistent id returns 404."""
    app.dependency_overrides[get_gadget_crud] = lambda: CRUDInterface(
        schema=_Gadget, repository=_FakeGadgetRepository()
    )
    try:
        response = client.patch("/gadgets", params={"id": 999}, json={"name": "Nobody"})
    finally:
        del app.dependency_overrides[get_gadget_crud]
    assert response.status_code == 404


def test_json_router_delete_missing_returns_404() -> None:
    """DELETE /gadgets?id= for a nonexistent id returns 404."""
    app.dependency_overrides[get_gadget_crud] = lambda: CRUDInterface(
        schema=_Gadget, repository=_FakeGadgetRepository()
    )
    try:
        response = client.delete("/gadgets", params={"id": 999})
    finally:
        del app.dependency_overrides[get_gadget_crud]
    assert response.status_code == 404


def test_json_router_list_applies_filters_and_sort() -> None:
    """GET /gadgets?name=...&sort=... filters and sorts the list."""
    repository = _FakeGadgetRepository()
    app.dependency_overrides[get_gadget_crud] = lambda: CRUDInterface(
        schema=_Gadget, repository=repository
    )
    try:
        client.post("/gadgets", json={"name": "apple", "tags": []})
        client.post("/gadgets", json={"name": "apricot", "tags": []})
        client.post("/gadgets", json={"name": "banana", "tags": []})

        response = client.get("/gadgets", params={"name__icontains": "ap", "sort": "-name"})
        assert response.status_code == 200
        assert [g["name"] for g in response.json()] == ["apricot", "apple"]
    finally:
        del app.dependency_overrides[get_gadget_crud]


def test_json_router_list_rejects_limit_over_the_cap() -> None:
    """GET /gadgets?limit=1001 is a 422, capping how many records one request can pull."""
    response = client.get("/gadgets", params={"limit": 1001})
    assert response.status_code == 422


def test_json_router_list_allows_limit_at_the_cap() -> None:
    """GET /gadgets?limit=1000 (the cap itself) is accepted."""
    response = client.get("/gadgets", params={"limit": 1000})
    assert response.status_code == 200


def test_json_router_bulk_update_via_filters() -> None:
    """PATCH /gadgets?<filters> with no id updates every matching record."""
    repository = _FakeGadgetRepository()
    app.dependency_overrides[get_gadget_crud] = lambda: CRUDInterface(
        schema=_Gadget, repository=repository
    )
    try:
        client.post("/gadgets", json={"name": "apple", "tags": []})
        client.post("/gadgets", json={"name": "apricot", "tags": []})
        client.post("/gadgets", json={"name": "banana", "tags": []})

        response = client.patch(
            "/gadgets", params={"name__icontains": "ap"}, json={"tags": ["updated"]}
        )
        assert response.status_code == 200
        body = response.json()
        assert body["matched"] == 2
        assert len(body["ids"]) == 2

        remaining = client.get("/gadgets").json()
        tags = sorted((g["tags"][0] if g["tags"] else "") for g in remaining)
        assert tags == ["", "updated", "updated"]
    finally:
        del app.dependency_overrides[get_gadget_crud]


def test_json_router_bulk_delete_via_filters() -> None:
    """DELETE /gadgets?<filters> with no id deletes every matching record."""
    repository = _FakeGadgetRepository()
    app.dependency_overrides[get_gadget_crud] = lambda: CRUDInterface(
        schema=_Gadget, repository=repository
    )
    try:
        client.post("/gadgets", json={"name": "apple", "tags": []})
        client.post("/gadgets", json={"name": "apricot", "tags": []})
        client.post("/gadgets", json={"name": "banana", "tags": []})

        response = client.delete("/gadgets", params={"name__icontains": "ap"})
        assert response.status_code == 200
        body = response.json()
        assert body["matched"] == 2

        remaining = client.get("/gadgets").json()
        assert [g["name"] for g in remaining] == ["banana"]
    finally:
        del app.dependency_overrides[get_gadget_crud]


def test_json_router_bulk_update_rejected_over_row_cap(monkeypatch: pytest.MonkeyPatch) -> None:
    """A bulk PATCH matching more records than bulk_action_max_matched is refused, untouched."""
    repository = _FakeGadgetRepository()
    app.dependency_overrides[get_gadget_crud] = lambda: CRUDInterface(
        schema=_Gadget, repository=repository
    )
    monkeypatch.setattr(crud_actions.settings, "bulk_action_max_matched", 1)
    try:
        client.post("/gadgets", json={"name": "apple", "tags": []})
        client.post("/gadgets", json={"name": "apricot", "tags": []})

        response = client.patch(
            "/gadgets", params={"name__icontains": "ap"}, json={"tags": ["updated"]}
        )
        assert response.status_code == 400

        remaining = client.get("/gadgets").json()
        assert all(g["tags"] == [] for g in remaining)
    finally:
        del app.dependency_overrides[get_gadget_crud]


def test_json_router_bulk_delete_rejected_over_row_cap(monkeypatch: pytest.MonkeyPatch) -> None:
    """A bulk DELETE matching more records than bulk_action_max_matched is refused, untouched."""
    repository = _FakeGadgetRepository()
    app.dependency_overrides[get_gadget_crud] = lambda: CRUDInterface(
        schema=_Gadget, repository=repository
    )
    monkeypatch.setattr(crud_actions.settings, "bulk_action_max_matched", 1)
    try:
        client.post("/gadgets", json={"name": "apple", "tags": []})
        client.post("/gadgets", json={"name": "apricot", "tags": []})

        response = client.delete("/gadgets", params={"name__icontains": "ap"})
        assert response.status_code == 400
        assert len(client.get("/gadgets").json()) == 2
    finally:
        del app.dependency_overrides[get_gadget_crud]


def test_json_router_bulk_update_logs_an_audit_entry(caplog: pytest.LogCaptureFixture) -> None:
    """A successful bulk update logs an audit entry naming the filters and affected ids."""
    repository = _FakeGadgetRepository()
    app.dependency_overrides[get_gadget_crud] = lambda: CRUDInterface(
        schema=_Gadget, repository=repository
    )
    try:
        client.post("/gadgets", json={"name": "apple", "tags": []})
        with caplog.at_level(logging.INFO, logger="app.controllers.crud_actions"):
            response = client.patch(
                "/gadgets", params={"name__icontains": "ap"}, json={"tags": ["updated"]}
            )
        assert response.status_code == 200
        assert "Bulk update: actor=unknown path=/gadgets" in caplog.text
    finally:
        del app.dependency_overrides[get_gadget_crud]


def test_json_router_bulk_delete_logs_an_audit_entry(caplog: pytest.LogCaptureFixture) -> None:
    """A successful bulk delete logs an audit entry naming the filters and affected ids."""
    repository = _FakeGadgetRepository()
    app.dependency_overrides[get_gadget_crud] = lambda: CRUDInterface(
        schema=_Gadget, repository=repository
    )
    try:
        client.post("/gadgets", json={"name": "apple", "tags": []})
        with caplog.at_level(logging.INFO, logger="app.controllers.crud_actions"):
            response = client.delete("/gadgets", params={"name__icontains": "ap"})
        assert response.status_code == 200
        assert "Bulk delete: actor=unknown path=/gadgets" in caplog.text
    finally:
        del app.dependency_overrides[get_gadget_crud]


def test_json_router_bulk_update_with_no_filters_and_no_id_rejected() -> None:
    """PATCH /gadgets with neither id nor filters is rejected (400), never a full-table update."""
    app.dependency_overrides[get_gadget_crud] = lambda: CRUDInterface(
        schema=_Gadget, repository=_FakeGadgetRepository()
    )
    try:
        response = client.patch("/gadgets", json={"name": "Nobody"})
    finally:
        del app.dependency_overrides[get_gadget_crud]
    assert response.status_code == 422


def test_json_router_bulk_delete_with_no_filters_and_no_id_rejected() -> None:
    """DELETE /gadgets with neither id nor filters is rejected (400), never a full-table delete."""
    repository = _FakeGadgetRepository()
    app.dependency_overrides[get_gadget_crud] = lambda: CRUDInterface(
        schema=_Gadget, repository=repository
    )
    try:
        client.post("/gadgets", json={"name": "apple", "tags": []})
        response = client.delete("/gadgets")
        assert response.status_code == 422
        assert client.get("/gadgets").json() != []
    finally:
        del app.dependency_overrides[get_gadget_crud]


def test_xml_router_crud_lifecycle() -> None:
    """Create, get, and delete a record through the generated XML routes."""
    repository = _FakeGadgetRepository()
    app.dependency_overrides[get_gadget_crud] = lambda: CRUDInterface(
        schema=_Gadget, repository=repository
    )
    try:
        create_response = client.post(
            "/gadgets/xml",
            content="<gadget><name>Widget</name><tags>a</tags></gadget>",
            headers={"Content-Type": "application/xml"},
        )
        assert create_response.status_code == 201
        assert create_response.headers["content-type"] == "application/xml"
        assert "<name>Widget</name>" in create_response.text

        list_response = client.get("/gadgets/xml")
        assert list_response.status_code == 200
        assert "<gadgets>" in list_response.text
        gadget_id = list_response.text.split("<id>")[1].split("</id>")[0]

        get_response = client.get("/gadgets/xml", params={"id": gadget_id})
        assert get_response.status_code == 200
        assert "<name>Widget</name>" in get_response.text

        delete_response = client.delete("/gadgets/xml", params={"id": gadget_id})
        assert delete_response.status_code == 204

        missing_response = client.get("/gadgets/xml", params={"id": gadget_id})
        assert missing_response.status_code == 404
    finally:
        del app.dependency_overrides[get_gadget_crud]


def test_xml_router_bulk_update_and_delete_via_filters() -> None:
    """PATCH/DELETE /gadgets/xml?<filters> act in bulk and render an XML bulk-result body."""
    repository = _FakeGadgetRepository()
    app.dependency_overrides[get_gadget_crud] = lambda: CRUDInterface(
        schema=_Gadget, repository=repository
    )
    try:
        client.post(
            "/gadgets/xml",
            content="<gadget><name>apple</name><tags>a</tags></gadget>",
            headers={"Content-Type": "application/xml"},
        )
        client.post(
            "/gadgets/xml",
            content="<gadget><name>apricot</name><tags>a</tags></gadget>",
            headers={"Content-Type": "application/xml"},
        )

        update_response = client.patch(
            "/gadgets/xml",
            params={"name__icontains": "ap"},
            content="<gadget><tags>updated</tags></gadget>",
            headers={"Content-Type": "application/xml"},
        )
        assert update_response.status_code == 200
        assert "<bulk-update-result>" in update_response.text
        assert "<matched>2</matched>" in update_response.text

        delete_response = client.delete("/gadgets/xml", params={"name__icontains": "ap"})
        assert delete_response.status_code == 200
        assert "<bulk-delete-result>" in delete_response.text
        assert "<matched>2</matched>" in delete_response.text
    finally:
        del app.dependency_overrides[get_gadget_crud]


def test_web_router_form_page_serves_html() -> None:
    """GET /gadgets/form serves an HTML page with the form and web-component tags."""
    response = client.get("/gadgets/form")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "<form" in response.text
    assert "<gadget-list" in response.text


def test_web_router_submit_form_splits_list_field_on_comma() -> None:
    """POST /gadgets/form comma-splits a list field's raw value before creating the record."""
    repository = _FakeGadgetRepository()
    app.dependency_overrides[get_gadget_crud] = lambda: CRUDInterface(
        schema=_Gadget, repository=repository
    )
    try:
        response = client.post(
            "/gadgets/form",
            data={"name": "Widget", "tags": "a, b, c"},
            follow_redirects=False,
        )
        assert response.status_code == 303

        list_response = client.get("/gadgets")
        assert list_response.json()[0]["tags"] == ["a", "b", "c"]
    finally:
        del app.dependency_overrides[get_gadget_crud]


def test_web_router_components_js_defines_custom_elements() -> None:
    """GET /gadgets/components.js serves the web-component JS."""
    response = client.get("/gadgets/components.js")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/javascript")
    assert "customElements.define" in response.text


def test_json_router_filters_metadata_describes_every_filterable_field() -> None:
    """GET /gadgets/filters describes every filterable field's kind and ops."""
    response = client.get("/gadgets/filters")
    assert response.status_code == 200
    by_name = {info["name"]: info for info in response.json()}
    assert "tags" not in by_name  # list fields aren't filterable
    assert by_name["name"]["kind"] == "string"
    assert set(by_name["name"]["ops"]) == {"eq", "contains", "icontains", "regex"}
    assert by_name["id"]["kind"] == "number"


def test_web_component_bulk_ui_reaches_the_json_router() -> None:
    """The rendered web component's bulk-delete call (id__in=) works against the JSON router.

    The web router itself has no data routes -- its JS fetches directly against
    api_base (the sibling JSON router's own prefix), so this exercises that the
    two routers' contracts actually line up end to end, not just that each
    factory's routes work in isolation.
    """
    repository = _FakeGadgetRepository()
    app.dependency_overrides[get_gadget_crud] = lambda: CRUDInterface(
        schema=_Gadget, repository=repository
    )
    try:
        first = client.post("/gadgets", json={"name": "apple", "tags": []}).json()
        second = client.post("/gadgets", json={"name": "apricot", "tags": []}).json()
        client.post("/gadgets", json={"name": "banana", "tags": []})

        response = client.delete("/gadgets", params={"id__in": f"{first['id']},{second['id']}"})
        assert response.status_code == 200
        assert response.json()["matched"] == 2

        remaining = client.get("/gadgets").json()
        assert [g["name"] for g in remaining] == ["banana"]
    finally:
        del app.dependency_overrides[get_gadget_crud]
