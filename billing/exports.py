"""Consistent snapshot exports and paginated, literal-text PDF letters."""
import json
from io import BytesIO
from xml.sax.saxutils import escape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from billing.advocate import report_markdown, local_summary
from billing.workspace import QUESTIONS

def markdown(data, kb):
    return report_markdown(data['bill'], data['audit'], local_summary(data['audit']), kb) + '\n\n## Review decisions and payment information\n\n```json\n' + json.dumps(data['review'], indent=2) + '\n```\n\n## Reference versions\n\n```json\n' + json.dumps(data['references'], indent=2) + '\n```'

def selected_letter(data, ids, tone):
    bill = data['bill']
    lines = ['EDUCATIONAL DRAFT - FICTIONAL REFERENCES', f"To: {bill['provider']} billing department",
             f"Account: {bill['account']}", '', 'Dear Billing Department,', '',
             'Please provide an itemized explanation and supporting records for the following charges.']
    if tone == 'Firm':
        lines.append('I request a written review and a corrected statement if an error is confirmed.')
    elif tone == 'Concise':
        lines.append('Please respond to the questions below in writing.')
    for finding in data['audit']['findings']:
        if finding['id'] in ids:
            lines += ['', finding['id'] + ': ' + finding['title'], 'Charge IDs: ' + ', '.join(finding['line_ids']),
                      QUESTIONS.get(finding['category'], 'Please explain this charge.')]
            for charge in bill['lines']:
                if charge['line_id'] in finding['line_ids']:
                    lines.append(f"{charge['line_id']}: {charge['code']}, {charge.get('service_date') or 'date unknown'}, USD {charge['amount']}")
    lines += ['', 'These questions do not allege fraud. Fictional reference prices do not establish an amount owed or a refund.',
              'Thank you,', bill['patient']]
    return '\n'.join(lines)

def letter_pdf(text):
    output = BytesIO()
    doc = SimpleDocTemplate(output, title='ClearClaim review letter', leftMargin=48, rightMargin=48, topMargin=48, bottomMargin=48)
    styles = getSampleStyleSheet()
    # Use a Unicode font where available; keep the default portable fallback.
    from pathlib import Path
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    candidates = [Path('C:/Windows/Fonts/arial.ttf'), Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')]
    font = next((path for path in candidates if path.exists()), None)
    if font:
        if 'ClearClaimBody' not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont('ClearClaimBody', str(font)))
        styles['Normal'].fontName = 'ClearClaimBody'
    styles['Normal'].leading = 15
    story = []
    for line in text.splitlines():
        story.append(Paragraph(escape(line), styles['Normal']) if line else Spacer(1, 10))
    def footer(canvas, document):
        canvas.setFont('Helvetica', 9)
        canvas.drawString(48, 25, f'ClearClaim | Review before sharing | Page {document.page}')
    doc.build(story or [Spacer(1, 1)], onFirstPage=footer, onLaterPages=footer)
    return output.getvalue()
