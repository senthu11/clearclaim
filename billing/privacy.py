"""Cloud boundary: reconstruct only fixed synthetic examples, never user data.

This is data isolation, not a claim that redaction or HIPAA de-identification
has succeeded. Uploaded content is never eligible for cloud processing.
"""

from dataclasses import dataclass

from billing.audit import audit_bill
from billing.knowledge import KnowledgeBase, context_text
from billing.models import Bill
from billing.samples import SAMPLE_LINES, sample_bill

QUESTIONS = {
    "overview": "Explain this fixed synthetic bill and its computed findings.",
    "duplicate": "Explain possible duplicate charges and questions for the billing office.",
    "pricing": "Explain fictional reference pricing, quantities, and the price threshold.",
    "bundling": "Explain the fictional panel and separately billed component rule.",
    "dates": "Explain the fixed synthetic example's date and visit-setting mismatches.",
    "savings": "Explain how the illustrative reduction avoids overlapping amounts.",
    "letter": "Explain how to review the classroom dispute-letter draft.",
}
WEB_QUERIES = {
    "overview": "site:cms.gov understanding medical bills",
    "duplicate": "site:cms.gov duplicate medical bill charges explanation",
    "pricing": "site:cms.gov medical bill charges explanation",
    "bundling": "site:cms.gov medical billing bundled services explanation",
    "dates": "site:cms.gov checking medical bill service dates",
    "savings": "site:cms.gov reviewing medical billing errors",
    "letter": "site:cms.gov disputing medical billing errors",
}


@dataclass(frozen=True)
class SyntheticRequest:
    sample_name: str
    purpose: str
    intent: str = "overview"


def request_for_bill(bill, sample_name, purpose, intent="overview"):
    """Changed samples and every upload use the local path."""
    if sample_name not in SAMPLE_LINES:
        return None
    actual = Bill.model_validate(bill).model_dump(mode="json")
    expected = sample_bill(sample_name).model_dump(mode="json")
    if actual != expected:
        return None
    return SyntheticRequest(sample_name, purpose, intent)


def model_payload(request):
    """Only fixed sample names/tasks/intents cross this boundary.

    No caller-supplied bill, text, description, question, history, or evidence
    is accepted. Reconstruct all content from the trusted bundled corpus.
    """
    if (type(request) is not SyntheticRequest or request.sample_name not in SAMPLE_LINES
            or request.purpose not in {"extractor", "auditor", "advocate", "chat"}
            or request.intent not in QUESTIONS):
        raise ValueError("Only fixed built-in synthetic requests are permitted.")
    fixture = sample_bill(request.sample_name)
    data = fixture.model_dump(mode="json")
    kb = KnowledgeBase()
    # Even fictional patient/provider/account names are unnecessary to cloud calls.
    safe_bill = {key: data[key] for key in ("visit_type", "visit_start", "visit_end", "lines")}
    if request.purpose == "extractor":
        return {"synthetic_demo": True, "purpose": "extractor", "lines": data["lines"]}
    audit = audit_bill(fixture, kb)
    docs = {doc.metadata["source_id"]: doc for doc in kb.retrieve(
        QUESTIONS[request.intent] + " " + " ".join(line.code for line in fixture.lines), k=6)}
    for source in {sid for finding in audit["findings"] for sid in finding["citations"]} | {"POL-SAVINGS", "POL-DISPUTE"}:
        docs[source] = kb.get(source)
    return {
        "synthetic_demo": True, "purpose": request.purpose, "bill": safe_bill,
        "audit": audit, "question": QUESTIONS[request.intent],
        "evidence": context_text(docs.values()),
    }


def question_intent(question):
    """Classify locally into fixed topics; never forward the question's text."""
    text = question.lower()
    for intent, words in (
        ("bundling", ("glucose", "82947", "82565", "80053", "panel", "bundl")),
        ("duplicate", ("duplicat", "repeat")),
        ("savings", ("saving", "reduc", "double", "overlap")),
        ("pricing", ("pric", "benchmark", "quantity", "quantities", "reference", "overcharg")),
        ("dates", ("date", "visit", "setting", "inpatient", "outpatient")),
        ("letter", ("letter", "dispute", "billing office")),
        ("overview", ("explain", "flag", "bill", "charge", "issue", "report")),
    ):
        if any(word in text for word in words):
            return intent
    return None
