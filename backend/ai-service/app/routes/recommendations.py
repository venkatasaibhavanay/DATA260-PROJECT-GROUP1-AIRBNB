#backend/ai-service/app/routes/recommendations.py
from asyncio import sleep
from datetime import timezone
from functools import lru_cache
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Request, WebSocket, WebSocketDisconnect, status
from fastapi.concurrency import run_in_threadpool
from fastapi.encoders import jsonable_encoder
from kafka.errors import KafkaError

from app.config import settings
from app.models.recommendation_store import RecommendationStore
from app.schemas.recommendations import (
    RecommendationAccepted,
    RecommendationDecision,
    RecommendationRequest,
    RecommendationStatus,
)
from shared.auth import CurrentUser, require_role
from shared.auth.jwt_auth import ws_user_from_token
from shared.errors import AppError
from shared.errors.errors import get_trace_id
from shared.kafka.envelope import EventEnvelope, new_event
from shared.kafka.producer import EnvelopeProducer
from shared.responses import Envelope, ok


router = APIRouter(tags=["recommendations"])

Guest = Annotated[CurrentUser, Depends(require_role("guest"))]
Reader = Annotated[CurrentUser, Depends(require_role("guest", "admin"))]
Reviewer = Annotated[CurrentUser, Depends(require_role("admin"))]
def get_store() -> RecommendationStore:
    return RecommendationStore()


Store = Annotated[RecommendationStore, Depends(get_store)]


@lru_cache(maxsize=1)
def get_producer() -> EnvelopeProducer:
    return EnvelopeProducer(
        settings.kafka_bootstrap_servers,
        client_id="ai-recommendations-api",
    )


def publish(event: EventEnvelope) -> None:
    # AI topics use the original task trace ID as the Kafka partition key.
    try:
        get_producer().publish(event.event_type, event, key=event.trace_id)
    except KafkaError as exc:
        raise AppError(
            503,
            "KAFKA_UNAVAILABLE",
            "Kafka did not confirm publication.",
            fields={"task_id": event.entity.entity_id},
        ) from exc


def find_task(store: RecommendationStore, task_id: UUID) -> dict:
    task = store.get_task(task_id)
    if task is None:
        raise AppError(404, "AI_TASK_NOT_FOUND", "Recommendation task not found.")
    return task


def task_status(task: dict, *, reviewer: bool) -> dict:
    proposal = task["proposal"]
    decision = task["decision"]
    state = RecommendationStatus(task["status"])

    # Keep the initial proposal separate from the worker's final authorization.
    result = {
        "task_id": task["_id"],
        "trace_id": task["trace_id"],
        "status": state.value,
        "authorized": task["authorized"],
        "proposal": proposal,
        "decision": None,
    }
    if decision and (
        reviewer or state in {RecommendationStatus.APPROVED, RecommendationStatus.REJECTED}
    ):
        result["decision"] = {
            "decision": decision["decision"],
            "recorded_at": decision["recorded_at"],
            "edited_property_id": decision.get("edited_property_id"),
            "category": (
                "edited" if decision.get("edited_property_id")
                else "approved_as_is" if decision["decision"] == "approved" else "rejected"
            ),
        }
        if reviewer:
            result["decision"]["reason"] = decision["reason"]
    return result


@router.post(
    "/requests",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=Envelope[RecommendationAccepted],
)
def submit_request(
    body: RecommendationRequest,
    request: Request,
    user: Guest,
    store: Store,
):
    task_id = uuid4()
    trace_id = get_trace_id(request)
    if len(trace_id) > 128:
        raise AppError(400, "INVALID_TRACE_ID", "X-Trace-ID exceeds 128 characters.")

    event = new_event(
        "ai.requests",
        source_service="ai-service",
        actor_id=user.actor_id,
        entity_type="ai_task",
        entity_id=str(task_id),
        trace_id=trace_id,
        payload=body.model_dump(mode="json"),
    )

    # The worker needs the MongoDB task as soon as Kafka delivers the message.
    store.create_task(task_id, trace_id, user.actor_id, body)
    publish(event)
    return ok(RecommendationAccepted(task_id=task_id), request)


