# backend/ai-service/app/kafka/recommendation_worker.py
import json
import logging
import os
from pathlib import Path
from threading import Event, Thread
from uuid import UUID

from kafka.errors import KafkaError
from pymongo.errors import AutoReconnect, ExecutionTimeout
from pydantic import ValidationError

from app.config import settings
from app.models.recommendation_store import RecommendationStore
from app.schemas.recommendations import RecommendationDecision, RecommendationRequest
from app.services.recommendations import (
    AGENTS,
    build_candidate_snapshot,
    cast_vote,
    explain_result,
    fixture,
    independent_opinion,
    parse_guest_request,
    plan_challenge,
    reflect_on_result,
)
from shared.kafka.consumer import PermanentError, TransientError, run_consumer
from shared.kafka.envelope import EventEnvelope, new_event
from shared.kafka.producer import EnvelopeProducer


TOPICS = [
    "ai.requests",
    "ai.parsed",
    "debate.round.0",
    "debate.round.1",
    "debate.round.2",
    "ai.results",
    "ai.decisions",
]

VOTE_CHOICES = {"keep_original", "choose_challenger", "abstain"}
INITIAL_STATUSES = {"pending_review", "no_match", "needs_clarification", "failed"}
logger = logging.getLogger(__name__)

PLAN = [
    ("Parse requirements and capture candidate snapshot", "guest request", "snapshot", "guest-request-parser"),
    ("Collect independent opinions", "snapshot", "rankings", "matching, risk, fairness"),
    ("Ask challenge questions", "rankings", "challenges", "booking-assistant-chair"),
    ("Collect answers and votes", "challenges", "votes", "matching, risk, fairness"),
    ("Reflect and prepare verdict", "votes and evidence", "checked result", "booking-assistant-chair"),
]


def candidate_pool(requirements):
    """Load a fixed property export when configured, or use the demo fixture."""
    path = os.environ.get("AI_CANDIDATE_POOL_FILE")
    if not path:
        return fixture(requirements)
    try:
        rows = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as exc:
        raise PermanentError("Could not read the configured AI candidate pool.") from exc
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise PermanentError("The AI candidate pool must be a JSON array of listings.")
    return rows


