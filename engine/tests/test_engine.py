from __future__ import annotations

import json
from pathlib import Path

from app.schemas import Resume
from app.services.consistency import check_consistency
from app.services.groundedness import check_groundedness, is_blocking
from app.services.jd import analyze_jd
from app.services.parser import parse_resume_text
from app.services.pipeline import run_pipeline
from app.services.tailor import tailor_resume

FIXTURES = Path(__file__).parent / "fixtures"


def load_resume(name: str) -> Resume:
    return Resume.model_validate(json.loads((FIXTURES / name).read_text(encoding="utf-8")))


def test_parser_reflows_word_per_line_highlights():
    text = """Ada Meridian
ada@example.com

Experience
Northwind Labs
Software Engineer
Mar 2021 - Present
•
Built
FastAPI
services
on
PostgreSQL
•
Cut
p95
latency
40%

Education
University of Texas
B.S. Computer Science
Sep 2014 - May 2018

Skills
Python, PostgreSQL
"""
    resume = parse_resume_text(text)
    assert resume.work
    joined = " ".join(resume.work[0].highlights).lower()
    assert "fastapi" in joined
    assert all(len(h.split()) >= 3 for h in resume.work[0].highlights)


def test_parser_extracts_contact_and_sections():
    text = """Ada Meridian
Software Engineer
ada.meridian@example.com
+1 415 555 0199

Experience
Software Engineer | Northwind Labs
Mar 2021 - Present
- Built FastAPI services on PostgreSQL
- Cut p95 API latency 40%

Education
B.S. Computer Science | University of Texas
Sep 2014 - May 2018

Skills
Python, PostgreSQL, Docker
"""
    resume = parse_resume_text(text)
    assert resume.basics.name.startswith("Ada")
    assert "ada.meridian" in resume.basics.email
    assert resume.work
    assert resume.education
    assert resume.skills


def test_tailor_does_not_invent_employer():
    resume = load_resume("resume_en.json")
    jd = (FIXTURES / "jd_en.txt").read_text(encoding="utf-8")
    analysis = analyze_jd(jd)
    tailored, _, _ = tailor_resume(resume, analysis)
    names = {w.name for w in tailored.work}
    assert names <= {"Northwind Labs", "Helios Analytics"}


def test_groundedness_rejects_new_employer():
    resume = load_resume("resume_en.json")
    fake = resume.model_copy(deep=True)
    fake.work[0].name = "Totally Fake Corp"
    score, issues = check_groundedness(resume, fake)
    assert is_blocking(issues)
    assert any(i.code == "new_employer" for i in issues)
    assert score < 80


def test_groundedness_rejects_new_tool():
    resume = load_resume("resume_en.json")
    fake = resume.model_copy(deep=True)
    fake.work[0].highlights[0] = fake.work[0].highlights[0] + " using COBOL and Fortran"
    _, issues = check_groundedness(resume, fake)
    assert any(i.code in {"new_tool", "ungrounded_highlight"} for i in issues)


def test_groundedness_allows_fact_preserving_paraphrase():
    resume = load_resume("resume_en.json")
    para = resume.model_copy(deep=True)
    para.work[0].highlights[0] = (
        "Delivered FastAPI services on PostgreSQL that processed 2M payments per month with 99.95% uptime."
    )
    score, issues = check_groundedness(resume, para)
    assert not is_blocking(issues)
    assert score >= 80


def test_consistency_rejects_extreme_rewrite():
    resume = load_resume("resume_en.json")
    fake = resume.model_copy(deep=True)
    fake.work = fake.work[:1]
    fake.work[0].highlights = [
        "Invented entirely new narrative about quantum blockchain leadership.",
        "Another fabricated achievement with no master CV overlap whatsoever.",
    ]
    fake.basics.summary = "Completely unrelated executive summary about hospitality management."
    score, issues = check_consistency(resume, fake)
    assert score < 75
    assert any(
        i.code in {"highlight_drift", "summary_drift", "employer_dropped", "consistency_low"}
        for i in issues
    )


def test_consistency_passes_normal_tailor():
    resume = load_resume("resume_en.json")
    jd = (FIXTURES / "jd_en.txt").read_text(encoding="utf-8")
    result = run_pipeline(resume, jd, template="classic", roundtrip=False)
    assert result.scores.consistency >= 75
    assert not any(i.code == "employer_dropped" for i in result.scores.issues)


def test_pipeline_scores_and_passes_for_matching_jd():
    resume = load_resume("resume_en.json")
    jd = (FIXTURES / "jd_en.txt").read_text(encoding="utf-8")
    result = run_pipeline(resume, jd, template="classic", roundtrip=False)
    assert result.scores.groundedness >= 80
    assert result.scores.keyword >= 50
    assert result.scores.passed
    assert "Python" in " ".join(k for s in result.resume.skills for k in s.keywords)
    assert any("PostgreSQL" in k or "Postgres" in k for s in result.resume.skills for k in s.keywords)
    assert result.cover_letter.strip()
    assert "Ada Meridian" in result.cover_letter
    assert any(token in result.cover_letter for token in ("FastAPI", "PostgreSQL", "40%", "Redis"))
    assert "Globex" not in result.cover_letter
    assert "Acme" not in result.cover_letter
    assert result.baseline_scores is not None
    assert 0 <= result.baseline_scores.ats <= 100
    assert 0 <= result.scores.ats <= 100
    assert result.scores.ats >= result.baseline_scores.ats
    assert result.scores.ats >= 80
    assert result.scores.consistency >= 75
    assert result.scores.semantic >= result.baseline_scores.semantic
    assert result.scores.ats - result.baseline_scores.ats >= 5 or result.baseline_scores.ats >= 80
    assert "backend" in result.resume.basics.label.lower() or "engineer" in result.resume.basics.label.lower()
    assert result.scores.passed
    assert not any(i.code == "ats_below_target" for i in result.scores.issues)


