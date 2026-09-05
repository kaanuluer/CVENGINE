from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import httpx
from rapidfuzz import fuzz

from app.schemas import Fact, JobAnalysis, Resume
from app.services.groundedness import check_groundedness, is_blocking


SYSTEM = """You rewrite resume bullet points for a specific job description.
Rules:
- Never invent employers, dates, degrees, tools, metrics, or titles.
- Only rephrase existing bullets. Keep the same facts and numbers.
- Mirror job-description skill spelling when that skill already appears in the resume.
- No cliches: leverage, passionate, delve, synergy, cutting-edge, results-driven.
- Return JSON only: {"highlights": {"<path>": "rewritten bullet", ...}}
Paths look like work[0].highlights[1].
Do not add new bullets. Do not drop numbers.
"""


@dataclass
class RewriteOutcome:
    resume: Resume | None
    applied: int = 0
    status: str = "failed"


def ollama_available(base_url: str, timeout: float = 1.5) -> bool:
    try:
        response = httpx.get(base_url.rstrip("/") + "/api/tags", timeout=timeout)
        return response.status_code == 200
    except Exception:
        return False


def rewrite_with_ollama(
    resume: Resume,
    analysis: JobAnalysis,
    facts: list[Fact],
    base_url: str,
    model: str,
) -> RewriteOutcome:
    payload = {
        "work": [
            {
                "path": f"work[{i}]",
                "name": w.name,
                "position": w.position,
                "highlights": [{"path": f"work[{i}].highlights[{j}]", "text": h} for j, h in enumerate(w.highlights)],
            }
            for i, w in enumerate(resume.work)
        ],
        "summary": resume.basics.summary,
        "allowed_tools": sorted({f.value for f in facts if f.type == "tool"}),
        "job": {
            "title": analysis.title,
            "keywords": analysis.keywords[:20],
            "required_skills": analysis.required_skills,
            "language": analysis.language,
        },
    }
    prompt = SYSTEM + "\n\nINPUT:\n" + json.dumps(payload, ensure_ascii=False)
    try:
        response = httpx.post(
            base_url.rstrip("/") + "/api/generate",
            json={"model": model, "prompt": prompt, "stream": False, "format": "json"},
            timeout=60.0,
        )
        response.raise_for_status()
        raw = response.json().get("response", "")
        data = _parse_json(raw)
    except Exception:
        return RewriteOutcome(None, 0, "failed")
    if not isinstance(data, dict):
        return RewriteOutcome(None, 0, "failed")

    mapping = _highlight_map(data)
    current = resume.model_copy(deep=True)
    applied = 0
    rejected = 0
    for i, work in enumerate(current.work):
        for j, original in enumerate(work.highlights):
            path = f"work[{i}].highlights[{j}]"
            candidate = mapping.get(path)
            if not candidate or not candidate.strip():
                continue
            if fuzz.token_set_ratio(candidate, original) < 55:
                rejected += 1
                continue
            trial = current.model_copy(deep=True)
            trial.work[i].highlights[j] = candidate.strip()
            score, issues = check_groundedness(resume, trial, facts)
            if is_blocking(issues) or score < 80:
                rejected += 1
                continue
            current.work[i].highlights[j] = candidate.strip()
            applied += 1

    summary = data.get("summary")
    if isinstance(summary, str) and summary.strip() and resume.basics.summary:
        if fuzz.token_set_ratio(summary, resume.basics.summary) >= 60:
            trial = current.model_copy(deep=True)
            trial.basics.summary = summary.strip()
            score, issues = check_groundedness(resume, trial, facts)
            if not is_blocking(issues) and score >= 80:
                current.basics.summary = summary.strip()
                applied += 1
            else:
                rejected += 1

    if applied > 0:
        return RewriteOutcome(current, applied, "applied")
    if rejected > 0:
        return RewriteOutcome(None, 0, "rejected")
    return RewriteOutcome(None, 0, "failed")


def _highlight_map(data: dict) -> dict[str, str]:
    mapping: dict[str, str] = {}
    raw = data.get("highlights")
    if isinstance(raw, dict):
        for key, value in raw.items():
            if isinstance(value, str) and value.strip():
                mapping[str(key)] = value
    work = data.get("work")
    if isinstance(work, list):
        for i, item in enumerate(work):
            if not isinstance(item, dict):
                continue
            highs = item.get("highlights") or []
            if isinstance(highs, dict):
                for key, value in highs.items():
                    if isinstance(value, str) and value.strip():
                        mapping[str(key)] = value
                continue
            if not isinstance(highs, list):
                continue
            for j, entry in enumerate(highs):
                if isinstance(entry, str) and entry.strip():
                    mapping[f"work[{i}].highlights[{j}]"] = entry
                elif isinstance(entry, dict):
                    text = entry.get("text") or entry.get("highlight")
                    if isinstance(text, str) and text.strip():
                        path = entry.get("path") or f"work[{i}].highlights[{j}]"
                        mapping[str(path)] = text
    return mapping


def _parse_json(raw: str) -> Any:
    raw = raw.strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        start, end = raw.find("{"), raw.rfind("}")
        if start >= 0 and end > start:
            return json.loads(raw[start : end + 1])
        raise
