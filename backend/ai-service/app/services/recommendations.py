# backend/ai-service/app/services/recommendations.py
import re
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from decimal import Decimal

from app.schemas.recommendations import (
    GuestRequirements,
    RecommendationRequest,
)

NUMBER_WORDS = {"one": 1, "two": 2, "three": 3}
SUPPORTED_AMENITIES = ("parking", "kitchen", "wifi", "pool", "laundry")


def parse_guest_request(request: RecommendationRequest) -> GuestRequirements:
    """Extract requirements from the wording supported by the demo."""
    text = request.text
    destination = re.search(
        r"\b(?:stay|nights?)\s+in\s+([^,]+?)\s+for\s+"
        r"(\d+|one|two|three)\s+(?:people|guests?|person)\b",
        text,
        re.IGNORECASE,
    )
    budget = re.search(
        r"\b(?:under|below)\s+\$([\d,]+(?:\.\d{1,2})?)\s+per night\b",
        text,
        re.IGNORECASE,
    )
    if destination is None or budget is None:
        raise ValueError(
            "Please specify a city, guest count, and nightly budget "
            "such as 'in San Jose for two people, under $250 per night.'"
        )

    duration = re.search(r"\b(\d+|one|two|three)[ -]nights?\b", text, re.IGNORECASE)
    if duration:
        nights = parse_count(duration[1])
        if nights != (request.check_out - request.check_in).days:
            raise ValueError("The requested number of nights conflicts with the dates.")

    rating = re.search(
        r"\brating of at least\s+(\d+(?:\.\d+)?)\b", text, re.IGNORECASE
    )

    return GuestRequirements(
        city=destination[1],
        check_in=request.check_in,
        check_out=request.check_out,
        guests=parse_count(destination[2]),
        nightly_price_ceiling=Decimal(budget[1].replace(",", "")),
        amenities=[
            amenity
            for amenity in SUPPORTED_AMENITIES
            if re.search(rf"\b{amenity}\b", text, re.IGNORECASE)
        ],
        minimum_rating=Decimal(rating[1]) if rating else None,
    )


def parse_count(value: str) -> int:
    value = value.lower()
    return int(value) if value.isdecimal() else NUMBER_WORDS[value]


def build_candidate_snapshot(
    requirements: GuestRequirements, listings: list[dict]
) -> dict:
    """Give all Round 0 agents the same requirements and candidate data."""
    return {
        "requirements": requirements.model_dump(mode="json"),
        "listings": listings,
    }

@dataclass(frozen=True)
class Listing:
    property_id: str
    city: str
    capacity: int
    nightly_price: Decimal  # Fixture uses a flat USD nightly rate.
    amenities: frozenset[str]
    rating: Decimal | None
    available_nights: frozenset[date]


@dataclass(frozen=True)
class RankedProperty:
    property_id: str
    rank: int
    score: float
    reasons: tuple[str, ...]


def rank_properties(
    request: GuestRequirements, listings: list[Listing]
) -> list[RankedProperty]:
    """Filter on guest requirements, then prefer lower price and higher rating."""
    # Check-out day is excluded. A listing must be available for every occupied night.
    nights = {
        request.check_in + timedelta(days=offset)
        for offset in range((request.check_out - request.check_in).days)
    }
    required_amenities = {name.strip().casefold() for name in request.amenities}
    eligible = []
    for listing in listings:
        if listing.city.strip().casefold() != request.city.strip().casefold():
            continue
        if listing.capacity < request.guests or listing.nightly_price >= request.nightly_price_ceiling:
            continue
        if not nights.issubset(listing.available_nights):
            continue
        offered_amenities = {name.strip().casefold() for name in listing.amenities}
        if not required_amenities.issubset(offered_amenities):
            continue
        if request.minimum_rating is not None and (
            listing.rating is None or listing.rating < request.minimum_rating
        ):
            continue
        eligible.append(listing)

    # Rank eligible listings by price, then rating, then ID for stable ties.
    eligible.sort(
        key=lambda listing: (
            listing.nightly_price,
            -(listing.rating if listing.rating is not None else Decimal("-1")),
            listing.property_id,
        )
    )
    return [
        RankedProperty(
            property_id=listing.property_id,
            rank=rank,
            score=1 / rank,
            reasons=(
                f"Available for all {len(nights)} nights in {request.city} "
                f"and accommodates {request.guests} guests.",
                f"Meets amenity requirements; nightly rate is ${listing.nightly_price:.2f}.",
                (
                    f"Guest rating is {listing.rating}/5."
                    if listing.rating is not None
                    else "Guest rating is unavailable."
                ),
            ),
        )
        for rank, listing in enumerate(eligible, start=1)
    ]