@router.get("/requests/{task_id}", response_model=Envelope[dict])
def get_request_status(
    task_id: UUID,
    request: Request,
    user: Reader,
    store: Store,
):
    task = find_task(store, task_id)
    if user.role != "admin" and task["requester_id"] != user.actor_id:
        raise AppError(404, "AI_TASK_NOT_FOUND", "Recommendation task not found.")

    return ok(task_status(task, reviewer=user.role == "admin"), request)


@router.post(
    "/requests/{task_id}/decision",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=Envelope[dict],
)
def review_proposal(
    task_id: UUID,
    body: RecommendationDecision,
    request: Request,
    reviewer: Reviewer,
    store: Store,
):
    task = find_task(store, task_id)
    payload = body.model_dump(mode="json")

    if body.edited_property_id:
        proposal_payload = (task.get("proposal") or {}).get("payload", {})
        if (
            body.edited_property_id not in proposal_payload.get("ranked_property_ids", [])
            or body.edited_property_id == proposal_payload.get("recommended_property")
        ):
            raise AppError(409, "AI_INVALID_EDIT", "Select a different eligible property.")

    if task["decision"] is None:
        if not store.record_decision(task_id, body, reviewer.actor_id, uuid4()):
            # Another reviewer may have recorded a decision while this ran.
            task = find_task(store, task_id)
            if task["decision"] is None:
                raise AppError(
                    409,
                    "AI_PROPOSAL_NOT_PENDING",
                    "This proposal is no longer available for review.",
                )
        else:
            task = find_task(store, task_id)

    saved = task["decision"]
    if saved["reviewer_id"] != reviewer.actor_id or any(
        saved.get(field) != value for field, value in payload.items()
    ):
        raise AppError(
            409,
            "AI_DECISION_ALREADY_RECORDED",
            "A different decision has already been recorded for this task.",
        )

    if task["status"] == RecommendationStatus.PENDING_REVIEW.value:
        # Reuse the stored UUID on retries. The worker checks this exact event ID.
        # PyMongo may return a naive datetime even though MongoDB stores UTC.
        recorded_at = saved["recorded_at"]
        if recorded_at.tzinfo is None:
            recorded_at = recorded_at.replace(tzinfo=timezone.utc)

        event = EventEnvelope(
            event_id=saved["event_id"],
            event_type="ai.decisions",
            schema_version=1,
            trace_id=task["trace_id"],
            timestamp=recorded_at,
            source_service="ai-service",
            actor_id=saved["reviewer_id"],
            entity={"entity_type": "ai_task", "entity_id": str(task_id)},
            idempotency_key=f"ai.decisions:{task_id}:human",
            payload=payload,
        )
        publish(event)
        task = find_task(store, task_id)

    return ok(task_status(task, reviewer=True), request)

@router.websocket("/tasks/{task_id}/stream")
async def stream_debate(websocket: WebSocket, task_id: UUID):
    try:
        user = await run_in_threadpool(
            ws_user_from_token, websocket.query_params.get("token")
        )
    except AppError:
        await websocket.close(code=4401)
        return

    await websocket.accept()
    store = await run_in_threadpool(get_store)
    previous = None
    try:
        while True:
            task = await run_in_threadpool(store.get_task, task_id)
            if task is None or (
                user.role != "admin" and task["requester_id"] != user.actor_id
            ):
                await websocket.close(code=4404)
                return

            data = task_status(task, reviewer=user.role == "admin")
            data.update(
                can_review=user.role == "admin",
                phase=task.get("phase", task["status"]),
                plan=task.get("plan"),
                transitions=task.get("transitions", []),
                reflection=task.get("reflection"),
                messages=[
                    message for message in task["debate_messages"]
                    if message["event_type"].startswith("debate.round.")
                ],
                errors=task.get("errors", []) if user.role == "admin" else [],
            )
            if data != previous:
                await websocket.send_json(jsonable_encoder(data))
                previous = data
            if task["status"] in {
                "approved", "rejected", "failed", "timed_out", "no_match", "needs_clarification"
            }:
                await websocket.close()
                return
            await sleep(0.5)
    except WebSocketDisconnect:
        return
