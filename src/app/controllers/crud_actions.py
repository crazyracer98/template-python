"""Shared id/filter/bulk decision logic for the CRUD router factories.

Route bodies factored out of app.controllers.crud_router so build_json_router and
build_xml_router share one implementation of "id present -> single record;
otherwise -> filtered list, or a bulk update/delete over whatever filters are
given" -- each router factory wraps the same calls in its own response format
(a plain value for JSON, an XML-rendered Response for XML). build_json_router's
and build_xml_router's own public signatures are unchanged by this split.
"""

from typing import Any

from fastapi import HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel

from app.controllers.crud_query import parse_filters, parse_sort
from app.crud.base import CRUDLike
from app.views.bulk import BulkDeleteResult, BulkUpdateResult

_NO_TARGET_ERROR = [
    {
        "loc": ("query",),
        "msg": "at least one filter or id is required for a bulk action",
        "type": "value_error",
    }
]


async def resolve_list_or_get(
    crud: CRUDLike[Any],
    schema: type[BaseModel],
    request: Request,
    *,
    id: int | None,  # noqa: A002 -- the wire name this query param uses, see controllers/README.md
    skip: int,
    limit: int,
    not_found: str,
) -> Any:  # BaseModel | list[BaseModel], see module docstring
    """Return one record by id, or a filtered/sorted list of matching records."""
    if id is not None:
        record = await crud.get(id)
        if record is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, not_found)
        return record
    filters = parse_filters(schema, request.query_params)
    sort = parse_sort(schema, request.query_params)
    return await crud.list(skip=skip, limit=limit, filters=filters, sort=sort)


async def resolve_update(
    crud: CRUDLike[Any],
    schema: type[BaseModel],
    request: Request,
    *,
    id: int | None,  # noqa: A002
    data: BaseModel,
    not_found: str,
) -> Any:  # BaseModel | BulkUpdateResult, see module docstring
    """Update one record by id, or bulk-update every record matching the query filters."""
    if id is not None:
        updated = await crud.update(id, data)
        if updated is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, not_found)
        return updated
    filters = parse_filters(schema, request.query_params)
    if not filters:
        raise RequestValidationError(_NO_TARGET_ERROR)
    updated_records = await crud.update_many(filters=filters, data=data)
    return BulkUpdateResult(
        matched=len(updated_records),
        ids=[record.id for record in updated_records],
    )


async def resolve_delete(
    crud: CRUDLike[Any],
    schema: type[BaseModel],
    request: Request,
    *,
    id: int | None,  # noqa: A002
    not_found: str,
) -> BulkDeleteResult | None:
    """Delete one record by id, or bulk-delete every record matching the query filters."""
    if id is not None:
        if not await crud.delete(id):
            raise HTTPException(status.HTTP_404_NOT_FOUND, not_found)
        return None
    filters = parse_filters(schema, request.query_params)
    if not filters:
        raise RequestValidationError(_NO_TARGET_ERROR)
    deleted_records = await crud.delete_many(filters=filters)
    return BulkDeleteResult(
        matched=len(deleted_records),
        ids=[record.id for record in deleted_records],
    )
