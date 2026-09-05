from __future__ import annotations

from rapidfuzz import fuzz

from app.schemas import Fact, GapItem, JobAnalysis, MatchResult, Resume
from app.services.facts import extract_facts, tools_set
from app.services.ontology import alias_index, canonical_skill
from app.services.text import cosine_to_query

# Soft-skill evidence proxies when the literal skill name is absent.
SOFT_SKILL_PROXIES: dict[str, tuple[str, ...]] = {
    "communication": (
        "stakeholder",
        "cross-functional",
        "cross functional",
        "presentation",
        "executive communication",
        "customer experience",
        "collaboration",
        "partnered",
        "worked closely",
    ),
    "leadership": (
        "people management",
        "led",
        "managed team",
        "managed teams",
        "coach",
        "mentored",
        "leadership",
        "head of",
        "manager",
        "director",
    ),
    "rest": (
        "fastapi",
        "flask",
        "django",
        "restful",
        "rest api",
        "http api",
        "api gateway",
    ),
    "ci/cd": (
        "github actions",
        "gitlab ci",
        "jenkins",
        "ci/cd",
        "continuous integration",
        "continuous delivery",
    ),
}


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
    corpus_l = corpus.lower()
    if needle in owned_tools:
        return True
    if any(needle == t or needle in t or t in needle for t in owned_tools):
        return True
    if needle in corpus_l:
        return True
    # Ontology aliases / translations
    canon = (canonical_skill(skill) or skill).lower()
    entry = alias_index().get(needle) or alias_index().get(canon)
    if entry:
        for alias in [*entry.get("aliases", []), *entry.get("tr", []), entry.get("canonical", "")]:
            alias_l = str(alias).lower().strip()
            if len(alias_l) < 3:
                continue
            if alias_l in corpus_l or alias_l in owned_tools:
                return True
            if any(fuzz.partial_ratio(alias_l, t) >= 90 for t in owned_tools if len(t) >= 3):
                return True
    # Soft-skill proxies
    for key, proxies in SOFT_SKILL_PROXIES.items():
        if key == needle or key in needle or needle in key:
            if any(p in corpus_l for p in proxies):
                return True
    if any(fuzz.partial_ratio(needle, t) >= 90 for t in owned_tools if len(t) >= 3):
        return True
    return False


def match_resume(resume: Resume, analysis: JobAnalysis, facts: list[Fact] | None = None) -> MatchResult:
    facts = facts or extract_facts(resume)
    owned_tools = tools_set(facts)
    corpus = resume_corpus(resume)
    if not (analysis.required_skills or analysis.preferred_skills):
        # Fall back to keyword-derived skills when ontology finds nothing.
        _ = [canonical_skill(k) or k for k in analysis.keywords[:12]]

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

    # Domain keyword lift: multi-word / high-signal JD terms present in the resume.
    keyword_coverage = round(
        min(100.0, keyword_coverage + _domain_keyword_bonus(analysis, corpus)),
        1,
    )

    query_skills = " ".join(
        [analysis.title, *analysis.required_skills, *analysis.preferred_skills]
    ).strip()
    query_domain = " ".join([analysis.title, *analysis.keywords[:14]]).strip()
    query = (query_skills + " " + query_domain).strip()
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
    top_highlights = [h for _, h in sorted(entries, key=lambda item: -highlight_scores.get(item[0], 0))[:8]]
    focus = "\n".join(
        p
        for p in [
            resume.basics.label,
            analysis.title,
            skills_blob,
            skills_blob,
            resume.basics.summary,
            *top_highlights,
        ]
        if p
    )
    # Score semantic against both skill-centric and domain-centric queries; keep the better fit.
    def _sem_for(q: str) -> float:
        if not q.strip() or not focus.strip():
            return 0.0
        fs = cosine_to_query([focus], q)[0]
        cs = cosine_to_query([corpus], q)[0] if corpus.strip() else 0.0
        ff = fuzz.token_set_ratio(focus, q) / 100.0
        fc = fuzz.token_set_ratio(corpus, q) / 100.0 if corpus.strip() else 0.0
        return (
            0.34 * fs
            + 0.10 * cs
            + 0.22 * highlight_top
            + 0.28 * ff
            + 0.06 * fc
        )

    semantic = round(100.0 * max(_sem_for(query_skills), _sem_for(query_domain), _sem_for(query)), 1)
    overall = round(0.62 * keyword_coverage + 0.38 * semantic, 1)
    return MatchResult(
        overall=overall,
        keyword_coverage=keyword_coverage,
        semantic=semantic,
        gaps=gaps,
        highlight_scores=highlight_scores,
    )


def _domain_keyword_bonus(analysis: JobAnalysis, corpus: str) -> float:
    """Small ATS lift when distinctive JD phrases already appear in the resume."""
    corpus_l = corpus.lower()
    skill_names = {s.lower() for s in analysis.required_skills + analysis.preferred_skills}
    candidates: list[str] = []
    for kw in analysis.keywords:
        token = kw.strip()
        if len(token) < 5:
            continue
        if token.lower() in skill_names:
            continue
        if " " in token or len(token) >= 8:
            candidates.append(token.lower())
    if not candidates:
        return 0.0
    hits = sum(1 for c in candidates[:16] if c in corpus_l)
    if hits <= 0:
        return 0.0
    return min(24.0, hits * 3.5)
