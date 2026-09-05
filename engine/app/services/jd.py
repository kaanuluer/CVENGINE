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
    r"(preferred|nice to have|plus|tercihen|artı|bonus)",
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
    parts = re.split(NICE_MARKERS, text, maxsplit=1)
    required_blob = parts[0]
    preferred_blob = parts[1] if len(parts) > 1 else ""
    required = [c for c in canonicals if _mentions(required_blob, c)]
    preferred = [c for c in canonicals if c not in required and _mentions(preferred_blob or text, c)]
    if not required:
        required = canonicals[:]
        preferred = []
    return required, preferred


def _mentions(blob: str, canonical: str) -> bool:
    return bool(re.search(rf"(?<![A-Za-z0-9+.#]){re.escape(canonical)}(?![A-Za-z0-9+.#])", blob, re.I))
