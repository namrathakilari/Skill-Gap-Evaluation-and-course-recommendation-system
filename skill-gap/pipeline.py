#!/usr/bin/env python3
"""
India Skill Gap System — Dataset Processing Pipeline
=====================================================

STEP 1: Download these datasets from Kaggle (requires free Kaggle account):
  - Indeed India:    kaggle datasets download promptcloud/india-job-data-from-indeed
  - Naukri:          kaggle datasets download iqbal303/job-postings-dataset-from-naukri-com
  - LinkedIn India:  kaggle datasets download michellemiranda/linkedin-jobs-dataset-for-india
  - Internshala:     kaggle datasets download vipul143/internshala-internship-dataset
  - Internshala Aug: kaggle datasets download rahulbharadwaj0506/internshala-internships-dataset-aug-2023
  - Coursera 2023:   kaggle datasets download tianyimasf/coursera-course-dataset
  - Udemy 2023:      kaggle datasets download ankushbisht005/udemy-courses-data-2023

STEP 2: Place unzipped CSVs in ./data/ and run:
  python3 pipeline.py

STEP 3: Outputs written to ./output/db.json — paste into the quiz HTML.

What this script does with each dataset
-----------------------------------------
INDEED INDIA (india-job-data-from-indeed):
  Columns used: job_title, company_name, location, salary, skills, job_type
  → Extracts: top skills per role category, salary ranges, city demand

NAUKRI (job-postings-dataset-from-naukri-com):
  Columns used: Job Title, Company, Location, Skills, Experience, Salary
  → Extracts: skills frequency by role, experience band salary, top companies

LINKEDIN INDIA (linkedin-jobs-dataset-for-india):
  Columns used: title, company, location, skills_desc, applies, listed_time
  → Extracts: demand index (apply count proxy), top cities, role velocity

INTERNSHALA (internshala-internship-dataset):
  Columns used: Profile, Stipend, Location, Work_From_Home, Duration, Skills_Required
  → Extracts: internship listings, stipend ranges, WFH flag, skills needed

COURSERA 2023 (coursera-course-dataset):
  Columns used: course_name, institution, difficulty_level, course_rating, course_url, skills
  → Extracts: course-skill mappings, ratings, difficulty

UDEMY 2023 (udemy-courses-data-2023):
  Columns used: title, rating, num_subscribers, price, topic, course_url
  → Extracts: course-skill mappings, popularity (subscribers), price
"""

import json, os, re
from collections import Counter, defaultdict

# ── CONFIG ──────────────────────────────────────────────────────
DATA_DIR = "./data"
OUTPUT_DIR = "./output"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Role classification keywords (maps free-text job titles → canonical role)
ROLE_KEYWORDS = {
    "Software / Full-Stack Engineering": [
        "software engineer","full stack","backend","frontend","web developer",
        "java developer","python developer","node","react","angular","spring"
    ],
    "Data Science / Analytics": [
        "data scientist","data analyst","business analyst","analytics","bi developer",
        "power bi","tableau","reporting","data engineer"
    ],
    "AI / ML Engineering": [
        "machine learning","ml engineer","ai engineer","deep learning","nlp",
        "computer vision","llm","generative ai","research scientist"
    ],
    "Cloud / DevOps": [
        "devops","cloud engineer","aws","azure","gcp","kubernetes","docker",
        "site reliability","sre","infrastructure","terraform"
    ],
    "Cybersecurity": [
        "security analyst","cybersecurity","soc analyst","penetration","ethical hacker",
        "infosec","network security","vapt","cissp","ceh"
    ],
    "Product Management": [
        "product manager","product owner","program manager","scrum master",
        "agile coach","product lead"
    ],
    "Digital Marketing / Growth": [
        "digital marketing","seo","sem","growth hacker","content marketer",
        "social media","performance marketing","google ads","meta ads"
    ],
    "Finance / BFSI": [
        "financial analyst","investment banking","equity research","ca ","cfa",
        "risk analyst","credit analyst","auditor","finance manager","treasury"
    ]
}

def classify_role(title):
    t = title.lower()
    for role, kws in ROLE_KEYWORDS.items():
        if any(kw in t for kw in kws):
            return role
    return None

