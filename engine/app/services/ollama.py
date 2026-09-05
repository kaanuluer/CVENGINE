from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Literal

import httpx
from rapidfuzz import fuzz

from app.schemas import Fact, JobAnalysis, Resume
from app.services.consistency import check_consistency
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

SUMMARY_SYSTEM = """You write a cohesive professional resume summary tailored to a job description.
Rules:
- Write 3–5 sentences of prose in the language given (en or tr). Match that language exactly.
- Ground ONLY in the provided master evidence and tailored highlights, titles, and owned skills.
- Never invent employers, tools, metrics, titles, degrees, dates, or achievements.
- Do NOT write a formulaic skills inventory like "skills: A, B, C" or "yetkinlikler: …".
- Prefer a role-led paragraph that weaves owned skills into natural sentences.
- Return JSON only: {"summary": "..."}
"""

PREFERRED_MODELS = ("llama3.1", "llama3", "mistral")
OllamaHealth = Literal["connected", "model_ok", "model_missing", "offline"]


@dataclass
class RewriteOutcome:
    resume: Resume | None
    applied: int = 0
    status: str = "failed"


@dataclass
class OllamaStatus:
    available: bool = False
    models: list[str] = field(default_factory=list)
    selected: str = ""
    healthy: bool = False
    error: str = ""
    status: OllamaHealth = "offline"
    status_label_tr: str = "Ollama kapalı"

    def as_dict(self) -> dict[str, Any]:
        return {
            "available": self.available,
            "models": self.models,
            "selected": self.selected,
            "healthy": self.healthy,
            "error": self.error,
            "status": self.status,
            "status_label_tr": self.status_label_tr,
        }


def ollama_available(base_url: str, timeout: float = 1.5) -> bool:
    try:
        response = httpx.get(base_url.rstrip("/") + "/api/tags", timeout=timeout)
        return response.status_code == 200
    except Exception:
        return False


def list_ollama_models(base_url: str, timeout: float = 3.0) -> list[str]:
    """Return installed model names from GET /api/tags (empty if daemon down)."""
    try:
        response = httpx.get(base_url.rstrip("/") + "/api/tags", timeout=timeout)
        response.raise_for_status()
        models = response.json().get("models") or []
    except Exception:
        return []
    names: list[str] = []
    seen: set[str] = set()
    for entry in models:
        if not isinstance(entry, dict):
            continue
        name = (entry.get("name") or entry.get("model") or "").strip()
        if not name:
            continue
        # Prefer bare tag without :latest duplication noise for matching
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        names.append(name)
    return names


def _model_matches(installed: str, wanted: str) -> bool:
    a = installed.lower().strip()
    b = wanted.lower().strip()
    if not a or not b:
        return False
    if a == b:
        return True
    # "llama3.1" matches "llama3.1:latest" and vice versa
    a_base = a.split(":")[0]
    b_base = b.split(":")[0]
    return a_base == b_base or a.startswith(b + ":") or b.startswith(a + ":")


def find_installed_model(models: list[str], wanted: str) -> str | None:
    for name in models:
        if _model_matches(name, wanted):
            return name
    return None


def ping_model(base_url: str, model: str, timeout: float = 25.0) -> bool:
    """Short generate ping to verify the selected model actually runs."""
    if not model:
        return False
    try:
        response = httpx.post(
            base_url.rstrip("/") + "/api/generate",
            json={
                "model": model,
                "prompt": "Reply with exactly: ok",
                "stream": False,
                "options": {"num_predict": 8, "temperature": 0},
            },
            timeout=timeout,
        )
        response.raise_for_status()
        body = response.json()
        # Ollama returns response text on success; error field on failure
        if body.get("error"):
            return False
        return True
    except Exception:
        return False