def matching_opinion(
    request: GuestRequirements, listings: list[Listing]
) -> dict[str, object]:
    """Return a proposed payload for debate.round.0."""
    ranking = rank_properties(request, listings)
    return {
        "agent_id": "property-matching",
        "ranked_properties": [asdict(item) for item in ranking],
        "reasons": [
            "Eligible listings are sorted by nightly price, then by rating. Score is 1 divided by rank."
            if ranking
            else "No listing in the supplied pool meets all guest requirements."
        ],
        "confidence": "medium" if listings else "low",
    }




# These topic names match the project and act as the durable workflow history.


MATCH = "property-matching"
RISK = "review-and-risk"
AUDIT = "fairness-and-bias"
AGENTS = (MATCH, RISK, AUDIT)
CHAIR = "booking-assistant-chair"


def fixture(request):
    nights = [
        (request.check_in + timedelta(days=i)).isoformat()
        for i in range((request.check_out - request.check_in).days)
    ]
    return [
        {
            "property_id": "property-a", "city": "San Jose", "capacity": 2,
            "nightly_price": "189", "rating": "4.6", "amenities": ["parking", "kitchen"],
            "available_nights": nights,
            "evidence": [
                {"id": "demo-review-1", "kind": "cancellation", "summary": "Host canceled a confirmed stay."},
                {"id": "demo-review-2", "kind": "cancellation", "summary": "Host canceled a second confirmed stay."},
            ],
        },
        {
            "property_id": "property-b", "city": "San Jose", "capacity": 4,
            "nightly_price": "209", "rating": "4.9", "amenities": ["parking", "kitchen"],
            "available_nights": nights, "evidence": [],
        },
    ]


def to_listing(row):
    return Listing(
        row["property_id"], row["city"], row["capacity"], Decimal(row["nightly_price"]),
        frozenset(row["amenities"]), Decimal(row["rating"]) if row["rating"] is not None else None,
        frozenset(date.fromisoformat(night) for night in row["available_nights"]),
    )


def independent_opinion(agent, snapshot):
    # Each Round 0 agent receives the same snapshot and cannot see peer opinions here.
    request = GuestRequirements.model_validate(snapshot["requirements"])
    rows = {row["property_id"]: row for row in snapshot["listings"]}
    listings = [to_listing(row) for row in rows.values()]
    eligible = [item.property_id for item in rank_properties(request, listings)]
    if agent == MATCH:
        return matching_opinion(request, listings)

    if agent == RISK:
        # These example weights express relative risk. Lower totals rank higher.
        weights = {"cancellation": 3, "missing_amenity": 2, "cleanliness": 2,
                   "unusual_price": 1, "unresponsive_host": 1}

        def risk_score(property_id):
            return sum(weights.get(item["kind"], 0) for item in rows[property_id]["evidence"])

        ordered = sorted(eligible, key=risk_score)
        reasons = [
            {"property_id": property_id, "risk_score": risk_score(property_id),
             "evidence": rows[property_id]["evidence"]}
            for property_id in ordered
        ]
        summary = "Ranks eligible listings by documented risk, with the lowest risk first."
    # The auditor takes another look at the eligible pool using aggregate ratings.
    else:
        ordered = sorted(eligible, key=lambda property_id: (
            rows[property_id]["rating"] is None,
            -Decimal(rows[property_id]["rating"] or "0"), property_id,
        ))
        reasons = [
            {"property_id": property_id, "aggregate_rating": rows[property_id]["rating"]}
            for property_id in ordered
        ]
        summary = (
            "Compared every eligible listing using aggregate guest rating. "
            "Review whether price or rating hides a comparable eligible option."
        )
    return {
        "agent_id": agent,
        "ranked_properties": [
            {"property_id": property_id, "rank": rank, "score": 1 / rank}
            for rank, property_id in enumerate(ordered, start=1)
        ],
        "reasons": [summary, *reasons],
        "confidence": "medium" if ordered else "low",
    }


