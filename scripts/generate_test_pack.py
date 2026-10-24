"""Run from project root: python -m scripts.generate_test_pack."""
import json
import zipfile
from pathlib import Path
import pymupdf
from billing.test_cases import cases, invalid_cases

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'outputs/synthetic-test-pack'

def document(bill):
    doc = pymupdf.open()
    rows = bill['lines']
    for start in range(0,len(rows),16):
        page = doc.new_page(width=842,height=595)
        lines = ['SYNTHETIC TEST BILL - ALL DATA IS FICTIONAL',
                 f"Patient: {bill['patient']}", f"Provider: {bill['provider']}", f"Account: {bill['account']}",
                 f"Visit type: {bill['visit_type']}",f"Visit start: {bill['visit_start']}",f"Visit end: {bill['visit_end']}",
                 'Code | Description | Service date | Quantity | Billed line total USD | Modifier']
        lines += [' | '.join(str(row.get(k) or '') for k in ('code','description','service_date','quantity','amount','modifiers')) for row in rows[start:start+16]]
        page.insert_text((30,35),'\n'.join(lines),fontname='cour',fontsize=10,lineheight=1.7)
        page.insert_text((30,570),f'Page {start//16+1} - No payment or patient responsibility inferred',fontsize=10)
    return doc

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    records=cases()
    for case in records:
        (OUT/(case['id']+'.json')).write_text(json.dumps(case,indent=2),encoding='utf-8')
        with document(case['bill']) as doc:
            doc.save(OUT/(case['id']+'.pdf'))
    with document(records[0]['bill']) as doc:
        png=doc[0].get_pixmap(dpi=180).tobytes('png')
        (OUT/'clean-office-scan.png').write_bytes(png)
        page=doc.new_page(width=842,height=595)
        page.insert_image(page.rect,stream=png)
        doc.save(OUT/'mixed-digital-scan.pdf')
    (OUT/'invalid-bills.json').write_text(json.dumps(invalid_cases(),indent=2),encoding='utf-8')
    eob={'unique':[{'code':'99213','service_date':'2026-10-01','billed':'100.00'}],
         'ambiguous':[{'code':'99213','service_date':'2026-10-01','billed':'100.00'}]*2,
         'financial':{'statement_total':'100.00','credits':'10.00','insurer_paid':'60.00','patient_paid':'0.00','patient_responsibility':''}}
    (OUT/'eob-and-payments.json').write_text(json.dumps(eob,indent=2),encoding='utf-8')
    (OUT/'manifest.json').write_text(json.dumps([{'id':x['id'],'expected':x['expected']} for x in records],indent=2),encoding='utf-8')
    (OUT/'START-HERE.txt').write_text('ALL DATA IS FICTIONAL. Use Upload a bill in the app.\n\n13 PDF bills and companion JSON fixtures cover clean charges, exact price thresholds, quantity calculations, repeats, bundling, modifiers, dates, setting mismatch, unknown codes and a 3-page bill.\n\nThe clean-office-scan.png tests local OCR. The mixed-digital-scan.pdf contains the SAME office charge on two pages: expected total 200.00, one duplicate finding, illustrative reduction 100.00 after confirming both rows. OCR may require manual correction.\n\nmanifest.json holds expected deterministic audit results. invalid-bills.json has 3 negative validation cases (programmatic input, not file uploads). eob-and-payments.json supplies manual EOB/payment entries: responsibility remains unknown.\n\nUploaded copies always stay on the local processing path, even when labeled synthetic. JSON files are developer fixtures; upload the PDF or PNG files to the app.\n',encoding='utf-8')
    archive=ROOT/'outputs/clearclaim-synthetic-test-pack.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as output:
        for path in sorted(OUT.iterdir()): output.write(path,path.name)
    print(f'Created {len(records)} cases and {archive}')

if __name__=='__main__': main()