def pick_preferred_model(models: list[str], preferred: str = "") -> str | None:
    """Prefer configured model if installed; else llama3.1 → llama3 → mistral → first."""
    if not models:
        return None
    if preferred:
        hit = find_installed_model(models, preferred)
        if hit:
            return hit
    for candidate in PREFERRED_MODELS:
        hit = find_installed_model(models, candidate)
        if hit:
            return hit
    return models[0]


def resolve_working_model(
    base_url: str,
    preferred: str = "",
    *,
    verify: bool = True,
    models: list[str] | None = None,
) -> tuple[str | None, OllamaStatus]:
    """
    Resolve a working installed model. Never returns a missing/broken name.
    When verify=True, pings candidates until one responds.
    """
    status = OllamaStatus(selected=preferred or "")
    installed = models if models is not None else list_ollama_models(base_url)
    if not installed:
        if ollama_available(base_url):
            status.available = True
            status.status = "model_missing"
            status.status_label_tr = "model yok"
            status.error = "Ollama açık ama yüklü model bulunamadı"
        else:
            status.status = "offline"
            status.status_label_tr = "Ollama kapalı"
            status.error = "Ollama erişilemiyor"
        return None, status

    status.available = True
    status.models = installed

    # Build ordered candidates: preferred (if installed) then preferences then rest
    ordered: list[str] = []
    primary = pick_preferred_model(installed, preferred)
    if primary:
        ordered.append(primary)
    for name in installed:
        if name not in ordered:
            ordered.append(name)

    if not verify:
        chosen = ordered[0]
        status.selected = chosen
        status.healthy = bool(chosen)
        status.status = "connected"
        status.status_label_tr = "bağlı"
        return chosen, status

    errors: list[str] = []
    for name in ordered:
        if ping_model(base_url, name):
            status.selected = name
            status.healthy = True
            status.status = "model_ok"
            status.status_label_tr = "model çalışıyor"
            if preferred and not find_installed_model([name], preferred):
                status.error = f"Yapılandırılan model kullanılamadı; {name} seçildi"
            return name, status
        errors.append(name)

    status.selected = preferred or (ordered[0] if ordered else "")
    status.healthy = False
    status.status = "model_missing"
    status.status_label_tr = "model yok"
    status.error = "Yüklü modeller yanıt vermedi: " + ", ".join(errors[:4])
    return None, status


def probe_ollama(base_url: str, preferred: str = "", *, verify_model: bool = True) -> OllamaStatus:
    """Full status for Settings / API: available, models, selected, healthy, labels."""
    models = list_ollama_models(base_url)
    if not models and not ollama_available(base_url):
        return OllamaStatus(
            available=False,
            models=[],
            selected=preferred or "",
            healthy=False,
            error="Ollama erişilemiyor",
            status="offline",
            status_label_tr="Ollama kapalı",
        )
    if not models:
        return OllamaStatus(
            available=True,
            models=[],
            selected=preferred or "",
            healthy=False,
            error="Yüklü model yok",
            status="model_missing",
            status_label_tr="model yok",
        )

    # Daemon up with models — at least "bağlı"
    model, status = resolve_working_model(
        base_url, preferred, verify=verify_model, models=models
    )
    if model and status.healthy:
        return status
    if not verify_model and model:
        status.status = "connected"
        status.status_label_tr = "bağlı"
        status.healthy = True
        return status
    # Models listed but ping failed
    if status.status == "model_missing":
        return status
    status.available = True
    status.models = models
    status.selected = find_installed_model(models, preferred) or pick_preferred_model(models, preferred) or ""
    status.status = "connected"
    status.status_label_tr = "bağlı"
    status.healthy = False
    return status


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
                "highlights": [
                    {"path": f"work[{i}].highlights[{j}]", "text": h}
                    for j, h in enumerate(w.highlights)
                ],
            }
            for i, w in enumerate(resume.work)
        ],
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

    if applied > 0:
        return RewriteOutcome(current, applied, "applied")
    if rejected > 0:
        return RewriteOutcome(None, 0, "rejected")
    return RewriteOutcome(None, 0, "failed")


