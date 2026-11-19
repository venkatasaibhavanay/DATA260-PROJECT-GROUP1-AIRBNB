"""Standard success envelope (API doc section 2.3).

    return ok(data, request)   ->  {"data": data, "meta": {"request_id": ..., "trace_id": ...}}

Use Envelope[T] as response_model so Swagger shows the wrapped shape:

    @router.post("/properties/get", response_model=Envelope[PropertyOut])
    def get_property(body: GetPropertyIn, request: Request):
        return ok(service.get(body.property_id), request)

Health endpoints stay unwrapped. 204 responses have no body.
"""
from typing import Any, Generic, TypeVar

from fastapi import Request
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel

from shared.errors.errors import ResponseMeta, get_request_id, get_trace_id

T = TypeVar("T")


class Envelope(BaseModel, Generic[T]):
    data: T
    meta: ResponseMeta


def ok(data: Any, request: Request) -> dict[str, Any]:
    return {
        "data": jsonable_encoder(data),
        "meta": {"request_id": get_request_id(request), "trace_id": get_trace_id(request)},
    }


__all__ = ["Envelope", "ResponseMeta", "ok"]
