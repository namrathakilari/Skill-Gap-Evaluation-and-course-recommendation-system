"""
extractor.py  —  v2.1
Fixes:
  - Personal info (name, email, phone, location, LinkedIn, GitHub) extracted
    FIRST and stored as a blocklist so they never leak into skills
  - Section parser anchored to known headers only — no bleed-through
  - Skills Pass 2 uses ONLY taxonomy matches (no catch-all bucket)
  - Name detection prefers ALL-CAPS header line
"""

import re
import time
from typing import Any


# ══════════════════════════════════════════════════════════════════════════════
# Skill taxonomy
# ══════════════════════════════════════════════════════════════════════════════
SKILL_TAXONOMY = {
    "languages": [
        "python","java","javascript","typescript","c++","c#","c","r","scala",
        "kotlin","swift","go","rust","php","ruby","bash","sql","html","css",
        "matlab","julia","perl","dart","haskell","elixir","solidity",
    ],
    "frameworks": [
        "react","angular","vue","django","flask","fastapi","spring","node.js",
        "express","tensorflow","pytorch","keras","scikit-learn","opencv",
        "huggingface","transformers","spacy","nltk","langchain","streamlit",
        "next.js","nuxt","svelte","laravel","rails","asp.net","xamarin",
        "flutter","react native","fastai","xgboost","lightgbm","catboost",
        "prophet","statsmodels","plotly","bokeh","dash","numpy","pandas",
        "matplotlib",
    ],
    "tools": [
        "aws","azure","gcp","google cloud platform","docker","kubernetes",
        "terraform","jenkins","github actions","ci/cd","linux","git","github",
        "gitlab","bitbucket","jira","confluence","figma","postman","swagger",
        "airflow","dbt","kafka","spark","hadoop","tableau","power bi","excel",
        "postgresql","mysql","mongodb","redis","elasticsearch","firebase",
        "supabase","pinecone","chromadb","weaviate","ollama","mlflow",
        "wandb","dvc","jupyter","colab","vscode","pycharm",
    ],
    "concepts": [
        "machine learning","deep learning","nlp","natural language processing",
        "computer vision","llm","large language model","rag",
        "retrieval augmented generation","fine-tuning","transfer learning",
        "reinforcement learning","mlops","data engineering","data science",
        "time series","forecasting","recommendation system","classification",
        "regression","clustering","object detection","speech recognition",
        "rest api","graphql","microservices","system design","devops","agile",
        "scrum","tdd","cloud computing","distributed systems",
        "data structures","algorithms","oops","functional programming",
        "neural networks","cnn","rnn","lstm","transformer","bert","gpt",
        "vector database","semantic search","prompt engineering",
    ],
    "soft_skills": [
        "leadership","communication","teamwork","problem solving",
        "critical thinking","project management","time management",
        "collaboration","mentoring","public speaking","research",
    ],
}

SKILL_LOOKUP: dict[str, str] = {
    skill: cat
    for cat, skills in SKILL_TAXONOMY.items()
    for skill in skills
}

# Section headers — used to anchor section boundaries
ALL_SECTION_HEADERS = (
    r"experience|work experience|employment|internship|"
    r"education|academic|qualification|"
    r"technical skills|skills|tools|technologies|tech stack|"
    r"certifications|courses|awards|achievements|"
    r"projects|personal projects|academic projects|"
    r"summary|objective|profile|about|overview|"
    r"publications|languages|references|contact|hobbies|interests"
)