# Role-specific curated skill lists — only these skills will appear per role
ROLE_SKILLS = {
    "Data Science / Analytics": [
        "Python", "SQL", "R", "Machine Learning", "Deep Learning", "NLP",
        "Data Analysis", "Data Science", "Data Engineering", "Data Modeling",
        "Business Analysis", "Business Intelligence", "Statistical Analysis", "Statistical Modeling",
        "Power BI", "Tableau", "Excel", "Looker", "QlikView",
        "Spark", "Hadoop", "Kafka", "Airflow", "dbt", "ETL", "Data Pipeline",
        "TensorFlow", "PyTorch", "Scikit-learn", "MATLAB", "SAS", "SPSS",
        "MySQL", "PostgreSQL", "MongoDB", "Git", "AWS", "Azure", "GCP",
    ],
    "AI / ML Engineering": [
        "Python", "Machine Learning", "Deep Learning", "NLP", "Computer Vision",
        "Generative AI", "LLM", "TensorFlow", "PyTorch", "Keras", "Scikit-learn", "OpenCV",
        "SQL", "Spark", "Docker", "Kubernetes", "AWS", "Azure", "GCP",
        "MLOps", "Data Engineering", "Statistical Modeling", "Git", "Linux",
        "Airflow", "dbt", "FastAPI", "REST API",
    ],
    "Software / Full-Stack Engineering": [
        "Python", "Java", "JavaScript", "TypeScript", "C++", "C#", "Go", "Scala",
        "React", "Angular", "Node.js", "Django", "Flask", "Spring Boot", "FastAPI",
        "MySQL", "PostgreSQL", "MongoDB", "Redis", "Elasticsearch",
        "Docker", "Kubernetes", "AWS", "Azure", "GCP", "CI/CD", "Git",
        "REST API", "GraphQL", "Microservices", "System Design", "HTML", "CSS", "Linux",
    ],
    "Cloud / DevOps": [
        "AWS", "Azure", "GCP", "Docker", "Kubernetes", "Terraform", "Jenkins", "CI/CD",
        "Linux", "Shell Scripting", "Python", "Git",
        "DevOps", "MLOps", "Cloud Computing", "Microservices", "REST API",
        "Kafka", "Elasticsearch",
    ],
    "Cybersecurity": [
        "Cybersecurity", "Network Security", "Penetration Testing", "VAPT", "SOC",
        "Python", "Linux", "Shell Scripting",
        "Risk Analysis", "Cloud Security", "AWS", "Azure", "Cryptography",
    ],
    "Product Management": [
        "Product Management", "Roadmapping", "JIRA", "Agile", "Scrum",
        "SQL", "Data Analysis", "A/B Testing", "User Research",
        "Business Analysis", "Python", "Tableau", "Power BI",
    ],
    "Digital Marketing / Growth": [
        "SEO", "SEM", "Google Ads", "Meta Ads", "Performance Marketing", "Content Marketing",
        "Digital Marketing", "Social Media", "Email Marketing", "Growth Hacking",
        "Data Analysis", "SQL", "Excel", "Tableau",
    ],
    "Finance / BFSI": [
        "Financial Modeling", "Equity Research", "Risk Analysis", "Valuation",
        "Excel", "Python", "SQL", "R", "MATLAB",
        "Statistical Analysis", "Data Analysis", "Power BI", "Tableau",
    ],
}

# Flat list of all known skills for generic parsing
KNOWN_SKILLS = sorted(set(sk for skills in ROLE_SKILLS.values() for sk in skills), key=len, reverse=True)

def parse_skills(raw, role=None):
    """Parse skills from raw text. If role is given, filter to that role's skill list."""
    if not raw or (isinstance(raw, float)):
        return []
    s = str(raw).strip()

    allowed = ROLE_SKILLS.get(role, KNOWN_SKILLS) if role else KNOWN_SKILLS

    # Try standard delimiters first
    for delim in ["|", ",", ";", "\n"]:
        parts = [p.strip().strip('"\'[]') for p in s.split(delim)]
        if len(parts) > 1:
            cleaned = [p for p in parts if 2 < len(p) < 60]
            if role:
                allowed_lower = {a.lower(): a for a in allowed}
                return [allowed_lower[p.lower()] for p in cleaned if p.lower() in allowed_lower]
            return cleaned

    # For concatenated strings, match against allowed skill list
    found = []
    s_lower = s.lower()
    for skill in allowed:
        if skill.lower() in s_lower:
            found.append(skill)
    return found if found else ([s] if 2 < len(s) < 60 else [])


