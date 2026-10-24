"""Validated data exchanged between agents."""

import re
from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Charge(BaseModel):
    model_config = ConfigDict(extra="forbid")

    line_id: str = Field(min_length=1, max_length=30)
    code: str = Field(default="UNKNOWN", max_length=15)
    description: str = Field(default="", max_length=500)
    service_date: date | None = None
    quantity: int = Field(default=1, ge=1, le=1000)
    amount: Decimal = Field(ge=0, le=1_000_000, max_digits=12, decimal_places=2)
    modifiers: str = Field(default="", max_length=100)

    @field_validator("code", mode="before")
    @classmethod
    def normalize_code(cls, value):
        return str(value or "UNKNOWN").strip().upper()

    @field_validator("modifiers", mode="before")
    @classmethod
    def normalize_modifiers(cls, value):
        return ",".join(sorted(set(re.findall(r"[A-Z0-9]+", str(value or "").upper()))))


class Bill(BaseModel):
    model_config = ConfigDict(extra="forbid")

    patient: str = Field(default="Not provided", max_length=200)
    provider: str = Field(default="Not provided", max_length=200)
    account: str = Field(default="Not provided", max_length=100)
    visit_type: str = Field(default="unknown", max_length=100)
    visit_start: date | None = None
    visit_end: date | None = None
    lines: list[Charge] = Field(min_length=1, max_length=300)
    extraction_notes: list[str] = Field(default_factory=list, max_length=30)

    @model_validator(mode="after")
    def validate_bill(self):
        ids = [line.line_id for line in self.lines]
        if len(ids) != len(set(ids)):
            raise ValueError("Line IDs must be unique.")
        if self.visit_start and self.visit_end and self.visit_end < self.visit_start:
            raise ValueError("Visit end must be on or after visit start.")
        return self


def money(value) -> str:
    return f"{Decimal(str(value)).quantize(Decimal('0.01')):.2f}"


def bill_readiness_errors(bill: Bill) -> list[str]:
    """Reject empty extraction scaffolding before audit or any model call."""
    errors = []
    if not any(line.amount > 0 for line in bill.lines):
        errors.append("Enter at least one actual charge with a billed amount greater than zero.")
    for index, line in enumerate(bill.lines, 1):
        if line.description.strip() == "Enter a charge from the local source":
            errors.append(f"Row {index} is an empty extraction placeholder. Replace it with an actual service or remove it.")
        elif line.code == "UNKNOWN" and not line.description.strip():
            errors.append(f"Row {index} needs a procedure code or a service description.")
    return errors


def require_auditable_bill(bill: Bill) -> Bill:
    errors = bill_readiness_errors(bill)
    if errors:
        raise ValueError("Audit blocked. " + " ".join(errors))
    return bill
