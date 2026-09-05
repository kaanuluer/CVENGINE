from __future__ import annotations

import hashlib
import re
import unicodedata

from app.schemas import Fact, Resume
from app.services.ontology import find_skills_in_text

METRIC_RE = re.compile(
    r"(?<![A-Za-z])(\d+(?:[.,]\d+)?\s?%|\d+(?:[.,]\d+)?\s?(?:x|k|m|M|K|mio|bin)?|\+\d+)"
)


def _fid(kind: str, value: str, path: str) -> str:
    raw = f"{kind}|{value}|{path}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def _fold(text: str) -> str:
    return unicodedata.normalize("NFKC", text).strip()


def extract_facts(resume: Resume) -> list[Fact]:
    facts: list[Fact] = []

    def add(kind: str, value: str, path: str, **extra: object) -> None:
        value = _fold(str(value))
        if not value:
            return
        facts.append(
            Fact(
                id=_fid(kind, value.lower(), path),
                type=kind,
                value=value,
                source_path=path,
                extra=extra,
            )
        )

    b = resume.basics
    add("name", b.name, "basics.name")
    add("contact", b.email, "basics.email")
    add("contact", b.phone, "basics.phone")
    add("contact", b.url, "basics.url")
    add("title", b.label, "basics.label")
    add("summary", b.summary, "basics.summary")

    blob_parts: list[str] = [b.summary, b.label]
    for i, work in enumerate(resume.work):
        path = f"work[{i}]"
        add("employer", work.name, f"{path}.name")
        add("title", work.position, f"{path}.position")
        add("date", work.startDate, f"{path}.startDate")
        add("date", work.endDate, f"{path}.endDate")
        add("summary", work.summary, f"{path}.summary")
        blob_parts.extend([work.name, work.position, work.summary, *work.highlights])
        for j, highlight in enumerate(work.highlights):
            add("highlight", highlight, f"{path}.highlights[{j}]", employer=work.name)
            for metric in METRIC_RE.findall(highlight):
                add("metric", metric, f"{path}.highlights[{j}]")

    for i, edu in enumerate(resume.education):
        path = f"education[{i}]"
        add("school", edu.institution, f"{path}.institution")
        add("degree", " ".join(p for p in [edu.studyType, edu.area] if p), path)
        add("date", edu.startDate, f"{path}.startDate")
        add("date", edu.endDate, f"{path}.endDate")
        blob_parts.extend([edu.institution, edu.area, edu.studyType])

    for i, skill in enumerate(resume.skills):
        add("skill_group", skill.name, f"skills[{i}].name")
        for kw in skill.keywords:
            add("tool", kw, f"skills[{i}].keywords")
            blob_parts.append(kw)

    for i, project in enumerate(resume.projects):
        path = f"projects[{i}]"
        add("project", project.name, f"{path}.name")
        add("highlight", project.description, f"{path}.description")
        blob_parts.extend([project.name, project.description, *project.highlights])
        for j, highlight in enumerate(project.highlights):
            add("highlight", highlight, f"{path}.highlights[{j}]")

    for i, cert in enumerate(resume.certificates):
        add("certificate", cert.name, f"certificates[{i}].name")
        add("issuer", cert.issuer, f"certificates[{i}].issuer")

    blob = "\n".join(blob_parts)
    for canonical, surface in find_skills_in_text(blob):
        add("tool", canonical, "derived.tools", surface=surface)

    unique: dict[str, Fact] = {}
    for fact in facts:
        unique[fact.id] = fact
    return list(unique.values())


def fact_values(facts: list[Fact], kind: str) -> set[str]:
    return {f.value.lower() for f in facts if f.type == kind}


def tools_set(facts: list[Fact]) -> set[str]:
    return {f.value.lower() for f in facts if f.type in {"tool", "skill_group"}}
