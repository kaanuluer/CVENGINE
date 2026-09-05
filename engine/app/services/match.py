from __future__ import annotations

from rapidfuzz import fuzz

from app.schemas import Fact, GapItem, JobAnalysis, MatchResult, Resume
from app.services.facts import extract_facts, tools_set
from app.services.ontology import canonical_skill
from app.services.text import cosine_to_query


def resume_corpus(resume: Resume) -> str:
    parts: list[str] = [
        resume.basics.summary,
        resume.basics.label,
        " ".join(kw for s in resume.skills for kw in s.keywords),
    ]
    for work in resume.work:
        parts.extend([work.position, work.name, work.summary, *work.highlights])
    for project in resume.projects:
        parts.extend([project.name, project.description, *project.highlights])
    return "\n".join(p for p in parts if p)


def highlight_entries(resume: Resume) -> list[tuple[str, str]]:
    entries: list[tuple[str, str]] = []
    for i, work in enumerate(resume.work):
        for j, highlight in enumerate(work.highlights):
            entries.append((f"work[{i}].highlights[{j}]", highlight))
    return entries


def skill_owned(skill: str, owned_tools: set[str], corpus: str) -> bool:
    needle = skill.lower().strip()
    if not needle:
        return False
    if needle in owned_tools:
        return True
    if any(needle == t or needle in t or t in needle for t in owned_tools):
        return True
    if needle in corpus.lower():
        return True
    if any(fuzz.partial_ratio(needle, t) >= 90 for t in owned_tools if len(t) >= 3):
        return True
    return False


def match_resume(resume: Resume, analysis: JobAnalysis, facts: list[Fact] | None = None) -> MatchResult:
    facts = facts or extract_facts(resume)
    owned_tools = tools_set(facts)
    corpus = resume_corpus(resume)
    jd_skills = analysis.required_skills + [s for s in analysis.preferred_skills if s not in analysis.required_skills]
    if not jd_skills:
        jd_skills = [canonical_skill(k) or k for k in analysis.keywords[:12]]

    hits = 0.0
    gaps: list[GapItem] = []
    for skill in analysis.required_skills:
        present = skill_owned(skill, owned_tools, corpus)
        hits += int(present)
        gaps.append(GapItem(skill=skill, in_resume=present, weight="required"))
    for skill in analysis.preferred_skills:
        present = skill_owned(skill, owned_tools, corpus)
        hits += int(present) * 0.5
        gaps.append(GapItem(skill=skill, in_resume=present, weight="preferred"))

    denom = max(len(analysis.required_skills) + 0.5 * len(analysis.preferred_skills), 1)
    keyword_coverage = round(min(100.0, 100.0 * hits / denom), 1)

    query = " ".join([analysis.title, *analysis.required_skills, *analysis.preferred_skills]).strip()
    if not query:
        query = " ".join(analysis.keywords[:12])
    entries = highlight_entries(resume)
    texts = [t for _, t in entries]
    highlight_scores: dict[str, float] = {}
    highlight_top = 0.0
    if texts and query:
        scores = cosine_to_query(texts, query)
        highlight_scores = {path: round(score * 100, 1) for (path, _), score in zip(entries, scores)}
        ranked = sorted(scores, reverse=True)
        top_n = max(3, min(6, max(1, len(ranked) // 2)))
        highlight_top = sum(ranked[:top_n]) / top_n

    skills_blob = " ".join(kw for group in resume.skills for kw in group.keywords)
    top_highlights = [h for _, h in sorted(entries, key=lambda item: -highlight_scores.get(item[0], 0))[:6]]
    focus = "\n".join(
        p
        for p in [
            resume.basics.label,
            skills_blob,
            skills_blob,
            resume.basics.summary,
            *top_highlights,
        ]
        if p
    )
    focus_score = cosine_to_query([focus], query)[0] if focus.strip() else 0.0
    corpus_score = cosine_to_query([corpus], query)[0] if corpus.strip() else 0.0
    fuzzy_focus = fuzz.token_set_ratio(focus, query) / 100.0 if focus.strip() and query.strip() else 0.0
    fuzzy_corpus = fuzz.token_set_ratio(corpus, query) / 100.0 if corpus.strip() and query.strip() else 0.0
    semantic = round(
        100.0
        * (
            0.34 * focus_score
            + 0.10 * corpus_score
            + 0.22 * highlight_top
            + 0.28 * fuzzy_focus
            + 0.06 * fuzzy_corpus
        ),
        1,
    )
    overall = round(0.62 * keyword_coverage + 0.38 * semantic, 1)
    return MatchResult(
        overall=overall,
        keyword_coverage=keyword_coverage,
        semantic=semantic,
        gaps=gaps,
        highlight_scores=highlight_scores,
    )