def parse_salary_inr(raw):
    """Return (min_lpa, max_lpa) tuple or None."""
    if not raw or (isinstance(raw, float)):
        return None
    s = str(raw).lower().replace(",","").replace(" ","")
    # patterns: "4-6lpa", "₹400000-600000", "400000to600000"
    nums = re.findall(r'[\d.]+', s)
    if not nums:
        return None
    vals = [float(n) for n in nums[:2]]
    # Convert to LPA if values look like absolute (>100)
    if vals[0] > 100:
        vals = [v/100000 for v in vals]
    if len(vals) == 2 and 1 <= vals[0] <= 200 and 1 <= vals[1] <= 200:
        return (round(vals[0],1), round(vals[1],1))
    if len(vals) == 1 and 1 <= vals[0] <= 200:
        return (round(vals[0],1), round(vals[0],1))
    return None

# ── PROCESS INDEED INDIA ─────────────────────────────────────────
def process_indeed(filepath):
    print(f"Processing Indeed India: {filepath}")
    try:
        import csv
        results = defaultdict(lambda: {"skills": Counter(), "salaries": [], "cities": Counter(), "companies": Counter()})
        with open(filepath, encoding="utf-8", errors="ignore") as f:
            reader = csv.DictReader(f)
            # Detect actual column names
            sample = reader.fieldnames or []
            print(f"  Columns: {sample[:10]}")
            # Common column aliases in this dataset
            title_col = next((c for c in sample if "title" in c.lower() or "job" in c.lower()), None)
            skill_col = next((c for c in sample if "skill" in c.lower()), None)
            salary_col = next((c for c in sample if "salary" in c.lower() or "pay" in c.lower()), None)
            loc_col = next((c for c in sample if "location" in c.lower() or "city" in c.lower()), None)
            co_col = next((c for c in sample if "company" in c.lower()), None)

            for row in reader:
                role = classify_role(row.get(title_col,"") if title_col else "")
                if not role:
                    continue
                if skill_col:
                    for sk in parse_skills(row.get(skill_col,""), role):
                        results[role]["skills"][sk] += 1
                if salary_col:
                    sal = parse_salary_inr(row.get(salary_col,""))
                    if sal:
                        results[role]["salaries"].append(sal)
                if loc_col:
                    city = str(row.get(loc_col,"")).strip().split(",")[0].strip()
                    if city:
                        results[role]["cities"][city] += 1
                if co_col:
                    co = str(row.get(co_col,"")).strip()
                    if co:
                        results[role]["companies"][co] += 1
        return results
    except Exception as e:
        print(f"  ERROR: {e}")
        return {}

# ── PROCESS NAUKRI ───────────────────────────────────────────────
def process_naukri(filepath):
    print(f"Processing Naukri: {filepath}")
    try:
        import csv
        results = defaultdict(lambda: {"skills": Counter(), "salaries_by_exp": defaultdict(list), "companies": Counter()})
        with open(filepath, encoding="utf-8", errors="ignore") as f:
            reader = csv.DictReader(f)
            sample = reader.fieldnames or []
            print(f"  Columns: {sample[:10]}")
            title_col  = next((c for c in sample if "title" in c.lower() or "designation" in c.lower()), None)
            skill_col  = next((c for c in sample if "skill" in c.lower()), None)
            # Accept "Package_Details" or any salary/package column
            salary_col = next((c for c in sample if "package" in c.lower() or "salary" in c.lower()), None)
            exp_col    = next((c for c in sample if "experience" in c.lower() or "exp" in c.lower()), None)
            co_col     = next((c for c in sample if "company" in c.lower()), None)

            for row in reader:
                role = classify_role(row.get(title_col,"") if title_col else "")
                if not role:
                    continue

                # Skills — use parse_skills (handles delimiters + known skill matching)
                if skill_col:
                    for sk in parse_skills(row.get(skill_col, ""), role):
                        results[role]["skills"][sk] += 1

                # Salary — also handles "Not disclosed"
                if salary_col and exp_col:
                    sal = parse_salary_inr(row.get(salary_col,""))
                    exp_raw = str(row.get(exp_col,""))
                    if sal:
                        exp_nums = re.findall(r'\d+', exp_raw)
                        if exp_nums:
                            exp_val = int(exp_nums[0])
                            band = "fresher" if exp_val <= 1 else "mid" if exp_val <= 5 else "senior"
                            results[role]["salaries_by_exp"][band].append(sal)

                if co_col:
                    co = str(row.get(co_col,"")).strip()
                    if co:
                        results[role]["companies"][co] += 1
        return results
    except Exception as e:
        print(f"  ERROR: {e}")
        return {}

