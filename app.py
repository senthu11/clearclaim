"""Streamlit entry point: python -m streamlit run app.py."""

import json
import os
import uuid
from decimal import Decimal

import pandas as pd
import streamlit as st
try:
    import xxhash
except ImportError:
    st.error("The xxhash native dependency could not load. Close the server and run scripts/start.ps1 after repairing the environment with requirements.windows-py312.lock.txt. The supported Windows wheel is xxhash 3.6.0; do not disable Application Control.")
    st.stop()
from langgraph.types import Command
from pydantic import ValidationError
from langsmith import tracing_context

from billing.advocate import report_markdown, draft_letter, local_summary, escape_currency
from billing.chat import answer_question, safe_web_url
from billing.extraction import read_upload, tesseract_path
from billing.knowledge import KnowledgeBase
from billing.llm import NebiusModel, UserError, available_models, provider_settings, disable_external_tracing
from billing.models import Bill, bill_readiness_errors, require_auditable_bill
from billing.samples import SAMPLE_LINES, sample_document
from billing.workflow import build_graph
from billing.design import apply_design, dashboard, providers, empty_reports, new_bill, clear_review
from billing.person import person_details, personalized_bill
from billing.excel import workbook_bytes, MIME as EXCEL_MIME
from billing.workspace import confirm_charges, report_questions, QUESTIONS
from billing.review import snapshot
from billing.review_ui import financial_review, finding_decision, save_review, saved_reviews
from billing.exports import markdown as snapshot_markdown, selected_letter, letter_pdf
from billing.provenance import show_charge_source

st.set_page_config(page_title="ClearClaim · Medical Bill Review", page_icon=":material/verified_user:", layout="wide")
apply_design()
if os.getenv('CLEARCLAIM_PUBLIC_DEMO') == '1':
    st.info('Public educational demo — use synthetic data only. Uploads and entries are processed on the hosting server, not on your device, and are not sent to an LLM. Saved reviews are disabled. Download results before ending your session.')


@st.cache_resource
def knowledge_base():
    return KnowledgeBase()


@st.cache_data
def sample_bytes(name, image=False):
    return sample_document(name, image)


kb = knowledge_base()
ss = st.session_state
ss.setdefault("stage", "upload")
ss.setdefault("messages", [])
if ss.get("pending_navigation"):
    ss.navigation = ss.pop("pending_navigation")


def show_evidence(source_ids):
    for source_id in sorted(set(source_ids)):
        document = kb.get(source_id)
        if document:
            st.markdown(f"**{source_id} · {document.metadata['title']}**")
            st.write(document.page_content)
            st.caption("Reference version: " + document.metadata.get("version", "unknown") + " · Fictional educational data; no payer applicability or clinical effective date.")


def drive_graph(graph_input):
    labels = {"extractor": "Extractor structured the bill", "human_review": "Charge data confirmed",
              "auditor": "Auditor checked charges and retrieved evidence",
              "advocate": "Advocate prepared your report and letter"}
    with st.status("Agents are working…", expanded=True) as status, tracing_context(enabled=False):
        try:
            for update in ss.graph.stream(graph_input, config=ss.graph_config, stream_mode="updates"):
                for node in update:
                    if node in labels:
                        st.write(labels[node])
            ss.result = ss.graph.get_state(ss.graph_config).values
            if "audit" in ss.result:
                ss.stage = "results"
                status.update(label="Bill review complete", state="complete", expanded=False)
            else:
                ss.stage = "review"
                status.update(label="Ready for your review", state="complete", expanded=False)
        except Exception:
            try:
                ss.result = ss.graph.get_state(ss.graph_config).values
            except Exception:
                ss.result = ss.get("result", {})
            ss.stage = "retry" if ss.result.get("bill") else "upload"
            status.update(label="Workflow paused after an error", state="error")
            raise


with st.container(key="app_header"):
    brand, navigation, settings = st.columns([1.2, 4, .8])
    brand.markdown(":material/verified_user: **ClearClaim**")
    page = navigation.radio("Navigation", ["Overview", "Investigations", "Providers", "Reports", "Saved reviews"],
                            horizontal=True, label_visibility="collapsed", key="navigation")

