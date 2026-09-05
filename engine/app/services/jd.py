from __future__ import annotations

import re

from app.schemas import JobAnalysis, ResumeLanguage
from app.services.language import detect_language
from app.services.ontology import find_skills_in_text
from app.services.text import extract_keywords

SENIORITY_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("intern", re.compile(r"\b(intern|stajyer|internship)\b", re.I)),
    ("junior", re.compile(r"\b(junior|jr\.?|giriş|giris seviyesi)\b", re.I)),
    ("mid", re.compile(r"\b(mid[-\s]?level|orta seviye)\b", re.I)),
    ("senior", re.compile(r"\b(senior|sr\.?|kıdemli|kidemli)\b", re.I)),
    ("staff", re.compile(r"\b(staff|principal|lead|baş|bas)\b", re.I)),
    ("manager", re.compile(r"\b(manager|director|head|müdür|mudur)\b", re.I)),
]

TITLE_HINTS = [
    re.compile(r"(?:we are looking for|looking for|position[:\s]+|role[:\s]+|title[:\s]+)\s*(.+)", re.I),
    re.compile(r"(?:arıyoruz|aranıyor|pozisyon[:\s]+|unvan[:\s]+)\s*(.+)", re.I),
]

MUST_MARKERS = re.compile(
    r"(required|must have|minimum qualifications|zorunlu|aranan nitelikler|requirements)",
    re.I,
)
NICE_MARKERS = re.compile(
    r"(preferred qualifications|preferred skills|nice to have|tercihen|bonus skills|"
    r"is a plus|are a plus|is plus|as a plus)",
    re.I,
)
OPTIONAL_WINDOW = re.compile(
    r"\b(plus|preferred|nice to have|bonus|tercihen|art[ıi])\b",
    re.I,
)


def analyze_jd(text: str, company: str = "", title: str = "") -> JobAnalysis:
    language: ResumeLanguage = detect_language(text)
    skills = find_skills_in_text(text)
    surface_forms = {canonical: surface for canonical, surface in skills}
    required, preferred = _split_skill_priority(text, [c for c, _ in skills])
    keywords = extract_keywords(text)
    seniority = _detect_seniority(text)
    guessed_title = title or _guess_title(text)
    guessed_company = company or _guess_company(text)
    return JobAnalysis(
        language=language,
        title=guessed_title.strip(),
        company=guessed_company.strip(),
        seniority=seniority,
        keywords=keywords,
        required_skills=required,
        preferred_skills=preferred,
        surface_forms=surface_forms,
    )


def _detect_seniority(text: str) -> str:
    for label, pattern in SENIORITY_PATTERNS:
        if pattern.search(text):
            return label
    return ""


def _guess_title(text: str) -> str:
    first = text.strip().splitlines()[0] if text.strip() else ""
    if first and len(first) < 80 and not MUST_MARKERS.search(first):
        return re.sub(r"^job title[:\s]*", "", first, flags=re.I).strip()
    for pattern in TITLE_HINTS:
        match = pattern.search(text)
        if match:
            return match.group(1).split("\n")[0].strip(" .")[:80]
    return ""


def _guess_company(text: str) -> str:
    match = re.search(r"(?:at|@|company[:\s]+|şirket[:\s]+)\s*([A-ZÇĞİÖŞÜ][\w&.\- ]{2,40})", text)
    return match.group(1).strip() if match else ""


def _split_skill_priority(text: str, canonicals: list[str]) -> tuple[list[str], list[str]]:
    """Classify ontology skills as required vs preferred.

    Skills mentioned only in optional phrasing (e.g. "Python, SQL is a plus")
    must not be treated as required — otherwise ATS keyword coverage collapses.
    """
    section = NICE_MARKERS.search(text)
    hard_blob = text[: section.start()] if section else text
    soft_blob = text[section.start() :] if section else ""

    required: list[str] = []
    preferred: list[str] = []
    for canonical in canonicals:
        optional = _skill_is_optional(text, canonical)
        in_hard = _mentions(hard_blob, canonical) and not optional
        in_soft = _mentions(soft_blob, canonical) or optional
        if in_hard:
            required.append(canonical)
        elif in_soft:
            preferred.append(canonical)

    if not required and not preferred:
        required = canonicals[:]
    elif not required:
        # Only optional skills found — keep them preferred, don't promote to required.
        pass
    return required, preferred


def _skill_is_optional(text: str, canonical: str) -> bool:
    """True when every mention of the skill sits on an optional line/clause."""
    from app.services.ontology import alias_index

    names = {canonical}
    entry = alias_index().get(canonical.lower())
    if entry:
        names.update(entry.get("aliases", []))
        names.update(entry.get("tr", []))
        names.add(entry.get("canonical", canonical))

    mentions: list[re.Match[str]] = []
    for name in sorted(names, key=len, reverse=True):
        if len(name) < 2:
            continue
        pattern = re.compile(
            rf"(?<![A-Za-z0-9+.#]){re.escape(name)}(?![A-Za-z0-9+.#])",
            re.I,
        )
        mentions.extend(pattern.finditer(text))
    if not mentions:
        return False
    by_start = {m.start(): m for m in mentions}
    mentions = list(by_start.values())
    optional_hits = 0
    for match in mentions:
        line_start = text.rfind("\n", 0, match.start()) + 1
        line_end = text.find("\n", match.end())
        line = text[line_start : line_end if line_end != -1 else match.end() + 40]
        # Same-line optional markers, or tight "is a plus" clause around the skill.
        clause = text[max(0, match.start() - 50) : match.end() + 25]
        if OPTIONAL_WINDOW.search(line) or re.search(
            r"\b(?:is|are)\s+a\s+plus\b|\bnice to have\b|\bpreferred\b",
            clause,
            re.I,
        ):
            optional_hits += 1
    return optional_hits == len(mentions)


def _mentions(blob: str, canonical: str) -> bool:
    from app.services.ontology import alias_index

    names = {canonical}
    entry = alias_index().get(canonical.lower())
    if entry:
        names.update(entry.get("aliases", []))
        names.update(entry.get("tr", []))
        names.add(entry.get("canonical", canonical))
    for name in names:
        if len(name) < 2:
            continue
        if re.search(
            rf"(?<![A-Za-z0-9+.#]){re.escape(name)}(?![A-Za-z0-9+.#])",
            blob,
            re.I,
        ):
            return True
    return False
