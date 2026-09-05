from __future__ import annotations

import re

from rapidfuzz import fuzz

from app.schemas import Fact, GateIssue, Resume
from app.services.facts import extract_facts, fact_values, tools_set
from app.services.ontology import find_skills_in_text

PROPER_RE = re.compile(r"\b([A-Z][A-Za-z0-9+.#]{2,})\b")
SKIP_CAPS = {
    "the", "and", "for", "with", "from", "this", "that", "these", "those",
    "using", "via", "into", "onto", "over", "after", "before", "while",
    "sql", "api", "aws", "gcp", "ci", "cd",
    "led", "built", "created", "designed", "launched", "improved", "reduced",
    "increased", "owned", "shipped", "implemented", "migrated", "automated",
    "scaled", "delivered", "optimized", "developed", "managed", "introduced",
    "drove", "partnered", "supported", "established", "defined", "wrote",
    "ran", "grew", "cut", "helped", "worked", "applied", "produced",
    "evaluated", "maintained", "coordinated", "ensured", "started",
    "giving", "making", "taking", "monitoring", "designing", "operating",
    "kurdum", "geliştirdim", "gelistirdim", "yönettim", "yonettim",
    "artırdım", "azalttım", "oluşturdum", "olusturdum", "otomatikleştirdim",
    "hazırladım", "hazirladim", "sundum", "yürüttüm", "yuruttum",
}


def check_groundedness(master: Resume, tailored: Resume, facts: list[Fact] | None = None) -> tuple[float, list[GateIssue]]:
    facts = facts or extract_facts(master)
    issues: list[GateIssue] = []
    employers = fact_values(facts, "employer")
    schools = fact_values(facts, "school")
    degrees = fact_values(facts, "degree")
    dates = fact_values(facts, "date")
    highlights = [f.value for f in facts if f.type == "highlight"]
    tools = tools_set(facts)
    original_blob = _blob(master).lower()

    for work in tailored.work:
        if work.name and work.name.lower() not in employers:
            issues.append(
                GateIssue(
                    code="new_employer",
                    message=f"Yeni işveren uydurulmuş olabilir: {work.name}",
                    severity="block",
                )
            )
        if work.startDate and work.startDate.lower() not in dates and work.startDate not in {f.value for f in facts if f.type == "date"}:
            if work.startDate.lower() not in original_blob:
                issues.append(
                    GateIssue(
                        code="new_date",
                        message=f"Tarih master CV'de yok: {work.startDate}",
                        severity="block",
                    )
                )
        for highlight in work.highlights:
            if not highlight_allowed(highlight, highlights, original_blob):
                issues.append(
                    GateIssue(
                        code="ungrounded_highlight",
                        message=f"Madde master kanıta bağlanamadı: {highlight[:120]}",
                        severity="block",
                    )
                )

    for edu in tailored.education:
        if edu.institution and edu.institution.lower() not in schools:
            issues.append(
                GateIssue(
                    code="new_school",
                    message=f"Yeni okul: {edu.institution}",
                    severity="block",
                )
            )
        degree = " ".join(p for p in [edu.studyType, edu.area] if p).strip()
        if degree and degree.lower() not in degrees and degree.lower() not in original_blob:
            issues.append(
                GateIssue(
                    code="new_degree",
                    message=f"Yeni diploma: {degree}",
                    severity="block",
                )
            )

    for canonical, surface in find_skills_in_text(_blob(tailored)):
        if canonical.lower() not in tools and surface.lower() not in original_blob:
            issues.append(
                GateIssue(
                    code="new_tool",
                    message=f"Master CV'de olmayan araç: {surface}",
                    severity="block",
                )
            )

    if tailored.basics.email and master.basics.email and tailored.basics.email.lower() != master.basics.email.lower():
        issues.append(GateIssue(code="email_changed", message="E-posta değiştirildi", severity="block"))
    if tailored.basics.name and master.basics.name and tailored.basics.name.lower() != master.basics.name.lower():
        issues.append(GateIssue(code="name_changed", message="İsim değiştirildi", severity="block"))

    blocks = [i for i in issues if i.severity == "block"]
    score = 100.0 if not blocks else max(0.0, 100.0 - 25.0 * len(blocks))
    if not blocks and issues:
        score = 85.0
    return round(score, 1), issues


def highlight_allowed(highlight: str, originals: list[str], blob: str) -> bool:
    if not highlight.strip():
        return True
    if any(highlight.strip() == original.strip() for original in originals):
        return True
    if _invented_tokens(highlight, blob):
        return False
    if not originals:
        return True
    best_set = max(fuzz.token_set_ratio(highlight, original) for original in originals)
    best_partial = max(fuzz.partial_ratio(highlight, original) for original in originals)
    return best_set >= 68 or best_partial >= 80


def _invented_tokens(highlight: str, blob: str) -> list[str]:
    invented: list[str] = []
    stripped = highlight.strip()
    first = stripped.split()[0] if stripped.split() else ""
    first = first.strip("•-–—,;:.")
    for token in PROPER_RE.findall(highlight):
        if token.lower() in blob:
            continue
        if token.lower() in SKIP_CAPS:
            continue
        if token == first or token.lower() == first.lower():
            continue
        invented.append(token)
    return invented


def _blob(resume: Resume) -> str:
    parts = [resume.basics.summary, resume.basics.name, resume.basics.label, resume.basics.email]
    for work in resume.work:
        parts.extend([work.name, work.position, work.summary, work.startDate, work.endDate, *work.highlights])
    for edu in resume.education:
        parts.extend([edu.institution, edu.area, edu.studyType])
    for skill in resume.skills:
        parts.extend([skill.name, *skill.keywords])
    for project in resume.projects:
        parts.extend([project.name, project.description, *project.highlights])
    return "\n".join(p for p in parts if p)


def is_blocking(issues: list[GateIssue]) -> bool:
    return any(i.severity == "block" for i in issues)
