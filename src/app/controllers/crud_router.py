"""Generic FastAPI router factories for a resource's CRUD endpoints.

Parameterized by a resource's Pydantic views and an already-built CRUD
dependency (app.crud.base.CRUDLike) -- covers both a current version
(CRUDInterface) and a deprecated one (CompatCRUD) identically, since
both satisfy CRUDLike structurally. Each factory builds its route
functions internally as closures over its arguments: the generated
functions' `crud`/`record` parameters are annotated with a TypeVar-bound
runtime type, which mypy cannot verify statically -- each such line
carries a narrow `# type: ignore[valid-type]`. This factory's own
signature (every parameter, `-> APIRouter`) stays fully strict-typed,
so a caller gets real type-checking on the call itself.

Record addressing is a query parameter (`?id=`), not a path segment, on every
factory here -- see app.controllers.crud_actions for the shared "id present ->
single record; otherwise -> filtered list, or a bulk update/delete over the
given filters" logic each factory's routes wrap in their own response format.
"""

from collections.abc import Sequence
from typing import Annotated, Any

from defusedxml.common import DefusedXmlException
from fastapi import APIRouter, HTTPException, Query, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import RedirectResponse, Response
from pydantic import BaseModel, ValidationError

from app.config import get_settings
from app.controllers.crud_actions import resolve_delete, resolve_list_or_get, resolve_update
from app.controllers.crud_query import FieldFilterInfo, describe_fields
from app.rate_limit import exempt_single_record_action, limiter
from app.views.bulk import BulkDeleteResult, BulkUpdateResult
from app.web_components import render_crud_component_js, render_crud_form
from app.xml_codec import from_xml, is_list_annotation, to_xml

settings = get_settings()

# Unbounded `?limit=` would let a caller pull an entire table in one response --
# cap it the same way skip=0 already bounds the low end.
_MAX_LIMIT = 1000

# Version of these factories' own route shape/behavior -- not a resource's shape.
# Bump only when build_json_router/build_xml_router/build_web_router themselves
# change in a breaking way; every existing resource-version's path still names it
# explicitly (see build_resource_router and docs/adrs/0009-...md) rather than
# hardcoding "v1" independently per resource.
ROUTER_VERSION = 1


def _with_dependency_headers[ResponseT: Response](
    response: Response, built: ResponseT
) -> ResponseT:
    """Copy headers a router-level dependency set on the shared `response` onto `built`.

    FastAPI merges a dependency's `response.headers` mutations into the framework's
    own auto-built Response, but not into one a route handler constructs and returns
    itself -- every build_xml_router/build_web_router route does that (XML/redirect/
    JS bodies), so a router-level header dependency like app.http_headers.sunset(...)
    would otherwise have no visible effect on any of them.
    """
    built.headers.raw.extend(response.headers.raw)
    return built


def _parse_xml_body[ModelT: BaseModel](body: bytes, schema: type[ModelT]) -> ModelT:
    """Parse a request body with from_xml, rejecting a malicious payload with 400.

    defusedxml.ElementTree.fromstring raises a DefusedXmlException (e.g.
    EntitiesForbidden) for a "billion laughs"-style entity-expansion attack --
    without this, that exception would otherwise reach problem_details.py's generic
    500 handler instead of being reported as the client error it is.
    """
    try:
        return from_xml(body, schema)
    except DefusedXmlException as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Malformed XML body") from exc


