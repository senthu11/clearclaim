"""In-memory digital PDF and image/OCR ingestion."""

import io
import os
import re
import shutil
from functools import lru_cache
from pathlib import Path

import pymupdf as fitz
import pytesseract
from PIL import Image, ImageOps

from billing.llm import UserError
from billing.models import Bill

MAX_UPLOAD = 15 * 1024 * 1024
MAX_TEXT = 120_000
MAX_PAGES = 20
Image.MAX_IMAGE_PIXELS = 25_000_000


def tesseract_path():
    configured = os.getenv("TESSERACT_CMD", "").strip()
    candidates = [configured, shutil.which("tesseract"),
                  "C:/Program Files/Tesseract-OCR/tesseract.exe",
                  str(Path(__file__).resolve().parents[1] / ".local-tools/tesseract/tesseract.exe")]
    return next((str(path) for path in candidates if path and Path(path).is_file()), None)


def ocr(image):
    path = tesseract_path()
    if not path:
        return local_ocr(image)
    pytesseract.pytesseract.tesseract_cmd = path
    try:
        return pytesseract.image_to_string(ImageOps.exif_transpose(image).convert("RGB"), timeout=60)
    except Exception:
        raise UserError("OCR failed or timed out. Try a clearer image or a digital PDF.") from None


def local_ocr(image):
    """Bundled CPU OCR avoids requiring a system Tesseract installation."""
    import numpy as np

    engine = _rapid_engine()
    try:
        results, _ = engine(np.asarray(ImageOps.exif_transpose(image).convert("RGB")))
        return "\n".join(item[1] for item in (results or []))
    except Exception:
        raise UserError("Local OCR failed. Try a clearer image or digital PDF.") from None


@lru_cache(maxsize=1)
def _rapid_engine():
    from rapidocr_onnxruntime import RapidOCR
    return RapidOCR(intra_op_num_threads=2, inter_op_num_threads=2)


def read_upload(content: bytes, filename: str, progress=None) -> str:
    if not content or len(content) > MAX_UPLOAD:
        raise UserError("Upload a nonempty PDF or image smaller than 15 MB.")
    suffix = Path(filename).suffix.lower()
    try:
        if suffix == ".pdf":
            with fitz.open(stream=content, filetype="pdf") as document:
                if document.needs_pass:
                    raise UserError("Password-protected PDFs are not supported. Upload an unlocked copy.")
                if not 1 <= document.page_count <= MAX_PAGES:
                    raise UserError("Upload a PDF containing 1 to 20 pages.")
                pages = []
                for page in document:
                    if progress:
                        progress(page.number + 1, document.page_count)
                    text = page.get_text(sort=True)
                    image_area = sum(fitz.Rect(item["bbox"]).get_area() for item in page.get_image_info())
                    if len(text.strip()) < 40 or image_area > page.rect.get_area() * 0.4:
                        if page.rect.width * page.rect.height * (180 / 72) ** 2 > Image.MAX_IMAGE_PIXELS:
                            raise UserError("A scanned page is too large. Resize it before uploading.")
                        pix = page.get_pixmap(dpi=180, alpha=False)
                        text = ocr(Image.open(io.BytesIO(pix.tobytes("png"))))
                    pages.append(text)
                text = "\n\f\n".join(pages)
        elif suffix in {".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff"}:
            with Image.open(io.BytesIO(content)) as image:
                if getattr(image, "n_frames", 1) > 1:
                    raise UserError("Upload a single-page image or convert all pages to PDF.")
                text = ocr(image)
        else:
            raise UserError("Supported inputs: PDF, PNG, JPEG, WebP, or single-page TIFF.")
    except UserError:
        raise
    except (Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise UserError("Image is too large. Resize it to under 25 megapixels.") from None
    except Exception:
        raise UserError("The document could not be read. Check that it is a valid PDF or image.") from None
    if not text.strip():
        raise UserError("No readable text was found. Try a clearer scan or a digital PDF.")
    if len(text) > MAX_TEXT:
        raise UserError("The bill contains too much text. Upload a shorter document.")
    return text


def parse_bill_locally(text):
    """Conservative local parser. Unrecognized layouts require manual entry.

    Supported table columns are code | description | ISO date | quantity |
    billed total | modifier. No document classification grants cloud access.
    """
    metadata, rows, notes = {}, [], []
    headers = {"patient": "patient", "provider": "provider", "account": "account",
               "visit type": "visit_type", "visit start": "visit_start", "visit end": "visit_end"}
    for source_line in text.splitlines():
        header = re.match(r"^\s*([A-Za-z ]+):\s*(.*?)\s*$", source_line)
        if header and header[1].strip().lower() in headers:
            key = headers[header[1].strip().lower()]
            value = header[2]
            if key in {"visit_start", "visit_end"}:
                from datetime import date
                try:
                    value = date.fromisoformat(value).isoformat()
                except ValueError:
                    notes.append("A visit date could not be parsed locally; confirm it manually.")
                    continue
            if key == "visit_type" and value.lower() not in {"unknown", "outpatient", "inpatient"}:
                value = "unknown"
            metadata[key] = value
        fields = [part.strip() for part in source_line.split("|")]
        if len(fields) >= 5 and re.fullmatch(r"(?:\d{5}|[A-Z]\d{4}|UNKNOWN)", fields[0]):
            from billing.models import Charge
            try:
                row = Charge.model_validate({
                    "line_id": f"L{len(rows) + 1:03}", "code": fields[0], "description": fields[1],
                    "service_date": fields[2] or None, "quantity": fields[3],
                    "amount": fields[4].replace("$", "").replace(",", ""),
                    "modifiers": fields[5] if len(fields) > 5 else "",
                })
                rows.append(row)
            except ValueError:
                notes.append("A charge row could not be parsed locally; enter it manually.")
    if not rows:
        rows = [{"line_id": "L001", "code": "UNKNOWN", "description": "Enter a charge from the local source",
                 "quantity": 1, "amount": "0.00"}]
        notes.append("This layout could not be extracted automatically on this computer. "
                     "Enter the charges manually using the source preview. Nothing was sent externally.")
    return Bill.model_validate({**metadata, "lines": rows, "extraction_notes": notes})


def extract_bill(model, text, synthetic_sample=None):
    if synthetic_sample is None:
        return parse_bill_locally(text)
    from billing.privacy import SyntheticRequest
    from billing.samples import sample_bill
    fixture = sample_bill(synthetic_sample)
    if model is not None:
        # The external boundary reconstructs the fixture. Raw OCR text never enters this call.
        result = model.json(
            "You are the Extractor agent. Structure only the supplied fixed synthetic charge rows. "
            "Return the supplied line items unchanged as JSON matching the schema. "
            "Personal details are deliberately absent; do not invent them.",
            SyntheticRequest(synthetic_sample, "extractor"),
            {"type": "object", "properties": {"lines": {"type": "array", "items": {
                "type": "object", "properties": {"line_id": {"type": "string"},
                "code": {"type": "string"}, "quantity": {"type": "integer"},
                "amount": {"type": "string"}}}}}, "required": ["lines"]},
        )
        from billing.models import Charge, money
        try:
            structured = [Charge.model_validate(row) for row in result["lines"]]
            signature = lambda rows: [(row.line_id, row.code, row.quantity, money(row.amount)) for row in rows]
            if signature(structured) != signature(fixture.lines):
                raise ValueError("Synthetic extraction changed the fixture")
        except (ValueError, TypeError, KeyError):
            raise UserError("The model did not preserve the fixed synthetic charges. Retry with another model.") from None
    # The fixture is authoritative; generated content cannot introduce personal details.
    return fixture