def top(opinion):
    ranking = opinion["payload"]["ranked_properties"]
    return ranking[0]["property_id"] if ranking else None


def plan_challenge(opinions):
    if MATCH not in opinions or RISK not in opinions:
        raise ValueError("Matching and risk opinions are required.")
    # The matching agent supplies the initial proposal. A competing top pick triggers challenges.
    original = top(opinions[MATCH])
    alternative = next(
        (top(opinions[agent]) for agent in (RISK, AUDIT)
         if agent in opinions and top(opinions[agent]) not in (None, original)), None,
    )
    disagreements = {
        agent: top(opinion) for agent, opinion in opinions.items() if top(opinion) != original
    }
    # The auditor receives a challenge even when the other agents agree.
    questions = {AUDIT: (
        "Which eligible listing might the chair be overlooking, and did either "
        "ranking use a signal unrelated to this guest's request?"
    )} if AUDIT in opinions else {}
    if disagreements:
        questions[MATCH] = f"Why prefer {original} to {alternative} when review risks are considered?"
        for agent in disagreements:
            if agent != AUDIT:
                questions[agent] = f"What stored evidence supports {top(opinions[agent])} over {original}?"
    return {
        "agent_id": CHAIR, "original": original, "challenger": alternative,
        "disagreements": disagreements, "questions": questions,
        "opinion_event_ids": [opinion["event_id"] for opinion in opinions.values()],
    }


def cast_vote(agent, opinions, challenge):
    proposal = challenge["payload"]
    own_opinion = opinions[agent]
    # The ballot has two property options. An agent abstains if neither matches its preference.
    preferred = top(own_opinion)
    choice = "abstain"
    if preferred is not None:
        if preferred == proposal["original"]:
            choice = "keep_original"
        elif preferred == proposal["challenger"]:
            choice = "choose_challenger"
    reason = {
        MATCH: "I prioritize the nightly price among listings that meet the guest's requirements.",
        RISK: "I prioritize the eligible listing with the lowest documented review risk.",
        AUDIT: (
            "I compared the eligible listings. A lower price alone can overlook a property "
            "with stronger guest reviews. The supplied fields contain no guest identity attributes."
        ),
    }[agent]
    if choice == "abstain":
        reason += " My ranking does not support either of the two ballot options."
    row = next(
        (item for item in own_opinion["payload"]["reasons"]
         if isinstance(item, dict) and item.get("property_id") == preferred), {}
    )
    # Challenged agents answer using stored opinions and, where available, review records.
    answer = None
    review_ids = []
    if agent in proposal["questions"]:
        if agent == RISK:
            risk_rows = {
                item["property_id"]: item for item in own_opinion["payload"]["reasons"]
                if isinstance(item, dict)
            }
            original = risk_rows[proposal["original"]]
            review_ids = [item["id"] for item in original["evidence"] + row["evidence"]]
            answer = (
                f"{preferred} scored {row['risk_score']} on documented risk versus "
                f"{original['risk_score']} for {proposal['original']}. "
                f"Review records: {', '.join(review_ids) or 'none supplied'}."
            )
        elif agent == MATCH:
            first = own_opinion["payload"]["ranked_properties"][0]
            answer = " ".join(first["reasons"]) + (
                " My availability and price ranking does not account for cancellation risk."
            )
        else:
            answer = (
                f"Consider {preferred} based on its supplied aggregate rating of "
                f"{row['aggregate_rating']}."
                if row.get("aggregate_rating") is not None
                else "The snapshot has no eligible rated listing to flag."
            )
            answer += " The rankings use listing attributes and review evidence."
    return {
        "agent_id": agent, "choice": choice, "preferred_property": preferred,
        "reason": reason, "answer": answer,
        "evidence_event_ids": [own_opinion["event_id"], challenge["event_id"]],
        "review_evidence_ids": review_ids,
    }


