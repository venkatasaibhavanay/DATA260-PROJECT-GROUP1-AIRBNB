"""Offline Section 7 evaluator. Run with the AI app on PYTHONPATH."""
import argparse
import json
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from statistics import mean
from uuid import uuid4

from app.schemas.recommendations import RecommendationRequest
from app.services.recommendations import (
    AGENTS, AUDIT, MATCH, build_candidate_snapshot, cast_vote,
    explain_result, independent_opinion, parse_guest_request,
    plan_challenge, reflect_on_result,
)


def baseline(requirements, listings):
    nights = {
        (requirements.check_in + timedelta(days=i)).isoformat()
        for i in range((requirements.check_out - requirements.check_in).days)
    }

    def score(row):
        rating = row["rating"]
        checks = [
            row["city"].casefold() == requirements.city.casefold(),
            row["capacity"] >= requirements.guests,
            Decimal(row["nightly_price"]) < requirements.nightly_price_ceiling,
            nights.issubset(row["available_nights"]),
        ]
        if requirements.minimum_rating is not None:
            checks.append(rating is not None and Decimal(rating) >= requirements.minimum_rating)
        amenities = {item.casefold() for item in row["amenities"]}
        return sum(checks) + sum(item.casefold() in amenities for item in requirements.amenities)

    return [
        row["property_id"] for row in sorted(listings, key=lambda r: (-score(r), r["property_id"]))
    ]


def local_debate(snapshot, agents):
    def envelope(payload):
        return {"event_id": str(uuid4()), "payload": payload}

    opinions = {agent: envelope(independent_opinion(agent, snapshot)) for agent in agents}
    challenge = envelope(plan_challenge(opinions))
    votes = {agent: envelope(cast_vote(agent, opinions, challenge)) for agent in agents}
    result = explain_result(snapshot, challenge, votes, opinions)
    reflection = reflect_on_result(snapshot, result, [*opinions.values(), challenge, *votes.values()])
    return result, reflection


def metrics(ranking, truth, missing_rank):
    hits = len(set(ranking[:10]) & set(truth))
    return {
        "precision_at_10": hits / 10,
        "recall_at_10": hits / len(truth),
        "human_top_rank": ranking.index(truth[0]) + 1 if truth[0] in ranking else missing_rank,
    }


def evaluate(dataset):
    listings, cases = dataset["listings"], dataset["cases"]
    ids = {row["property_id"] for row in listings}
    if len(ids) != len(listings) or len(ids) < 200:
        raise ValueError("Supply a fixed pool of at least 200 distinct properties.")
    if len(cases) != 50 or len({case["id"] for case in cases}) != 50:
        raise ValueError("Supply 50 uniquely identified requests.")
    if len({case["category"] for case in cases}) < 4:
        raise ValueError("Supply at least four categories.")

    rows = []
    for case in cases:
        labels = [case[key] for key in ("labeler_a", "labeler_b", "adjudicated_top_10")]
        if any(len(label) != 10 or len(set(label)) != 10 or not set(label) <= ids for label in labels):
            raise ValueError(f"Case {case['id']} needs three valid top-10 label lists.")
        first, second, truth = labels
        requirements = parse_guest_request(RecommendationRequest.model_validate(case["request"]))
        snapshot = build_candidate_snapshot(requirements, listings)
        with_auditor, reflection = local_debate(snapshot, AGENTS)
        without_auditor, _ = local_debate(snapshot, tuple(a for a in AGENTS if a != AUDIT))
        rank = {
            "filter_count": baseline(requirements, listings),
            "matching_only": [
                row["property_id"]
                for row in independent_opinion(MATCH, snapshot)["ranked_properties"]
            ],
            "without_auditor": without_auditor["ranked_property_ids"],
            "with_auditor": with_auditor["ranked_property_ids"] if reflection["decision"] == "keep" else [],
            "with_auditor_no_reflection": with_auditor["ranked_property_ids"],
        }
        rows.append({
            "id": case["id"],
            "human_agreement_at_10": len(set(first) & set(second)) / 10,
            "labeler_a_vs_adjudicated": metrics(first, truth, len(ids) + 1),
            "labeler_b_vs_adjudicated": metrics(second, truth, len(ids) + 1),
            "metrics": {mode: metrics(ranking, truth, len(ids) + 1) for mode, ranking in rank.items()},
            "auditor_changed_verdict": (
                with_auditor["recommended_property"] != without_auditor["recommended_property"]
            ),
            "with_auditor_verdict": with_auditor["recommended_property"],
            "without_auditor_verdict": without_auditor["recommended_property"],
            "reflection": reflection,
        })

    modes = rows[0]["metrics"]
    return {
        "missing_rank_penalty": len(ids) + 1,
        "human_agreement_at_10": mean(row["human_agreement_at_10"] for row in rows),
        "human_labeler_ceiling_against_adjudicated": {
            key: mean(row[label][key] for row in rows
                      for label in ("labeler_a_vs_adjudicated", "labeler_b_vs_adjudicated"))
            for key in rows[0]["labeler_a_vs_adjudicated"]
        },
        "summary": {
            mode: {
                key: mean(row["metrics"][mode][key] for row in rows)
                for key in rows[0]["metrics"][mode]
            }
            for mode in modes
        },
        "cases": rows,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", type=Path)
    args = parser.parse_args()
    dataset = json.loads(args.dataset.read_text(encoding="utf-8-sig"))
    print(json.dumps(evaluate(dataset), indent=2))


if __name__ == "__main__":
    main()

