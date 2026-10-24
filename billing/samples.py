"""Generate deterministic, clearly labeled sample documents in memory."""

import pymupdf as fitz

SAMPLE_LINES = {
    "Issues to find": [
        ("99213", "Office visit", "2026-10-01", 1, "200.00", ""),
        ("99213", "Office visit repeated", "2026-10-01", 1, "200.00", ""),
        ("80053", "Metabolic panel", "2026-10-01", 1, "70.00", ""),
        ("82947", "Glucose component", "2026-10-01", 1, "40.00", ""),
        ("71046", "Chest X ray", "2026-10-03", 1, "80.00", ""),
        ("99223", "Hospital evaluation", "2026-10-01", 1, "250.00", ""),
    ],
    "Clean comparison": [
        ("99213", "Office visit", "2026-10-01", 1, "100.00", ""),
        ("80053", "Metabolic panel", "2026-10-01", 1, "50.00", ""),
        ("85025", "Blood count", "2026-10-01", 2, "60.00", ""),
    ],
    "Distinct services": [
        ("99213", "Office visit", "2026-10-01", 1, "100.00", ""),
        ("99213", "Separate office service", "2026-10-01", 1, "100.00", "25"),
        ("80053", "Metabolic panel", "2026-10-01", 1, "50.00", ""),
        ("82947", "Distinct glucose service", "2026-10-01", 1, "10.00", "59"),
    ],
}


def sample_text(name):
    rows = SAMPLE_LINES[name]
    lines = ["SYNTHETIC MEDICAL BILL - CLASSROOM DEMO", "All people, services and prices are fictional.",
             "Patient: Alex Example", "Provider: Example Learning Clinic", "Account: SYN-2026-001",
             "Visit type: outpatient", "Visit start: 2026-10-01", "Visit end: 2026-10-01", "",
             "Code | Description | Service date | Quantity | Billed line total USD | Modifier"]
    lines += [" | ".join(map(str, row)) for row in rows]
    from decimal import Decimal
    lines += ["", f"TOTAL BILLED USD: {sum(Decimal(row[4]) for row in rows):.2f}",
              "No insurance payment or patient responsibility is shown."]
    return "\n".join(lines)


def sample_document(name, image=False):
    with fitz.open() as document:
        page = document.new_page(width=792, height=612)
        page.insert_text((36, 48), sample_text(name), fontsize=10, fontname="cour", lineheight=1.8)
        if image:
            return page.get_pixmap(dpi=180, alpha=False).tobytes("png")
        return document.tobytes()


def sample_bill(name):
    """Trusted server-side fixture, never populated from an uploaded document."""
    from billing.models import Bill
    return Bill.model_validate({
        "patient": "Alex Example", "provider": "Example Learning Clinic", "account": "SYN-2026-001",
        "visit_type": "outpatient", "visit_start": "2026-10-01", "visit_end": "2026-10-01",
        "lines": [dict(line_id=f"L{i:03}", code=row[0], description=row[1], service_date=row[2],
                       quantity=row[3], amount=row[4], modifiers=row[5])
                  for i, row in enumerate(SAMPLE_LINES[name], 1)],
    })
