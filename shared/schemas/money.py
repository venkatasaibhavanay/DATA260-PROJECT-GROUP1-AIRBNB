"""Money: decimal amounts with 2 decimal places, serialized as strings ("189.00")."""
from decimal import ROUND_HALF_UP, Decimal
from typing import Annotated, Literal

from pydantic import AfterValidator, Field, PlainSerializer

Currency = Literal["USD"]

_CENT = Decimal("0.01")


def _two_places(v: Decimal) -> Decimal:
    if not v.is_finite():
        raise ValueError("amount must be a finite number")
    q = v.quantize(_CENT, rounding=ROUND_HALF_UP)
    if q != v:
        raise ValueError("amount must have at most 2 decimal places")
    return q


Money = Annotated[
    Decimal,
    Field(max_digits=12, decimal_places=2, examples=["189.00"]),
    AfterValidator(_two_places),
    PlainSerializer(lambda v: f"{v:.2f}", return_type=str, when_used="always"),
]

__all__ = ["Money", "Currency"]