with settings.popover("Settings", icon=":material/tune:", width="stretch"):
    st.markdown("**Workspace settings**")
    st.caption("Synthetic AI demo and local upload processing")
    st.markdown("**Model connection**")
    st.caption("Nebius key configured" if provider_settings()["api_key"] else "Nebius key missing")
    if st.button("Refresh keys and list models", width="stretch"):
        try:
            from dotenv import load_dotenv
            from billing.llm import ROOT
            for env_file in (ROOT / ".local-config/.env", ROOT / ".env"):
                load_dotenv(env_file, override=True)
            disable_external_tracing()
            with st.spinner("Checking Nebius…"):
                ss.model_options = [name for name in available_models() if "embedding" not in name.lower()]
            st.success("Nebius connected")
        except UserError as error:
            st.error(str(error))
    default_model = os.getenv("NEBIUS_MODEL") or "Qwen/Qwen3-30B-A3B-Instruct-2507"
    if ss.get("model_options"):
        options = ss.model_options
        model_name = st.selectbox("Nebius chat model", options,
                                  index=options.index(default_model) if default_model in options else 0)
    else:
        model_name = st.text_input("Nebius chat model", value=default_model)
    st.caption("Model changes apply to the next bill. Current runs keep their selected model.")
    st.divider()
    web_enabled = st.toggle("Web context for chat", value=False)
    st.caption("For unchanged built-in samples only: Keenable receives a fixed public topic query. "
               "Uploaded documents, typed questions, and conversation are never forwarded.")
    if web_enabled and not (os.getenv("KEENABLE_API_KEY") or os.getenv("KEENABLE")):
        st.warning("Add KEENABLE_API_KEY to enable web search.")
    st.divider()
    st.caption("Local RAG · lexical vectors · no embedding API key")
    st.caption("OCR · Tesseract" if tesseract_path() else "OCR · bundled local CPU engine")
    st.button("Start a new bill", width="stretch", on_click=new_bill)
    st.button("Clear this review and personal details", on_click=clear_review)
    st.caption("Clears this session’s source, charges, notes and chat. Saved encrypted snapshots and downloaded files must be deleted separately.")

if page == "Saved reviews":
    saved_reviews()
    st.stop()

if page == "Overview":
    dashboard(kb)
    st.stop()
if page == "Providers":
    providers(kb)
    st.stop()
if page == "Reports" and ss.stage != "results":
    empty_reports()
    st.stop()

with st.container(key="workflow_heading"):
    introduction, privacy_note = st.columns([3.5, 1.4], gap="large")
    with introduction:
        st.markdown('<p class="eyebrow">PRIVATE BILL REVIEW</p>', unsafe_allow_html=True)
        st.title("Here’s what to ask about." if ss.stage == "results" else
                 "A clearer view of every charge." if ss.stage == "review" else "Your bill, explained.")
        st.write("Keep the source beside the extracted fields. Correct a charge before continuing."
                 if ss.stage == "review" else
                 "Review the evidence, understand each finding, and prepare your next step.")
        st.caption(":material/info: Educational review only. A flagged charge can reflect missing context—not proof of fraud.")
    with privacy_note, st.container(key="workflow_privacy"):
        st.markdown(":material/lock: **Your files stay in this session**")
        st.caption("Uploads, personal details, and chat wording stay local. Only fixed synthetic examples may use cloud AI.")

steps = ["Add your bill", "Review charges", "Build your report"]
active = {"upload": 0, "review": 1, "retry": 2, "results": 2}[ss.stage]
with st.container(key="workflow_steps"):
    for i, column in enumerate(st.columns(3)):
        with column, st.container(key=f"workflow_step_{i}"):
            st.caption(f"STEP {i + 1}")
            icon = "check_circle" if i < active else "radio_button_checked" if i == active else "radio_button_unchecked"
            st.markdown(f":material/{icon}: **{steps[i]}**")
