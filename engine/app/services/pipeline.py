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
from app.services.ats import ATS_TARGET, ats_alignment, score_ats
from app.services.consistency import CONSISTENCY_TARGET, check_consistency
from app.services.cover_letter import build_cover_letter
from app.services.export_pdf import write_pdf
from app.services.facts import extract_facts
from app.services.groundedness import check_groundedness, is_blocking
from app.services.jd import analyze_jd
from app.services.match import match_resume
from app.services.ollama import ollama_available, rewrite_with_ollama
from app.services.parser import parse_resume_bytes
from app.services.sanitize import sanitize_resume
from app.services.tailor import ATS_BOOST_ROUNDS, amplify_for_ats, tailor_resume


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
    baseline_scores, _ = _score_resume(
        resume,
        analysis,
        facts,
        template,
        parsed=None,
        master=resume,
        enforce_ats_target=False,
    )

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
    consistency_score, consistency_issues = check_consistency(resume, tailored)
    if (is_blocking(grounded_issues) or is_blocking(consistency_issues)) and used_ollama:
        tailored, diff, fact_map = tailor_resume(resume, analysis, facts)
        used_ollama = False
        rolled_back = True
        grounded_score, grounded_issues = check_groundedness(resume, tailored, facts)
        consistency_score, consistency_issues = check_consistency(resume, tailored)

    # Boost ATS toward the minimum target without inventing facts.
    scores, match = _score_resume(
        tailored,
        analysis,
        facts,
        template,
        parsed=None,
        master=resume,
        grounded_score=grounded_score,
        grounded_issues=grounded_issues,
        consistency_score=consistency_score,
        consistency_issues=consistency_issues,
    )
    for _ in range(ATS_BOOST_ROUNDS):
        if scores.ats >= ATS_TARGET and scores.consistency >= CONSISTENCY_TARGET:
            break
        before_ats = scores.ats
        tailored, extra_diff, fact_map = amplify_for_ats(tailored, analysis, facts, fact_map)
        if not extra_diff:
            break
        diff.extend(extra_diff)
        tailored = sanitize_resume(tailored)
        grounded_score, grounded_issues = check_groundedness(resume, tailored, facts)
        consistency_score, consistency_issues = check_consistency(resume, tailored)
        if is_blocking(grounded_issues) or is_blocking(consistency_issues):
            # Roll back last amplify by re-tailoring from master (deterministic).
            tailored, diff, fact_map = tailor_resume(resume, analysis, facts)
            grounded_score, grounded_issues = check_groundedness(resume, tailored, facts)
            consistency_score, consistency_issues = check_consistency(resume, tailored)
            scores, match = _score_resume(
                tailored,
                analysis,
                facts,
                template,
                parsed=None,
                master=resume,
                grounded_score=grounded_score,
                grounded_issues=grounded_issues,
                consistency_score=consistency_score,
                consistency_issues=consistency_issues,
            )
            break
        scores, match = _score_resume(
            tailored,
            analysis,
            facts,
            template,
            parsed=None,
            master=resume,
            grounded_score=grounded_score,
            grounded_issues=grounded_issues,
            consistency_score=consistency_score,
            consistency_issues=consistency_issues,
        )
        if scores.ats <= before_ats + 0.05:
            break

    parsed = None
    if roundtrip:
        parsed = _roundtrip(tailored, template, analysis.language)

    scores, match = _score_resume(
        tailored,
        analysis,
        facts,
        template,
        parsed=parsed,
        master=resume,
        grounded_score=grounded_score,
        grounded_issues=grounded_issues,
        consistency_score=consistency_score,
        consistency_issues=consistency_issues,
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
    master: Resume | None = None,
    grounded_score: float | None = None,
    grounded_issues: list[GateIssue] | None = None,
    consistency_score: float | None = None,
    consistency_issues: list[GateIssue] | None = None,
    enforce_ats_target: bool = True,
) -> tuple[ScoreBlock, MatchResult]:
    if grounded_score is None:
        grounded_score, grounded_issues = 100.0, []
    grounded_issues = grounded_issues or []
    if consistency_score is None:
        if master is not None:
            consistency_score, consistency_issues = check_consistency(master, resume)
        else:
            consistency_score, consistency_issues = 100.0, []
    consistency_issues = consistency_issues or []

    parse_score, ats_issues = score_ats(resume, analysis, template, parsed)
    _, aihr_issues, breakdown = score_aihr(resume, analysis)
    match = match_resume(resume, analysis, facts)
    keyword = breakdown["keyword"]
    semantic = breakdown["semantic"]
    evidence = breakdown["evidence"]
    ats = ats_alignment(keyword, semantic)
    overall = round(
        0.18 * parse_score
        + 0.18 * keyword
        + 0.14 * semantic
        + 0.14 * evidence
        + 0.18 * grounded_score
        + 0.18 * consistency_score,
        1,
    )
    issues = [*grounded_issues, *consistency_issues, *ats_issues, *aihr_issues]
    if enforce_ats_target and ats < ATS_TARGET:
        issues.append(
            GateIssue(
                code="ats_below_target",
                message=f"ATS uyumu {ats:.0f} — hedef en az {ATS_TARGET:.0f}",
                severity="block",
            )
        )
    blocking = any(i.severity == "block" for i in issues)
    passed = (
        (not blocking)
        and grounded_score >= 80
        and consistency_score >= CONSISTENCY_TARGET
        and parse_score >= 55
        and (not enforce_ats_target or ats >= ATS_TARGET)
    )
    scores = ScoreBlock(
        parse=parse_score,
        keyword=keyword,
        semantic=semantic,
        evidence=evidence,
        groundedness=grounded_score,
        consistency=consistency_score,
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
