"""
main.py — Unified DEET + Skill Gap API  (v4 — quiz-first, single server)
=========================================================================

New user flow:
  1. User visits  /              → Skill Gap Quiz (entry point)
  2. User completes quiz         → Report is shown with a "Register on DEET" button
  3. User uploads resume         → POST /api/v1/resume/analyze-for-deet → returns JSON + deet_url
  4. Browser opens /deet?deet=  → DEET portal auto-fills from base64 profile
  5. User confirms & submits     → POST /api/v1/deet/register → returns skill_gap_url
  6. Success screen              → "⚡ View My Skill Gap Report" button → back to quiz with ?deet=

Single server: uvicorn main:app --port 8000 --reload
No Streamlit needed.
"""

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import uvicorn, sys, os, json, base64
from urllib.parse import quote
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))
from core.pipeline import ResumePipeline

app = FastAPI(
    title="Skill Gap + DEET — Quiz-First API",
    description="Quiz → Resume Upload → DEET Registration → Skill Gap Report",
    version="4.0.0",
)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

BASE          = os.path.dirname(__file__)
QUIZ_FILE     = os.path.join(BASE, "skill-gap", "india-skill-gap-quiz-v3.html")
DEET_FILE     = os.path.join(BASE, "deet_portal", "index.html")
SG_OUTPUT_DIR = os.path.join(BASE, "skill-gap", "output")

# Serve db.json at /output/db.json  (quiz fetches './output/db.json' relative to its page at /)
if os.path.exists(SG_OUTPUT_DIR):
    app.mount("/output", StaticFiles(directory=SG_OUTPUT_DIR), name="sg-output")

_profiles: list[dict] = []
_pipeline: ResumePipeline | None = None

def get_pipeline() -> ResumePipeline:
    global _pipeline
    if _pipeline is None:
        _pipeline = ResumePipeline()
    return _pipeline


# ── Pages ─────────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def quiz_page():
    """Entry point — Skill Gap Quiz."""
    if not os.path.exists(QUIZ_FILE):
        return HTMLResponse("<h2>Quiz file not found.</h2>", status_code=404)
    return HTMLResponse(open(QUIZ_FILE, encoding="utf-8").read())


@app.get("/deet", response_class=HTMLResponse, include_in_schema=False)
def deet_page():
    """DEET Registration Portal. Reads ?deet=<base64> to auto-fill the form."""
    if not os.path.exists(DEET_FILE):
        return HTMLResponse("<h2>DEET portal not found.</h2>", status_code=404)
    return HTMLResponse(open(DEET_FILE, encoding="utf-8").read())


# ── Resume API ─────────────────────────────────────────────────────────────────

@app.post("/api/v1/resume/analyze-for-deet", tags=["Resume"])
async def analyze_for_deet(file: UploadFile = File(...)):
    """
    Called by the quiz page after user finishes quiz and uploads resume.
    Returns extracted profile JSON + a ready /deet?deet=<base64> URL.
    """
    ext = os.path.splitext(file.filename or "")[-1].lower()
    if ext not in {".pdf", ".png", ".jpg", ".jpeg"}:
        raise HTTPException(400, f"Unsupported file type '{ext}'. Use PDF, PNG or JPG.")
    try:
        result  = get_pipeline().process_bytes(await file.read(), file.filename)
        profile = result["profile"]
        meta    = result["meta"]
        skills  = profile.get("skills", {})
        edu_list= profile.get("education", [{}])
        edu0    = edu_list[0] if edu_list else {}

        deet_profile = {
            "personal": {
                "full_name": profile.get("full_name", ""),
                "email":     profile.get("email", ""),
                "phone":     profile.get("phone", ""),
                "location":  profile.get("location", ""),
                "linkedin":  profile.get("linkedin", ""),
                "github":    profile.get("github", ""),
                "summary":   (profile.get("summary") or "")[:500],
            },
            "skills": {
                "languages":  skills.get("languages", []),
                "frameworks": skills.get("frameworks", []),
                "tools":      skills.get("tools", []),
                "concepts":   skills.get("concepts", []),
            },
            "skills_flat": profile.get("skills_flat", []),
            "education": {
                "degree_level":   _map_degree(edu0.get("degree", "")),
                "field_of_study": edu0.get("degree", ""),
                "institution":    edu0.get("institution", ""),
                "grad_year":      str(edu0.get("year", "")),
            },
            "experience": {
                "years_category":   "0",
                "certifications":   "\n".join(profile.get("certifications", [])),
                "projects_summary": "\n".join(
                    f"{p['title']} — {p.get('desc','')[:120]}"
                    for p in profile.get("projects", [])[:4]
                ),
            },
            "preferences": {
                "preferred_roles":     "",
                "preferred_locations": (profile.get("location") or "").split(",")[0].strip(),
                "job_type":            "full_time",
                "availability":        "immediate",
                "work_mode":           "hybrid",
            },
            "meta": {
                "profile_score": meta.get("profile_score", 0),
                "source":        "quiz_resume_upload",
            },
        }

        encoded  = base64.b64encode(json.dumps(deet_profile, ensure_ascii=False).encode()).decode()
        deet_url = f"/deet?deet={quote(encoded, safe='')}"

        return {"status": "success", "profile": deet_profile, "deet_url": deet_url, "meta": meta}

    except Exception as e:
        raise HTTPException(500, f"Extraction failed: {e}")