def explain_result(snapshot, challenge, votes, opinions):
    proposal = challenge["payload"]
    # A challenger needs more votes. A supported original wins a tie.
    counts = defaultdict(int)
    for event in votes.values():
        counts[event["payload"]["choice"]] += 1
    property_id = proposal["original"]
    if counts["choose_challenger"] > counts["keep_original"]:
        property_id = proposal["challenger"]
    elif counts["keep_original"] == 0:
        property_id = None
    row = next((row for row in snapshot["listings"] if row["property_id"] == property_id), None)
    reason = (
        f"{property_id} meets the guest's requirements at ${row['nightly_price']} per night. "
        f"The chair counted {counts['keep_original']} votes for the original listing, "
        f"{counts['choose_challenger']} for the challenger, and {counts['abstain']} abstentions. "
        "A tie with support for the original keeps the original."
        if row else "The debate produced no supported recommendation."
    )
    ranking = sorted(
        (item["property_id"] for item in opinions[MATCH]["payload"]["ranked_properties"]),
        key=lambda candidate: (
            candidate != property_id,
            sum(
                next(
                    (item["rank"] for item in event["payload"]["ranked_properties"]
                     if item["property_id"] == candidate),
                    len(snapshot["listings"]) + 1,
                )
                for event in opinions.values()
            ),
        ),
    )
    dissent = [
        {"agent_id": agent, "preferred_property": top(event),
         "round_zero_reasons": event["payload"]["reasons"],
         "vote_reason": votes[agent]["payload"]["reason"]}
        for agent, event in opinions.items() if top(event) != property_id
    ]
    return {
        "confidence": (
            "low" if not row or counts["keep_original"] == counts["choose_challenger"]
            else "medium"
        ),
        "ranked_property_ids": ranking,
        "dissent": dissent,
        "decision_rule": "Most votes wins. In a supported tie, retain the original. All abstain means no result.",
        "status": "pending_review" if row else "no_match", "authorized": False,
        "recommended_property": property_id, "explanation": reason,
        "limitations": [
            "The demo uses a fixed listing and review snapshot. Verify live availability and price.",
            "Missing review reports do not establish that a listing is risk-free.",
        ],
        "review_evidence": {
            item["property_id"]: item["evidence"]
            for item in opinions[RISK]["payload"]["reasons"] if isinstance(item, dict)
        },
        "disagreements": proposal["disagreements"], "original": proposal["original"],
        "challenger": proposal["challenger"], "votes": [event["payload"] for event in votes.values()],
    }


def reflect_on_result(snapshot, proposal, messages):
    """One bounded check. Reject unsupported results before human review."""
    selected = proposal["recommended_property"]
    req = GuestRequirements.model_validate(snapshot["requirements"])
    eligible = {entry.property_id for entry in rank_properties(
        req, [to_listing(row) for row in snapshot["listings"]]
    )}
    identifiers = {event["event_id"] for event in messages}
    checks = {
        "constraints": selected is None or selected in eligible,
        "evidence": all(
            set(vote["evidence_event_ids"]).issubset(identifiers)
            for vote in proposal["votes"]
        ),
        "approval_gate": proposal["authorized"] is False,
    }
    return {
        "cycle": 1,
        "decision": "keep" if all(checks.values()) else "reject",
        "checks": checks,
        "concerns": [
            *proposal["limitations"],
            *[item["summary"] for item in proposal["review_evidence"].get(selected, [])],
        ],
        "conflicts": proposal["dissent"],
    }
