from __future__ import annotations

import json
import re
from functools import lru_cache

from app.config import skills_path


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


@lru_cache(maxsize=1)
def load_ontology() -> dict:
    path = skills_path()
    if not path.exists():
        return {"skills": []}
    return json.loads(path.read_text(encoding="utf-8"))


def clear_ontology_cache() -> None:
    load_ontology.cache_clear()
    alias_index.cache_clear()
    all_skill_terms.cache_clear()


@lru_cache(maxsize=1)
def alias_index() -> dict[str, dict]:
    index: dict[str, dict] = {}
    for skill in load_ontology().get("skills", []):
        canonical = skill["canonical"]
        names = {canonical, *skill.get("aliases", []), *skill.get("tr", [])}
        entry = {
            "canonical": canonical,
            "aliases": [canonical, *skill.get("aliases", [])],
            "tr": skill.get("tr", [canonical]),
        }
        for name in names:
            index[_norm(name)] = entry
    return index


def canonical_skill(term: str) -> str | None:
    entry = alias_index().get(_norm(term))
    return entry["canonical"] if entry else None


@lru_cache(maxsize=1)
def all_skill_terms() -> tuple[str, ...]:
    terms: list[str] = []
    for skill in load_ontology().get("skills", []):
        terms.append(skill["canonical"])
        terms.extend(skill.get("aliases", []))
        terms.extend(skill.get("tr", []))
    unique = sorted(set(terms), key=lambda t: (-len(t), t.lower()))
    return tuple(unique)


def surface_for(canonical: str, language: str, jd_surface: str | None = None) -> str:
    if jd_surface:
        return jd_surface
    for skill in load_ontology().get("skills", []):
        if skill["canonical"] == canonical:
            if language == "tr":
                return (skill.get("tr") or [canonical])[0]
            return canonical
    return canonical


def find_skills_in_text(text: str) -> list[tuple[str, str]]:
    """Return list of (canonical, surface_form) found in text."""
    found: list[tuple[str, str]] = []
    seen: set[str] = set()
    for term in all_skill_terms():
        pattern = re.compile(rf"(?<![A-Za-z0-9+.#]){re.escape(term)}(?![A-Za-z0-9+.#])", re.I)
        match = pattern.search(text)
        if not match:
            continue
        canon = canonical_skill(term)
        if not canon or canon in seen:
            continue
        seen.add(canon)
        found.append((canon, match.group(0)))
    return found