# ── PROCESS LINKEDIN INDIA ───────────────────────────────────────
def process_linkedin(filepath):
    print(f"Processing LinkedIn India: {filepath}")
    try:
        import csv
        results = defaultdict(lambda: {"apply_count": 0, "cities": Counter(), "companies": Counter(), "skills": Counter()})
        with open(filepath, encoding="utf-8", errors="ignore") as f:
            reader = csv.DictReader(f)
            sample = reader.fieldnames or []
            print(f"  Columns: {sample[:10]}")
            title_col  = next((c for c in sample if "title" in c.lower()), None)
            apply_col  = next((c for c in sample if "application" in c.lower() or "appli" in c.lower()), None)
            city_col   = next((c for c in sample if "city" in c.lower()), None)
            state_col  = next((c for c in sample if "state" in c.lower()), None)
            co_col     = next((c for c in sample if "company" in c.lower()), None)
            desc_col   = next((c for c in sample if "description" in c.lower()), None)

            for row in reader:
                role = classify_role(row.get(title_col,"") if title_col else "")
                if not role:
                    continue

                # Extract skills from "Skill: x, y, z;" pattern in description
                if desc_col:
                    desc = row.get(desc_col, "")
                    skill_match = re.search(r'Skill:\s*([^;]+)', str(desc), re.IGNORECASE)
                    if skill_match:
                        for sk in skill_match.group(1).split(","):
                            sk = sk.strip()
                            if 2 < len(sk) < 50:
                                results[role]["skills"][sk] += 1

                # Applications count as demand proxy
                if apply_col:
                    try:
                        results[role]["apply_count"] += float(str(row.get(apply_col, 0) or 0).split(".")[0])
                    except:
                        pass

                # City — prefer city column, fall back to state
                city = ""
                if city_col:
                    city = str(row.get(city_col, "")).strip()
                if not city and state_col:
                    city = str(row.get(state_col, "")).strip()
                if city:
                    results[role]["cities"][city] += 1

                if co_col:
                    co = str(row.get(co_col,"")).strip()
                    if co:
                        results[role]["companies"][co] += 1

        return results
    except Exception as e:
        print(f"  ERROR: {e}")
        return {}

# ── PROCESS INTERNSHALA ──────────────────────────────────────────
def process_internshala(filepath):
    print(f"Processing Internshala: {filepath}")
    try:
        import csv
        listings = []
        with open(filepath, encoding="utf-8", errors="ignore") as f:
            reader = csv.DictReader(f)
            sample = reader.fieldnames or []
            print(f"  Columns: {sample[:15]}")
            profile_col = next((c for c in sample if "profile" in c.lower() or "title" in c.lower() or "role" in c.lower()), None)
            stipend_col = next((c for c in sample if "stipend" in c.lower()), None)
            loc_col = next((c for c in sample if "location" in c.lower() or "city" in c.lower()), None)
            wfh_col = next((c for c in sample if "work_from_home" in c.lower() or "remote" in c.lower() or "wfh" in c.lower()), None)
            dur_col = next((c for c in sample if "duration" in c.lower()), None)
            skill_col = next((c for c in sample if "skill" in c.lower()), None)
            co_col = next((c for c in sample if "company" in c.lower()), None)

            for row in reader:
                profile = str(row.get(profile_col,"")).strip() if profile_col else ""
                if not profile:
                    continue
                role = classify_role(profile)
                if not role:
                    continue
                listing = {
                    "role": profile,
                    "canonicalRole": role,
                    "company": str(row.get(co_col,"")).strip() if co_col else "Company via Internshala",
                    "stipend": str(row.get(stipend_col,"")).strip() if stipend_col else "Unpaid/Negotiable",
                    "location": str(row.get(loc_col,"")).strip() if loc_col else "India",
                    "wfh": str(row.get(wfh_col,"")).strip().lower() in ["yes","true","1","y","work from home"] if wfh_col else False,
                    "duration": str(row.get(dur_col,"")).strip() if dur_col else "",
                    "skills": parse_skills(row.get(skill_col,"") if skill_col else ""),
                    "source": f"Internshala Dataset ({os.path.basename(filepath)})"
                }
                listings.append(listing)
        print(f"  Found {len(listings)} classified internship listings")
        return listings
    except Exception as e:
        print(f"  ERROR: {e}")
        return []

