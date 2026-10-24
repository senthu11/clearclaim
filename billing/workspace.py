"""Local document preview and charge confirmation for the Evidence workspace."""

import io
from pathlib import Path

import pandas as pd
import pymupdf
import streamlit as st
from PIL import Image, ImageOps

from billing.models import Bill, bill_readiness_errors


def preview_page(content, filename, page_number=0):
    """Rasterize only the selected page; never embed active PDF content or URLs."""
    if Path(filename).suffix.lower() == ".pdf":
        with pymupdf.open(stream=content, filetype="pdf") as document:
            page = document[page_number]
            scale = min(1.5, 1400 / max(page.rect.width, page.rect.height))
            return page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), alpha=False).tobytes("png")
    with Image.open(io.BytesIO(content)) as image:
        image = ImageOps.exif_transpose(image).convert("RGB")
        image.thumbnail((1400, 1800))
        output = io.BytesIO()
        image.save(output, format="PNG")
        return output.getvalue()


def source_preview():
    st.caption("SOURCE DOCUMENT")
    st.subheader("Compare with your bill")
    source = st.session_state.get("source_document")
    if source:
        st.caption(source["filename"])
        image_tab, text_tab = st.tabs(["Document", "Extracted text"])
        with image_tab:
            try:
                page_number = 0
                if Path(source["filename"]).suffix.lower() == ".pdf":
                    with pymupdf.open(stream=source["content"], filetype="pdf") as document:
                        count = document.page_count
                    if count > 1:
                        page_number = st.selectbox("Source page", range(count),
                                                   format_func=lambda n: f"Page {n + 1} of {count}",
                                                   key="source_page")
                st.image(preview_page(source["content"], source["filename"], page_number),
                         caption="Original source · stored only in this session", width="stretch")
                st.caption("Use the image’s Fullscreen control for small print, or switch to Extracted text.")
            except Exception:
                st.warning("Document preview is unavailable. Compare the extracted text with your original file.")
        with text_tab:
            st.text(st.session_state.result["raw_text"])
    else:
        st.text(st.session_state.result["raw_text"])
    st.caption("Repeated services may be legitimate. Check dates, quantities, and modifiers before continuing.")


def confirm_charges(original):
    """Return submitted form values; validation and graph resume remain in the caller."""
    errors = bill_readiness_errors(Bill.model_validate(original))
    with st.container(key="evidence_workspace"):
        source, editor = st.columns([1, 1.25], gap="large")
        with source, st.container(border=True, key="source_panel"):
            source_preview()
            with st.expander("Find a charge on the original PDF"):
                from billing.provenance import show_charge_source
                show_charge_source(original["lines"], "review_confirm_source")
        with editor, st.container(border=True, key="charge_panel"):
            st.caption("EXTRACTED CHARGES")
            st.subheader("Check the details")
            st.write("Edit any cell to correct it. Amounts are billed line totals in USD, not unit prices.")
            for note in original.get("extraction_notes", []):
                st.warning(note)
            if errors:
                st.error("Audit paused: enter the actual charges from the source bill before continuing.")
                for error in errors:
                    st.caption(error)
            uncertain = [{"line": row["line_id"], "fields to verify": ", ".join(field for field in ("code", "description", "service_date") if not row.get(field) or row.get(field) == "UNKNOWN")}
                         for row in original["lines"]]
            uncertain = [row for row in uncertain if row["fields to verify"]]
            if uncertain:
                st.warning("Some extracted fields are missing. No numeric OCR confidence is assumed.")
                st.dataframe(uncertain, hide_index=True)
            with st.form("confirm_bill"):
                statement_total = st.text_input("Statement charge total USD (optional)", key="review_statement_total")
                reconciliation_note = st.text_input("Explain any difference from the charge total", key="review_reconciliation_note")
                rows = pd.DataFrame(original["lines"])
                rows["service_date"] = rows["service_date"].fillna("")
                edited = st.data_editor(
                    rows, num_rows="dynamic", hide_index=True, width="stretch", key="charge_editor",
                    column_order=["line_id", "description", "amount", "code", "service_date", "quantity", "modifiers"],
                    column_config={
                        "amount": st.column_config.TextColumn("Line total USD", required=True),
                        "line_id": st.column_config.TextColumn("Line", required=True),
                        "code": st.column_config.TextColumn("Code"),
                        "description": st.column_config.TextColumn("Service"),
                        "service_date": st.column_config.TextColumn("Date (YYYY-MM-DD)"),
                        "modifiers": st.column_config.TextColumn("Modifiers"),
                        "quantity": st.column_config.NumberColumn("Qty", min_value=1, step=1),
                    })
                st.caption("Scroll the charge table to check codes, dates and modifiers. Add or delete rows as needed; line IDs must be unique.")
                with st.expander("Patient & visit details"):
                    patient = st.text_input("Patient", original["patient"])
                    provider = st.text_input("Provider", original["provider"])
                    account = st.text_input("Account", original["account"])
                    options = ["unknown", "outpatient", "inpatient"]
                    visit_type = st.selectbox("Visit setting", options,
                                              index=options.index(original["visit_type"])
                                              if original["visit_type"] in options else 0)
                    visit_start = st.text_input("Visit start (YYYY-MM-DD or blank)", original["visit_start"] or "")
                    visit_end = st.text_input("Visit end (YYYY-MM-DD or blank)", original["visit_end"] or "")
                st.caption("Confirm against the source document. Editing a synthetic sample switches the remaining review to local processing.")
                submitted = st.form_submit_button(
                    "Check charges and continue" if errors else "Confirm charges and run audit", type="primary")
    return submitted, edited, {"patient": patient, "provider": provider, "account": account,
                               "visit_type": visit_type, "visit_start": visit_start or None,
                               "visit_end": visit_end or None}


QUESTIONS = {
    "duplicate": "Can you explain whether these charges represent separate services?",
    "overpricing": "Can you provide an itemized explanation of this charge and the applicable rate?",
    "unbundling": "Is this test already included in the panel, or was it a distinct service?",
    "date_mismatch": "Can you verify the service date against the visit records?",
    "visit_mismatch": "Can you confirm the visit setting and explain the service code?",
}


def report_questions(audit):
    st.subheader("Questions for the billing office")
    if not audit["findings"]:
        st.success("No issues matched the limited demo rules. You can still request an itemized explanation.")
        return
    seen = set()
    for finding in audit["findings"]:
        category = finding["category"]
        if category in seen:
            continue
        seen.add(category)
        with st.expander(finding["title"], expanded=len(seen) == 1):
            st.write(QUESTIONS.get(category, "Please clarify this charge and provide supporting records."))
            st.caption("See Findings & evidence for the exact charges, rule explanation, and references.")
