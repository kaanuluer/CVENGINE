from __future__ import annotations

import re

from app.schemas import GateIssue, JobAnalysis, Resume
from app.services.match import match_resume
from app.services.text import tokenize

SLOP = {
    "leverage", "leveraging", "passionate", "delve", "delving",
    "robust synergy", "synergy", "utilize", "utilizing", "spearhead",
    "spearheading", "seamless", "cutting-edge", "results-driven",
    "dynamic", "go-getter", "think outside the box", "move the needle",
    "circle back", "low-hanging fruit", "best-in-class", "disruptive",
    "harness", "foster", "facilitate",
}

ACTION = {
    "led", "built", "created", "designed", "launched", "improved", "reduced",
    "increased", "owned", "shipped", "implemented", "migrated", "automated",
    "scaled", "delivered", "optimized", "developed", "managed", "introduced",
    "kurdum", "geliştirdim", "gelistirdim", "yönettim", "yonettim", "artırdım",
    "azalttım", "oluşturdum", "olusturdum", "otomatikleştirdim",
}

METRIC_RE = re.compile(r"(\d+(?:[.,]\d+)?\s?%|\b\d{1,4}\b)")


def score_aihr(resume: Resume, analysis: JobAnalysis) -> tuple[float, list[GateIssue], dict[str, float]]:
    issues: list[GateIssue] = []
    highlights = [h for w in resume.work for h in w.highlights]
    if not highlights:
        highlights = [resume.basics.summary] if resume.basics.summary else []

    quantified = sum(1 for h in highlights if METRIC_RE.search(h))
    evidence = round(100.0 * quantified / max(len(highlights), 1), 1)
    if evidence < 30:
        issues.append(GateIssue(code="low_evidence", message="Ölçülebilir madde oranı düşük", severity="warn"))

    action_hits = sum(1 for h in highlights if any(tok in tokenize(h) for tok in ACTION) or h[:1].isupper())
    star = round(100.0 * action_hits / max(len(highlights), 1), 1)

    slop_hits = []
    blob = " ".join(highlights + [resume.basics.summary]).lower()
    for phrase in SLOP:
        if phrase in blob:
            slop_hits.append(phrase)
    slop_penalty = min(40.0, 8.0 * len(slop_hits))
    if slop_hits:
        issues.append(
            GateIssue(
                code="ai_slop",
                message="Yapay zeka klişesi tespit edildi: " + ", ".join(slop_hits[:4]),
                severity="warn",
            )
        )

    stuffing = _stuffing_penalty(resume, analysis)
    if stuffing > 0:
        issues.append(GateIssue(code="keyword_stuffing", message="Anahtar kelime doldurma sinyali", severity="warn"))

    timeline_ok = _timeline_ok(resume)
    if not timeline_ok:
        issues.append(GateIssue(code="timeline", message="Tarih çizelgesi tutarsız", severity="warn"))

    match = match_resume(resume, analysis)
    keyword = match.keyword_coverage
    semantic = match.semantic
    evidence_score = max(0.0, evidence - stuffing)
    overall = round(
        0.28 * keyword
        + 0.22 * semantic
        + 0.28 * evidence_score
        + 0.12 * star
        + 0.10 * (100 - slop_penalty)
        - (0 if timeline_ok else 8),
        1,
    )
    overall = max(0.0, min(100.0, overall))
    breakdown = {
        "keyword": keyword,
        "semantic": semantic,
        "evidence": evidence_score,
        "star": star,
        "slop_penalty": slop_penalty,
    }
    return overall, issues, breakdown


def _stuffing_penalty(resume: Resume, analysis: JobAnalysis) -> float:
    blob = " ".join(
        [resume.basics.summary]
        + [h for w in resume.work for h in w.highlights]
    ).lower()
    penalty = 0.0
    for skill in analysis.required_skills:
        count = len(re.findall(rf"\b{re.escape(skill.lower())}\b", blob))
        if count >= 12:
            penalty += 12
        elif count >= 9:
            penalty += 6
    return penalty


def _timeline_ok(resume: Resume) -> bool:
    for work in resume.work:
        if work.startDate and work.endDate and work.endDate < work.startDate:
            return False
    return True
