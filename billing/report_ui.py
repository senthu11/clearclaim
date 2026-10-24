"""Report rendering, actions and exports, separate from graph orchestration."""
import json
from decimal import Decimal
import pandas as pd
import streamlit as st
from billing.advocate import local_summary, escape_currency
from billing.person import personalized_bill
from billing.workspace import report_questions, QUESTIONS
from billing.excel import workbook_bytes, MIME as EXCEL_MIME
from billing.review import snapshot, snapshot_knowledge
from billing.review_ui import financial_review, finding_decision, save_review
from billing.exports import markdown as snapshot_markdown, selected_letter, letter_pdf
from billing.provenance import show_charge_source
from billing.chat import answer_question, safe_web_url
from billing.llm import UserError

def render_results(kb, web_enabled, show_evidence):
    ss = st.session_state
    state = ss.result
    kb = snapshot_knowledge(state, kb)
    def show_evidence(source_ids):
        for source_id in sorted(set(source_ids)):
            document = kb.get(source_id)
            if document:
                st.markdown(f"**{source_id} · {document.metadata['title']}**")
                st.write(document.page_content)
                st.caption('Version: ' + document.metadata.get('version', 'unknown') + ' · Fictional educational data; no payer applicability or clinical effective date.')
    audit = state["audit"]
    local_bill = personalized_bill(state["bill"], ss.get("local_person", {}))
    for warning in state.get("warnings", []):
        st.warning(warning)
    if state.get("warnings") and ss.get("model") is not None and st.button("Retry optional AI summary"):
        from billing.advocate import advocate
        try:
            state.update(advocate(ss.model, state['bill'], state['audit'], kb, state.get('synthetic_sample')))
            st.success('Summary refreshed. Original deterministic findings are unchanged.')
        except UserError:
            st.warning('AI is still unavailable. Your local report remains ready.')
    financial_review(state)
    include_personal = st.checkbox("Include patient, provider and account details in downloads and saved reviews", value=False)
    st.caption("Excluding these fields does not redact free-text descriptions or notes. Inspect exports before sharing.")
    export_data = snapshot(state, ss.get("local_person", {}), ss.get("review_meta", {}), kb, include_personal)
    st.caption("Processing: fixed synthetic AI demo" if state.get("cloud_eligible") else
               "Processing: fully local — no uploaded data sent to an LLM or web service")
    cols = st.columns(3)
    cols[0].metric("Total billed", f"${Decimal(audit['total_billed']):,.2f}")
    cols[1].metric("Illustrative potential reduction", f"${Decimal(audit['potential_savings']):,.2f}")
    cols[2].metric("Issues to review", len(audit["findings"]))
    st.caption("Potential reductions use fictional references and avoid counting overlapping findings twice.")
    summary_tab, finding_tab, letter_tab, chat_tab = st.tabs(["Report", "Findings & evidence", "Dispute letter", "Ask about this bill"])
    with summary_tab:
        summary_text = local_summary(audit)
        report_questions(audit)
        with st.expander("Full review summary"):
            st.markdown(summary_text)
        if state.get("cloud_eligible"):
            with st.expander("Additional AI explanation"):
                st.markdown(escape_currency(state["summary"]))
        st.subheader("Take your review with you")
        st.caption("Downloads stay on your device. Review the letter before sharing it.")
        st.download_button("Download all details (Excel)", workbook_bytes({}, export_data, kb),
                           "clearclaim-details.xlsx", EXCEL_MIME, icon=":material/table_view:", type="primary")
        st.download_button("Download report (.md)", snapshot_markdown(export_data, kb),
                           "synthetic-bill-review.md", "text/markdown")
        st.download_button("Download complete review (.json)", json.dumps(export_data, indent=2),
                           "confirmed-charges.json", "application/json")
        save_review(export_data)
        if audit["comparisons"]:
            chart = pd.DataFrame(audit["comparisons"])
            chart[["billed", "reference_total"]] = chart[["billed", "reference_total"]].astype(float)
            st.subheader("Billed amounts and fictional references")
            st.bar_chart(chart.set_index("line_id")[["billed", "reference_total"]], stack=False)
        with st.expander("Confirmed charge data"):
            st.dataframe(pd.DataFrame(state["bill"]["lines"]), hide_index=True, width="stretch")
        with st.expander("Limitations and unsupported codes"):
            for limitation in audit["limitations"]:
                st.write("• " + limitation)
            if audit["unknown_codes"]:
                st.write("No price reference for: " + ", ".join(audit["unknown_codes"]))
    with finding_tab:
        with st.expander("Auditor summary"):
            st.markdown(escape_currency(state["auditor_notes"]))
        if not audit["findings"]:
            st.success("No issues matched the demo rules. This is a limited check, not certification of the bill.")
        selected_finding = st.selectbox("Choose a finding", audit["findings"], format_func=lambda f: f["id"] + " · " + f["title"], key="review_selected_finding") if audit["findings"] else None
        for finding in ([selected_finding] if selected_finding else []):
            with st.container(border=True):
                st.markdown(f"**{finding['id']} · {finding['title']} · {finding['severity'].upper()}**")
                finding_decision(finding)
                with st.expander("Locate source text"):
                    show_charge_source([line for line in state["bill"]["lines"] if line["line_id"] in finding["line_ids"]], "review_source_" + finding["id"])
                st.markdown("**Source charges**")
                st.dataframe(pd.DataFrame([line for line in state["bill"]["lines"]
                                          if line["line_id"] in finding["line_ids"]]),
                             hide_index=True, width="stretch")
                st.markdown("**Why it needs review**")
                st.markdown(escape_currency(finding["detail"]))
                st.caption("Lines: " + ", ".join(finding["line_ids"]) + " · " + finding["confidence"])
                st.markdown(f"Standalone candidate amount: **USD {Decimal(finding['candidate_amount']):,.2f}**. "
                            "May overlap with other findings; do not add these amounts.")
                st.markdown("**Supporting references**")
                show_evidence(finding["citations"])
                st.markdown("**What to ask**")
                st.write(QUESTIONS.get(finding["category"], "Please clarify the charge and provide supporting records."))
        with st.expander("How the reduction was calculated"):
            st.dataframe(pd.DataFrame([
                {"line_id": key, "disputed_amount": value}
                for key, value in audit["disputed_by_line"].items()
            ]), hide_index=True, width="stretch")
            show_evidence(["POL-SAVINGS"])
    with letter_tab:
        st.write("Review and edit this classroom draft before downloading. It uses fictional reference data.")
        selected = st.multiselect("Findings to include", [f["id"] for f in audit["findings"]], default=[f["id"] for f in audit["findings"]], key="review_letter_selection")
        tone = st.selectbox("Letter tone", ["Neutral", "Concise", "Firm"], key="review_letter_tone")
        local_letter = selected_letter(export_data, selected, tone)
        letter = st.text_area("Dispute letter draft", value=local_letter, height=500,
                              key=f"local_letter_{ss.graph_config['configurable']['thread_id']}_{ss.get('person_revision', 0)}_{include_personal}_{tone}_{'-'.join(selected)}")
        st.download_button("Download letter (.txt)", letter, "synthetic-dispute-letter.txt", "text/plain")
        st.download_button("Download letter (.pdf)", letter_pdf(letter), "review-letter.pdf", "application/pdf")
        st.caption("Changing selection, tone or identifier inclusion starts a fresh draft. Download edits you want to keep first.")
    with chat_tab:
        st.caption("Questions are interpreted locally into billing topics. Free text and history stay local. "
                   "Uploads get local rule explanations; unchanged built-in examples can use the cloud AI demo.")
        for message in ss.messages:
            with st.chat_message(message["role"]):
                st.markdown(escape_currency(message["content"]))
                if message.get("sources"):
                    with st.expander("Retrieved evidence"):
                        for item in message["sources"]:
                            st.markdown(f"**{item['id']} · {item['title']}**")
                            st.write(item["text"])
                            if item.get("url") and safe_web_url(item["url"]):
                                st.link_button("Open web source", item["url"])
        st.caption("Try: Why is this charge flagged? • How are overlapping amounts counted? • What should I ask the billing office? Coverage and patient liability cannot be established by this demo.")
        question = st.chat_input("Ask a question about this bill", max_chars=3000)
        if question:
            try:
                with st.spinner("Retrieving evidence and answering…"):
                    response = answer_question(ss.model, kb, state, question, ss.messages, web_enabled)
                ss.messages += [{"role": "user", "content": question},
                                {"role": "assistant", "content": response["answer"], "sources": response["sources"]}]
                if response["warning"]:
                    ss.messages[-1]["content"] += "\n\n" + response["warning"]
                st.rerun()
            except UserError as error:
                st.error(str(error))
            except Exception:
                st.error("The answer could not be generated. Please retry.")