class RecommendationWorker:
    def __init__(
        self,
        store: RecommendationStore,
        producer: EnvelopeProducer,
    ) -> None:
        self.store = store
        self.producer = producer

    def publish(
        self,
        incoming: EventEnvelope,
        topic: str,
        step: str,
        payload: dict,
    ) -> None:
        task_id = incoming.entity.entity_id
        event = new_event(
            topic,
            source_service="ai-service",
            actor_id="service:ai-worker",
            entity_type="ai_task",
            entity_id=task_id,
            trace_id=incoming.trace_id,
            idempotency_key=f"{topic}:{task_id}:{step}",
            payload=payload,
        )
        self.producer.publish(topic, event, key=incoming.trace_id)

    def handle(self, incoming: EventEnvelope) -> None:
        try:
            self.process(incoming)
        except (AutoReconnect, ExecutionTimeout) as exc:
            raise TransientError(str(exc)) from exc
        except (PermanentError, ValueError, KeyError, TypeError) as exc:
            try:
                task_id = UUID(incoming.entity.entity_id)
            except ValueError:
                raise PermanentError(str(exc)) from exc
            try:
                task = self.store.get_task(task_id)
                if task and task["trace_id"] == incoming.trace_id:
                    self.store.record_error(task_id, incoming.event_type, str(exc))
            except (AutoReconnect, ExecutionTimeout) as db_error:
                raise TransientError(str(db_error)) from db_error
            raise PermanentError(str(exc)) from exc
        except KafkaError as exc:
            if exc.retriable:
                raise TransientError(str(exc)) from exc
            raise

    def process(self, incoming: EventEnvelope) -> None:
        if incoming.entity.entity_type != "ai_task":
            raise PermanentError("Expected an ai_task event.")
        task_id = UUID(incoming.entity.entity_id)
        topic = incoming.event_type
        event = incoming.model_dump(mode="json")

        task = self.store.get_task(task_id)
        if task is None:
            raise PermanentError("Task not found. Create it before publishing ai.requests.")
        if task["trace_id"] != incoming.trace_id:
            raise PermanentError("Event trace ID does not match the task.")

        if topic == "ai.decisions":
            self.resolve(incoming, task_id, task)
            return

        if topic == "ai.results":
            if incoming.payload.get("status") in INITIAL_STATUSES:
                self.store.save_result(task_id, event)
            # Resolved results are for downstream consumers.
            return

        if task["status"] != "queued":
            return

        if topic == "ai.requests":
            self.start(incoming, task)
            return

        if topic in {"debate.round.0", "debate.round.2"}:
            if incoming.payload.get("agent_id") not in AGENTS:
                raise PermanentError("Unknown debate agent.")

        if topic == "debate.round.2":
            reason = incoming.payload.get("reason")
            evidence = incoming.payload.get("evidence_event_ids")
            if (
                incoming.payload.get("choice") not in VOTE_CHOICES
                or not isinstance(reason, str)
                or not reason.strip()
                or not isinstance(evidence, list)
                or not evidence
            ):
                raise PermanentError("Round 2 vote requires a choice, reason, and evidence.")

        if topic == "debate.round.0":
            snapshots = self.messages(task, "ai.parsed")
            if not snapshots:
                raise PermanentError("No candidate snapshot.")
            candidates = {row["property_id"] for row in snapshots[0]["payload"]["listings"]}
            rows = incoming.payload["ranked_properties"]
            ids = [row["property_id"] for row in rows]
            if (
                len(ids) != len(set(ids)) or not set(ids).issubset(candidates)
                or [row["rank"] for row in rows] != list(range(1, len(rows) + 1))
                or any(type(row.get("score")) not in (int, float)
                       or not 0 < row["score"] <= 1 for row in rows)
                or not incoming.payload.get("reasons")
                or incoming.payload.get("confidence") not in {"low", "medium", "high"}
            ):
                raise PermanentError("Invalid ranking, reasons or confidence.")
        if topic == "debate.round.2":
            available = {row["event_id"] for row in task["debate_messages"]}
            if not set(incoming.payload["evidence_event_ids"]).issubset(available):
                raise PermanentError("Vote cites missing debate evidence.")

        self.store.record_debate_message(task_id, event)
        if topic == "debate.round.2":
            # Keep the audit envelope before recording the vote that references it.
            self.store.record_vote(task_id, event)

        task = self.store.get_task(task_id)
        if task is None:
            raise PermanentError("Task disappeared while recording the debate.")
        self.advance(incoming, task)

    def start(self, incoming: EventEnvelope, task: dict) -> None:
        if self.messages(task, "ai.parsed"):
            return

        self.store.save_plan(UUID(incoming.entity.entity_id), incoming.trace_id, [
            {"name": name, "input": input_, "expected_output": output,
             "agent": agent, "status": "pending"}
            for name, input_, output, agent in PLAN
        ])
        # The API route saves the validated request before publishing ai.requests.
        request = RecommendationRequest.model_validate(task["request"])
        try:
            requirements = parse_guest_request(request)
        except (ValueError, ValidationError) as exc:
            self.publish(incoming, "ai.results", "initial", {
                "status": "needs_clarification",
                "authorized": False,
                "explanation": str(exc),
            })
            return

        snapshot = build_candidate_snapshot(requirements, candidate_pool(requirements))
        self.publish(incoming, "ai.parsed", "snapshot", snapshot)

    @staticmethod
    def messages(task: dict, topic: str) -> list[dict]:
        return [
            event for event in task["debate_messages"]
            if event["event_type"] == topic
        ]

    def advance(self, incoming: EventEnvelope, task: dict) -> None:
        snapshots = self.messages(task, "ai.parsed")
        if not snapshots:
            raise PermanentError("Missing the Round 0 candidate snapshot.")
        snapshot = snapshots[0]["payload"]
        task_id = UUID(incoming.entity.entity_id)
        self.store.complete_step(task_id, 0, "debate")

        opinions = {}
        for event in self.messages(task, "debate.round.0"):
            opinions.setdefault(event["payload"]["agent_id"], event)

        if incoming.event_type == "ai.parsed":
            # Every agent sees the same snapshot and receives no peer opinions.
            for agent in AGENTS:
                if agent not in opinions:
                    opinion = independent_opinion(agent, snapshot)
                    self.publish(incoming, "debate.round.0", agent, opinion)
            return

        if any(agent not in opinions for agent in AGENTS):
            return
        opinions = {agent: opinions[agent] for agent in AGENTS}

        challenges = self.messages(task, "debate.round.1")
        if incoming.event_type == "debate.round.0":
            if not challenges:
                self.store.complete_step(task_id, 1, "opinions_collected")
                self.publish(
                    incoming, "debate.round.1", "challenge",
                    plan_challenge(opinions),
                )
            return

        if not challenges:
            raise PermanentError("Missing the chair's Round 1 challenge.")
        challenge = challenges[0]
        self.store.complete_step(task_id, 2, "challenging")
        saved_votes = {vote["agent_id"]: vote for vote in task["votes"]}

        if incoming.event_type == "debate.round.1":
            for agent in AGENTS:
                if agent not in saved_votes:
                    vote = cast_vote(agent, opinions, challenge)
                    self.publish(incoming, "debate.round.2", agent, vote)
            return

        if any(agent not in saved_votes for agent in AGENTS):
            return

        # Tally only the first vote that MongoDB accepted for each agent.
        round_two = {
            event["event_id"]: event
            for event in self.messages(task, "debate.round.2")
        }
        votes = {
            agent: round_two[saved_votes[agent]["event_id"]]
            for agent in AGENTS
        }
        self.store.complete_step(task_id, 3, "reflecting")
        proposal = explain_result(snapshot, challenge, votes, opinions)
        reflection = task.get("reflection") or reflect_on_result(
            snapshot, proposal, task["debate_messages"]
        )
        self.store.save_reflection(task_id, reflection)
        if reflection["decision"] == "reject":
            proposal.update(status="failed", recommended_property=None,
                            explanation="The reflection check rejected the result.")
        proposal["reflection"] = reflection
        self.store.complete_step(task_id, 4, "verdict_ready")
        self.publish(incoming, "ai.results", "initial", proposal)

    def resolve(self, incoming: EventEnvelope, task_id: UUID, task: dict) -> None:
        decision = RecommendationDecision.model_validate(incoming.payload)
        stored = task["decision"]
        if (
            stored is None
            or stored["event_id"] != incoming.event_id
            or stored["proposal_event_id"] != str(decision.proposal_event_id)
            or stored["decision"] != decision.decision.value
            or stored["reason"] != decision.reason
            or stored.get("edited_property_id") != decision.edited_property_id
            or stored["reviewer_id"] != incoming.actor_id
        ):
            raise PermanentError("Decision does not match the stored reviewer decision.")

        self.store.finalize_decision(task_id, UUID(incoming.event_id))
        current = self.store.get_task(task_id)
        if current is None or current["status"] != stored["decision"]:
            raise PermanentError("The stored decision could not be finalized.")

        proposal = current["proposal"]["payload"]
        authorized = current["status"] == "approved" and current["authorized"]
        approved_property = (
            decision.edited_property_id or proposal.get("recommended_property")
        ) if authorized else None
        self.publish(incoming, "ai.results", "resolved", {
            **proposal,
            "status": current["status"],
            "authorized": authorized,
            "approved_property": approved_property,
            "recommendation_source": "reviewer_edit" if decision.edited_property_id else "debate",
            "review_category": (
                "edited" if decision.edited_property_id
                else "approved_as_is" if authorized else "rejected"
            ),
            "human_decision": {
                **decision.model_dump(mode="json"),
                "reviewer_id": stored["reviewer_id"],
                "event_id": incoming.event_id,
            },
        })


def expire_overdue_tasks(store: RecommendationStore, stop: Event) -> None:
    while not stop.wait(2):
        try:
            store.expire_tasks()
        except (AutoReconnect, ExecutionTimeout):
            logger.warning("Could not check recommendation deadlines.", exc_info=True)


def main() -> None:
    bootstrap = settings.kafka_bootstrap_servers
    producer = EnvelopeProducer(bootstrap, client_id="ai-recommendation-worker")
    store = RecommendationStore()
    stop = Event()
    watchdog = Thread(target=expire_overdue_tasks, args=(store, stop), daemon=True)
    watchdog.start()
    try:
        worker = RecommendationWorker(store, producer)
        run_consumer(
            TOPICS,
            group_id="ai-recommendation-worker-v1",
            handler=worker.handle,
            bootstrap_servers=bootstrap,
            client_id="ai-recommendation-worker",
        )
    finally:
        stop.set()
        watchdog.join(timeout=3)
        producer.close()


if __name__ == "__main__":
    main()
