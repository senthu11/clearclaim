"""Optional real-provider check. Sends only the bundled synthetic bill."""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from langgraph.types import Command

from billing.chat import answer_question
from billing.extraction import read_upload
from billing.knowledge import KnowledgeBase
from billing.llm import NebiusModel, UserError
from billing.samples import sample_document
from billing.workflow import build_graph


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="Qwen/Qwen3-30B-A3B-Instruct-2507")
    parser.add_argument("--chat", action="store_true")
    args = parser.parse_args()
    model = NebiusModel(args.model)
    kb = KnowledgeBase()
    graph = build_graph(model, kb, synthetic_sample="Issues to find")
    config = {"configurable": {"thread_id": "synthetic-live-check"}}
    text = read_upload(sample_document("Issues to find"), "sample.pdf")
    state = graph.invoke({"raw_text": text}, config)
    if not state.get("__interrupt__"):
        raise RuntimeError("Review interrupt was not reached.")
    print("Extractor: review checkpoint reached; lines:", len(state["bill"]["lines"]), flush=True)
    state = graph.invoke(Command(resume=state["bill"]), config)
    assert state["audit"]["total_billed"] == "840.00", "Incorrect extracted bill total"
    assert state["audit"]["potential_savings"] == "340.00", "Unexpected synthetic savings"
    assert state["summary"] and state["letter"]
    print("Auditor: total $840.00; illustrative reduction $340.00; findings:",
          len(state["audit"]["findings"]), flush=True)
    print("Advocate: explanation and dispute letter generated.", flush=True)
    if args.chat:
        result = answer_question(model, kb, state, "Why was the glucose charge flagged?", [])
        assert "POL-BUNDLE" in result["answer"], "Answer did not cite the bundling policy"
        print("Chat: answered with the expected local policy citation.", flush=True)


if __name__ == "__main__":
    try:
        main()
    except UserError as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(1)
