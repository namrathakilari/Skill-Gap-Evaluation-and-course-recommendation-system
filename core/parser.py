"""
parser.py
PDF + image → raw text. No system dependencies (no tesseract).
  - PyMuPDF  → text-based PDFs (fast, accurate)
  - EasyOCR  → scanned PDFs / images (deep learning OCR)
"""

import io
import fitz
from PIL import Image


class ResumeParser:
    def __init__(self):
        self._ocr_reader = None   # lazy-load (heavy)

    def parse(self, uploaded_file) -> str:
        """Streamlit UploadedFile → raw text string."""
        name  = uploaded_file.name.lower()
        data  = uploaded_file.read()
        return self.parse_bytes(data, name)

    def parse_bytes(self, file_bytes: bytes, filename: str) -> str:
        """Raw bytes + filename → raw text string. Used by FastAPI."""
        name = filename.lower()
        if name.endswith(".pdf"):
            return self._parse_pdf(file_bytes)
        return self._parse_image(file_bytes)

    # ── PDF ───────────────────────────────────────────────────────────────────
    def _parse_pdf(self, data: bytes) -> str:
        doc   = fitz.open(stream=data, filetype="pdf")
        pages = []
        for page in doc:
            text = page.get_text("text").strip()
            if text:
                pages.append(text)
            else:
                pix = page.get_pixmap(dpi=200)
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                pages.append(self._ocr_image(img))
        return "\n".join(pages)

    # ── Image ─────────────────────────────────────────────────────────────────
    def _parse_image(self, data: bytes) -> str:
        img = Image.open(io.BytesIO(data)).convert("RGB")
        w, h    = img.size
        scale   = max(1, 2000 // max(w, h))
        if scale > 1:
            img = img.resize((w * scale, h * scale), Image.LANCZOS)
        return self._ocr_image(img)

    # ── EasyOCR (lazy) ────────────────────────────────────────────────────────
    def _ocr_image(self, img: Image.Image) -> str:
        import easyocr
        import numpy as np
        if self._ocr_reader is None:
            self._ocr_reader = easyocr.Reader(["en"], gpu=False, verbose=False)
        return "\n".join(
            self._ocr_reader.readtext(np.array(img), detail=0, paragraph=True)
        )
