# for backend/ai-service/app/models/recommendation_store.py
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4
from datetime import timedelta

from pymongo.collection import Collection

from app.database.connection import get_mongo_db
from app.schemas.recommendations import (
    RecommendationDecision,
    RecommendationRequest,
    RecommendationStatus,
    ReviewDecision,
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class RecommendationStore:
    def __init__(self, collection: Collection | None = None) -> None:
        # Passing a collection explicitly makes the store easier to test.
        self.tasks = (
            collection if collection is not None else get_mongo_db()["ai_tasks"]
        )

    def create_task(
        self,
        task_id: UUID,
        trace_id: str,
        requester_id: str,
        request: RecommendationRequest,
    ) -> None:
        """Create the task once. A retry keeps the original task and request."""
        now = utc_now()
        self.tasks.update_one(
            {"_id": str(task_id)},
            {
                "$setOnInsert": {
                    "trace_id": trace_id,
                    "requester_id": requester_id,
                    "request": request.model_dump(mode="json"),
                    "status": RecommendationStatus.QUEUED.value,
                    "authorized": False,
                    "debate_messages": [],
                    "votes": [],
                    "proposal": None,
                    "decision": None,
                    "deadline_at": now + timedelta(seconds=120),
                    "phase": "waiting",
                    "transitions": [{"phase": "waiting", "at": now}],
                    "errors": [],
                    "created_at": now,
                    "updated_at": now,
                }
            },
            upsert=True,
        )

    def save_plan(self, task_id: UUID, trace_id: str, steps: list[dict]) -> None:
        self.tasks.update_one(
            {"_id": str(task_id), "status": "queued", "plan": {"$exists": False}},
            {"$set": {"plan": {
                "plan_id": str(uuid4()), "trace_id": trace_id,
                "original_steps": steps, "steps": steps, "changes": [],
            }}},
        )

    def complete_step(self, task_id: UUID, index: int, phase: str) -> None:
        query = {"_id": str(task_id), "status": "queued",
                 f"plan.steps.{index}.status": "pending"}
        if index:
            query[f"plan.steps.{index - 1}.status"] = "complete"
        now = utc_now()
        self.tasks.update_one(query, {
            "$set": {f"plan.steps.{index}.status": "complete",
                     "phase": phase, "updated_at": now},
            "$push": {"transitions": {"phase": phase, "at": now}},
        })

    def save_reflection(self, task_id: UUID, reflection: dict) -> None:
        self.tasks.update_one(
            {"_id": str(task_id), "status": "queued", "reflection": {"$exists": False}},
            {"$set": {"reflection": reflection}},
        )

    def record_error(self, task_id: UUID, topic: str, reason: str) -> None:
        self.tasks.update_one({"_id": str(task_id)}, {
            "$push": {"errors": {"topic": topic, "reason": reason[:500], "at": utc_now()}},
        })

    def expire_tasks(self) -> None:
        now = utc_now()
        self.tasks.update_many(
            {"status": "queued", "deadline_at": {"$lte": now}},
            {
                "$set": {"status": "timed_out", "phase": "timed_out",
                         "authorized": False, "updated_at": now},
                "$push": {
                    "transitions": {"phase": "timed_out", "at": now},
                    "errors": {"reason": "Debate deadline expired.", "at": now},
                },
            },
        )

    def get_task(self, task_id: UUID) -> dict[str, Any] | None:
        return self.tasks.find_one({"_id": str(task_id)})

    def record_debate_message(
        self,
        task_id: UUID,
        envelope: dict[str, Any],
    ) -> bool:
        """Append a validated Kafka envelope once per logical message."""
        result = self.tasks.update_one(
            {
                "_id": str(task_id),
                "trace_id": envelope["trace_id"],
                "debate_messages.idempotency_key": {
                    "$ne": envelope["idempotency_key"]
                },
            },
            {
                "$push": {"debate_messages": envelope},
                "$set": {"updated_at": utc_now()},
            },
        )
        return result.modified_count == 1

    def record_vote(
        self,
        task_id: UUID,
        envelope: dict[str, Any],
    ) -> bool:
        """Keep the first valid Round 2 vote from each agent."""
        vote = envelope["payload"]
        result = self.tasks.update_one(
            {
                "_id": str(task_id),
                "trace_id": envelope["trace_id"],
                "status": RecommendationStatus.QUEUED.value,
                "votes.agent_id": {"$ne": vote["agent_id"]},
            },
            {
                "$push": {
                    "votes": {
                        **vote,
                        "event_id": envelope["event_id"],
                    }
                },
                "$set": {"updated_at": utc_now()},
            },
        )
        return result.modified_count == 1

    def save_result(
        self,
        task_id: UUID,
        envelope: dict[str, Any],
    ) -> bool:
        """Save the chair's initial result, which is never actionable."""
        status = RecommendationStatus(envelope["payload"]["status"])
        if status not in {
            RecommendationStatus.PENDING_REVIEW,
            RecommendationStatus.NO_MATCH,
            RecommendationStatus.FAILED,
            RecommendationStatus.NEEDS_CLARIFICATION,
        }:
            raise ValueError("Expected an initial recommendation result.")

        result = self.tasks.update_one(
            {
                "_id": str(task_id),
                "trace_id": envelope["trace_id"],
                "status": RecommendationStatus.QUEUED.value,
            },
            {
                "$set": {
                    "phase": status.value,
                    "status": status.value,
                    "authorized": False,
                    "proposal": {
                        "event_id": envelope["event_id"],
                        "payload": {**envelope["payload"], "authorized": False},
                    },
                    "updated_at": utc_now(),
                },
                "$push": {"transitions": {"phase": status.value, "at": utc_now()}},
            },
        )
        return result.modified_count == 1

    def record_decision(
        self,
        task_id: UUID,
        decision: RecommendationDecision,
        reviewer_id: str,
        decision_event_id: UUID,
    ) -> bool:
        """Record a single decision for the exact proposal the reviewer saw."""
        now = utc_now()
        result = self.tasks.update_one(
            {
                "_id": str(task_id),
                "status": RecommendationStatus.PENDING_REVIEW.value,
                "proposal.event_id": str(decision.proposal_event_id),
                "decision": None,
            },
            {
                "$set": {
                    "decision": {
                        **decision.model_dump(mode="json"),
                        "event_id": str(decision_event_id),
                        "reviewer_id": reviewer_id,
                        "recorded_at": now,
                    },
                    "updated_at": now,
                }
            },
        )
        return result.modified_count == 1

    def finalize_decision(self, task_id: UUID, decision_event_id: UUID) -> bool:
        """Apply the stored decision after the worker receives it from Kafka."""
        task = self.get_task(task_id)
        if task is None or task["decision"] is None:
            return False

        decision = task["decision"]
        if decision["event_id"] != str(decision_event_id):
            return False

        approved = decision["decision"] == ReviewDecision.APPROVED.value
        result = self.tasks.update_one(
            {
                "_id": str(task_id),
                "status": RecommendationStatus.PENDING_REVIEW.value,
                "decision.event_id": str(decision_event_id),
            },
            {
                "$set": {
                    "phase": decision["decision"],
                    "status": decision["decision"],
                    "authorized": approved,
                    "updated_at": utc_now(),
                },
                "$push": {"transitions": {"phase": decision["decision"], "at": utc_now()}},
            },
        )
        return result.modified_count == 1