def build_json_router[SchemaT: BaseModel, CreateT: BaseModel, UpdateT: BaseModel](
    *,
    prefix: str,
    tags: Sequence[str],
    resource_label: str,
    schema: type[SchemaT],
    create_schema: type[CreateT],
    update_schema: type[UpdateT],
    crud_dependency: Any,  # Annotated[CRUDLike[SchemaT], Depends(...)]
    read_roles: Any,  # a Depends(...) object, e.g. heroes.ReadRoles
    write_roles: Any,
    delete_roles: Any,
    router_dependencies: Sequence[Any] = (),
) -> APIRouter:
    """Build the standard list/create/get/update/delete JSON router for one resource.

    `id`, when present as a query parameter, addresses a single record on the
    GET/PATCH/DELETE routes (404 if missing) -- otherwise GET lists (optionally
    filtered/sorted per app.controllers.crud_query) and PATCH/DELETE act in bulk
    over whatever filters are given, rejecting an empty filter set with no `id`
    (400) so an empty query string can never target every record by accident.
    """
    router = APIRouter(prefix=prefix, tags=list(tags), dependencies=list(router_dependencies))
    not_found = f"{resource_label} not found"

    @router.get("", dependencies=[read_roles])
    async def list_records(
        crud: crud_dependency,
        request: Request,
        id: int | None = None,  # noqa: A002
        skip: int = 0,
        limit: Annotated[int, Query(le=_MAX_LIMIT)] = 100,
    ) -> schema | list[schema]:  # type: ignore[valid-type]
        return await resolve_list_or_get(  # type: ignore[no-any-return]
            crud, schema, request, id=id, skip=skip, limit=limit, not_found=not_found
        )

    @router.post("", status_code=status.HTTP_201_CREATED, dependencies=[write_roles])
    async def create_record(record: create_schema, crud: crud_dependency) -> schema:  # type: ignore[valid-type]
        return await crud.create(record)  # type: ignore[no-any-return]

    @router.get("/filters", dependencies=[read_roles])
    async def list_filters() -> list[FieldFilterInfo]:
        return describe_fields(schema)

    @router.patch("", dependencies=[write_roles])
    @limiter.limit(settings.rate_limit_bulk_action, exempt_when=exempt_single_record_action)
    async def update_records(
        crud: crud_dependency,
        request: Request,
        record: update_schema,  # type: ignore[valid-type]
        id: int | None = None,  # noqa: A002
    ) -> schema | BulkUpdateResult:  # type: ignore[valid-type]
        return await resolve_update(crud, schema, request, id=id, data=record, not_found=not_found)  # type: ignore[no-any-return]

    @router.delete("", dependencies=[delete_roles], response_model=None)
    @limiter.limit(settings.rate_limit_bulk_action, exempt_when=exempt_single_record_action)
    async def delete_records(
        crud: crud_dependency,
        request: Request,
        id: int | None = None,  # noqa: A002
    ) -> BulkDeleteResult | Response:
        result = await resolve_delete(crud, schema, request, id=id, not_found=not_found)
        return result if result is not None else Response(status_code=status.HTTP_204_NO_CONTENT)

    return router