st.divider()

workspace, knowledge, architecture = st.tabs(["Bill workspace", "Reference library", "How the agents work"])

with knowledge:
    st.subheader("The local RAG knowledge base")
    st.write("The Auditor and bill chat retrieve these fictional documents. Procedure codes also use "
             "exact lookups so a similar text match cannot supply another procedure’s price.")
    st.dataframe(pd.DataFrame(kb.prices.values()), hide_index=True, width="stretch")
    search = st.text_input("Search the reference library", placeholder="For example: duplicate charges or 99213")
    documents = kb.retrieve(search) if search.strip() else kb.documents
    for document in documents:
        with st.expander(f"{document.metadata['source_id']} · {document.metadata['title']}"):
            st.write(document.page_content)

with architecture:
    st.subheader("A coordinated three-agent workflow")
    st.graphviz_chart('''digraph {
        rankdir=LR; node [shape=box, style=rounded];
        upload [label="PDF / image"];
        extract [label="Extractor agent\nLocal text / OCR → validated charges"];
        review [label="Human review\nLangGraph interrupt", color="#0d9488"];
        audit [label="Auditor agent\nRules + RAG + LLM reasoning"];
        advocate [label="Advocate agent\nExplanation + letter"];
        kb [label="Synthetic reference library\nLocal vector retrieval", shape=cylinder];
        chat [label="Bill chat\nRAG + optional Keenable"];
        upload -> extract -> review -> audit -> advocate;
        kb -> audit; kb -> chat; advocate -> chat;
    }''')
    st.write("**LangGraph** passes shared state between agents and pauses for charge confirmation. "
             "**LangChain** connects Nebius and the local vector store. **Python rules** calculate "
             "the disputed amounts; the agents explain the evidence and uncertainties.")
    st.caption("Uploads, personal metadata, source text, and chat stay in local session memory. "
               "Only built-in synthetic fixtures may use Nebius. Edited fixtures automatically use local rules. "
               "No document classifier or redaction claim grants cloud access.")

