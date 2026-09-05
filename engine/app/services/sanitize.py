from __future__ import annotations

import re
import unicodedata

from app.schemas import Resume

SENTENCE_END = tuple(".!?;:")


def merge_fragments(parts: list[str]) -> list[str]:
    """Join word-per-line PDF artifacts into real bullets."""
    cleaned = [re.sub(r"\s+", " ", p).strip(" \t•") for p in parts]
    cleaned = [p for p in cleaned if p]
    if not cleaned:
        return []
    out: list[str] = []
    for part in cleaned:
        words = part.split()
        if not out:
            out.append(part)
            continue
        prev = out[-1]
        prev_words = prev.split()
        looks_fragment = len(words) <= 2 or (len(words) <= 4 and not part[:1].isupper())
        prev_open = not prev.endswith(SENTENCE_END) and len(prev_words) < 28
        if looks_fragment and (prev_open or len(prev_words) <= 4):
            out[-1] = f"{prev} {part}".strip()
            continue
        if len(words) == 1 and len(part) <= 18 and prev_open:
            out[-1] = f"{prev} {part}".strip()
            continue
        out.append(part)
    return [item for item in out if len(item) >= 3]


def sanitize_resume(resume: Resume) -> Resume:
    copy = resume.model_copy(deep=True)
    copy.basics.name = _nfc(copy.basics.name)
    copy.basics.label = _nfc(copy.basics.label)
    copy.basics.summary = _nfc(copy.basics.summary)
    copy.basics.email = _nfc(copy.basics.email)
    copy.basics.phone = _nfc(copy.basics.phone)
    copy.basics.url = _nfc(copy.basics.url)
    copy.basics.location.city = _nfc(copy.basics.location.city)
    copy.basics.location.region = _nfc(copy.basics.location.region)
    copy.basics.location.address = _nfc(copy.basics.location.address)
    for work in copy.work:
        work.highlights = merge_fragments([_nfc(h) for h in work.highlights])
        work.name = _nfc(work.name)
        work.position = _nfc(work.position)
        work.summary = _nfc(work.summary)
        work.location = _nfc(work.location)
    for edu in copy.education:
        edu.institution = _nfc(edu.institution)
        edu.area = _nfc(edu.area)
        edu.studyType = _nfc(edu.studyType)
    for project in copy.projects:
        project.name = _nfc(project.name)
        project.description = _nfc(project.description)
        project.highlights = merge_fragments([_nfc(h) for h in project.highlights])
    for skill in copy.skills:
        skill.name = _nfc(skill.name)
        seen: list[str] = []
        for kw in skill.keywords:
            token = _nfc(kw).strip()
            if token and token.lower() not in {s.lower() for s in seen}:
                seen.append(token)
        skill.keywords = seen
    copy.skills = [s for s in copy.skills if s.keywords or s.name]
    copy.work = [w for w in copy.work if w.name or w.position or w.highlights]
    copy.education = [e for e in copy.education if e.institution or e.area]
    for cert in copy.certificates:
        cert.name = _nfc(cert.name)
        cert.issuer = _nfc(cert.issuer)
    copy.certificates = [c for c in copy.certificates if c.name]
    copy.projects = [p for p in copy.projects if p.name or p.highlights]
    for lang in copy.languages:
        lang.language = _nfc(lang.language)
        lang.fluency = _nfc(lang.fluency)
    return copy


def _nfc(value: str) -> str:
    if not value:
        return value
    return unicodedata.normalize("NFC", value).replace("\ufeff", "").replace("\u200b", "").replace("\u200c", "").replace("\u200d", "")
