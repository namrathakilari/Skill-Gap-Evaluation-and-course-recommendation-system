"""
pipeline.py
Single entry point for the entire resume processing pipeline.
Both the FastAPI layer AND the Streamlit app call this.

Usage:
    from core.pipeline import ResumePipeline
    result = ResumePipeline().process_file(uploaded_file)
    result = ResumePipeline().process_bytes(file_bytes, filename)
    result = ResumePipeline().process_text(raw_text)
"""

import time
from core.parser import ResumeParser
from core.extractor import TransformerExtractor
from core.mapper import DEETMapper


class ResumePipeline:
    def __init__(self):
        self._parser    = ResumeParser()
        self._extractor = TransformerExtractor()
        self._mapper    = DEETMapper()

    # ── Main entry points ─────────────────────────────────────────────────────

    def process_file(self, uploaded_file) -> dict:
        """For Streamlit: accepts UploadedFile object."""
        raw_text = self._parser.parse(uploaded_file)
        return self._run(raw_text)

    def process_bytes(self, file_bytes: bytes, filename: str) -> dict:
        """For FastAPI: accepts raw bytes + filename."""
        raw_text = self._parser.parse_bytes(file_bytes, filename)
        return self._run(raw_text)

    def process_text(self, raw_text: str) -> dict:
        """For testing or direct text input."""
        return self._run(raw_text)

    # ── Internal ──────────────────────────────────────────────────────────────

    def _run(self, raw_text: str) -> dict:
        t0 = time.time()

        extracted    = self._extractor.extract(raw_text)
        deet_profile = self._mapper.map(extracted)

        total_ms = round((time.time() - t0) * 1000)

        return {
            "status": "success",
            "profile": deet_profile,
            "meta": {
                "extraction_ms":    extracted.get("_extraction_ms", 0),
                "total_ms":         total_ms,
                "overall_confidence": self._overall_confidence(
                    extracted.get("field_confidence", {})
                ),
                "profile_score":    extracted.get("profile_score", 0),
                "fields_extracted": sum(
                    1 for v in extracted.get("field_confidence", {}).values()
                    if v > 0
                ),
            },
            # Raw extraction kept for debugging / accuracy report
            "_raw": extracted,
        }

    def _overall_confidence(self, field_conf: dict) -> int:
        if not field_conf:
            return 0
        return round(sum(field_conf.values()) / len(field_conf))
