"""Auditor rules: evidence-backed findings and Decimal monetary calculations."""

from collections import defaultdict
from decimal import Decimal

from billing.models import Bill, money, require_auditable_bill

ZERO = Decimal("0")
DISTINCT = {"59", "XE", "XP", "XS", "XU"}


def audit_bill(bill: Bill, kb) -> dict:
    require_auditable_bill(bill)
    findings = []
    disputed = {line.line_id: ZERO for line in bill.lines}
    by_id = {line.line_id: line for line in bill.lines}
    comparisons = []
    unknown = set()

    def add(category, title, lines, detail, sources, candidates=None, severity="medium"):
        candidates = candidates or {}
        for line_id, amount in candidates.items():
            disputed[line_id] = max(disputed[line_id], min(by_id[line_id].amount, amount))
        findings.append({
            "id": f"F{len(findings) + 1:03}", "category": category, "title": title,
            "line_ids": lines, "detail": detail, "severity": severity,
            "confidence": "Rule match; requires human review",
            "citations": sources,
            "candidate_amount": money(sum(candidates.values(), ZERO)),
        })

    groups = defaultdict(list)
    for line in bill.lines:
        if line.service_date and line.code != "UNKNOWN":
            groups[(line.code, line.service_date, line.modifiers)].append(line)
        price = kb.prices.get(line.code)
        if price:
            benchmark = Decimal(price["unit_price"]) * line.quantity
            comparisons.append({"line_id": line.line_id, "code": line.code,
                                "billed": money(line.amount), "reference_total": money(benchmark)})
            if line.amount > benchmark * Decimal("1.5"):
                add("overpricing", "Above fictional price threshold", [line.line_id],
                    f"Line {line.line_id} bills ${money(line.amount)} for {line.quantity} unit(s); "
                    f"the fictional reference total is ${money(benchmark)}. "
                    "It exceeds the demo threshold of 150% of reference.",
                    ["POL-PRICE", f"PRICE-{line.code}"],
                    {line.line_id: line.amount - benchmark})
            setting = bill.visit_type.strip().lower()
            if setting in {"inpatient", "outpatient"} and price["visit_type"] not in {"any", setting}:
                add("visit_mismatch", "Visit setting needs clarification", [line.line_id],
                    f"The bill says {setting}; the fictional code reference specifies "
                    f"{price['visit_type']}. Confirm the service setting.",
                    ["POL-VISIT", f"PRICE-{line.code}"])
        else:
            unknown.add(line.code)
        if line.service_date and (
            (bill.visit_start and line.service_date < bill.visit_start) or
            (bill.visit_end and line.service_date > bill.visit_end)
        ):
            add("date_mismatch", "Service date falls outside the visit", [line.line_id],
                f"Service date {line.service_date} is outside the stated visit period. "
                "Ask for clarification; no savings are assumed.", ["POL-DATE"])

    for (code, day, modifiers), lines in groups.items():
        if len(lines) > 1:
            add("duplicate", "Possible repeated charge",
                [line.line_id for line in lines],
                f"Code {code} appears {len(lines)} times on {day} with the same modifiers. "
                "Repeated services can be legitimate; ask for supporting records. "
                f"The demo provisionally retains {lines[0].line_id} and disputes the later entries.",
                ["POL-DUP"], {line.line_id: line.amount for line in lines[1:]}, severity="high")

    bundle = next(policy for policy in kb.policies if policy["id"] == "POL-BUNDLE")
    parent_dates = {line.service_date for line in bill.lines
                    if line.code == bundle["parent"] and line.service_date}
    for line in bill.lines:
        if (line.code in bundle["components"] and line.service_date in parent_dates
                and not (set(line.modifiers.split(",")) & DISTINCT)):
            add("unbundling", "Possible separately billed panel component", [line.line_id],
                f"Code {line.code} appears with {bundle['parent']} on {line.service_date}. "
                "Under the fictional demo policy the panel includes this component. "
                "Ask whether a distinct service justifies the separate charge.",
                ["POL-BUNDLE"], {line.line_id: line.amount}, severity="high")

    total = sum((line.amount for line in bill.lines), ZERO)
    savings = sum(disputed.values(), ZERO)
    return {
        "findings": findings, "total_billed": money(total), "potential_savings": money(savings),
        "illustrative_remaining": money(total - savings), "unknown_codes": sorted(unknown),
        "disputed_by_line": {key: money(value) for key, value in disputed.items()},
        "comparisons": comparisons,
        "limitations": [
            "All prices and policies are fictional educational examples.",
            "Possible billing issues do not establish fraud or a guaranteed refund.",
            "Overlapping findings use the largest disputed amount per line, not their sum [POL-SAVINGS].",
            "Missing service dates and differing modifiers do not establish duplicates.",
            "Credits and negative adjustment lines are not supported in this demo.",
        ],
    }
