"""Local review controls, reconciliation, and encrypted review history."""
import json
import uuid
import pandas as pd
import streamlit as st
from billing.review import STATUSES, amount, decision, compare_eob
from billing import storage

def financial_review(state):
    review = st.session_state.setdefault('review_meta', {})
    with st.expander('Payments, credits and EOB comparison'):
        st.caption('Enter amounts from your documents. These are independent of fictional audit reductions. Blank means unknown. Credits and payments must be nonnegative and separate from charge rows.')
        previous = review.get('financial', {})
        with st.form('financial_form'):
            values = {key: st.text_input(label, previous.get(key, ''), key='review_fin_' + key) for key, label in (
                ('statement_total', 'Statement charge total USD'), ('credits', 'Credits / adjustments USD'),
                ('insurer_paid', 'Insurer payments USD'), ('patient_paid', 'Patient payments USD'),
                ('patient_responsibility', 'Patient responsibility explicitly stated on EOB USD'))}
            note = st.text_input('Reconciliation notes', previous.get('note', ''))
            if st.form_submit_button('Save payment information'):
                try:
                    cleaned = {k: str(amount(v)) if v.strip() else '' for k, v in values.items()}
                    review['financial'] = {**cleaned, 'note': note}
                    st.success('Payment information saved locally.')
                except ValueError as error:
                    st.error(str(error))
        info = review.get('financial', {})
        st.write('Patient responsibility: ' + ('USD ' + info['patient_responsibility'] if info.get('patient_responsibility') else 'Unknown — not inferred from the bill or audit.'))
        if info.get('statement_total'):
            difference = amount(info['statement_total']) - amount(state['audit']['total_billed'])
            if difference:
                st.warning(f'Statement charge total minus confirmed charge rows: USD {difference}. Check missing rows, credits and statement scope.')
            else:
                st.success('Statement charge total reconciles with confirmed rows.')
        st.markdown('**Compare EOB line items**')
        st.caption('Use ISO dates. Repeated code/date pairs remain unresolved. A match does not establish coverage or liability.')
        rows = st.data_editor(pd.DataFrame(review.get('eob', []), columns=['code', 'service_date', 'billed']),
                              num_rows='dynamic', key='review_eob_editor', hide_index=True)
        if st.button('Compare EOB with bill'):
            try:
                records = rows.fillna('').to_dict('records')
                for row in records:
                    row['billed'] = str(amount(row['billed']))
                review['eob'] = records
                review['eob_comparison'] = compare_eob(state['bill']['lines'], records)
            except ValueError as error:
                st.error(str(error))
        if review.get('eob_comparison'):
            st.dataframe(review['eob_comparison'], hide_index=True)

def finding_decision(finding):
    ss = st.session_state
    review = ss.setdefault('review_meta', {})
    old = review.get('decisions', {}).get(finding['id'], {})
    with st.form('review_decision_' + finding['id']):
        status = st.selectbox('Your assessment', STATUSES, index=STATUSES.index(old.get('status', STATUSES[0])))
        note = st.text_area('Your notes', old.get('note', ''), max_chars=3000)
        if st.form_submit_button('Save assessment'):
            ss.review_meta = decision(review, finding['id'], status, note)
            st.rerun()
    st.caption('Your assessment is separate from the original audit; it does not recalculate the illustrative reduction.')

def save_review(data):
    with st.expander('Save an encrypted review on this computer'):
        st.caption('Optional. Saves confirmed charges, findings, decisions and payment information. Original uploads and chat are excluded. Expired files are deleted when Saved reviews is opened; no background deletion service runs. Deleting files does not erase external backups.')
        with st.form('review_save'):
            password = st.text_input('New review passphrase (12+ characters)', type='password')
            days = st.selectbox('Retention in days', [1, 7, 30, 90], index=2)
            if st.form_submit_button('Save encrypted snapshot'):
                try:
                    identifier = storage.save(data, password, days)
                    st.success('Saved review ' + identifier)
                except (ValueError, OSError) as error:
                    st.error(str(error))

def saved_reviews():
    st.title('Saved reviews')
    st.caption('Encrypted snapshots on this computer. A passphrase is required to open each review. Forgotten passphrases cannot be recovered. Expired files are removed on this page.')
    items = storage.list_saved()
    if not items:
        st.info('No saved reviews. Complete a bill review and use Save an encrypted review.')
        return
    for item in items:
        with st.expander(item['id'] + ' · ' + item['created'][:10]):
            st.caption('Expires: ' + item['expires'])
            with st.form('unlock_' + item['id']):
                password = st.text_input('Passphrase', type='password')
                if st.form_submit_button('Open saved review'):
                    try:
                        data = storage.load(item['id'], password)
                        for key in list(st.session_state):
                            if key.startswith(('review_', 'local_letter_')):
                                st.session_state.pop(key, None)
                        from billing.advocate import local_summary
                        st.session_state.update(result={**data, 'auditor_notes': local_summary(data['audit']),
                            'summary': local_summary(data['audit']), 'raw_text': 'Original source was not saved.'},
                            review_meta=data['review'], stage='results', model=None, messages=[],
                            graph_config={'configurable': {'thread_id': str(uuid.uuid4())}},
                            pending_navigation='Reports')
                        st.session_state.pop('source_document', None)
                        st.session_state.pop('local_person', None)
                        st.rerun()
                    except (ValueError, OSError) as error:
                        st.error(str(error))
            if st.button('Delete this saved review', key='delete_' + item['id']):
                storage.delete(item['id'])
                st.rerun()
