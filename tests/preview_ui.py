"""Visual QA harness for real UI components, independent of the graph runtime.

Run with: .venv/Scripts/python -m streamlit run tests/preview_ui.py
This is not an end-to-end application test.
"""
import json
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import streamlit as st
from billing.audit import audit_bill
from billing.design import apply_design, dashboard
from billing.samples import sample_bill, sample_document, sample_text
from billing.workspace import confirm_charges, report_questions

st.set_page_config(page_title="ClearClaim · Component QA", layout="wide")
apply_design()
kb = SimpleNamespace(
    prices={row["code"]: row for row in json.loads((ROOT / "data/pricing.json").read_text())},
    policies=json.loads((ROOT / "data/policies.json").read_text()))
st.caption("UI component preview · synthetic data · workflow integration is not exercised here")
with st.container(key="app_header"):
    st.markdown(":material/verified_user: **ClearClaim**")
    page = st.radio("Preview page", ["Overview", "Evidence workspace", "Report"], horizontal=True)
bill = sample_bill("Issues to find").model_dump(mode="json")
if page == "Overview":
    dashboard(kb)
elif page == "Evidence workspace":
    st.session_state.result = {"raw_text": sample_text("Issues to find")}
    st.session_state.source_document = {"content": sample_document("Issues to find"), "filename": "synthetic-bill.pdf"}
    st.title("A clearer view of every charge.")
    st.write("Keep the source beside the extracted fields. Correct a charge before continuing.")
    submitted, _, _ = confirm_charges(bill)
    if submitted:
        st.info("Form submitted in component preview. No audit workflow was started.")
else:
    st.title("Here’s what to ask about.")
    audit = audit_bill(sample_bill("Issues to find"), kb)
    columns = st.columns(3)
    columns[0].metric("Total billed", "$" + audit["total_billed"])
    columns[1].metric("Illustrative potential reduction", "$" + audit["potential_savings"])
    columns[2].metric("Issues to review", len(audit["findings"]))
    st.caption("Fictional references · overlapping findings count once · no savings are guaranteed")
    report_questions(audit)
