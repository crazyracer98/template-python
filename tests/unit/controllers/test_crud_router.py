"""Unit test: build_json_router/build_xml_router/build_web_router's generic route wiring.

Exercises the three router factories directly against a minimal fake schema/model
pair, not tied to Hero -- mirrors how tests/unit/crud/test_compat.py tests
CompatCRUD generically.
"""

from dataclasses import dataclass
from typing import Annotated, Any

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel, ConfigDict

from app.controllers.crud_router import build_json_router, build_web_router, build_xml_router
from app.crud.base import CRUDInterface


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


class _FakeGadgetRepository:
    """In-memory Repository implementation, keyed by id."""

    def __init__(self) -> None:
        """Start with no records and the first id to hand out."""
        self._records: dict[int, _GadgetRecord] = {}
        self._next_id = 1

    async def get(self, record_id: int) -> _GadgetRecord | None:
        """Return the record with the given id, or None if it doesn't exist."""
        return self._records.get(record_id)

    async def list(self, *, skip: int = 0, limit: int = 100) -> list[_GadgetRecord]:
        """Return up to `limit` records, skipping the first `skip`."""
        return list(self._records.values())[skip : skip + limit]

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

        get_response = client.get(f"/gadgets/{gadget_id}")
        assert get_response.status_code == 200
        assert get_response.json()["name"] == "Widget"

        update_response = client.patch(f"/gadgets/{gadget_id}", json={"tags": ["b"]})
        assert update_response.status_code == 200
        assert update_response.json()["tags"] == ["b"]

        delete_response = client.delete(f"/gadgets/{gadget_id}")
        assert delete_response.status_code == 204

        missing_response = client.get(f"/gadgets/{gadget_id}")
        assert missing_response.status_code == 404
    finally:
        del app.dependency_overrides[get_gadget_crud]


def test_json_router_get_missing_returns_404() -> None:
    """GET /gadgets/{id} for a nonexistent id returns 404."""
    app.dependency_overrides[get_gadget_crud] = lambda: CRUDInterface(
        schema=_Gadget, repository=_FakeGadgetRepository()
    )
    try:
        response = client.get("/gadgets/999")
    finally:
        del app.dependency_overrides[get_gadget_crud]
    assert response.status_code == 404


def test_json_router_update_missing_returns_404() -> None:
    """PATCH /gadgets/{id} for a nonexistent id returns 404."""
    app.dependency_overrides[get_gadget_crud] = lambda: CRUDInterface(
        schema=_Gadget, repository=_FakeGadgetRepository()
    )
    try:
        response = client.patch("/gadgets/999", json={"name": "Nobody"})
    finally:
        del app.dependency_overrides[get_gadget_crud]
    assert response.status_code == 404


def test_json_router_delete_missing_returns_404() -> None:
    """DELETE /gadgets/{id} for a nonexistent id returns 404."""
    app.dependency_overrides[get_gadget_crud] = lambda: CRUDInterface(
        schema=_Gadget, repository=_FakeGadgetRepository()
    )
    try:
        response = client.delete("/gadgets/999")
    finally:
        del app.dependency_overrides[get_gadget_crud]
    assert response.status_code == 404


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

        delete_response = client.delete(f"/gadgets/xml/{gadget_id}")
        assert delete_response.status_code == 204

        missing_response = client.get(f"/gadgets/xml/{gadget_id}")
        assert missing_response.status_code == 404
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
