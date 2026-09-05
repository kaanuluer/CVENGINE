from __future__ import annotations

import re

from rapidfuzz import fuzz

from app.schemas import DiffChange, Fact, JobAnalysis, Resume, SkillItem, WorkItem
from app.services.facts import extract_facts, tools_set
from app.services.match import highlight_entries, match_resume, skill_owned
from app.services.ontology import find_skills_in_text, surface_for
from app.services.text import cosine_to_query, extractive_summary

SENIORITY_TOKENS = {
    "intern", "stajyer", "junior", "jr", "senior", "sr", "staff",
    "principal", "lead", "head", "director", "müdür", "mid",
}

HIGHLIGHT_CAP = 6
ATS_BOOST_ROUNDS = 4


def tailor_resume(resume: Resume, analysis: JobAnalysis, facts: list[Fact] | None = None) -> tuple[Resume, list[DiffChange], dict[str, list[str]]]:
    facts = facts or extract_facts(resume)
    match = match_resume(resume, analysis, facts)
    tailored = resume.model_copy(deep=True)
    diffs: list[DiffChange] = []
    fact_map: dict[str, list[str]] = {}

    _rerank_work(tailored, analysis, diffs)
    _rerank_highlights(tailored, match.highlight_scores, diffs)
    _trim_highlights(tailored, match.highlight_scores, diffs)
    _mirror_surface_forms(tailored, analysis, facts, diffs)
    _align_titles(tailored, analysis, diffs)
    _align_label(tailored, analysis, diffs)
    _rewrite_skills(tailored, analysis, facts, diffs, fact_map)
    _rewrite_summary(tailored, analysis, facts, diffs, fact_map, dense=True)
    _map_work_facts(tailored, facts, fact_map)

    return tailored, diffs, fact_map


def amplify_for_ats(
    resume: Resume,
    analysis: JobAnalysis,
    facts: list[Fact],
    fact_map: dict[str, list[str]],
) -> tuple[Resume, list[DiffChange], dict[str, list[str]]]:
    """Grounded second-pass to push ATS keyword/semantic alignment toward the target."""
    tailored = resume.model_copy(deep=True)
    diffs: list[DiffChange] = []
    match = match_resume(tailored, analysis, facts)
    _rerank_highlights(tailored, match.highlight_scores, diffs)
    _mirror_surface_forms(tailored, analysis, facts, diffs)
    _align_label(tailored, analysis, diffs)
    _rewrite_skills(tailored, analysis, facts, diffs, fact_map, aggressive=True)
    _weave_owned_skills_into_highlights(tailored, analysis, facts, diffs)
    _rewrite_summary(tailored, analysis, facts, diffs, fact_map, dense=True)
    _map_work_facts(tailored, facts, fact_map)
    return tailored, diffs, fact_map


def _rerank_work(resume: Resume, analysis: JobAnalysis, diffs: list[DiffChange]) -> None:
    if len(resume.work) < 2:
        return
    query = " ".join([analysis.title, *analysis.required_skills, *analysis.keywords[:10]])
    blobs = [
        " ".join([w.position, w.name, w.summary, *w.highlights[:4]])
        for w in resume.work
    ]
    scores = cosine_to_query(blobs, query) if query.strip() else [0.0] * len(blobs)
    order = sorted(range(len(resume.work)), key=lambda i: -scores[i])
    if order == list(range(len(resume.work))):
        return
    before = [w.position or w.name for w in resume.work]
    resume.work = [resume.work[i] for i in order]
    after = [w.position or w.name for w in resume.work]
    diffs.append(
        DiffChange(
            path="work",
            kind="moved",
            before=" | ".join(before[:4]),
            after=" | ".join(after[:4]),
        )
    )


def _rerank_highlights(resume: Resume, scores: dict[str, float], diffs: list[DiffChange]) -> None:
    for i, work in enumerate(resume.work):
        if len(work.highlights) < 2:
            continue
        indexed = list(enumerate(work.highlights))
        indexed.sort(key=lambda pair: -scores.get(f"work[{i}].highlights[{pair[0]}]", 0))
        new_list = [h for _, h in indexed]
        if new_list != work.highlights:
            diffs.append(
                DiffChange(
                    path=f"work[{i}].highlights",
                    kind="moved",
                    before=" | ".join(work.highlights[:3]),
                    after=" | ".join(new_list[:3]),
                )
            )
            work.highlights = new_list