# ── PROCESS COURSERA ─────────────────────────────────────────────
def process_coursera(filepath):
    print(f"Processing Coursera: {filepath}")
    try:
        import csv
        courses = []
        with open(filepath, encoding="utf-8", errors="ignore") as f:
            reader = csv.DictReader(f)
            sample = reader.fieldnames or []
            print(f"  Columns: {sample[:15]}")
            name_col = next((c for c in sample if "name" in c.lower() or "title" in c.lower() or "course" in c.lower()), None)
            inst_col = next((c for c in sample if "institution" in c.lower() or "provider" in c.lower() or "partner" in c.lower()), None)
            rating_col = next((c for c in sample if "rating" in c.lower()), None)
            diff_col = next((c for c in sample if "difficulty" in c.lower() or "level" in c.lower()), None)
            url_col = next((c for c in sample if "url" in c.lower() or "link" in c.lower()), None)
            skill_col = next((c for c in sample if "skill" in c.lower()), None)

            for row in reader:
                name = str(row.get(name_col,"")).strip() if name_col else ""
                if not name:
                    continue
                try:
                    rating = float(str(row.get(rating_col,"0")).strip())
                except:
                    rating = 0
                if rating < 4.0:  # Filter low-quality courses
                    continue
                courses.append({
                    "title": name,
                    "platform": "Coursera",
                    "by": str(row.get(inst_col,"")).strip() if inst_col else "",
                    "rating": rating,
                    "difficulty": str(row.get(diff_col,"")).strip() if diff_col else "",
                    "url": str(row.get(url_col,"")).strip() if url_col else "https://www.coursera.org",
                    "skills": parse_skills(row.get(skill_col,"") if skill_col else ""),
                    "cost": "Free audit available",
                    "source": f"Coursera 2023 Dataset (Kaggle: tianyimasf, {os.path.basename(filepath)})"
                })
        print(f"  Found {len(courses)} Coursera courses (rating ≥ 4.0)")
        return courses
    except Exception as e:
        print(f"  ERROR: {e}")
        return []

# ── PROCESS UDEMY ────────────────────────────────────────────────
def process_udemy(filepath):
    print(f"Processing Udemy: {filepath}")
    try:
        import csv
        courses = []
        with open(filepath, encoding="utf-8", errors="ignore") as f:
            reader = csv.DictReader(f)
            sample = reader.fieldnames or []
            print(f"  Columns: {sample[:10]}")
            title_col   = next((c for c in sample if "title" in c.lower()), None)
            url_col     = next((c for c in sample if "url" in c.lower()), None)
            rating_col  = next((c for c in sample if "rating" in c.lower()), None)
            reviews_col = next((c for c in sample if "review" in c.lower() or "subscriber" in c.lower()), None)

            for row in reader:
                title = str(row.get(title_col,"")).strip() if title_col else ""
                if not title:
                    continue
                try:
                    rating = float(row.get(rating_col, 0) or 0)
                except:
                    rating = 0.0
                try:
                    reviews = int(str(row.get(reviews_col, 0) or 0).split(".")[0])
                except:
                    reviews = 0
                if rating < 4.0 or reviews < 1000:
                    continue

                url = str(row.get(url_col,"")).strip() if url_col else ""
                if url and not url.startswith("http"):
                    url = "https://www.udemy.com" + url

                # Infer topic and skills from title keywords
                topic = ""
                title_lower = title.lower()
                for role, kws in ROLE_KEYWORDS.items():
                    if any(kw in title_lower for kw in kws):
                        topic = role
                        break

                courses.append({
                    "title": title,
                    "platform": "Udemy",
                    "by": "",
                    "rating": round(rating, 1),
                    "subscribers": reviews,
                    "price_inr": "Check Udemy",
                    "topic": topic,
                    "url": url,
                    "skills": [topic] if topic else [],
                    "source": "Udemy Dataset (Kaggle)"
                })

        courses.sort(key=lambda x: x["subscribers"], reverse=True)
        print(f"  Found {len(courses)} Udemy courses (rating ≥ 4.0, ≥1K reviews)")
        return courses
    except Exception as e:
        print(f"  ERROR: {e}")
        return []

