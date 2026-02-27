"""
app.py  —  Streamlit demo UI v2.1
Upload resume → extract → show preview → redirect to DEET portal (pre-filled)
"""

import streamlit as st
import json, urllib.parse
from core.pipeline import ResumePipeline

st.set_page_config(
    page_title="Resume → DEET",
    page_icon="📄",
    layout="wide",
)

st.markdown("""
<style>
  .main { background: #f4f3ee; }
  .header { background: linear-gradient(135deg,#0d0f1a,#1a1d36);
            color:white; padding:2rem 2.5rem; border-radius:16px; margin-bottom:1.5rem; }
  .header h1 { color:white; margin:0; font-size:1.8rem; }
  .header p  { color:rgba(255,255,255,.65); margin:.4rem 0 0; font-size:.95rem; }
  .card { background:white; border-radius:12px; padding:1.5rem;
          border:1px solid #e2e1dc; margin-bottom:1rem; }
  .cat-badge { display:inline-block; padding:.2rem .65rem; border-radius:999px;
               font-size:.78rem; font-weight:600; margin:.15rem; }
  .lang   { background:#e8eaff; color:#3d5afe; }
  .fw     { background:#e0f7f4; color:#00796b; }
  .tool   { background:#fce4ec; color:#c62828; }
  .conc   { background:#fff8e1; color:#e65100; }
  .redirect-btn {
    display:block; width:100%; padding:1rem; margin-top:1rem;
    background:linear-gradient(135deg,#3d5afe,#00bfa5);
    color:white; border:none; border-radius:12px;
    font-size:1.1rem; font-weight:700; cursor:pointer; text-align:center;
    text-decoration:none;
  }
  .step { display:flex; align-items:center; gap:.75rem; padding:.6rem 0; }
  .step-num { width:28px; height:28px; border-radius:50%; background:#3d5afe;
              color:white; font-weight:700; font-size:.8rem;
              display:flex; align-items:center; justify-content:center; flex-shrink:0; }
  .step-done .step-num { background:#00c853; }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="header">
  <h1>📄 Resume → DEET Registration</h1>
  <p>Upload your resume · AI extracts your profile · Opens DEET portal pre-filled</p>
</div>
""", unsafe_allow_html=True)

# ── State ─────────────────────────────────────────────────────────────────────
if "result" not in st.session_state:
    st.session_state.result = None
if "portal_url" not in st.session_state:
    st.session_state.portal_url = None
if "skill_gap_url" not in st.session_state:
    st.session_state.skill_gap_url = None

col_left, col_right = st.columns([1, 1], gap="large")

# ── Left: Upload + Steps ───────────────────────────────────────────────────────
with col_left:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("📤 Upload Resume")

    uploaded = st.file_uploader(
        "PDF, PNG or JPG",
        type=["pdf","png","jpg","jpeg"],
        label_visibility="collapsed"
    )

    if uploaded:
        st.success(f"✅ {uploaded.name}  ({round(uploaded.size/1024,1)} KB)")
        if st.button("🧠 Extract & Preview", use_container_width=True, type="primary"):
            with st.spinner("Extracting profile from resume..."):
                pipe = ResumePipeline()
                st.session_state.result = pipe.process_file(uploaded)
                # Build portal redirect URL
                profile = st.session_state.result["profile"]
                skills  = profile.get("skills", {})
                params  = {k: v for k, v in {
                    "name":       profile.get("full_name",""),
                    "email":      profile.get("email",""),
                    "phone":      profile.get("phone",""),
                    "location":   profile.get("location",""),
                    "linkedin":   profile.get("linkedin",""),
                    "github":     profile.get("github",""),
                    "summary":    profile.get("summary","")[:400],
                    "languages":  ",".join(skills.get("languages",[])),
                    "frameworks": ",".join(skills.get("frameworks",[])),
                    "tools":      ",".join(skills.get("tools",[])),
                    "concepts":   ",".join(skills.get("concepts",[])),
                    "skills_flat": ",".join(profile.get("skills_flat",[])),
                    "certifications": "\n".join(profile.get("certifications",[])),
                    "job_type":   "full_time",
                    "preferred_locations": profile.get("location",""),
                }.items() if v}

                edu = profile.get("education",[])
                if edu:
                    params["degree"]       = edu[0].get("degree","")
                    params["institution"]  = edu[0].get("institution","")
                    params["grad_year"]    = edu[0].get("year","")
                    params["field_of_study"] = edu[0].get("degree","")

                projects = profile.get("projects",[])
                if projects:
                    params["projects"] = "\n".join(
                        f"{p['title']} ({p.get('year','')}) — {p.get('desc','')[:120]}"
                        for p in projects[:4]
                    )

                params = {k:v for k,v in params.items() if v}
                # Build base64-encoded deet param for skill-gap redirect
                import base64, json as _json
                encoded = base64.b64encode(_json.dumps({
                    "personal": {
                        "full_name": profile.get("full_name",""),
                        "email":     profile.get("email",""),
                        "phone":     profile.get("phone",""),
                        "location":  profile.get("location",""),
                        "linkedin":  profile.get("linkedin",""),
                        "github":    profile.get("github",""),
                        "summary":   profile.get("summary",""),
                    },
                    "skills":      skills,
                    "skills_flat": profile.get("skills_flat",[]),
                    "education":   profile.get("education",[{}])[0] if profile.get("education") else {},
                    "experience":  {"years_category": "0"},
                    "preferences": {"preferred_roles": "", "preferred_locations": profile.get("location","")},
                    "meta":        {"profile_score": st.session_state.result["meta"]["profile_score"]},
                }, ensure_ascii=False).encode()).decode()
                st.session_state.portal_url = f"http://localhost:8000/portal/?" + urllib.parse.urlencode(params)
                st.session_state.skill_gap_url = f"http://localhost:8000/skill-gap?deet={encoded}"

    st.markdown('</div>', unsafe_allow_html=True)

    # ── How it works ──────────────────────────────────────────────────────────
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown("**How it works**")
    steps = [
        ("done" if st.session_state.result else "", "Upload resume (PDF or image)"),
        ("done" if st.session_state.result else "", "AI extracts name, skills, education, projects"),
        ("done" if st.session_state.result else "", "Review extracted data below"),
        ("", "Click 'Open DEET Portal' — form is pre-filled"),
        ("", "Confirm details and submit to register"),
        ("", "Profile sent to Skill Gap Engine for job/course matching"),
    ]
    for i, (state, label) in enumerate(steps, 1):
        st.markdown(
            f'<div class="step {state}"><div class="step-num">{"✓" if state else i}</div><span style="font-size:.88rem">{label}</span></div>',
            unsafe_allow_html=True
        )
    st.markdown('</div>', unsafe_allow_html=True)