def build_xml_router[SchemaT: BaseModel, CreateT: BaseModel, UpdateT: BaseModel](
    *,
    prefix: str,
    tags: Sequence[str],
    resource_label: str,
    item_tag: str,
    list_tag: str,
    schema: type[SchemaT],
    create_schema: type[CreateT],
    update_schema: type[UpdateT],
    crud_dependency: Any,
    read_roles: Any,
    write_roles: Any,
    delete_roles: Any,
    router_dependencies: Sequence[Any] = (),
) -> APIRouter:
    """Build the XML-flavored sibling of build_json_router's routes, id/filter/bulk included."""
    router = APIRouter(prefix=prefix, tags=list(tags), dependencies=list(router_dependencies))
    not_found = f"{resource_label} not found"
    xml_media_type = "application/xml"

    @router.get("", dependencies=[read_roles])
    async def list_records_xml(
        crud: crud_dependency,
        request: Request,
        response: Response,
        id: int | None = None,  # noqa: A002
        skip: int = 0,
        limit: Annotated[int, Query(le=_MAX_LIMIT)] = 100,
    ) -> Response:
        result = await resolve_list_or_get(
            crud, schema, request, id=id, skip=skip, limit=limit, not_found=not_found
        )
        if isinstance(result, list):
            body = f"<{list_tag}>" + "".join(to_xml(r, item_tag) for r in result) + f"</{list_tag}>"
        else:
            body = to_xml(result, item_tag)
        return _with_dependency_headers(response, Response(content=body, media_type=xml_media_type))

    @router.post("", status_code=status.HTTP_201_CREATED, dependencies=[write_roles])
    async def create_record_xml(
        crud: crud_dependency, request: Request, response: Response
    ) -> Response:
        record = _parse_xml_body(await request.body(), create_schema)
        created = await crud.create(record)
        return _with_dependency_headers(
            response,
            Response(
                content=to_xml(created, item_tag),
                media_type=xml_media_type,
                status_code=status.HTTP_201_CREATED,
            ),
        )

    @router.patch("", dependencies=[write_roles])
    @limiter.limit(settings.rate_limit_bulk_action, exempt_when=exempt_single_record_action)
    async def update_records_xml(
        crud: crud_dependency,
        request: Request,
        response: Response,
        id: int | None = None,  # noqa: A002
    ) -> Response:
        record = _parse_xml_body(await request.body(), update_schema)
        result = await resolve_update(
            crud, schema, request, id=id, data=record, not_found=not_found
        )
        if isinstance(result, BulkUpdateResult):
            body = to_xml(result, "bulk-update-result")
        else:
            body = to_xml(result, item_tag)
        return _with_dependency_headers(response, Response(content=body, media_type=xml_media_type))

    @router.delete("", dependencies=[delete_roles])
    @limiter.limit(settings.rate_limit_bulk_action, exempt_when=exempt_single_record_action)
    async def delete_records_xml(
        crud: crud_dependency,
        request: Request,
        response: Response,
        id: int | None = None,  # noqa: A002
    ) -> Response:
        result = await resolve_delete(crud, schema, request, id=id, not_found=not_found)
        if result is None:
            built = Response(status_code=status.HTTP_204_NO_CONTENT)
        else:
            built = Response(
                content=to_xml(result, "bulk-delete-result"), media_type=xml_media_type
            )
        return _with_dependency_headers(response, built)

    return router


def build_web_router[CreateT: BaseModel](
    *,
    prefix: str,
    tags: Sequence[str],
    resource: str,
    api_base: str,
    fields: Sequence[str],
    create_schema: type[CreateT],
    crud_dependency: Any,
    read_roles: Any,
    write_roles: Any,
    router_dependencies: Sequence[Any] = (),
) -> APIRouter:
    """Build the zero-JS-form + web-component-JS sibling router for one resource.

    `list_fields` (which of `fields` are arrays, for comma-split parsing and
    ", "-joined display) is derived from `create_schema`'s own annotations via
    `is_list_annotation`, rather than passed separately -- one less value for a
    caller to keep in sync with its own view module.

    The rendered web component (`app.web_components.render_crud_component_js`)
    talks directly to `api_base` -- the sibling build_json_router's own prefix --
    for every list/create/update/delete/filters-metadata call, so this router
    itself only ever serves `/form` and `/components.js`; filtering/sorting/bulk
    actions reach the UI automatically once the JSON router that `api_base`
    points at supports them, with no separate data routes needed here.

    A submitted form redirects back to `request.url.path` (this route's own
    URL), not `api_base` -- the two only coincided by construction while every
    format shared one prefix; since `build_resource_router` mounts JSON/XML/web
    under their own explicit sub-prefixes, `api_base` names a sibling path that
    is no longer this router's own.

    The generic `Request.form()` parsing this needs (fields aren't known until
    runtime) loses FastAPI's typed-`Form()` per-field OpenAPI documentation, so
    `openapi_extra` rebuilds an equivalent requestBody schema by hand -- every
    field as a required string, matching what the form actually submits (a list
    field's comma-separated raw value, not the parsed array).
    """
    router = APIRouter(prefix=prefix, tags=list(tags), dependencies=list(router_dependencies))
    list_fields = tuple(
        f for f in fields if is_list_annotation(create_schema.model_fields[f].annotation)
    )
    form_openapi_extra = {
        "requestBody": {
            "required": True,
            "content": {
                "application/x-www-form-urlencoded": {
                    "schema": {
                        "type": "object",
                        "properties": {field: {"type": "string"} for field in fields},
                        "required": list(fields),
                    }
                }
            },
        }
    }

    @router.get("/form", dependencies=[read_roles])
    async def form_page(request: Request, response: Response) -> Response:
        own_base = request.url.path.removesuffix("/form")
        return _with_dependency_headers(
            response,
            Response(
                content=render_crud_form(resource, fields, api_base, own_base),
                media_type="text/html",
            ),
        )

    @router.post(
        "/form",
        status_code=status.HTTP_303_SEE_OTHER,
        dependencies=[write_roles],
        openapi_extra=form_openapi_extra,
    )
    async def submit_form(
        request: Request, crud: crud_dependency, response: Response
    ) -> RedirectResponse:
        form = await request.form()
        data: dict[str, str | list[str]] = {}
        for field in fields:
            raw = str(form.get(field, ""))
            data[field] = (
                [v.strip() for v in raw.split(",") if v.strip()] if field in list_fields else raw
            )
        try:
            validated = create_schema.model_validate(data)
        except ValidationError as exc:
            raise RequestValidationError(exc.errors()) from exc
        await crud.create(validated)
        return _with_dependency_headers(
            response, RedirectResponse(request.url.path, status_code=status.HTTP_303_SEE_OTHER)
        )

    @router.get("/components.js")
    async def components_js(response: Response) -> Response:
        return _with_dependency_headers(
            response,
            Response(
                content=render_crud_component_js(
                    resource, api_base, fields, list_fields=list_fields
                ),
                media_type="application/javascript",
            ),
        )

    return router