# ── PROCESS JOBS (Indian Job Market Dataset 2025 · Kaggle) ───────
def process_jobs(filepath):
    print(f"Processing Jobs Dataset: {filepath}")
    try:
        import openpyxl, re as _re

        # City normalisation map
        CITY_MAP = {
            "bengaluru": "Bengaluru", "bangalore": "Bengaluru",
            "hyderabad": "Hyderabad", "secunderabad": "Hyderabad",
            "mumbai": "Mumbai", "navi mumbai": "Mumbai",
            "mumbai suburban": "Mumbai", "thane": "Mumbai",
            "pune": "Pune",
            "delhi": "Delhi NCR", "gurugram": "Delhi NCR", "gurgaon": "Delhi NCR",
            "noida": "Delhi NCR", "new delhi": "Delhi NCR", "faridabad": "Delhi NCR",
            "greater noida": "Delhi NCR",
            "chennai": "Chennai", "kolkata": "Kolkata",
            "ahmedabad": "Ahmedabad", "chandigarh": "Chandigarh",
            "jaipur": "Jaipur", "kochi": "Kochi",
            "coimbatore": "Coimbatore", "indore": "Indore",
            "bhopal": "Bhopal", "nagpur": "Nagpur",
            "remote": "Remote",
        }

        def _norm_city(raw):
            r = _re.sub(r'^hybrid\s*[-–]\s*', '', (raw or "").lower().strip())
            for k, v in CITY_MAP.items():
                if k in r:
                    return v
            return (raw or "").split(",")[0].split("(")[0].strip()[:30] or "India"

        def _norm_exp(min_e, max_e):
            try:
                lo = int(float(min_e or 0))
            except:
                lo = 0
            if lo <= 1: return "0-1"
            if lo <= 3: return "1-3"
            if lo <= 5: return "3-5"
            return "5+"

        def _fmt_salary(sal_str, min_s, max_s):
            if sal_str and str(sal_str).strip() not in ("", "Not disclosed"):
                return str(sal_str).strip()
            try:
                lo, hi = int(float(min_s or 0)), int(float(max_s or 0))
                if lo > 0 and hi > 0:
                    return f"₹{lo//100000}–{hi//100000} LPA"
                if lo > 0:
                    return f"₹{lo//100000}+ LPA"
            except:
                pass
            return ""

        wb = openpyxl.load_workbook(filepath, read_only=True)
        ws = wb.active
        headers = [cell.value for cell in next(ws.iter_rows(min_row=1, max_row=1))]
        print(f"  Columns: {headers[:10]}")

        # Column detection
        def _col(keywords):
            return next((h for h in headers if h and any(k in h.lower() for k in keywords)), None)

        title_col   = _col(["title"])
        co_col      = _col(["companyname", "company"])
        skill_col   = _col(["tagsandskills", "skills", "tags"])
        loc_col     = _col(["location"])
        exp_col     = _col(["experience"])
        sal_col     = _col(["salary"])
        min_sal_col = _col(["minimumsalary", "min_salary"])
        max_sal_col = _col(["maximumsalary", "max_salary"])
        min_exp_col = _col(["minimumexperience", "min_exp"])
        max_exp_col = _col(["maximumexperience", "max_exp"])
        id_col      = _col(["jobid", "id"])
        rating_col  = _col(["aggregaterating", "rating"])
        uploaded_col = _col(["jobuploaded", "uploaded"])

        jobs_by_role = defaultdict(list)
        seen_ids = set()
        total_added = 0

        for row in ws.iter_rows(min_row=2, values_only=True):
            d = dict(zip(headers, row))

            title   = str(d.get(title_col) or "").strip()
            company = str(d.get(co_col) or "").strip()
            if not title or not company:
                continue

            role = classify_role(title)
            # Fallback: classify by skills if title doesn't match
            if not role:
                skills_raw = str(d.get(skill_col) or "")
                role = classify_role(skills_raw)
            if not role:
                continue

            # Dedup by jobId
            job_id = str(d.get(id_col) or "")
            key = job_id if job_id else f"{title[:40]}|{company[:20]}"
            if key in seen_ids:
                continue
            seen_ids.add(key)

            # Parse skills — comma-separated tagsAndSkills field
            skills_raw = str(d.get(skill_col) or "")
            skill_list = [s.strip().lower() for s in skills_raw.split(",")
                          if s.strip() and 1 < len(s.strip()) < 50][:15]

            city   = _norm_city(str(d.get(loc_col) or ""))
            exp    = _norm_exp(d.get(min_exp_col), d.get(max_exp_col))
            salary = _fmt_salary(d.get(sal_col), d.get(min_sal_col), d.get(max_sal_col))

            # ── Classify exp_band and job_type for filter pills ─────────────
            try:
                min_e = int(float(d.get(min_exp_col) or 0))
            except:
                min_e = 0
            if min_e == 0:
                exp_band = "Entry Level"
            elif min_e <= 4:
                exp_band = "Mid-Senior"
            else:
                exp_band = "Senior"

            # Infer job_type from title/skills keywords
            title_lower = title.lower()
            skills_lower = skills_raw.lower()
            if any(k in title_lower or k in skills_lower for k in ["contract","freelance","consultant","part-time","part time","temporary"]):
                job_type = "Contract"
            else:
                job_type = "Full-time"
            rating = str(d.get(rating_col) or "").strip()
            uploaded = str(d.get(uploaded_col) or "").strip()

            # Direct Naukri apply URL
            url = f"https://www.naukri.com/job-listings-{job_id}" if job_id else ""

            jobs_by_role[role].append({
                "title":    title[:80],
                "company":  company[:60],
                "location": city,
                "role":     role,
                "exp":      exp,
                "exp_band": exp_band,
                "job_type": job_type,
                "salary":   salary,
                "skills":   skill_list,
                "url":      url,
                "rating":   rating,
                "uploaded": uploaded,
            })
            total_added += 1

            if total_added % 10000 == 0:
                print(f"  {total_added} jobs processed...")

        print(f"  Found {total_added} classified jobs across {len(jobs_by_role)} roles:")
        for role, lst in sorted(jobs_by_role.items(), key=lambda x: -len(x[1])):
            print(f"    {role}: {len(lst)}")
        return dict(jobs_by_role)

    except Exception as e:
        import traceback
        print(f"  ERROR: {e}")
        traceback.print_exc()
        return {}