@app.post("/api/v1/resume/parse", tags=["Resume"])
async def parse_resume(file: UploadFile = File(...)):
    """Raw parse — returns full profile JSON (Swagger / debug)."""
    ext = os.path.splitext(file.filename or "")[-1].lower()
    if ext not in {".pdf", ".png", ".jpg", ".jpeg"}:
        raise HTTPException(400, f"Unsupported file type '{ext}'")
    try:
        return get_pipeline().process_bytes(await file.read(), file.filename)
    except Exception as e:
        raise HTTPException(500, f"Extraction failed: {e}")


# ── DEET registration ──────────────────────────────────────────────────────────

@app.post("/api/v1/deet/register", tags=["DEET"])
async def register_profile(profile: dict):
    """
    Stores confirmed DEET profile from the portal form.
    Returns skill_gap_url so the portal can show the "View My Report" button.
    """
    profile["_id"]            = len(_profiles) + 1
    profile["_registered_at"] = datetime.utcnow().isoformat()
    _profiles.append(profile)

    encoded       = base64.b64encode(json.dumps(profile, ensure_ascii=False).encode()).decode()
    skill_gap_url = f"/?deet={quote(encoded, safe='')}&skipToReport=1"

    return {
        "status":        "registered",
        "profile_id":    profile["_id"],
        "skill_gap_url": skill_gap_url,
        "message":       "Profile saved. View your personalised Skill Gap Report.",
    }


@app.get("/api/v1/deet/profiles", tags=["DEET"])
def list_profiles():
    return {
        "count":    len(_profiles),
        "profiles": [
            {"id": p.get("_id"), "name": p.get("personal", {}).get("full_name", ""),
             "email": p.get("personal", {}).get("email", ""),
             "skills_flat": p.get("skills_flat", []),
             "registered_at": p.get("_registered_at")}
            for p in _profiles
        ],
    }


# ── Jobs Search (in-memory · Kaggle Indian Job Market 2025 · 38k jobs) ─────────

import threading as _threading

_JOBS_DB: list[dict] = []
_JOBS_LOCK = _threading.Lock()
_JOBS_FILE = os.path.join(BASE, "skill-gap", "output", "jobs.json")

def _load_jobs():
    global _JOBS_DB
    with _JOBS_LOCK:
        if not _JOBS_DB and os.path.exists(_JOBS_FILE):
            with open(_JOBS_FILE, encoding="utf-8") as f:
                _JOBS_DB = json.load(f)

_load_jobs()  # pre-load at startup

