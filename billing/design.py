"""ClearClaim dashboard, built with native Streamlit controls and local data."""

from html import escape
from pathlib import Path
from uuid import uuid4

import pandas as pd
import altair as alt
import streamlit as st

from billing.audit import audit_bill
from billing.models import money
from billing.samples import SAMPLE_LINES, sample_bill, sample_text, sample_document
from billing.person import person_details
from billing.excel import workbook_bytes, MIME as EXCEL_MIME


def apply_design():
    css = (Path(__file__).resolve().parents[1] / "assets/clearclaim.css").read_text(encoding="utf-8")
    st.html(f"<style>{css}</style>")


def new_bill(sample=None, upload=False):
    """Navigation callback; do not call a model merely by selecting a case."""
    for key in ("graph", "graph_config", "model", "result", "charge_editor", "source_document", "source_page"):
        st.session_state.pop(key, None)
    for key in list(st.session_state):
        if key.startswith(("review_", "local_letter_", "unlock_")) or key in ("bill_upload",):
            st.session_state.pop(key, None)
    st.session_state["stage"] = "upload"
    st.session_state["messages"] = []
    st.session_state["navigation"] = "Investigations"
    if sample:
        st.session_state["sample_scenario"] = sample
        st.session_state["bill_source"] = "Use a synthetic sample"
    elif upload:
        st.session_state["bill_source"] = "Upload a bill"


def clear_review():
    from billing.person import clear_person
    clear_person()
    new_bill()

def view_all_cases():
    st.session_state["queue_search"] = ""
    st.session_state["queue_status"] = "All"


def open_investigation(sample, kb):
    """Open the selected demo at its review checkpoint, entirely locally."""
    from langsmith import tracing_context
    from billing.workflow import build_graph

    graph = build_graph(None, kb)
    config = {"configurable": {"thread_id": str(uuid4())}}
    with tracing_context(enabled=False):
        graph.invoke({"raw_text": sample_text(sample)}, config)
    result = graph.get_state(config).values
    new_bill(sample)
    st.session_state.update(graph=graph, graph_config=config, model=None,
                            result=result, stage="review",
                            source_document={"content": sample_document(sample), "filename": "synthetic-bill.pdf"})


def mark_reviewed(case_id):
    reviewed = set(st.session_state.get("reviewed_demo_cases", []))
    reviewed.add(case_id)
    st.session_state["reviewed_demo_cases"] = sorted(reviewed)


def case_panel(selected, kb):
    st.caption("BILL ANALYSIS")
    st.subheader(selected["id"])
    st.badge(selected["status"], color="orange" if selected["status"] == "Needs review" else "green")
    with st.container(border=True, key="risk_indicator"):
        chart_column, description = st.columns([1, 1.35])
        values = pd.DataFrame({"status": ["Flagged", "Unflagged"],
                               "count": [selected["flagged_lines"], selected["lines"] - selected["flagged_lines"]]})
        chart = alt.Chart(values).mark_arc(innerRadius=32, outerRadius=40).encode(
            theta=alt.Theta("count:Q", stack=True),
            color=alt.Color("status:N", scale=alt.Scale(domain=["Flagged", "Unflagged"],
                            range=["#df713c", "#e5eeea"]), legend=None),
        )
        text = alt.Chart(pd.DataFrame({"label": [f"{selected['flagged_lines']}/{selected['lines']}"]})).mark_text(
            font="Segoe UI", fontSize=20, fontWeight=600, color="#102d35").encode(text="label:N")
        chart_column.altair_chart((chart + text).properties(height=105).configure_view(strokeWidth=0),
                                  width="stretch", theme=None)
        description.caption("Lines flagged")
        description.markdown("**Requires review**" if selected["flagged_lines"] else "**No rule matches**")
        description.caption("Rule indicators, not a fraud probability")
    st.divider()
    st.markdown("**Why this was flagged**" if selected["audit"]["findings"] else "**No rule matches**")
    seen = set()
    for finding in sorted(selected["audit"]["findings"], key=lambda f: f["severity"] != "high"):
        if finding["category"] in seen:
            continue
        seen.add(finding["category"])
        number, detail = st.columns([.17, 1])
        number.badge(str(len(seen)), color="orange")
        detail.markdown(f"**{finding['title']}**")
        detail.caption("Evidence: " + ", ".join(finding["citations"]))
        if len(seen) == 3:
            break
    if not seen:
        st.caption("These limited fictional checks found no issues. Review the source bill before drawing a conclusion.")
    st.button("Open investigation", key="open_selected_case", icon=":material/arrow_forward:",
              width="stretch", type="primary", on_click=open_investigation, args=(selected["name"], kb))
    st.button("Mark as reviewed", icon=":material/check:", width="stretch",
              disabled=selected["status"] == "Reviewed", on_click=mark_reviewed, args=(selected["id"],))
    st.caption("Review status applies to this demo session. It does not resolve or remove findings.")


