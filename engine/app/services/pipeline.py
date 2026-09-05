from __future__ import annotations

from pathlib import Path
from tempfile import NamedTemporaryFile

from app.schemas import (
    GateIssue,
    JobAnalysis,
    MatchResult,
    Resume,
    ResumeLanguage,
    ScoreBlock,
    TailorResult,
    TemplateName,
)
from app.services.aihr import score_aihr
from app.services.ats import ats_alignment, score_ats
from app.services.cover_letter import build_cover_letter
from app.services.export_pdf import write_pdf
from app.services.facts import extract_facts
from app.services.groundedness import check_groundedness, is_blocking
from app.services.jd import analyze_jd
from app.services.match import match_resume
from app.services.ollama import ollama_available, rewrite_with_ollama
from app.services.parser import parse_resume_bytes
from app.services.sanitize import sanitize_resume
from app.services.tailor import tailor_resume


def run_pipeline(
    resume: Resume,
    job_text: str,
    template: TemplateName = "classic",
    company: str = "",
    role: str = "",
    use_ollama: bool = False,
    ollama_url: str = "http://127.0.0.1:11434",
    ollama_model: str = "llama3.1",
    roundtrip: bool = True,
) -> TailorResult:
    resume = sanitize_resume(resume)
    analysis = analyze_jd(job_text, company=company, title=role)
    facts = extract_facts(resume)
    baseline_scores, _ = _score_resume(resume, analysis, facts, template, parsed=None)

    tailored, diff, fact_map = tailor_resume(resume, analysis, facts)
    used_ollama = False
    rolled_back = False
    if use_ollama and ollama_available(ollama_url):
        outcome = rewrite_with_ollama(tailored, analysis, facts, ollama_url, ollama_model)
        if outcome.status == "applied" and outcome.resume is not None:
            tailored = outcome.resume
            used_ollama = True
        elif outcome.status == "rejected":
            rolled_back = True

    tailored = sanitize_resume(tailored)
    grounded_score, grounded_issues = check_groundedness(resume, tailored, facts)
    if is_blocking(grounded_issues) and used_ollama:
        tailored, diff, fact_map = tailor_resume(resume, analysis, facts)
        used_ollama = False
        rolled_back = True
        grounded_score, grounded_issues = check_groundedness(resume, tailored, facts)

    parsed = None
    if roundtrip:
        parsed = _roundtrip(tailored, template, analysis.language)

    scores, match = _score_resume(
        tailored,
        analysis,
        facts,
        template,
        parsed=parsed,
        grounded_score=grounded_score,
        grounded_issues=grounded_issues,
    )
    cover_letter, cover_used_ollama = build_cover_letter(
        tailored,
        analysis,
        match,
        company=company or analysis.company,
        role=role or analysis.title,
        ollama_url=ollama_url,
        ollama_model=ollama_model,
        prefer_ollama=True,
    )

    return TailorResult(
        resume=tailored,
        analysis=analysis,
        match=match,
        scores=scores,
        baseline_scores=baseline_scores,
        diff=diff,
        fact_map=fact_map,
        template=template,
        used_ollama=used_ollama,
        ollama_rolled_back=rolled_back,
        language=analysis.language,
        cover_letter=cover_letter,
        cover_used_ollama=cover_used_ollama,
    )


def _score_resume(
    resume: Resume,
    analysis: JobAnalysis,
    facts: list,
    template: TemplateName,
    parsed: Resume | None = None,
    grounded_score: float | None = None,
    grounded_issues: list[GateIssue] | None = None,
) -> tuple[ScoreBlock, MatchResult]:
    if grounded_score is None:
        grounded_score, grounded_issues = 100.0, []
    grounded_issues = grounded_issues or []
    parse_score, ats_issues = score_ats(resume, analysis, template, parsed)
    _, aihr_issues, breakdown = score_aihr(resume, analysis)
    match = match_resume(resume, analysis, facts)
    keyword = breakdown["keyword"]
    semantic = breakdown["semantic"]
    evidence = breakdown["evidence"]
    ats = ats_alignment(keyword, semantic)
    overall = round(
        0.22 * parse_score
        + 0.22 * keyword
        + 0.18 * semantic
        + 0.18 * evidence
        + 0.20 * grounded_score,
        1,
    )
    issues = [*grounded_issues, *ats_issues, *aihr_issues]
    blocking = any(i.severity == "block" for i in issues)
    passed = (not blocking) and grounded_score >= 80 and parse_score >= 55
    scores = ScoreBlock(
        parse=parse_score,
        keyword=keyword,
        semantic=semantic,
        evidence=evidence,
        groundedness=grounded_score,
        overall=overall,
        ats=ats,
        passed=passed,
        issues=issues,
    )
    return scores, match


def _roundtrip(resume: Resume, template: TemplateName, language: ResumeLanguage) -> Resume | None:
    try:
        with NamedTemporaryFile(suffix=".pdf", delete=False) as handle:
            path = Path(handle.name)
        write_pdf(path, resume, template, language)
        parsed = parse_resume_bytes(path.read_bytes(), "roundtrip.pdf")
        path.unlink(missing_ok=True)
        return parsed
    except Exception:
        return None
