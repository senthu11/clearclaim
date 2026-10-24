"""Additional deterministic fixtures. All identities and prices are fictional."""
from copy import deepcopy
from datetime import date, timedelta

def charge(code='99213', amount='100.00', quantity=1, day='2026-10-01', modifiers=''):
    return dict(code=code, description='Synthetic service ' + code, service_date=day,
                quantity=quantity, amount=amount, modifiers=modifiers)

def cases():
    definitions = [
        ('clean-office', [charge()], '100.00', '0.00', {}),
        ('price-at-threshold', [charge(amount='150.00')], '150.00', '0.00', {}),
        ('price-one-cent-over', [charge(amount='150.01')], '150.01', '50.01', {'overpricing': 1}),
        ('quantity-within-threshold', [charge('85025','120.00',3)], '120.00','0.00',{}),
        ('quantity-over-threshold', [charge('85025','160.00',3)], '160.00','70.00',{'overpricing':1}),
        ('three-repeated-services', [charge(),charge(),charge()], '300.00','200.00',{'duplicate':1}),
        ('panel-two-components', [charge('80053','50.00'),charge('82947','10.00'),charge('82565','12.00')], '72.00','22.00',{'unbundling':2}),
        ('distinct-components', [charge('80053','50.00'),charge('82947','10.00',modifiers='59')], '60.00','0.00',{}),
        ('outside-visit-date', [charge('71046','80.00',day='2026-10-02')], '80.00','0.00',{'date_mismatch':1}),
        ('inpatient-code-outpatient', [charge('99223','250.00')], '250.00','0.00',{'visit_mismatch':1}),
        ('unsupported-code', [charge('99999','99.00')], '99.00','0.00',{}),
        ('missing-dates', [charge(day=None),charge(day=None)], '200.00','0.00',{}),
        ('multipage-40-services', [charge('99999','1.00',day=(date(2026,10,1)+timedelta(days=i)).isoformat()) for i in range(40)], '40.00','0.00',{}),
    ]
    result = []
    for index, (name, rows, total, reduction, categories) in enumerate(definitions, 1):
        bill = {'patient': f'Synthetic Person {index:02}', 'provider': 'Fictional Test Clinic',
                'account': f'TEST-{index:03}', 'visit_type':'outpatient', 'visit_start':'2026-10-01',
                'visit_end':'2026-11-15' if name.startswith('multipage') else '2026-10-01',
                'lines':[{'line_id':f'L{i:03}', **row} for i,row in enumerate(rows,1)]}
        result.append({'id':name, 'bill':bill, 'expected':{'total_billed':total,'potential_savings':reduction,
            'categories':categories, 'unknown_codes':['99999'] if rows[0]['code']=='99999' else []}})
    return result

def invalid_cases():
    base = cases()[0]['bill']
    result = []
    for name, field, value in [('negative-charge','amount','-10.00'),('invalid-quantity','quantity',0),('zero-only','amount','0.00')]:
        bill = deepcopy(base)
        bill['lines'][0][field] = value
        result.append({'id':name,'bill':bill,'expected':'Reject before audit'})
    return result
