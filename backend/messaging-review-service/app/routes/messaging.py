from fastapi import APIRouter, Depends, Request, Response

from app.schemas.messaging import OpenThreadRequest
from app.services.messaging import open_or_reuse_thread
from shared.auth import CurrentUser, require_role
from shared.responses import ok


router = APIRouter(
    prefix="/threads",
    tags=["messaging"],
)


@router.post("/open")
def open_thread(
    payload: OpenThreadRequest,
    request: Request,
    response: Response,
    user: CurrentUser = Depends(require_role("guest", "host")),
):
    thread, created = open_or_reuse_thread(
        payload=payload,
        user=user,
        authorization=request.headers.get("authorization"),
    )

    response.status_code = 201 if created else 200
    return ok(thread, request)