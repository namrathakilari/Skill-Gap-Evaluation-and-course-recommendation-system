"""
mapper.py  —  v2
Maps extracted fields → DEET registration schema.
skills_flat is the key output for teammate's Skill Gap engine (#74).
"""

from typing import Any


class DEETMapper:
    def map(self, extracted: dict[str, Any]) -> dict[str, Any]:
        return {
            # ── Identity ──────────────────────────────────────────────────────
            "full_name":  self._clean(extracted, "full_name"),
            "email":      self._clean(extracted, "email"),
            "phone":      self._clean(extracted, "phone"),
            "location":   self._clean(extracted, "location"),
            "linkedin":   self._clean(extracted, "linkedin"),
            "github":     self._clean(extracted, "github"),

            # ── Professional ──────────────────────────────────────────────────
            "summary":        self._clean(extracted, "summary"),
            "skills":         extracted.get("skills", {}),        # categorized
            "skills_flat":    extracted.get("skills_flat", []),   # ← teammate uses this
            "experience":     extracted.get("experience", []),
            "education":      extracted.get("education", []),
            "certifications": extracted.get("certifications", []),
            "projects":       extracted.get("projects", []),

            # ── DEET fields ───────────────────────────────────────────────────
            "job_type_preference": "Full-Time",
            "availability":        "Immediate",
            "expected_salary":     "",
            "preferred_locations": [self._clean(extracted, "location")],
            "languages_known":     ["English"],

            # ── Scores (used by #74 skill gap ranker) ─────────────────────────
            "profile_score":      extracted.get("profile_score", 0),
            "field_confidence":   extracted.get("field_confidence", {}),
            "profile_completeness": self._completeness(extracted),

            # ── Status ────────────────────────────────────────────────────────
            "registration_status": "pending",
        }

    def _clean(self, d: dict, key: str) -> str:
        val = d.get(key, "")
        return "" if (not val or val == "Not found") else val

    def _completeness(self, e: dict) -> int:
        checks = [
            bool(self._clean(e, "full_name")),
            bool(self._clean(e, "email")),
            bool(self._clean(e, "phone")),
            bool(e.get("skills")),
            bool(e.get("experience")),
            bool(e.get("education")),
            bool(self._clean(e, "summary")),
        ]
        return round(sum(checks) / len(checks) * 100)
