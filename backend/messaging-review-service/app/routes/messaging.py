from fastapi import (
    APIRouter,
    Depends,
    Header,
    Request,
    Response,
    WebSocket,
    WebSocketDisconnect,
)

from app.schemas.messaging import (
    CreateReviewRequest,
    GetThreadRequest,
    ListMessagesRequest,
    MarkMessagesReadRequest,
    OpenThreadRequest,
    SendMessageRequest,
    ThreadsByUserRequest,
)

from app.services.messaging import (
    create_review,
    get_thread_data,
    list_messages,
    list_threads_by_user,
    mark_messages_read,
    open_or_reuse_thread,
    send_message,
)
from shared.auth import (
    CurrentUser,
    require_role,
    ws_user_from_token,
)
from shared.responses import ok


router = APIRouter(
    prefix="/threads",
    tags=["messaging"],
)

ws_router = APIRouter(
    prefix="/ws",
    tags=["messaging"],
)


class MessageConnectionManager:
    def __init__(self):
        self.connections: dict[str, set[WebSocket]] = {}

    async def connect(self, actor_id: str, websocket: WebSocket):
        await websocket.accept()
        self.connections.setdefault(actor_id, set()).add(websocket)

    async def disconnect(self, actor_id: str, websocket: WebSocket):
        connections = self.connections.get(actor_id, set())
        connections.discard(websocket)

        if not connections:
            self.connections.pop(actor_id, None)


connection_manager = MessageConnectionManager()


@ws_router.websocket("/messages")
async def messages_websocket(websocket: WebSocket):
    token = websocket.query_params.get("token")

    try:
        user = ws_user_from_token(token)
    except Exception:
        await websocket.close(code=4401)
        return

    await connection_manager.connect(user.actor_id, websocket)

    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await connection_manager.disconnect(
            user.actor_id,
            websocket,
        )

message_router = APIRouter(
    prefix="/messages",
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

@router.post("/get")
def get_thread(
    payload: GetThreadRequest,
    request: Request,
    user: CurrentUser = Depends(require_role("guest", "host")),
):
    thread = get_thread_data(
        payload=payload,
        user=user,
    )

    return ok(thread, request)

@router.post("/byUser")
def get_threads_by_user(
    payload: ThreadsByUserRequest,
    request: Request,
    user: CurrentUser = Depends(require_role("guest", "host")),
):
    threads = list_threads_by_user(
        payload=payload,
        user=user,
    )

    return ok(threads, request)

review_router = APIRouter(
    prefix="/reviews",
    tags=["reviews"],
)

@message_router.post("/list")
def get_messages(
    payload: ListMessagesRequest,
    request: Request,
    user: CurrentUser = Depends(require_role("guest", "host")),
):
    messages = list_messages(
        payload=payload,
        user=user,
    )

    return ok(messages, request)

@message_router.post("/send")
def create_message(
    payload: SendMessageRequest,
    request: Request,
    response: Response,
    idempotency_key: str = Header(
        ...,
        alias="Idempotency-Key",
    ),
    user: CurrentUser = Depends(require_role("guest", "host")),
):
    message, created = send_message(
        payload=payload,
        user=user,
        idempotency_key=idempotency_key,
    )

    response.status_code = 201 if created else 200
    return ok(message, request)

@message_router.post("/markRead")
def mark_read(
    payload: MarkMessagesReadRequest,
    request: Request,
    user: CurrentUser = Depends(require_role("guest", "host")),
):
    result = mark_messages_read(
        payload=payload,
        user=user,
    )

    return ok(result, request)

@review_router.post("/create")
def create_review_route(
    payload: CreateReviewRequest,
    request: Request,
    response: Response,
    user: CurrentUser = Depends(require_role("guest")),
):
    review = create_review(
        payload=payload,
        user=user,
    )

    response.status_code = 201
    return ok(review, request)