_ROLE_ALIASES = {
    "Data Science / Analytics":             "Data Science / Analytics",
    "AI / ML Engineering":                  "AI / ML Engineering",
    "Software / Full-Stack Engineering":    "Software / Full-Stack Engineering",
    "Cloud / DevOps":                       "Cloud / DevOps",
    "Cybersecurity":                        "Cybersecurity",
    "Product Management":                   "Product Management",
    "Digital Marketing / Growth":           "Digital Marketing / Growth",
    "Finance / BFSI":                       "Finance / BFSI",
    # quiz icon prefixes
    "📊 Data Science / Analytics":          "Data Science / Analytics",
    "🤖 AI / ML Engineering":              "AI / ML Engineering",
    "💻 Software / Full-Stack Engineering": "Software / Full-Stack Engineering",
    "☁️ Cloud / DevOps":                 "Cloud / DevOps",
    "🔐 Cybersecurity":                    "Cybersecurity",
    "📱 Product Management":               "Product Management",
    "📈 Digital Marketing / Growth":       "Digital Marketing / Growth",
    "💰 Finance / BFSI":                   "Finance / BFSI",
}

# Which exp bands are compatible with each experience category
_EXP_COMPAT = {
    "0":   {"0-1", "any"},
    "0-1": {"0-1", "any"},
    "1-3": {"0-1", "1-3", "any"},
    "3-5": {"1-3", "3-5", "any"},
    "5+":  {"3-5", "5+", "any"},
}


@app.post("/api/v1/jobs/search", tags=["Jobs"])
async def search_jobs(payload: dict):
    """
    Search Indian Job Market 2025 dataset (38k+ jobs, Naukri).
    Matches by role → skills → city → experience. Returns top N ranked results.

    Body: { skills_flat, roles, cities, experience, limit }
    """
    _load_jobs()

    user_skills  = [s.strip().lower() for s in payload.get("skills_flat", [])]
    raw_roles    = payload.get("roles", [])
    cities_raw   = payload.get("cities", [])
    exp_cat      = str(payload.get("experience", "0"))
    limit        = min(int(payload.get("limit", 20)), 50)

    # Resolve role aliases (strip emoji prefixes from quiz)
    target_roles, seen_r = [], set()
    for r in raw_roles:
        canon = _ROLE_ALIASES.get(r) or _ROLE_ALIASES.get(r.strip())
        if not canon:
            # try stripping leading emoji chars
            stripped = r.strip()
            for alias, val in _ROLE_ALIASES.items():
                if stripped.endswith(val):
                    canon = val
                    break
        if canon and canon not in seen_r:
            target_roles.append(canon)
            seen_r.add(canon)

    primary_role = target_roles[0] if target_roles else _guess_role(user_skills)
    allowed_exp  = _EXP_COMPAT.get(exp_cat, {"0-1", "any"})
    cities_lower = [c.strip().lower() for c in cities_raw if c.strip()]

    scored = []
    for job in _JOBS_DB:
        job_role   = job["role"]
        job_skills = job.get("skills", [])   # already lowercase
        job_city   = job.get("location", "").lower()
        job_exp    = job.get("exp", "any")

        # Hard filter by role
        if target_roles and job_role not in target_roles:
            continue

        score = 0

        # 1. Role priority (40 pts)
        score += 40 if job_role == primary_role else 25

        # 2. Skill overlap (40 pts)
        matched = []
        if job_skills and user_skills:
            for js in job_skills:
                if any(us in js or js in us for us in user_skills):
                    matched.append(js)
            score += round((len(matched) / len(job_skills)) * 40)

        # 3. City match (10 pts)
        if cities_lower:
            if any(c in job_city for c in cities_lower):
                score += 10
        else:
            score += 3  # neutral bonus when no city preference

        # 4. Experience match (10 pts)
        if job_exp in allowed_exp:
            score += 10

        # 5. Has rating bonus (2 pts)
        if job.get("rating"):
            score += 2

        skill_pct = round(len(matched) / len(job_skills) * 100) if job_skills else 0

        # Classify exp_band + job_type for filter pills
        exp_num_map = {"0-1": 0, "1-3": 2, "3-5": 4, "5+": 6, "any": 0}
        exp_num = exp_num_map.get(job_exp, 0)
        exp_band = "Entry Level" if exp_num == 0 else ("Senior" if exp_num > 4 else "Mid-Senior")
        job_type = job.get("job_type", "")
        if not job_type:
            tl = job.get("title","").lower()
            sl = " ".join(job.get("skills",[])).lower()
            job_type = "Contract" if any(k in tl or k in sl for k in ["contract","freelance","consultant","part-time","temporary"]) else "Full-time"

        scored.append({
            **job,
            "exp_band":        exp_band,
            "job_type":        job_type,
            "match_score":     score,
            "matched_skills":  matched,
            "skill_match_pct": skill_pct,
        })

    # Sort: score desc → skill_pct desc → exp band
    scored.sort(key=lambda x: (-x["match_score"], -x["skill_match_pct"]))
    results = scored[:limit]

    return {
        "status":        "ok",
        "source":        "kaggle_indian_jobs_2025",
        "total_matched": len(scored),
        "returned":      len(results),
        "primary_role":  primary_role,
        "jobs":          results,
    }