# ── AGGREGATE & BUILD DB ─────────────────────────────────────────
def aggregate(indeed, naukri, linkedin, internshala_listings, coursera_courses, udemy_courses, jobs_by_role=None):
    db = {"roles": {}, "internships": {}, "courses": {}, "jobs": {}, "sources": {}}

    all_roles = list(ROLE_KEYWORDS.keys())

    for role in all_roles:
        # SKILLS: merge frequency counts from Naukri + LinkedIn
        skill_counter = Counter()
        if role in indeed:
            skill_counter.update(indeed[role]["skills"])
        if role in naukri:
            skill_counter.update(naukri[role]["skills"])
        if role in linkedin:
            skill_counter.update(linkedin[role]["skills"])
        top_skills = [s for s,_ in skill_counter.most_common(12) if len(s) > 2]

        # SALARY: from Naukri (has structured salary + exp band)
        sal = {"fresher": None, "mid": None, "senior": None}
        if role in naukri:
            for band in ["fresher","mid","senior"]:
                vals = naukri[role]["salaries_by_exp"].get(band,[])
                if vals:
                    mins = [v[0] for v in vals]
                    maxs = [v[1] for v in vals]
                    sal[band] = f"₹{sorted(mins)[len(mins)//4]:.0f}–{sorted(maxs)[3*len(maxs)//4]:.0f} LPA"

        # CITIES: from Indeed + LinkedIn
        city_counter = Counter()
        if role in indeed:
            city_counter.update(indeed[role]["cities"])
        if role in linkedin:
            city_counter.update(linkedin[role]["cities"])
        top_cities = [c for c,_ in city_counter.most_common(5) if len(c) > 2]

        # COMPANIES: from Indeed + Naukri
        co_counter = Counter()
        if role in indeed:
            co_counter.update(indeed[role]["companies"])
        if role in naukri:
            co_counter.update(naukri[role]["companies"])
        top_cos = [c for c,_ in co_counter.most_common(6) if len(c) > 2]

        # DEMAND INDEX: from LinkedIn apply count (normalised 0-100)
        apply_count = linkedin[role]["apply_count"] if role in linkedin else 0

        db["roles"][role] = {
            "topSkills": top_skills,
            "salaryFresher": sal["fresher"] or "Data insufficient",
            "salaryMid": sal["mid"] or "Data insufficient",
            "salarySenior": sal["senior"] or "Data insufficient",
            "topCities": top_cities,
            "topCos": top_cos,
            "rawApplyCount": apply_count  # normalise after all roles processed
        }

    # Normalise demand index
    max_apply = max((db["roles"][r]["rawApplyCount"] for r in db["roles"]), default=1)
    for role in db["roles"]:
        raw = db["roles"][role].pop("rawApplyCount")
        db["roles"][role]["demandIndex"] = round((raw / max(max_apply,1)) * 100) if max_apply else 0

    # INTERNSHIPS: group by canonical role
    for listing in internshala_listings:
        role = listing["canonicalRole"]
        if role not in db["internships"]:
            db["internships"][role] = []
        if len(db["internships"][role]) < 4:  # max 4 per role
            db["internships"][role].append(listing)

    # COURSES: map by skill keyword
    # Coursera — map each course to skills it teaches
    for c in coursera_courses:
        for sk in c["skills"]:
            key = sk.strip().title()
            if key not in db["courses"]:
                db["courses"][key] = []
            if len(db["courses"][key]) < 3:
                db["courses"][key].append(c)

    # Udemy — map by topic field
    for c in udemy_courses:
        key = c["topic"].strip().title() if c["topic"] else ""
        if not key:
            continue
        if key not in db["courses"]:
            db["courses"][key] = []
        if len(db["courses"][key]) < 3:
            db["courses"][key].append(c)

    # JOBS: from Indian Job Market Dataset 2025 — keyed by canonical role
    if jobs_by_role:
        for role, listings in jobs_by_role.items():
            # Sort: salary-disclosed first, then by company rating
            def _job_sort_key(j):
                has_sal = 1 if j.get("salary") else 0
                try:
                    rat = float(j.get("rating") or 0)
                except:
                    rat = 0.0
                return (-has_sal, -rat)
            db["jobs"][role] = sorted(listings, key=_job_sort_key)

    # SOURCE TRANSPARENCY
    db["sources"] = {
        "naukri":      "Kaggle: iqbal303/job-postings-dataset-from-naukri-com",
        "linkedin":    "Kaggle: michellemiranda/linkedin-jobs-dataset-for-india",
        "internshala": "Kaggle: aayush9119/internshala-dataset",
        "udemy":       "Kaggle: ankushbisht005/udemy-courses-data-2023",
        "jobs":        "Kaggle: shivamshrivastava21/indian-job-market-dataset-2025-2026",
    }

    return db