def rewrite_summary_with_ollama(
    resume: Resume,
    analysis: JobAnalysis,
    facts: list[Fact],
    base_url: str,
    model: str,
    *,
    master: Resume | None = None,
) -> RewriteOutcome:
    """Dedicated cohesive summary rewrite; rolls back on validation failure."""
    master = master or resume
    prior = (resume.basics.summary or "").strip()
    owned_tools = sorted({f.value for f in facts if f.type == "tool"})
    titles = [f.value for f in facts if f.type == "title"]
    highlights = [
        h
        for w in resume.work
        for h in w.highlights[:4]
    ][:12]
    metrics = [f.value for f in facts if f.type == "metric"][:12]
    lang = "Turkish" if analysis.language == "tr" else "English"
    payload = {
        "language": analysis.language,
        "language_name": lang,
        "job_title": analysis.title,
        "current_summary": prior,
        "label": resume.basics.label,
        "owned_skills": owned_tools[:18],
        "titles": titles[:8],
        "quantified_highlights": highlights,
        "metrics": metrics,
        "required_skills_owned": [
            s
            for s in analysis.required_skills + analysis.preferred_skills
            if any(s.lower() in t.lower() or t.lower() in s.lower() for t in owned_tools)
        ][:12],
    }
    prompt = (
        SUMMARY_SYSTEM
        + f"\nWrite the summary in {lang}.\n\nEVIDENCE:\n"
        + json.dumps(payload, ensure_ascii=False)
    )
    try:
        response = httpx.post(
            base_url.rstrip("/") + "/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "stream": False,
                "format": "json",
                "options": {"temperature": 0.35, "num_predict": 500},
            },
            timeout=90.0,
        )
        response.raise_for_status()
        raw = response.json().get("response", "")
        data = _parse_json(raw)
    except Exception:
        return RewriteOutcome(None, 0, "failed")
    if not isinstance(data, dict):
        return RewriteOutcome(None, 0, "failed")
    summary = data.get("summary")
    if not isinstance(summary, str) or len(summary.strip()) < 40:
        return RewriteOutcome(None, 0, "failed")
    candidate = summary.strip()
    # Reject skill-list openers
    lower = candidate.lower()
    if lower.startswith("skills:") or "yetkinlikler:" in lower[:80]:
        return RewriteOutcome(None, 0, "rejected")

    evidence_pool = " ".join(
        [
            prior,
            master.basics.summary or "",
            *[h for w in master.work for h in w.highlights[:3]],
            *owned_tools[:10],
        ]
    )
    prior_ratio = fuzz.token_set_ratio(candidate, prior) if prior else 100
    pool_ratio = fuzz.token_set_ratio(candidate, evidence_pool) if evidence_pool.strip() else prior_ratio
    if prior and max(prior_ratio, pool_ratio) < 55:
        return RewriteOutcome(None, 0, "rejected")

    trial = resume.model_copy(deep=True)
    trial.basics.summary = candidate
    score, issues = check_groundedness(master, trial, facts)
    if is_blocking(issues) or score < 80:
        return RewriteOutcome(None, 0, "rejected")
    _, consistency_issues = check_consistency(master, trial)
    # summary_drift block → rollback; warn-level summary_loose is allowed
    if any(i.code == "summary_drift" and i.severity == "block" for i in consistency_issues):
        return RewriteOutcome(None, 0, "rejected")
    if is_blocking([i for i in consistency_issues if i.code != "summary_drift"]):
        # Other blocking consistency issues from summary alone are rare; still roll back
        blocking_from_summary = [i for i in consistency_issues if i.severity == "block"]
        if blocking_from_summary and any(i.code.startswith("summary") for i in blocking_from_summary):
            return RewriteOutcome(None, 0, "rejected")

    return RewriteOutcome(trial, 1, "applied")


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