with workspace:
    if ss.stage == "upload":
        person_details()
        st.subheader("Start with a bill")
        st.caption("Try the guided sample, or choose a bill from your device for a local review.")
        source = st.radio("Bill source", ["Use a synthetic sample", "Upload a bill"], horizontal=True, key="bill_source")
        content, filename, trusted_sample = None, "", None
        if source == "Use a synthetic sample":
            left, right = st.columns([2, 1])
            with left:
                sample = st.selectbox("Sample scenario", list(SAMPLE_LINES), key="sample_scenario")
                trusted_sample = sample
                st.caption({"Issues to find": "Includes repeated charges, fictional overpricing, a panel component, "
                            "and inconsistent dates and visit setting.",
                            "Clean comparison": "A comparison bill with no matches to the demo’s issue rules.",
                            "Distinct services": "Modifiers distinguish repeated codes and separately billed services."
                            }[sample])
            with right:
                sample_format = st.selectbox("Format", ["Digital PDF", "Image (PNG)"])
            is_image = sample_format == "Image (PNG)"
            content = sample_bytes(sample, is_image)
            filename = "synthetic-bill.png" if is_image else "synthetic-bill.pdf"
            if is_image:
                st.image(content, caption="Synthetic sample for OCR", width=900)
            use_cloud = st.checkbox("Use cloud AI for this fixed synthetic sample", value=False)
            st.caption("Leave this off to explore the complete review locally without an API key.")
        else:
            uploaded = st.file_uploader("Upload a synthetic bill", type=["pdf", "png", "jpg", "jpeg", "webp", "tif", "tiff"], key="bill_upload", accept_multiple_files=True)
            st.caption("Up to 15 MB, 20 PDF pages, or a 25-megapixel image. Use synthetic data for this class demo.")
            st.caption("Uploads use local OCR and a conservative table parser, then manual review. "
                       "Unrecognized layouts need manual charge entry. No upload is sent to any LLM or web search.")
            if uploaded:
                documents = uploaded if isinstance(uploaded, list) else [uploaded]
                if len(documents) > 10:
                    st.error("Select at most 10 statements. Statements are reviewed separately, never automatically merged.")
                else:
                    selected_document = st.selectbox("Statement to review", range(len(documents)), format_func=lambda i: documents[i].name)
                    content, filename = documents[selected_document].getvalue(), documents[selected_document].name
                    st.caption("Each statement is audited independently. Save the completed review before starting another statement; do not add totals across overlapping statements.")
        actions = st.container(horizontal=True, key="bill_actions")
        if source == "Use a synthetic sample":
            actions.download_button("Download this sample", content, filename,
                                     mime="image/png" if is_image else "application/pdf", icon=":material/download:")
        if actions.button("Extract bill charges", type="primary", disabled=content is None, icon=":material/auto_awesome:"):
            try:
                model = NebiusModel(model_name) if trusted_sample and use_cloud else None
                with st.spinner("Reading document and running OCR when needed…"):
                    import hashlib
                    cache_key = hashlib.sha256(content).hexdigest()
                    cached = ss.get("review_ocr_cache", {})
                    if cached.get("key") == cache_key:
                        text = cached["text"]
                    else:
                        progress = st.progress(0, text="Reading document")
                        text = read_upload(content, filename, lambda page, count: progress.progress(page / count, text=f"Reading page {page} of {count}"))
                        ss.review_ocr_cache = {"key": cache_key, "text": text}
                        progress.empty()
                for key in list(ss):
                    if key.startswith(("review_", "local_letter_")) and key != "review_ocr_cache":
                        ss.pop(key, None)
                ss.source_document = {"content": content, "filename": filename}
                ss.graph = build_graph(model, kb, synthetic_sample=trusted_sample)
                ss.model = model
                ss.graph_config = {"configurable": {"thread_id": str(uuid.uuid4())}}
                ss.messages = []
                drive_graph({"raw_text": text})
                st.rerun()
            except UserError as error:
                st.error(str(error))
            except Exception:
                st.error("Extraction could not finish. Check the document and model connection, then retry.")

    elif ss.stage == "review":
        original = ss.result["bill"]
        submitted, edited, metadata = confirm_charges(original)
        if submitted:
            try:
                records = json.loads(edited.to_json(orient="records"))
                for row in records:
                    row["service_date"] = row.get("service_date") or None
                    row["modifiers"] = row.get("modifiers") or ""
                corrected = Bill.model_validate({**original, **metadata, "lines": records})
                require_auditable_bill(corrected)
                from billing.review import amount
                stated = ss.get("review_statement_total", "").strip()
                if stated:
                    difference = amount(stated) - sum(line.amount for line in corrected.lines)
                    if difference and not ss.get("review_reconciliation_note", "").strip():
                        raise ValueError(f"Charge rows differ from the statement by USD {difference}. Correct missing rows or explain the difference before continuing.")
                    ss.setdefault("review_meta", {})["financial"] = {"statement_total": str(amount(stated)), "note": ss.get("review_reconciliation_note", "")}
                drive_graph(Command(resume=corrected.model_dump(mode="json")))
                st.rerun()
            except ValidationError:
                st.error("Check the table: use unique nonblank line IDs, ISO dates, whole quantities "
                         "of 1–1000, and nonnegative amounts with at most two decimal places.")
            except UserError as error:
                st.error(str(error))
            except ValueError as error:
                st.error(str(error))
            except Exception:
                st.error("The audit could not finish. Your confirmed data is preserved; retry the workflow.")

    elif ss.stage == "retry":
        st.subheader("Resume your bill review")
        st.info("The last agent call failed. Confirmed charges are preserved in this session.")
        if st.button("Retry remaining agents", type="primary"):
            try:
                drive_graph(None)
                st.rerun()
            except UserError as error:
                st.error(str(error))
            except Exception:
                st.error("The workflow could not resume. Check the model connection or start a new bill.")

    elif ss.stage == "results":
        from billing.report_ui import render_results
        render_results(kb, web_enabled, show_evidence)