# ── MAIN ─────────────────────────────────────────────────────────
def main():
    # Auto-detect CSV files in ./data/
    data_files = {}
    if os.path.exists(DATA_DIR):
        for root, dirs, files in os.walk(DATA_DIR):
            for f in files:
                fl = f.lower()
                parent = os.path.basename(root).lower()  # folder name
                ext = os.path.splitext(fl)[1]
                if ext not in (".csv", ".xlsx", ".xls"):
                    continue
                # Match by folder name OR filename
                if "naukri" in fl or "naukri" in parent:
                    data_files.setdefault("naukri", os.path.join(root, f))
                elif "linkedin" in fl or "linkedin" in parent:
                    data_files.setdefault("linkedin", os.path.join(root, f))
                elif "internshala" in fl or "internshala" in parent:
                    data_files.setdefault("internshala", os.path.join(root, f))
                elif "udemy" in fl or "udemy" in parent:
                    data_files.setdefault("udemy", os.path.join(root, f))
                elif "job" in fl or "job" in parent:
                    data_files.setdefault("jobs", os.path.join(root, f))
    print("\n=== India Skill Gap — Dataset Pipeline ===")
    print(f"Files detected: {list(data_files.keys())}\n")

    if not data_files:
        print("⚠️  No CSV files found in ./data/")
        print("    Download datasets from Kaggle and place CSVs in ./data/")
        print("    See comments at top of this file for dataset URLs.\n")
        # Write a sample empty db so the quiz still loads
        db = {"roles": {r: {"topSkills":[], "salaryFresher":"—","salaryMid":"—","salarySenior":"—","topCities":[],"topCos":[],"demandIndex":0} for r in ROLE_KEYWORDS}, "internships": {}, "courses": {}, "jobs": {}, "sources": {}}
        with open(os.path.join(OUTPUT_DIR,"db.json"), "w") as f:
            json.dump(db, f, indent=2)
        print(f"Empty db.json written to {OUTPUT_DIR}/db.json")
        return

    # Indeed removed as requested
    naukri   = process_naukri(data_files["naukri"])     if "naukri"   in data_files else {}
    linkedin = process_linkedin(data_files["linkedin"]) if "linkedin" in data_files else {}

    # Only using the new Internshala dataset
    internshala_listings = []
    if "internshala" in data_files:
        internshala_listings = process_internshala(data_files["internshala"])

    # Coursera removed, using only Udemy
    udemy_courses = process_udemy(data_files["udemy"]) if "udemy" in data_files else []

    # Indian Job Market Dataset 2025 (Kaggle) — xlsx
    jobs_by_role = process_jobs(data_files["jobs"]) if "jobs" in data_files else {}

    # Aggregate all sources
    db = aggregate({}, naukri, linkedin, internshala_listings, [], udemy_courses, jobs_by_role)

    out_path = os.path.join(OUTPUT_DIR, "db.json")
    with open(out_path, "w") as f:
        json.dump(db, f, indent=2)

    print(f"\n✅ Done! db.json written to {out_path}")
    print(f"   Roles populated:       {sum(1 for r in db['roles'] if db['roles'][r]['topSkills'])}")
    print(f"   Internship listings:   {sum(len(v) for v in db['internships'].values())}")
    print(f"   Course skill mappings: {len(db['courses'])}")
    print(f"   Job listings:          {sum(len(v) for v in db['jobs'].values())} across {len(db['jobs'])} roles")
    print(f"\nNext: paste the contents of db.json into the quiz HTML (replace the DB constant).")

if __name__ == "__main__":
    main()
