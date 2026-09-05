"""Integration test: /v2/heroes CRUD routes against the real Postgres stack service."""

import json
from collections.abc import Iterator
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select
from starlette.types import Message

from app.config import get_settings
from app.main import app
from app.models.base import async_session_factory
from app.models.hero import Hero
from app.oidc import get_current_claims

client = TestClient(app)


@pytest.fixture(autouse=True)
def _authed() -> Iterator[None]:
    """Grant every RBAC role for the duration of each test in this module."""
    settings = get_settings()
    app.dependency_overrides[get_current_claims] = lambda: {
        "sub": "test-user",
        "resource_access": {
            settings.oidc_client_id: {
                "roles": ["viewer", "editor", "maintainer", "security", "detective"]
            }
        },
    }
    yield
    del app.dependency_overrides[get_current_claims]


def test_hero_crud_lifecycle_against_real_postgres() -> None:
    """Create, list, get, update, and delete a hero through the live app and real DB."""
    create_response = client.post(
        "/v2/heroes", json={"name": "Wonder Woman", "powers": ["Super strength"]}
    )
    assert create_response.status_code == 201
    hero_id = create_response.json()["id"]

    try:
        list_response = client.get("/v2/heroes")
        assert list_response.status_code == 200
        assert any(hero["id"] == hero_id for hero in list_response.json())

        get_response = client.get("/v2/heroes", params={"id": hero_id})
        assert get_response.status_code == 200
        assert get_response.json()["name"] == "Wonder Woman"

        update_response = client.patch(
            "/v2/heroes", params={"id": hero_id}, json={"powers": ["Lasso of truth"]}
        )
        assert update_response.status_code == 200
        assert update_response.json()["powers"] == ["Lasso of truth"]
    finally:
        delete_response = client.delete("/v2/heroes", params={"id": hero_id})
        assert delete_response.status_code == 204

    missing_response = client.get("/v2/heroes", params={"id": hero_id})
    assert missing_response.status_code == 404


def test_hero_filter_sort_and_bulk_actions_against_real_postgres() -> None:
    """Filtering/sorting a list and bulk update/delete via filters work over the live app."""
    batman = client.post(
        "/v2/heroes", json={"name": "Batman Filter Test", "powers": ["Detective skills"]}
    ).json()
    batgirl = client.post(
        "/v2/heroes", json={"name": "Batgirl Filter Test", "powers": ["Detective skills"]}
    ).json()
    superman = client.post(
        "/v2/heroes", json={"name": "Superman Filter Test", "powers": ["Flight"]}
    ).json()

    try:
        filtered = client.get("/v2/heroes", params={"name__icontains": "Filter Test"})
        assert filtered.status_code == 200
        assert {hero["id"] for hero in filtered.json()} == {
            batman["id"],
            batgirl["id"],
            superman["id"],
        }

        sorted_response = client.get(
            "/v2/heroes", params={"name__icontains": "Filter Test", "sort": "name"}
        )
        assert [hero["name"] for hero in sorted_response.json()] == [
            "Batgirl Filter Test",
            "Batman Filter Test",
            "Superman Filter Test",
        ]

        bulk_update = client.patch(
            "/v2/heroes",
            params={"name__icontains": "Bat"},
            json={"powers": ["Martial arts"]},
        )
        assert bulk_update.status_code == 200
        body = bulk_update.json()
        assert body["matched"] == 2
        assert set(body["ids"]) == {batman["id"], batgirl["id"]}

        assert client.get("/v2/heroes", params={"id": batman["id"]}).json()["powers"] == [
            "Martial arts"
        ]

        bulk_delete = client.delete("/v2/heroes", params={"name__icontains": "Bat"})
        assert bulk_delete.status_code == 200
        assert bulk_delete.json()["matched"] == 2
        assert client.get("/v2/heroes", params={"id": batman["id"]}).status_code == 404
        assert client.get("/v2/heroes", params={"id": batgirl["id"]}).status_code == 404
    finally:
        client.delete("/v2/heroes", params={"id": batman["id"]})
        client.delete("/v2/heroes", params={"id": batgirl["id"]})
        client.delete("/v2/heroes", params={"id": superman["id"]})


def test_hero_bulk_actions_with_no_filters_and_no_id_are_rejected() -> None:
    """A bulk PATCH/DELETE with neither id nor filters is rejected, never a full-table action."""
    update_response = client.patch("/v2/heroes", json={"name": "Should Not Apply"})
    assert update_response.status_code == 422

    delete_response = client.delete("/v2/heroes")
    assert delete_response.status_code == 422


async def test_write_is_committed_before_the_response_is_sent() -> None:
    """A created hero is visible to an independent session by the time POST's body goes out.

    Regression test for the read-after-write race behind tests/e2e's intermittent
    "created hero missing from the list" failures: `get_db` commits in a yield
    dependency's exit code, which at `Depends()`'s default `scope="request"` runs
    *after* the response is sent, so a client that immediately acts on the write's
    own response could reach a database where the INSERT hadn't committed yet.
    `app.models.base.DBSession` pins `scope="function"` to close that window.

    Driven over raw ASGI rather than TestClient because TestClient only returns once
    the whole ASGI cycle (teardown included) has finished, which hides the ordering
    this asserts. The check runs from a separate session, so under the old scope it
    genuinely cannot see the still-uncommitted row.
    """
    name = f"Commit Order {uuid4()}"
    body = json.dumps({"name": name, "powers": ["Durability"]}).encode()
    visible_when_body_sent: list[bool] = []

    async def receive() -> Message:
        """Feed the request body to the app in a single ASGI message."""
        return {"type": "http.request", "body": body, "more_body": False}

    async def send(message: Message) -> None:
        """Record, as the response body goes out, whether the row is committed yet."""
        if message["type"] != "http.response.body":
            return
        async with async_session_factory() as probe:
            result = await probe.execute(select(Hero).where(Hero.name == name))
            visible_when_body_sent.append(result.scalar_one_or_none() is not None)

    await app(
        {
            "type": "http",
            "asgi": {"version": "3.0", "spec_version": "2.1"},
            "http_version": "1.1",
            "method": "POST",
            "scheme": "http",
            "path": "/v2/heroes",
            "raw_path": b"/v2/heroes",
            "query_string": b"",
            "root_path": "",
            "headers": [
                (b"host", b"testserver"),
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode()),
            ],
            "client": ("testclient", 50000),
            "server": ("testserver", 80),
        },
        receive,
        send,
    )

    try:
        assert visible_when_body_sent == [True], (
            "POST /v2/heroes returned its response before the INSERT was committed -- "
            "a client acting on that response can fail to see its own write"
        )
    finally:
        async with async_session_factory() as cleanup:
            await cleanup.execute(delete(Hero).where(Hero.name == name))
            await cleanup.commit()
