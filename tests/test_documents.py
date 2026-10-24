import unittest
from unittest.mock import patch

from billing.extraction import read_upload
from billing.llm import UserError
from billing.samples import sample_document


class DocumentTests(unittest.TestCase):
    def test_digital_pdf_preserves_procedure_codes(self):
        text = read_upload(sample_document("Issues to find"), "bill.pdf")
        self.assertIn("99213", text)
        self.assertIn("840.00", text)
        self.assertIn("SYNTHETIC", text)

    def test_sample_image_uses_local_ocr(self):
        with patch("billing.extraction.tesseract_path", return_value=None):
            text = read_upload(sample_document("Issues to find", image=True), "bill.png")
        self.assertIn("99213", text)
        self.assertIn("80053", text)
        self.assertIn("840.00", text)

    def test_bad_uploads_raise_safe_errors(self):
        for content, name in ((b"", "bill.pdf"), (b"not a pdf", "bill.pdf"),
                              (b"data", "bill.exe")):
            with self.assertRaises(UserError):
                read_upload(content, name)


if __name__ == "__main__":
    unittest.main()