def _trim_highlights(resume: Resume, scores: dict[str, float], diffs: list[DiffChange]) -> None:
    """After rerank, keep the strongest bullets first; leave the rest after the cap."""
    del scores  # order already encodes relevance from _rerank_highlights
    for i, work in enumerate(resume.work):
        if len(work.highlights) <= HIGHLIGHT_CAP:
            continue
        diffs.append(
            DiffChange(
                path=f"work[{i}].highlights",
                kind="changed",
                before=f"{len(work.highlights)} madde",
                after=f"İlanla en uyumlu {HIGHLIGHT_CAP} madde öne alındı",
            )
        )


def _mirror_surface_forms(
    resume: Resume,
    analysis: JobAnalysis,
    facts: list[Fact],
    diffs: list[DiffChange],
) -> None:
    owned = {t.lower() for t in tools_set(facts)}
    corpus = "\n".join(
        [
            resume.basics.summary,
            *[h for w in resume.work for h in w.highlights],
            *[kw for g in resume.skills for kw in g.keywords],
        ]
    )
    replacements: list[tuple[str, str]] = []
    for skill in analysis.required_skills + analysis.preferred_skills:
        if not skill_owned(skill, owned, corpus):
            continue
        surface = analysis.surface_forms.get(skill) or surface_for(skill, analysis.language)
        if not surface or surface.lower() == skill.lower():
            # Still try alias → JD/canonical spelling
            surface = analysis.surface_forms.get(skill, skill)
        aliases = _aliases_for(skill)
        for alias in aliases:
            if alias.lower() == surface.lower():
                continue
            if len(alias) < 3:
                continue
            replacements.append((alias, surface))

    if not replacements:
        return
    # Longer aliases first to avoid partial collisions
    replacements.sort(key=lambda pair: -len(pair[0]))
    changed = 0

    def apply(text: str) -> str:
        nonlocal changed
        out = text
        for alias, surface in replacements:
            pattern = re.compile(rf"(?<![A-Za-z0-9+.#]){re.escape(alias)}(?![A-Za-z0-9+.#])", re.I)
            if pattern.search(out):
                out, n = pattern.subn(surface, out)
                changed += n
        return out

    before_summary = resume.basics.summary
    resume.basics.summary = apply(resume.basics.summary)
    for work in resume.work:
        work.summary = apply(work.summary)
        work.highlights = [apply(h) for h in work.highlights]
    for group in resume.skills:
        group.keywords = [apply(kw) for kw in group.keywords]
    if changed and resume.basics.summary != before_summary:
        diffs.append(
            DiffChange(
                path="surface_forms",
                kind="changed",
                before="İlan yazımıyla hizalanmamış terimler",
                after=f"{changed} terim ilandaki yazıma çekildi",
            )
        )


def _aliases_for(canonical: str) -> list[str]:
    from app.services.ontology import load_ontology

    names = {canonical}
    for skill in load_ontology().get("skills", []):
        if skill["canonical"].lower() == canonical.lower():
            names.update(skill.get("aliases", []))
            names.update(skill.get("tr", []))
            names.add(skill["canonical"])
            break
    return sorted(names, key=len, reverse=True)


def _align_titles(resume: Resume, analysis: JobAnalysis, diffs: list[DiffChange]) -> None:
    if not analysis.title:
        return
    target = analysis.title.strip()
    for i, work in enumerate(resume.work):
        if not work.position:
            continue
        if _seniority_conflict(work.position, target):
            continue
        score = fuzz.token_set_ratio(work.position, target)
        if score >= 78:
            before = work.position
            work.position = _merge_title(work.position, target)
            if work.position != before:
                diffs.append(
                    DiffChange(
                        path=f"work[{i}].position",
                        kind="changed",
                        before=before,
                        after=work.position,
                    )
                )


def _align_label(resume: Resume, analysis: JobAnalysis, diffs: list[DiffChange]) -> None:
    target = (analysis.title or "").strip()
    if not target:
        return
    current = (resume.basics.label or "").strip()
    if current and _seniority_conflict(current, target):
        return
    score = fuzz.token_set_ratio(current, target) if current else 0
    if current and score < 55:
        # Keep a distinct professional identity unless close to JD
        return
    if current == target:
        return
    resume.basics.label = target
    diffs.append(DiffChange(path="basics.label", kind="changed", before=current, after=target))


def _seniority_conflict(original: str, target: str) -> bool:
    orig_tokens = set(_tokens(original)) & SENIORITY_TOKENS
    tgt_tokens = set(_tokens(target)) & SENIORITY_TOKENS
    return bool(orig_tokens and tgt_tokens and orig_tokens != tgt_tokens)


def _tokens(text: str) -> list[str]:
    return [t.lower() for t in text.replace("/", " ").replace("-", " ").split() if t]