# ══════════════════════════════════════════════════════════════════════════════
class TransformerExtractor:

    def __init__(self):
        self._ner_pipe = None
        self._load_ner()

    def _load_ner(self):
        try:
            from transformers import pipeline
            self._ner_pipe = pipeline(
                "ner",
                model="dslim/bert-base-NER",
                aggregation_strategy="simple",
                device=-1,
            )
        except Exception as e:
            print(f"[NER] Model unavailable: {e}. Falling back to regex-only.")
            self._ner_pipe = None

    # ── Public entry point ────────────────────────────────────────────────────
    def extract(self, text: str) -> dict[str, Any]:
        t0 = time.time()

        # ── Step 1: Extract personal info first, build blocklist ──────────────
        email    = self._extract_email(text)
        phone    = self._extract_phone(text)
        linkedin = self._extract_linkedin(text)
        github   = self._extract_github(text)

        # Blocklist: values that must NEVER appear in skills
        personal_blocklist = self._build_blocklist(email, phone, linkedin, github, text)

        # ── Step 2: NER for name + location ──────────────────────────────────
        entities = self._run_ner(text[:3000])
        full_name = self._get_name(entities, text)
        location  = self._get_location(entities, text)

        # Add name parts to blocklist
        for part in full_name.lower().split():
            if len(part) > 2:
                personal_blocklist.add(part)

        # ── Step 3: Structured sections ───────────────────────────────────────
        skills         = self._extract_skills_categorized(text, personal_blocklist)
        experience     = self._extract_experience(text)
        education      = self._extract_education(text)
        certifications = self._extract_certifications(text)
        summary        = self._extract_summary(text)
        projects       = self._extract_projects(text)

        # ── Step 4: Scoring ───────────────────────────────────────────────────
        field_confidence = self._field_confidence({
            "full_name": full_name, "email": email, "phone": phone,
            "location": location, "skills": skills, "experience": experience,
            "education": education, "summary": summary,
        })

        elapsed = round((time.time() - t0) * 1000)

        return {
            "full_name":        full_name,
            "email":            email,
            "phone":            phone,
            "linkedin":         linkedin,
            "github":           github,
            "location":         location,
            "summary":          summary,
            "skills":           skills,
            "skills_flat":      self._flatten_skills(skills),
            "experience":       experience,
            "education":        education,
            "certifications":   certifications,
            "projects":         projects,
            "field_confidence": field_confidence,
            "profile_score":    self._profile_score(field_confidence, skills, experience, education),
            "_extraction_ms":   elapsed,
        }

    # ── Blocklist builder ─────────────────────────────────────────────────────
    def _build_blocklist(self, email, phone, linkedin, github, text) -> set:
        blocked = set()

        # Email and its parts
        if email and email != "Not found":
            blocked.add(email.lower())
            blocked.add(email.split("@")[0].lower())

        # Phone digits
        if phone and phone != "Not found":
            blocked.add(phone.strip())
            blocked.add(re.sub(r"\D", "", phone))  # digits only

        # LinkedIn URL and handle
        if linkedin and linkedin != "Not found":
            blocked.add(linkedin.lower())
            m = re.search(r"linkedin\.com/in/([\w\-]+)", linkedin, re.IGNORECASE)
            if m:
                blocked.add(m.group(1).lower())

        # GitHub URL and handle
        if github and github != "Not found":
            blocked.add(github.lower())
            m = re.search(r"github\.com/([\w\-]+)", github, re.IGNORECASE)
            if m:
                blocked.add(m.group(1).lower())

        # City / state from location pattern
        loc_m = re.search(r"([A-Z][a-zA-Z]+),?\s*([A-Z][a-zA-Z]+)", text)
        if loc_m:
            blocked.add(loc_m.group(1).lower())
            blocked.add(loc_m.group(2).lower())

        # Generic noise words
        blocked.update([
            "contact","tools","skills","technical skills","languages",
            "frameworks","concepts","education","experience","projects",
            "profile","summary","objective","references","tools",
            "not found","n/a",
        ])

        return blocked

    # ── NER helpers ───────────────────────────────────────────────────────────
    def _run_ner(self, text: str) -> list:
        if not self._ner_pipe:
            return []
        try:
            return self._ner_pipe(text)
        except Exception:
            return []

    # Known section headers — lines matching these are NEVER a candidate name
    _SECTION_HEADERS = {
        "contact","profile","summary","objective","education","experience",
        "skills","technical skills","tools","projects","certifications",
        "tools & technologies","technologies","tech stack","languages",
        "frameworks","concepts","soft skills","awards","achievements",
        "publications","references","hobbies","interests","internship",
        "work experience","employment","academic","qualification",
    }

    def _get_name(self, entities: list, text: str) -> str:
        lines = [l.strip() for l in text.strip().split("\n") if l.strip()]

        # Strategy 1: ALL-CAPS name — search ALL lines (not just first 5).
        # Multi-column PDFs (like Tarun's) output the left sidebar first,
        # pushing "TARUN CHOWDARI" (right column header) further down.
        # Extra guards: no section header words anywhere in the line,
        # no skill/tech words, no typo variants like "PROFFESIONAL".
        _NAME_REJECT_WORDS = {
            "summary","objective","profile","about","overview","contact",
            "experience","education","skills","projects","certifications",
            "awards","publications","references","hobbies","interests",
            "professional","proffesional","profssional","technical","career",
            "personal","statement","internship","employment","qualification",
        }
        for line in lines:
            clean = line.strip()
            words = clean.split()
            if (clean.isupper()
                    and 2 <= len(words) <= 5
                    and re.match(r"^[A-Z\s]+$", clean)
                    and clean.lower() not in self._SECTION_HEADERS
                    and not any(w.lower() in _NAME_REJECT_WORDS for w in words)):
                return clean.title()

        # Strategy 2: Title Case 2-4 word line in first 25 lines
        city_names = {
            "hyderabad","bangalore","bengaluru","chennai","mumbai","delhi",
            "pune","kolkata","telangana","karnataka","maharashtra","india",
        }
        for line in lines[:25]:
            clean = line.strip()
            words = clean.split()
            if (2 <= len(words) <= 4
                    and all(w[0].isupper() for w in words if w)
                    and not any(c.isdigit() for c in clean)
                    and clean.lower() not in self._SECTION_HEADERS
                    and not any(w.lower() in city_names for w in words)
                    and not any(kw in clean.lower() for kw in
                                ["email","phone","linkedin","github","@","http",
                                 "b.tech","m.tech","data science","engineer"])):
                return clean

        # Strategy 3: NER PER — exclude institution name fragments
        exclude = {"rao","aimscs","institute","university","college","school"}
        persons = [
            e["word"] for e in entities
            if e.get("entity_group") == "PER"
            and e["word"].strip().lower() not in exclude
            and len(e["word"].strip().split()) >= 2
        ]
        return max(persons, key=len).strip() if persons else "Not found"

    # Known Indian cities and states for location validation
    _INDIAN_CITIES = {
        "hyderabad","bangalore","bengaluru","chennai","mumbai","delhi","pune",
        "kolkata","ahmedabad","jaipur","lucknow","noida","gurugram","gurgaon",
        "secunderabad","vizag","visakhapatnam","kochi","coimbatore","indore",
        "bhopal","nagpur","chandigarh","bhubaneswar","vadodara","surat",
        "telangana","karnataka","maharashtra","andhra pradesh","tamilnadu",
        "kerala","rajasthan","gujarat","haryana","uttar pradesh","india",
    }

    # Words that are NEVER a location (skills, noise, etc.)
    _NOT_LOCATION = {
        "html","css","java","python","sql","node","react","aws","git",
        "docker","linux","agile","scrum","data","machine","learning",
        "b.tech","m.tech","engineering","science","commerce","management",
        "bachelor","master","degree","diploma","gpa","cgpa","llm","ai",
        "internship","experience","education","projects","skills","tools",
        "summary","objective","profile","contact","references","languages",
        "javascript","typescript","mongodb","mysql","github","gitlab",
        "excel","power","tableau","spring","flask","django","angular","vue",
    }

    def _get_location(self, entities: list, text: str) -> str:
        # Strategy 1: NER LOC entities (most reliable)
        locs = [e["word"].strip() for e in entities if e.get("entity_group") == "LOC"]
        for loc in locs:
            # Skip if it looks like a skill or noise word
            if loc.lower() not in self._NOT_LOCATION and len(loc) > 2:
                return loc

        # Strategy 2: Explicit location label near city name
        # e.g. "Location: Hyderabad" or "Address: Pune, Maharashtra"
        label_m = re.search(
            r"(?:location|address|city|based\s+in|residing\s+in)[:\s]+([A-Za-z][A-Za-z\s,]{2,40})",
            text, re.IGNORECASE
        )
        if label_m:
            candidate = label_m.group(1).strip().split("\n")[0].strip().rstrip(",")
            if not any(w.lower() in self._NOT_LOCATION for w in candidate.split()[:2]):
                return candidate[:60]

        # Strategy 3: "City, State" pattern — ONLY if city is a known Indian city
        for m in re.finditer(r"([A-Z][a-zA-Z]{2,}),\s*([A-Z][a-zA-Z]{2,})", text):
            city  = m.group(1).lower()
            state = m.group(2).lower()
            if city in self._INDIAN_CITIES or state in self._INDIAN_CITIES:
                # Reject if either word is a known non-location
                if city not in self._NOT_LOCATION and state not in self._NOT_LOCATION:
                    return m.group(0).strip()

        # Strategy 4: Bare known city name on its own line or after contact info
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        for line in lines[:30]:
            words = line.lower().split()
            if len(words) <= 3 and any(w in self._INDIAN_CITIES for w in words):
                if not any(c.isdigit() for c in line) and "@" not in line:
                    return line.strip()

        return "Not found"

    # ── Regex helpers ─────────────────────────────────────────────────────────
    def _extract_email(self, text):
        m = re.search(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", text)
        return m.group() if m else "Not found"

    def _extract_phone(self, text):
        # Must be 10-digit Indian mobile or +91 prefix
        # Explicitly excludes year ranges like 2024-2028
        patterns = [
            r"\+91[\s\-]?[6-9]\d{9}",
            r"\+91[\s\-]?\d{5}[\s\-]?\d{5}",
            r"\b[6-9]\d{9}\b",
            r"\b[6-9]\d{4}[\s\-]\d{5}\b",
        ]
        for pat in patterns:
            m = re.search(pat, text)
            if m:
                return m.group().strip()
        return "Not found"
        return m.group().strip() if m else "Not found"

    def _extract_linkedin(self, text):
        m = re.search(r"linkedin\.com/in/[\w\-]+", text, re.IGNORECASE)
        return f"https://{m.group()}" if m else "Not found"

    def _extract_github(self, text):
        m = re.search(r"github\.com/[\w\-]+", text, re.IGNORECASE)
        return f"https://{m.group()}" if m else "Not found"

    # ── Categorized skill extraction ─────────────────────────────────────────
    def _extract_skills_categorized(self, text: str, blocklist: set) -> dict[str, list[str]]:
        text_lower = text.lower()
        found: dict[str, set] = {cat: set() for cat in SKILL_TAXONOMY}

        # Pass 1: Scan ENTIRE text for taxonomy keywords (whole-word match only)
        for skill, cat in SKILL_LOOKUP.items():
            if re.search(r"\b" + re.escape(skill) + r"\b", text_lower):
                # Make sure it's not a blocked personal value
                if skill not in blocklist and skill.title() not in blocklist:
                    found[cat].add(skill.title())

        # Pass 2: Skills sections only — match against taxonomy (NO catch-all)
        for section_header in ["technical skills", "skills", "tools", "technologies", "tech stack"]:
            section = self._get_section(text, [section_header])
            if not section:
                continue
            items = re.split(r"[,|\n•·\-\u2022&]", section)
            for item in items:
                item = item.strip().strip(".")
                if not item or len(item) < 2 or len(item) > 50:
                    continue
                item_lower = item.lower()

                # Skip if it's personal info
                if self._is_personal(item_lower, blocklist):
                    continue

                # Only add if it matches taxonomy (exact or substring)
                for skill, cat in SKILL_LOOKUP.items():
                    if re.search(r"\b" + re.escape(skill) + r"\b", item_lower):
                        found[cat].add(skill.title())
                        break

        return {cat: sorted(skills) for cat, skills in found.items() if skills}

    def _is_personal(self, value: str, blocklist: set) -> bool:
        """Return True if value looks like personal info, not a skill."""
        # Direct blocklist hit
        if value in blocklist:
            return True
        # Contains email pattern
        if "@" in value or "gmail" in value or "yahoo" in value:
            return True
        # Contains phone digits (10+ digits)
        if len(re.sub(r"\D", "", value)) >= 8:
            return True
        # Contains URL
        if "http" in value or "linkedin" in value or "github" in value:
            return True
        # Word-by-word: any word in blocklist
        for word in value.split():
            if word.lower() in blocklist and len(word) > 3:
                return True
        return False

    def _flatten_skills(self, categorized: dict) -> list[str]:
        result = []
        for skills in categorized.values():
            result.extend(skills)
        return sorted(set(result))

    # ── Experience ───────────────────────────────────────────────────────────
    def _extract_experience(self, text: str) -> list[dict]:
        section = self._get_section(
            text, ["experience","work experience","employment","work history","internship"]
        )
        if not section:
            return []
        entries = []
        date_pat = re.compile(
            r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|"
            r"January|February|March|April|May|June|July|August|"
            r"September|October|November|December|20\d\d|19\d\d)",
            re.IGNORECASE,
        )
        blocks = re.split(r"\n(?=[A-Z][^\n]{5,60}(?:\n|$))", section)
        for block in blocks[:6]:
            lines = [l.strip() for l in block.strip().split("\n") if l.strip()]
            if not lines:
                continue
            title, company, start, end = lines[0][:80], "", "", "Present"
            if len(lines) > 1:
                at_m = re.search(r"\bat\b|\b@\b", title, re.IGNORECASE)
                if at_m:
                    parts   = re.split(r"\bat\b|\b@\b", title, 1, re.IGNORECASE)
                    title   = parts[0].strip()
                    company = parts[1].strip()
                else:
                    company = lines[1][:80]
            dates = date_pat.findall(block)
            if len(dates) >= 2:
                start, end = dates[0], dates[-1]
            elif len(dates) == 1:
                start = dates[0]
            desc = " ".join(lines[2:])[:500]
            if title:
                entries.append({"title": title, "company": company,
                                "start": start, "end": end, "desc": desc})
        return entries

    # ── Education ────────────────────────────────────────────────────────────
    def _extract_education(self, text: str) -> list[dict]:
        section = self._get_section(text, ["education","academic","qualification"])
        if not section:
            return []
        degree_kw = ["b.tech","b.e","b.sc","b.com","b.a","m.tech","m.sc","m.com",
                     "m.a","mba","phd","ph.d","bachelor","master","doctor","diploma","cse"]
        entries, lines = [], [l.strip() for l in section.split("\n") if l.strip()]
        i = 0
        while i < len(lines) and len(entries) < 4:
            if any(kw in lines[i].lower() for kw in degree_kw):
                inst  = lines[i+1] if i+1 < len(lines) else ""
                chunk = "\n".join(lines[i:i+3])
                yr_m  = re.search(r"20\d\d|19\d\d", chunk)
                gp_m  = re.search(r"(?:gpa|cgpa|percentage|%)[:\s]*(\d[\d.]+)",
                                   chunk, re.IGNORECASE)
                entries.append({
                    "degree":      lines[i][:100],
                    "institution": inst[:100],
                    "year":        yr_m.group() if yr_m else "",
                    "grade":       gp_m.group(1) if gp_m else "",
                })
                i += 2
            else:
                i += 1
        return entries

    # ── Projects ─────────────────────────────────────────────────────────────
    def _extract_projects(self, text: str) -> list[dict]:
        section = self._get_section(text, ["projects","personal projects","academic projects"])
        if not section:
            return []
        entries = []
        blocks  = re.split(r"\n(?=[A-Z][^\n]{3,60}(?:\s{2,}20\d\d)?$)", section, flags=re.MULTILINE)
        for block in blocks[:8]:
            lines = [l.strip() for l in block.strip().split("\n") if l.strip()]
            if not lines:
                continue
            title = re.sub(r"\s+20\d\d$", "", lines[0]).strip()[:100]
            desc  = " ".join(lines[1:])[:500]
            yr_m  = re.search(r"20\d\d", lines[0])
            if title:
                entries.append({"title": title, "year": yr_m.group() if yr_m else "", "desc": desc})
        return entries

    # ── Certifications ───────────────────────────────────────────────────────
    def _extract_certifications(self, text: str) -> list[str]:
        section = self._get_section(
            text, ["certification","certifications","courses","awards","achievements"]
        )
        if not section:
            return []
        return [l.strip("•-– \t") for l in section.split("\n")
                if l.strip() and 5 < len(l.strip()) < 150][:10]

    # ── Summary ──────────────────────────────────────────────────────────────
    # Patterns that look like contact-header noise, not summary content
    _CONTACT_LINE_PAT = re.compile(
        r"@|linkedin|github|http|\+91|\d{10}|"
        r"\bphone\b|\bemail\b|\bcontact\b|"
        r"\baddress\b|\blinkedin\b|\bgithub\b",
        re.IGNORECASE
    )
    # Section header spellings including common typos
    _SUMMARY_HEADERS = [
        "summary", "professional summary", "proffesional summary",
        "profssional summary", "career summary", "career objective",
        "objective", "profile", "about me", "about", "overview",
        "personal statement", "professional profile",
    ]

    def _extract_summary(self, text: str) -> str:
        # Strategy 1: exact section match (including typo variants)
        section = self._get_section(text, self._SUMMARY_HEADERS)
        if section:
            # Strip any contact-header residue from start of section
            lines = [l.strip() for l in section.split("\n") if l.strip()]
            clean = []
            for line in lines:
                if self._CONTACT_LINE_PAT.search(line):
                    continue  # skip contact noise lines
                clean.append(line)
            result = " ".join(clean).strip()
            if result:
                return result[:600]

        # Strategy 2: fuzzy scan — find a line that IS the header (handles typos
        # like "PROFFESIONAL SUMMARY") then grab the prose that follows it.
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        for i, line in enumerate(lines):
            ll = line.lower().strip(":")
            # Match known summary header words with 1-char typo tolerance
            if any(
                ll == h or
                (len(ll) > 6 and len(h) > 6 and
                 sum(a != b for a, b in zip(ll, h)) <= 2 and
                 abs(len(ll) - len(h)) <= 3)
                for h in ["summary", "professional summary", "proffesional summary",
                           "objective", "profile", "about me"]
            ):
                # Collect the prose lines that follow, skip contact noise
                prose = []
                for j in range(i + 1, min(i + 8, len(lines))):
                    if self._CONTACT_LINE_PAT.search(lines[j]):
                        continue
                    # Stop at next section header
                    if re.match(
                        r"^(experience|education|skills|projects|certifications|"
                        r"awards|publications|references|contact|hobbies|interests)\b",
                        lines[j].lower()
                    ):
                        break
                    prose.append(lines[j])
                if prose:
                    return " ".join(prose)[:600]

        # Strategy 3: last resort — first long prose sentence not containing
        # contact info (skip short/noisy header lines)
        for line in lines[1:20]:
            if (len(line) > 60
                    and not self._CONTACT_LINE_PAT.search(line)
                    and not line.isupper()):
                return line[:500]

        return ""

    # ── Section extractor ────────────────────────────────────────────────────
    def _get_section(self, text: str, headers: list[str]) -> str:
        """
        Extract text between a matched section header and the next known header.
        Anchors strictly to known header names to avoid bleed-through.
        """
        hp = "|".join(re.escape(h) for h in headers)
        pattern = (
            rf"(?im)^[ \t]*({hp})[ \t]*:?[ \t]*\n"
            rf"(.*?)"
            rf"(?=^[ \t]*(?:{ALL_SECTION_HEADERS})[ \t]*:?[ \t]*$|\Z)"
        )
        m = re.search(pattern, text, re.DOTALL | re.IGNORECASE | re.MULTILINE)
        return m.group(2).strip() if m else ""

    # ── Per-field confidence ──────────────────────────────────────────────────
    def _field_confidence(self, fields: dict) -> dict[str, int]:
        scores = {}
        for field, val in fields.items():
            if isinstance(val, str):
                if not val or val == "Not found":
                    scores[field] = 0
                elif field == "email" and "@" in val:
                    scores[field] = 98
                elif field == "phone" and any(c.isdigit() for c in val):
                    scores[field] = 95
                elif field == "full_name":
                    scores[field] = 90
                else:
                    scores[field] = 75 if len(val) > 20 else 50
            elif isinstance(val, list):
                scores[field] = min(95, 50 + len(val) * 8) if val else 0
            elif isinstance(val, dict):
                total = sum(len(v) for v in val.values())
                scores[field] = min(95, 40 + total * 5) if total else 0
        return scores

    # ── Profile score (0–100) ─────────────────────────────────────────────────
    def _profile_score(self, field_confidence, skills, experience, education) -> int:
        score = 0
        completeness_weights = {
            "full_name": 8, "email": 8, "phone": 6,
            "location": 4, "summary": 8, "skills": 8, "education": 8,
        }
        for field, w in completeness_weights.items():
            if field_confidence.get(field, 0) > 0:
                score += w
        total_skills = sum(len(v) for v in skills.values())
        skill_cats   = len(skills)
        score += min(12, total_skills)
        score += min(8, skill_cats * 2)
        score += min(15, len(experience) * 7)
        score += min(10, len(education) * 10)
        return min(100, score)