def build_resource_router[SchemaT: BaseModel, CreateT: BaseModel, UpdateT: BaseModel](
    *,
    prefix: str,
    tags: Sequence[str],
    resource_label: str,
    resource: str,
    item_tag: str,
    list_tag: str,
    fields: Sequence[str],
    schema: type[SchemaT],
    create_schema: type[CreateT],
    update_schema: type[UpdateT],
    crud_dependency: Any,  # Annotated[CRUDLike[SchemaT], Depends(...)]
    read_roles: Any,  # a Depends(...) object, e.g. heroes.ReadRoles
    write_roles: Any,
    delete_roles: Any,
    router_dependencies: Sequence[Any] = (),
) -> APIRouter:
    """Compose build_json_router/build_xml_router/build_web_router into one resource-version router.

    `prefix` is the resource-version's full prefix (e.g. `/crud/v1/heroes/v2`, see
    docs/adrs/0009-...md) -- each format is mounted under it as its own explicit,
    non-empty `/json`/`/xml`/`/web` sub-prefix, so the returned router already
    carries its complete path and is mounted at the call site with a bare
    `include_router(router)` -- no further prefix to add there.

    `router_dependencies` (e.g. app.http_headers.sunset(...) for a deprecated
    version) is applied once, on this router's own constructor -- FastAPI merges a
    router's own `dependencies` into every route of a sub-router later
    `include_router`'d into it, so this single declaration reaches JSON/XML/web
    alike, rather than each per-format factory call repeating it.
    """
    router = APIRouter(prefix=prefix, tags=list(tags), dependencies=list(router_dependencies))
    router.include_router(
        build_json_router(
            prefix="",
            tags=tags,
            resource_label=resource_label,
            schema=schema,
            create_schema=create_schema,
            update_schema=update_schema,
            crud_dependency=crud_dependency,
            read_roles=read_roles,
            write_roles=write_roles,
            delete_roles=delete_roles,
        ),
        prefix="/json",
    )
    router.include_router(
        build_xml_router(
            prefix="",
            tags=tags,
            resource_label=resource_label,
            item_tag=item_tag,
            list_tag=list_tag,
            schema=schema,
            create_schema=create_schema,
            update_schema=update_schema,
            crud_dependency=crud_dependency,
            read_roles=read_roles,
            write_roles=write_roles,
            delete_roles=delete_roles,
        ),
        prefix="/xml",
    )
    router.include_router(
        build_web_router(
            prefix="",
            tags=tags,
            resource=resource,
            api_base=f"{prefix}/json",
            fields=fields,
            create_schema=create_schema,
            crud_dependency=crud_dependency,
            read_roles=read_roles,
            write_roles=write_roles,
        ),
        prefix="/web",
    )
    return router
