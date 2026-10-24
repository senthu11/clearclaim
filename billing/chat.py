"""Local question routing; cloud answers use fixed synthetic fixtures only."""

import json
import os
from urllib.parse import urlparse

from billing.advocate import local_summary, supported_citations
from billing.llm import UserError
from billing.privacy import WEB_QUERIES, question_intent, request_for_bill


def safe_web_url(value):
    url = str(value or "")
    return url if urlparse(url).scheme in {"http", "https"} else ""


def answer_question(model, kb, state, question, history, web=False):
    if not question.strip() or len(question) > 3000:
        raise UserError("Enter a question of 1 to 3,000 characters.")
    intent = question_intent(question)
    request = request_for_bill(state["bill"], state.get("synthetic_sample"), "chat", intent or "overview")
    cloud = bool(model is not None and state.get("cloud_eligible") and request is not None and intent)
    # Neither question nor history is included in a provider request.
    ids = {sid for item in state["audit"]["findings"] for sid in item["citations"]}
    ids.update({"POL-SAVINGS", "POL-DISPUTE"})
    sources = [{"id": sid, "title": kb.get(sid).metadata["title"],
                "text": kb.get(sid).page_content, "kind": "synthetic"} for sid in sorted(ids)]
    warning = None
    if cloud:
        try:
            answer = model.text(
                "Explain only the supplied fixed synthetic example and fixed topic. Cite the supplied "
                "source IDs in square brackets. All reference data is fictional. Do not invent medical "
                "or legal conclusions, personal details, prices, sources, or guaranteed savings. "
                "No user question or conversation is supplied. Keep the answer concise.", request)
            answer = supported_citations(answer, {doc.metadata["source_id"] for doc in kb.documents})
        except UserError:
            answer = local_summary(state['audit'])
            warning = 'Optional AI answer unavailable; showing the local audit summary. You can retry your question.'
            cloud = False
    elif intent:
        categories = {"bundling": {"unbundling"}, "duplicate": {"duplicate"},
                      "pricing": {"overpricing"}, "dates": {"date_mismatch", "visit_mismatch"}}
        selected = categories.get(intent)
        if selected:
            matches = [item for item in state["audit"]["findings"] if item["category"] in selected]
            answer = "**Local answer.** " + ("\n\n".join(
                item["detail"] + " " + " ".join(f"[{sid}]" for sid in item["citations"])
                for item in matches) if matches else "No findings of that type matched the demo rules.")
        elif intent == "letter":
            answer = ("**Local answer.** Review the draft in the Dispute letter tab. "
                      "Ask for an itemized explanation and supporting records. "
                      "The letter is composed locally and is not sent automatically [POL-DISPUTE].")
        else:
            answer = local_summary(state["audit"])
    else:
        answer = ("Your question stayed local. I can explain duplicate charges, fictional pricing, "
                  "bundling, date mismatches, the potential reduction, or the dispute letter. "
                  "Please ask about one of those topics.")
    if web and not cloud:
        warning = "External search is disabled for uploads, changed samples, and unrecognized topics; processed locally."
    elif web:
        key = os.getenv("KEENABLE_API_KEY") or os.getenv("KEENABLE")
        if not key:
            warning = "Keenable key is missing; no web search was made."
        else:
            try:
                from langchain_keenable import KeenableSearch
                # A fixed public query only: never forward the question, history, or bill.
                results = KeenableSearch(api_key=key, timeout=20, handle_tool_error=False).invoke(
                    {"query": WEB_QUERIES[intent]})
                if isinstance(results, str):
                    results = json.loads(results)
                if isinstance(results, dict):
                    results = results.get("results", [])
                if not isinstance(results, list):
                    raise ValueError("Unexpected search format")
                for i, item in enumerate(results[:3], 1):
                    sources.append({"id": f"WEB-{i}", "title": str(item.get("title", "Public source")),
                                    "url": safe_web_url(item.get("url")), "kind": "web",
                                    "text": str(item.get("snippet") or item.get("description") or "")[:3000]})
                warning = "Public links use a fixed topic search. Search results were not sent to the LLM."
            except Exception:
                warning = "Web search was unavailable; the answer uses only local reference evidence."
    return {"answer": answer, "sources": sources, "warning": warning}