def _merge_title(original: str, target: str) -> str:
    if len(target) > len(original) * 1.8:
        return original
    return target


def _blob(resume: Resume) -> str:
    parts = [resume.basics.summary, resume.basics.label]
    for work in resume.work:
        parts.extend([work.position, *work.highlights, work.summary])
    for skill in resume.skills:
        parts.extend([skill.name, *skill.keywords])
    for project in resume.projects:
        parts.extend([project.name, project.description, *project.highlights])
    return "\n".join(parts)


def _rewrite_skills(
    resume: Resume,
    analysis: JobAnalysis,
    facts: list[Fact],
    diffs: list[DiffChange],
    fact_map: dict[str, list[str]],
    aggressive: bool = False,
) -> None:
    owned = {t.lower() for t in tools_set(facts)}
    corpus = _blob(resume)
    selected: list[str] = []
    for skill in analysis.required_skills + analysis.preferred_skills:
        if not skill_owned(skill, owned, corpus):
            continue
        surface = analysis.surface_forms.get(skill) or surface_for(skill, analysis.language)
        # Only inject skill tokens that already appear in the master corpus
        # (soft-skill proxies may count for matching without inventing new words).
        if not _token_evidenced_in_corpus(skill, surface, corpus):
            continue
        if surface not in selected:
            selected.append(surface)
            fact_map.setdefault("skills", []).append(skill)

    # Grounded short JD keywords already present in the resume text
    for keyword in analysis.keywords:
        token = keyword.strip()
        if len(token) < 4 or len(token.split()) > 2:
            continue
        if token.lower() in {s.lower() for s in selected}:
            continue
        if token.lower() in corpus.lower() and skill_owned(token, owned, corpus):
            selected.append(token)

    leftover: list[str] = []
    for group in resume.skills:
        for kw in group.keywords:
            if kw not in selected and (kw.lower() in owned or skill_owned(kw, owned, corpus)):
                leftover.append(kw)

    core_cap = 18 if aggressive else 14
    extra_cap = 18 if aggressive else 16
    before = [kw for g in resume.skills for kw in g.keywords]
    groups: list[SkillItem] = []
    if selected:
        groups.append(
            SkillItem(
                name="Core" if analysis.language == "en" else "Temel",
                keywords=selected[:core_cap],
            )
        )
    if leftover:
        groups.append(
            SkillItem(
                name="Additional" if analysis.language == "en" else "Ek",
                keywords=leftover[:extra_cap],
            )
        )
    if groups:
        resume.skills = groups
        after = [kw for g in groups for kw in g.keywords]
        if before != after:
            diffs.append(
                DiffChange(
                    path="skills",
                    kind="changed",
                    before=", ".join(before[:8]),
                    after=", ".join(after[:8]),
                )
            )


def _token_evidenced_in_corpus(skill: str, surface: str, corpus: str) -> bool:
    corpus_l = corpus.lower()
    if surface.lower() in corpus_l:
        return True
    for alias in _aliases_for(skill):
        if len(alias) >= 3 and alias.lower() in corpus_l:
            return True
    return False


def _weave_owned_skills_into_highlights(
    resume: Resume,
    analysis: JobAnalysis,
    facts: list[Fact],
    diffs: list[DiffChange],
) -> None:
    """Prefix top bullets with owned JD skill surfaces when missing (no new claims)."""
    owned = {t.lower() for t in tools_set(facts)}
    corpus = _blob(resume)
    surfaces = []
    for skill in analysis.required_skills + analysis.preferred_skills:
        if not skill_owned(skill, owned, corpus):
            continue
        surface = analysis.surface_forms.get(skill) or surface_for(skill, analysis.language)
        if not _token_evidenced_in_corpus(skill, surface, corpus):
            # Prefer an alias that already exists in the corpus.
            evidenced = next((a for a in _aliases_for(skill) if a.lower() in corpus.lower()), None)
            if not evidenced:
                continue
            surface = evidenced
        surfaces.append(surface)
    if not surfaces or not resume.work:
        return
    changed = 0
    # Keep voice natural: at most one woven bullet per role, top role only.
    for work in resume.work[:1]:
        for idx, highlight in enumerate(work.highlights[:1]):
            lower = highlight.lower()
            missing = [s for s in surfaces if s.lower() not in lower][:1]
            if not missing:
                continue
            if len(highlight) < 28:
                continue
            # Prefer light parenthetical weave over "X ile:" which breaks sentence voice.
            if analysis.language == "tr":
                woven = f"{highlight.rstrip('.')} ({missing[0]})."
            else:
                woven = f"{highlight.rstrip('.')} ({missing[0]})."
            if woven != highlight and len(woven) < 280:
                work.highlights[idx] = woven
                changed += 1
    if changed:
        diffs.append(
            DiffChange(
                path="work.highlights",
                kind="changed",
                before="İlan yetkinlikleri vurgulanmamış maddeler",
                after=f"{changed} maddeye sahip olunan ilan yetkinlikleri eklendi",
            )
        )


