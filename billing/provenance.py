"""Exact text locations only: ambiguous matches remain visible as candidates."""
import pymupdf

def locate(content, line):
    matches = []
    with pymupdf.open(stream=content, filetype='pdf') as doc:
        for number, page in enumerate(doc):
            for rect in page.search_for(line.get('description', '')) if line.get('description') else []:
                # Description is a candidate location, not proof of row identity after edits.
                matches.append({'page': number, 'rect': tuple(rect)})
    return matches

def highlighted(content, match):
    with pymupdf.open(stream=content, filetype='pdf') as doc:
        page = doc[match['page']]
        annotation = page.add_highlight_annot(pymupdf.Rect(match['rect']))
        annotation.update()
        scale = min(1.5, 1400 / max(page.rect.width, page.rect.height))
        return page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), alpha=False).tobytes('png')

def show_charge_source(lines, key):
    import streamlit as st
    source = st.session_state.get('source_document')
    if not source or not source['filename'].lower().endswith('.pdf'):
        st.caption('Exact source locations unavailable for this source. Compare the original image/text manually.')
        return
    line = st.selectbox('Locate charge in source', lines, format_func=lambda x: x['line_id'] + ' · ' + x['description'], key=key)
    matches = locate(source['content'], line)
    if not matches:
        st.caption('No exact description match. The charge may be edited or scanned; check the original manually.')
        return
    st.caption('Exact description text matches only. Verify code, date and amount; repeated descriptions can identify several candidate locations.')
    match = st.selectbox('Candidate location', list(range(len(matches))), format_func=lambda i: f"Page {matches[i]['page'] + 1} · match {i + 1}", key=key + '_match')
    cache = st.session_state.setdefault('review_preview_cache', {})
    cache_key = (matches[match]['page'], matches[match]['rect'])
    if cache_key not in cache:
        if len(cache) >= 6:
            cache.pop(next(iter(cache)))
        cache[cache_key] = highlighted(source['content'], matches[match])
    st.image(cache[cache_key], caption='Highlighted candidate source text', width='stretch')
