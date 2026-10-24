"""User decisions and export snapshots never mutate deterministic audit findings."""
from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from billing.person import personalized_bill

STATUSES = ('Needs clarification', 'Explained', 'Possible error')

def snapshot_knowledge(data, kb):
    """Reopened reports cite the corpus that was saved with the audit."""
    if not data.get('references') or not all('text' in row for row in data['references']):
        return kb
    from types import SimpleNamespace
    from langchain_core.documents import Document
    documents = [Document(page_content=row['text'], metadata={k: v for k, v in row.items() if k != 'text'})
                 for row in data['references']]
    by_id = {doc.metadata['source_id']: doc for doc in documents}
    return SimpleNamespace(documents=documents, get=by_id.get)

def amount(value):
    try:
        number = Decimal(str(value).replace(',', '').replace('$', ''))
        if not number.is_finite() or number < 0 or number > 100000000 or number.as_tuple().exponent < -2:
            raise ValueError()
        return number
    except (InvalidOperation, ValueError):
        raise ValueError('Enter a nonnegative USD amount with at most two decimal places.') from None

def decision(review, finding_id, status, note):
    if status not in STATUSES or len(note) > 3000:
        raise ValueError('Invalid review decision.')
    result = deepcopy(review)
    entry = {'status': status, 'note': note}
    if result.setdefault('decisions', {}).get(finding_id) != entry:
        result['decisions'][finding_id] = entry
        result.setdefault('history', []).append({'finding': finding_id, **entry,
            'at': datetime.now(timezone.utc).isoformat()})
    return result

def snapshot(state, person, review, kb, include_personal=False):
    bill = personalized_bill(deepcopy(state['bill']), person if include_personal else {})
    if not include_personal:
        for field in ('patient', 'provider', 'account'):
            bill[field] = 'Excluded'
    return {'schema_version': 1, 'bill': bill, 'audit': deepcopy(state['audit']),
            'review': deepcopy(review), 'cloud_eligible': False,
            'references': deepcopy(state.get('references')) or [{**deepcopy(doc.metadata), "text": doc.page_content} for doc in kb.documents]}

def compare_eob(lines, eob):
    """Match unique code/date pairs only. Never infer patient liability."""
    result = []
    for item in eob:
        key = (str(item.get('code', '')).strip(), str(item.get('service_date', '')).strip())
        matches = [x for x in lines if (x['code'], x.get('service_date') or '') == key]
        repeated = sum((str(x.get('code', '')).strip(), str(x.get('service_date', '')).strip()) == key for x in eob) > 1
        result.append({**item, 'match': matches[0]['line_id'] if len(matches) == 1 and not repeated and all(key) else 'Unresolved',
                       'billed_difference': str(amount(matches[0]['amount']) - amount(item['billed']))
                       if len(matches) == 1 and not repeated and all(key) else None})
    return result
