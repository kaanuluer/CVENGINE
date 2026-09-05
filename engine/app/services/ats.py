from __future__ import annotations

import re

from app.schemas import GateIssue, JobAnalysis, Resume, ResumeLanguage, TemplateName
from app.services.match import match_resume

STANDARD_HEADINGS_EN = ("Experience", "Education", "Skills")
STANDARD_HEADINGS_TR = ("İş Deneyimi", "Eğitim", "Yetenekler")
EMAIL_RE = re.compile(r"[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}", re.I)
DATE_RE = re.compile(r"^\d{4}(?:-\d{2})?$")


HEADINGS = {
    "en": {
        "experience": "Experience",
        "education": "Education",
        "skills": "Skills",
        "projects": "Projects",
        "certificates": "Certificates",
        "summary": "Summary",
    },
    "tr": {
        "experience": "İş Deneyimi",
        "education": "Eğitim",
        "skills": "Yetenekler",
        "projects": "Projeler",
        "certificates": "Sertifikalar",
        "summary": "Özet",
    },
}


def ats_alignment(keyword: float, semantic: float) -> float:
    """JD fit for ATS: keyword coverage dominates; semantic is supporting signal."""
    return round(0.62 * keyword + 0.38 * semantic, 1)


def headings_for(language: ResumeLanguage) -> dict[str, str]:
    return HEADINGS[language]


def score_ats(
    resume: Resume,
    analysis: JobAnalysis | None = None,
    template: TemplateName = "classic",
    parsed_roundtrip: Resume | None = None,
) -> tuple[float, list[GateIssue]]:
    issues: list[GateIssue] = []
    score = 100.0

    if not resume.basics.name:
        issues.append(GateIssue(code="missing_name", message="İsim yok", severity="block"))
        score -= 25
    if not resume.basics.email or not EMAIL_RE.search(resume.basics.email):
        issues.append(GateIssue(code="missing_email", message="Geçerli e-posta yok", severity="block"))
        score -= 20
    if not resume.work:
        issues.append(GateIssue(code="missing_experience", message="İş deneyimi bölümü yok", severity="block"))
        score -= 25
    else:
        undated = [w for w in resume.work if not w.startDate]
        if undated:
            issues.append(GateIssue(code="missing_dates", message="Bazı deneyimlerde tarih yok", severity="warn"))
            score -= 8
        bad_dates = [
            w for w in resume.work
            if w.startDate and not DATE_RE.match(w.startDate)
        ]
        if bad_dates:
            issues.append(GateIssue(code="date_format", message="Tarihler YYYY-MM formatında değil", severity="warn"))
            score -= 6
    if not resume.education:
        issues.append(GateIssue(code="missing_education", message="Eğitim bölümü yok", severity="warn"))
        score -= 6
    if not resume.skills or not any(s.keywords for s in resume.skills):
        issues.append(GateIssue(code="missing_skills", message="Yetenekler bölümü yok", severity="warn"))
        score -= 10

    if analysis:
        coverage = match_resume(resume, analysis).keyword_coverage
        if coverage < 40:
            issues.append(GateIssue(code="low_keyword", message="İlan anahtar kelime kapsaması düşük", severity="warn"))
            score -= 12

    if parsed_roundtrip is not None:
        if resume.basics.name and parsed_roundtrip.basics.name:
            if resume.basics.name.split()[0].lower() not in parsed_roundtrip.basics.name.lower():
                issues.append(GateIssue(code="roundtrip_name", message="PDF round-trip isim kaybetti", severity="block"))
                score -= 20
        if resume.basics.email and parsed_roundtrip.basics.email:
            if resume.basics.email.lower() != parsed_roundtrip.basics.email.lower():
                issues.append(GateIssue(code="roundtrip_email", message="PDF round-trip e-posta kaybetti", severity="block"))
                score -= 20
        if resume.work and not parsed_roundtrip.work:
            issues.append(GateIssue(code="roundtrip_work", message="PDF round-trip deneyimi kaybetti", severity="warn"))
            score -= 10

    # Templates are always single-column / no tables; reward ATS-safe template.
    if template in {"classic", "executive", "compact"}:
        score = min(100.0, score + 0)

    return round(max(0.0, min(100.0, score)), 1), issues


def flatten_resume_text(resume: Resume, language: ResumeLanguage = "en") -> str:
    h = headings_for(language)
    lines = [
        resume.basics.name,
        resume.basics.label,
        resume.basics.email,
        resume.basics.phone,
        resume.basics.url,
        "",
        h["summary"],
        resume.basics.summary,
        "",
        h["experience"],
    ]
    for work in resume.work:
        dates = " – ".join(p for p in [_fmt_date(work.startDate, language), _fmt_date(work.endDate, language) or ("Present" if language == "en" else "Günümüz")] if p or work.startDate)
        lines.append(f"{work.position} | {work.name} | {dates}")
        lines.extend(f"- {item}" for item in work.highlights)
        lines.append("")
    lines += [h["education"]]
    for edu in resume.education:
        lines.append(f"{edu.studyType} {edu.area} | {edu.institution} | {_fmt_date(edu.startDate, language)} – {_fmt_date(edu.endDate, language)}")
    lines += ["", h["skills"]]
    for skill in resume.skills:
        lines.append(f"{skill.name}: {', '.join(skill.keywords)}")
    if resume.projects:
        lines += ["", h["projects"]]
        for project in resume.projects:
            lines.append(project.name)
            lines.extend(f"- {item}" for item in project.highlights)
    return "\n".join(lines)


def _fmt_date(value: str, language: ResumeLanguage) -> str:
    if not value:
        return ""
    months_en = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    months_tr = ["Oca", "Şub", "Mar", "Nis", "May", "Haz", "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara"]
    months = months_tr if language == "tr" else months_en
    match = re.match(r"^(\d{4})(?:-(\d{2}))?", value)
    if not match:
        return value
    year, month = match.group(1), match.group(2)
    if not month:
        return year
    label = months[max(0, min(11, int(month) - 1))]
    return f"{label} {year}"