def demo_cases(kb):
    cases = []
    for i, name in enumerate(SAMPLE_LINES, 1):
        bill = sample_bill(name)
        audit = audit_bill(bill, kb)
        flagged = {line_id for item in audit["findings"] for line_id in item["line_ids"]}
        cases.append({"id": f"DEMO-{i:03}", "name": name, "provider": bill.provider,
                      "audit": audit, "flagged_lines": len(flagged), "lines": len(bill.lines),
                      "status": "Needs review" if audit["findings"] else "Clear"})
    return cases


def dashboard(kb):
    cases = demo_cases(kb)
    for item in cases:
        if item["id"] in st.session_state.get("reviewed_demo_cases", []):
            item["status"] = "Reviewed"
    with st.container(key="overview_hero"):
        left, right = st.columns([5, 1])
        with left:
            st.markdown('<p class="eyebrow">A LITTLE CLARITY GOES A LONG WAY</p>', unsafe_allow_html=True)
            person = st.session_state.get("local_person", {})
            first_name = person.get("name", "").split()
            heading = f"Welcome, {first_name[0]}" if first_name else "Understand your bill. Know what to ask."
            st.markdown(f"<h1>{escape(heading)}</h1>", unsafe_allow_html=True)
            st.markdown('<p class="hero-description">Review possible billing issues, understand the evidence, and prepare your next step.</p>', unsafe_allow_html=True)
        with right:
            st.button("Analyze a bill", icon=":material/upload_file:", type="primary", width="stretch", on_click=new_bill)
            st.download_button("Download Excel", workbook_bytes(st.session_state.get("local_person", {}),
                               st.session_state.get("result"), kb), "clearclaim-details.xlsx", EXCEL_MIME,
                               icon=":material/table_view:", width="stretch")
    person_details()
    from decimal import Decimal
    example = cases[0]["audit"]
    metrics = [
        ("billed", "receipt_long", "Example bill total", f"${example['total_billed']}", "Issues-to-find synthetic scenario"),
        ("exposure", "verified_user", "Illustrative reduction", f"${example['potential_savings']}", "Fictional references · not guaranteed"),
        ("review", "fact_check", "Findings to understand", str(len(example['findings'])), "Some findings overlap"),
    ]
    for column, (key, icon, label, value, note) in zip(st.columns(3), metrics):
        with column, st.container(border=True, key=f"summary_{key}"):
            st.markdown(f":material/{icon}:")
            st.caption(label)
            st.markdown(f'<p class="stat-value">{escape(value)}</p>', unsafe_allow_html=True)
            st.caption(note)
    with st.container(key="dashboard_body"):
        queue, panel = st.columns([1.7, 1], gap="large")
        with queue, st.container(border=True, key="queue_panel"):
            heading, more = st.columns([4, 1])
            heading.subheader("Investigation queue")
            heading.caption("Explore synthetic scenarios and the billing signals behind each finding")
            more.button("View all", icon=":material/arrow_forward:", type="tertiary", on_click=view_all_cases)
            search_column, filter_column = st.columns([1.5, 1])
            query = search_column.text_input("Search claims or providers", placeholder="Search claims or providers", label_visibility="collapsed", key="queue_search")
            status = filter_column.radio("Queue status", ["All", "Needs review", "Clear", "Reviewed"], horizontal=True, label_visibility="collapsed", key="queue_status")
            visible = [item for item in cases if (status == "All" or item["status"] == status)
                       and query.casefold() in f"{item['id']} {item['name']} {item['provider']}".casefold()]
            st.session_state.setdefault("selected_case", cases[0]["name"])
            if visible and st.session_state.selected_case not in {item["name"] for item in visible}:
                st.session_state.selected_case = visible[0]["name"]
            if not visible:
                st.info("No scenarios match your search. Try a different name or status.")
            for index, item in enumerate(visible):
                selected = item["name"] == st.session_state.selected_case
                with st.container(key=f"queue_row_{index}"):
                    icon, title, amount, flags = st.columns([.12, .95, .3, .32])
                    icon.markdown(":material/description:")
                    with title:
                        if st.button(item["provider"], key=f"select_{item['id']}", type="secondary" if selected else "tertiary", width="stretch"):
                            st.session_state.selected_case = item["name"]
                            st.rerun()
                        st.caption(f"{item['id']} · {item['name']}")
                    with amount:
                        st.markdown(f"**${item['audit']['total_billed']}**")
                        st.caption("Fictional billed total")
                    with flags:
                        st.badge(item["status"], color="orange" if item["status"] == "Needs review" else "green")
                        st.caption(f"{len(item['audit']['findings'])} rule findings")
            st.caption("Demo scenarios · not a live claims portfolio")
        with panel, st.container(border=True, key="risk_panel"):
            if visible:
                selected = next(item for item in cases if item["name"] == st.session_state.selected_case)
                case_panel(selected, kb)
            else:
                st.caption("BILL ANALYSIS")
                st.write("No matching bill selected. Clear the search or choose another status.")
    with st.container(border=True, key="upload_callout"):
        text, action = st.columns([5, 1])
        text.markdown(":material/auto_awesome: **Analyze a new medical bill**")
        text.caption("Upload a PDF or bill image for a local review of charges, coding, and possible errors.")
        action.button("Choose a file", icon=":material/upload_file:", width="stretch", on_click=new_bill, kwargs={"upload": True})
    with st.container(key="private_note"):
        st.markdown(":material/verified_user: **Uploads and chat are not sent to an LLM.** Processing occurs where this app runs: your computer for desktop use, or the hosting server for the public demo. Use synthetic data only.")


def providers(kb):
    st.markdown('<p class="eyebrow">REFERENCE WORKSPACE</p>', unsafe_allow_html=True)
    st.title("Providers & reference library")
    st.write("Explore the fictional provider and billing references used in this classroom project.")
    with st.container(border=True):
        st.subheader("Example Learning Clinic")
        st.caption("Fictional provider · 3 bundled scenarios · no real provider profile or performance assessment")
        st.dataframe(pd.DataFrame(kb.prices.values()), hide_index=True, width="stretch")
    for document in kb.documents:
        with st.expander(f"{document.metadata['source_id']} · {document.metadata['title']}"):
            st.write(document.page_content)


def empty_reports():
    st.markdown('<p class="eyebrow">YOUR BILLING REVIEWS</p>', unsafe_allow_html=True)
    st.title("Reports")
    with st.container(border=True):
        st.markdown(":material/summarize: **Your completed review will appear here**")
        st.write("Analyze a bill and confirm its charges to generate a report, evidence, and a dispute letter.")
        st.button("Analyze a bill", type="primary", on_click=new_bill)
    st.caption("Reports are held in this session. They are not saved to a remote account.")