def _rewrite_summary(
    resume: Resume,
    analysis: JobAnalysis,
    facts: list[Fact],
    diffs: list[DiffChange],
    fact_map: dict[str, list[str]],
    dense: bool = False,
) -> None:
    owned = {t.lower() for t in tools_set(facts)}
    corpus = _blob(resume)
    skill_limit = 10 if dense else 6
    owned_required = []
    for skill in analysis.required_skills + analysis.preferred_skills:
        if not skill_owned(skill, owned, corpus):
            continue
        surface = analysis.surface_forms.get(skill) or surface_for(skill, analysis.language)
        if not _token_evidenced_in_corpus(skill, surface, corpus):
            evidenced = next((a for a in _aliases_for(skill) if a.lower() in corpus.lower()), None)
            if not evidenced:
                continue
            surface = evidenced
        owned_required.append(surface)
    owned_required = owned_required[:skill_limit]
    # Dedupe while preserving order
    seen: set[str] = set()
    owned_required = [s for s in owned_required if not (s.lower() in seen or seen.add(s.lower()))]

    # Distinctive JD phrases already evidenced in the resume (domain lift).
    domain_bits: list[str] = []
    corpus_l = corpus.lower()
    for kw in analysis.keywords:
        token = kw.strip()
        if len(token) < 5 or " " not in token:
            continue
        if token.lower() in corpus_l and token.lower() not in {s.lower() for s in owned_required}:
            domain_bits.append(token)
        if len(domain_bits) >= 4:
            break

    candidates: list[str] = []
    if resume.basics.summary:
        candidates.extend(_split_keep(resume.basics.summary))
    for work in resume.work:
        if work.summary:
            candidates.append(work.summary)
        candidates.extend(work.highlights[:4])
    query = " ".join(
        [analysis.title, *analysis.required_skills, *analysis.preferred_skills, *analysis.keywords[:10]]
    )
    evidence = extractive_summary(candidates, query, limit=5 if dense else 3)

    role = analysis.title or resume.basics.label or ("Professional" if analysis.language == "en" else "Profesyonel")
    skill_clause = ", ".join(owned_required)
    domain_clause = ", ".join(domain_bits)
    if analysis.language == "tr":
        opener = f"{role}."
        if skill_clause:
            opener += f" Doğrudan ilgili yetkinlikler: {skill_clause}."
        if domain_clause:
            opener += f" İlanla örtüşen odak: {domain_clause}."
    else:
        if skill_clause:
            opener = f"{role} with proven depth in {skill_clause}."
        else:
            opener = f"{role} with relevant, verifiable delivery against the posting."
        if domain_clause:
            opener += f" Domain focus aligned to {domain_clause}."
    summary = " ".join(p for p in [opener, evidence] if p).strip()
    # Avoid accidental duplication from prior dense passes
    summary = re.sub(r"(\b\S.{10,90}?\.)(?:\s+\1)+", r"\1", summary)
    # Drop evidence sentence if it mostly repeats the opener
    if evidence and fuzz.token_set_ratio(opener, evidence) >= 86:
        summary = opener

    if summary and summary != resume.basics.summary:
        diffs.append(
            DiffChange(
                path="basics.summary",
                kind="changed",
                before=(resume.basics.summary or "")[:180],
                after=summary[:180],
            )
        )
        resume.basics.summary = summary
        fact_map["basics.summary"] = ["summary"] + owned_required + domain_bits


def _split_keep(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [p.strip() for p in parts if len(p.strip()) > 24]


def _map_work_facts(resume: Resume, facts: list[Fact], fact_map: dict[str, list[str]]) -> None:
    by_value = {}
    for fact in facts:
        by_value.setdefault(fact.value.lower(), []).append(fact.id)
    for i, work in enumerate(resume.work):
        for j, highlight in enumerate(work.highlights):
            ids = by_value.get(highlight.lower(), [])
            if ids:
                fact_map[f"work[{i}].highlights[{j}]"] = ids
            fact_map.setdefault(f"work[{i}].name", [])
            emp = next((f.id for f in facts if f.type == "employer" and f.value.lower() == work.name.lower()), None)
            if emp:
                fact_map[f"work[{i}].name"] = [emp]


def work_highlights(work: WorkItem) -> list[str]:
    return list(work.highlights)