# ── Right: Extracted Preview + Redirect ───────────────────────────────────────
with col_right:
    if not st.session_state.result:
        st.markdown('<div class="card" style="text-align:center;padding:3rem;color:#9ca3af">', unsafe_allow_html=True)
        st.markdown("### Upload a resume to see the extracted profile")
        st.markdown("Fields will appear here before you're redirected to the DEET portal.")
        st.markdown('</div>', unsafe_allow_html=True)
    else:
        profile = st.session_state.result["profile"]
        meta    = st.session_state.result["meta"]

        # ── Metrics ───────────────────────────────────────────────────────────
        m1, m2, m3 = st.columns(3)
        m1.metric("Profile Score",   f"{meta['profile_score']}/100")
        m2.metric("Skills Found",    len(profile.get("skills_flat",[])))
        m3.metric("Extracted In",    f"{meta['total_ms']}ms")

        # ── Personal info ──────────────────────────────────────────────────────
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown("**👤 Personal**")
        c1, c2 = st.columns(2)
        c1.markdown(f"**Name** · {profile.get('full_name','—')}")
        c2.markdown(f"**Email** · {profile.get('email','—')}")
        c3, c4 = st.columns(2)
        c3.markdown(f"**Phone** · {profile.get('phone','—')}")
        c4.markdown(f"**Location** · {profile.get('location','—')}")
        st.markdown('</div>', unsafe_allow_html=True)

        # ── Skills ────────────────────────────────────────────────────────────
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown("**🛠️ Skills Extracted**")
        skills = profile.get("skills", {})
        cat_style = {"languages":"lang","frameworks":"fw","tools":"tool","concepts":"conc"}
        cat_label = {"languages":"Languages","frameworks":"Frameworks","tools":"Tools","concepts":"Concepts"}
        for cat, items in skills.items():
            if items:
                default_cat = cat_style.get(cat, "lang")
                badges = " ".join(f'<span class="cat-badge {default_cat}">{s}</span>' for s in items)
                st.markdown(f"*{cat_label.get(cat,cat)}* — {badges}", unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

        # ── Education & Projects ───────────────────────────────────────────────
        edu = profile.get("education",[])
        if edu:
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.markdown("**🎓 Education**")
            for e in edu:
                st.markdown(f"**{e.get('degree','—')}** · {e.get('institution','—')} · {e.get('year','')}")
            st.markdown('</div>', unsafe_allow_html=True)

        projects = profile.get("projects",[])
        if projects:
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.markdown("**🚀 Projects**")
            for p in projects[:3]:
                st.markdown(f"**{p['title']}** _{p.get('year','')}_")
                st.caption(p.get('desc','')[:150])
            st.markdown('</div>', unsafe_allow_html=True)

        # ── REDIRECT BUTTON ───────────────────────────────────────────────────
        st.markdown("---")
        portal_url = st.session_state.portal_url
        col_a, col_b = st.columns(2)
        with col_a:
            st.markdown(
                f'<a href="{portal_url}" target="_blank" class="redirect-btn">'
                f'📋 Open DEET Portal</a>',
                unsafe_allow_html=True
            )
            st.caption("Register on DEET portal — all fields pre-filled from your resume.")
        with col_b:
            skill_gap_url = st.session_state.get("skill_gap_url", "http://localhost:8000/skill-gap")
            st.markdown(
                f'<a href="{skill_gap_url}" target="_blank" class="redirect-btn" style="background:linear-gradient(135deg,#7c3aed,#4f46e5)">'
                f'⚡ Skip to Skill Gap Report</a>',
                unsafe_allow_html=True
            )
            st.caption("Jump straight to your personalised skill gap analysis — no quiz needed.")

        # ── JSON for teammate ──────────────────────────────────────────────────
        with st.expander("{ } Profile JSON  (for Skill Gap Engine #74)"):
            st.json({
                "skills_flat": profile.get("skills_flat",[]),
                "profile_score": meta["profile_score"],
                "name": profile.get("full_name",""),
                "education": profile.get("education",[]),
            })