def test_pipeline_turkish_fixture():
    resume = load_resume("resume_tr.json")
    jd = (FIXTURES / "jd_tr.txt").read_text(encoding="utf-8")
    result = run_pipeline(resume, jd, template="compact", roundtrip=False)
    assert result.language == "tr"
    assert result.scores.groundedness >= 80
    assert result.scores.consistency >= 75
    assert result.scores.ats >= 80
    assert result.scores.passed
    assert result.resume.work[0].name == "Mavi Yazılım"
    assert "Sayın Yetkili" in result.cover_letter
    assert "Ece Kaya" in result.cover_letter


def test_title_not_upgraded_across_seniority():
    resume = load_resume("resume_en.json")
    analysis = analyze_jd("Staff Principal Director of Everything\nRequirements\n- Python")
    tailored, _, _ = tailor_resume(resume, analysis)
    helios = next(w for w in tailored.work if w.name == "Helios Analytics")
    assert helios.position == "Junior Software Engineer"


def test_pdf_and_docx_export_roundtrip_name():
    from app.services.export_docx import build_docx
    from app.services.export_pdf import build_pdf
    from app.services.parser import parse_resume_bytes

    resume = load_resume("resume_en.json")
    pdf = build_pdf(resume, "classic", "en")
    parsed = parse_resume_bytes(pdf, "x.pdf")
    assert "Ada" in parsed.basics.name
    docx = build_docx(resume, "executive", "en")
    assert len(docx) > 1000


def test_language_upper_uses_locale_characters():
    from app.services.language import language_upper

    assert language_upper("İş Deneyimi", "tr") == "İŞ DENEYİMİ"
    assert language_upper("Eğitim", "tr") == "EĞİTİM"
    assert language_upper("Experience", "en") == "EXPERIENCE"
    assert language_upper("Certificates", "en") == "CERTIFICATES"
    assert "İ" not in language_upper("Certificates", "en")


def test_pdf_headings_match_target_language_characters():
    from io import BytesIO

    from pdfminer.high_level import extract_text

    from app.services.export_pdf import build_pdf

    tr_pdf = extract_text(BytesIO(build_pdf(load_resume("resume_tr.json"), "classic", "tr")))
    assert "İŞ DENEYİMİ" in tr_pdf
    assert "EĞİTİM" in tr_pdf
    assert "İstanbul" in tr_pdf

    en_pdf = extract_text(BytesIO(build_pdf(load_resume("resume_en.json"), "classic", "en")))
    assert "EXPERIENCE" in en_pdf
    assert "EDUCATION" in en_pdf
    assert "SKILLS" in en_pdf
    assert "EXPERİENCE" not in en_pdf
    assert "EDUCATİON" not in en_pdf


def test_ats_blocks_missing_email():
    from app.services.ats import score_ats

    resume = load_resume("resume_en.json")
    resume.basics.email = ""
    score, issues = score_ats(resume)
    assert any(i.code == "missing_email" for i in issues)
    assert score < 90


def test_pipeline_ollama_flag_without_daemon():
    resume = load_resume("resume_en.json")
    jd = (FIXTURES / "jd_en.txt").read_text(encoding="utf-8")
    result = run_pipeline(
        resume,
        jd,
        use_ollama=True,
        ollama_url="http://127.0.0.1:9",
        roundtrip=False,
    )
    assert result.used_ollama is False
    assert result.ollama_rolled_back is False
    assert result.cover_used_ollama is False
    assert result.scores.groundedness >= 80


def test_aihr_penalizes_slop():
    from app.services.aihr import score_aihr
    from app.services.jd import analyze_jd

    resume = load_resume("resume_en.json")
    resume.basics.summary = "Passionate engineer who leverages cutting-edge synergy to delve into robust platforms."
    analysis = analyze_jd((FIXTURES / "jd_en.txt").read_text(encoding="utf-8"))
    _, issues, breakdown = score_aihr(resume, analysis)
    assert any(i.code == "ai_slop" for i in issues)
    assert breakdown["slop_penalty"] > 0


def test_cover_letter_uses_real_highlights():
    from app.services.cover_letter import build_cover_letter
    from app.services.match import match_resume

    resume = load_resume("resume_en.json")
    jd = (FIXTURES / "jd_en.txt").read_text(encoding="utf-8")
    analysis = analyze_jd(jd, company="Northwind Customer", title="Senior Backend Engineer")
    match = match_resume(resume, analysis)
    letter, used_ai = build_cover_letter(
        resume,
        analysis,
        match,
        company="Northwind Customer",
        role="Senior Backend Engineer",
        prefer_ollama=False,
    )
    assert used_ai is False
    assert "Ada Meridian" in letter
    assert "Dear Northwind Customer Hiring Team" in letter
    assert "FastAPI" in letter or "PostgreSQL" in letter or "40%" in letter
    assert "Invented Labs" not in letter


def test_cover_letter_export_bytes():
    from app.services.export_cover import build_cover_docx, build_cover_pdf

    text = "Ada Meridian\n\nDear Hiring Manager,\n\nI am writing to apply."
    pdf = build_cover_pdf(text)
    assert pdf.startswith(b"%PDF")
    docx = build_cover_docx(text)
    assert len(docx) > 800