def _guess_role(skills: list[str]) -> str:
    """Infer best role from skills when user hasn't specified one."""
    s = " ".join(skills)
    if any(k in s for k in ["machine learning","deep learning","nlp","tensorflow","pytorch","keras"]):
        return "AI / ML Engineering"
    if any(k in s for k in ["data science","pandas","tableau","power bi","data analysis","sql"]):
        return "Data Science / Analytics"
    if any(k in s for k in ["aws","azure","gcp","kubernetes","docker","devops","terraform"]):
        return "Cloud / DevOps"
    if any(k in s for k in ["cybersecurity","penetration","infosec","network security"]):
        return "Cybersecurity"
    if any(k in s for k in ["seo","digital marketing","google analytics","content marketing"]):
        return "Digital Marketing / Growth"
    if any(k in s for k in ["financial modeling","equity","accounting","risk management","bfsi"]):
        return "Finance / BFSI"
    if any(k in s for k in ["product manager","roadmap","stakeholder","product owner"]):
        return "Product Management"
    return "Software / Full-Stack Engineering"


@app.get("/api/v1/jobs/test", tags=["Jobs"])
async def test_jobs():
    """Dataset stats. Visit http://localhost:8000/api/v1/jobs/test"""
    _load_jobs()
    from collections import Counter
    roles  = Counter(j["role"] for j in _JOBS_DB)
    cities = Counter(j["location"] for j in _JOBS_DB)
    sample_per_role = {}
    for role in roles:
        sample = next((j for j in _JOBS_DB if j["role"] == role), {})
        sample_per_role[role] = {
            "title": sample.get("title"),
            "company": sample.get("company"),
            "skills": sample.get("skills", [])[:5],
        }
    return {
        "total_jobs":      len(_JOBS_DB),
        "by_role":         dict(roles.most_common()),
        "top_cities":      dict(cities.most_common(10)),
        "sample_per_role": sample_per_role,
    }


@app.get("/api/v1/jobs/test", tags=["Jobs"])
async def test_jobs():
    """Diagnostic: shows dataset stats. Visit http://localhost:8000/api/v1/jobs/test"""
    _load_jobs()
    from collections import Counter
    roles = Counter(j["role"] for j in _JOBS_DB)
    cities = Counter(j["location"] for j in _JOBS_DB)
    return {
        "total_jobs": len(_JOBS_DB),
        "by_role": dict(roles.most_common()),
        "top_cities": dict(cities.most_common(10)),
        "sample_ds": next((j for j in _JOBS_DB if j["role"] == "Data Science / Analytics"), {}),
        "sample_swe": next((j for j in _JOBS_DB if j["role"] == "Software / Full-Stack Engineering"), {}),
    }


@app.get("/api/v1/health", tags=["System"])
def health():
    return {"status": "ok", "version": "4.0.0",
            "flow": "/ (quiz) → /deet (register) → / (report)",
            "registered_profiles": len(_profiles)}


def _map_degree(degree_str: str) -> str:
    d = (degree_str or "").lower()
    if any(x in d for x in ["b.tech","b.e","bachelor","bca","bsc"]):      return "bachelors"
    if any(x in d for x in ["m.tech","m.e","master","mca","msc","mba"]): return "masters"
    if any(x in d for x in ["phd","ph.d","doctorate"]):                   return "phd"
    if "diploma" in d:                                                      return "diploma"
    return "bachelors"


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)



