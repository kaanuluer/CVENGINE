from __future__ import annotations

from app.schemas import Fact, JobSuggestion, JobSuggestionsOut, Resume
from app.services.facts import extract_facts, tools_set
from app.services.ollama import ollama_available, resolve_working_model
from app.services.ontology import find_skills_in_text

import json

import httpx


# Heuristic skill → Turkish role suggestions (grounded in owned skills only).
SKILL_ROLE_HINTS: list[tuple[tuple[str, ...], str, str]] = [
    (("React", "Vue", "Angular", "Next.js", "TypeScript", "JavaScript"), "Ön uç geliştirici", "Arayüz teknolojileri CV'de yer alıyor."),
    (("FastAPI", "Django", "Flask", "Spring", "Node.js", "Express", "Go"), "Backend geliştirici", "Sunucu tarafı çerçeveler ve API deneyimi mevcut."),
    (("PostgreSQL", "MySQL", "SQL", "MongoDB", "Redis"), "Veri odaklı yazılım geliştirici", "Veritabanı ve veri katmanı becerileri öne çıkıyor."),
    (("Docker", "Kubernetes", "CI/CD", "Terraform", "AWS", "GCP", "Azure"), "DevOps / platform mühendisi", "Altyapı, bulut veya dağıtım araçları CV'de geçiyor."),
    (("Pandas", "NumPy", "scikit-learn", "PyTorch", "TensorFlow", "Machine Learning", "Spark", "Airflow"), "Veri mühendisi / ML mühendisi", "Veri ve makine öğrenmesi yığınına dair kanıt var."),
    (("Python",), "Python geliştirici", "Python ana dil olarak listelenmiş."),
    (("Swift", "Kotlin", "React Native"), "Mobil uygulama geliştirici", "Mobil geliştirme teknolojileri mevcut."),
]


SUGGEST_SYSTEM = """Master CV'ye dayanarak önerilen iş türleri / roller üret.
Kurallar:
- Yalnızca verilen deneyim, unvan ve becerilerden yola çık.
- İşveren, araç, metrik veya unvan UYDURMA.
- Türkçe yaz (UI dili).
- 5–8 madde üret.
- JSON döndür: {"suggestions": [{"title": "...", "rationale": "tek satır gerekçe"}, ...]}
"""


def suggest_job_types(
    resume: Resume,
    *,
    facts: list[Fact] | None = None,
    ollama_url: str = "",
    ollama_model: str = "",
    prefer_ollama: bool = True,
) -> JobSuggestionsOut:
    facts = facts or extract_facts(resume)
    if prefer_ollama and ollama_url and ollama_available(ollama_url):
        model, status = resolve_working_model(ollama_url, ollama_model, verify=False)
        if model:
            polished = _suggest_with_ollama(resume, facts, ollama_url, model)
            if polished and len(polished) >= 3:
                return JobSuggestionsOut(
                    suggestions=polished[:8],
                    source="ollama",
                    ollama_available=True,
                    model=model,
                )
        heuristic = _heuristic_suggestions(resume, facts)
        msg = "Ollama modeli kullanılamadı; sezgisel öneriler gösteriliyor."
        if not status.available:
            msg = "Ollama kapalı; sezgisel öneriler gösteriliyor."
        elif status.error:
            msg = status.error
        return JobSuggestionsOut(
            suggestions=heuristic,
            source="heuristic",
            ollama_available=status.available,
            model=status.selected or "",
            message=msg,
        )

    heuristic = _heuristic_suggestions(resume, facts)
    return JobSuggestionsOut(
        suggestions=heuristic,
        source="heuristic",
        ollama_available=False,
        model="",
        message="Ollama kapalı; sezgisel öneriler gösteriliyor.",
    )


def _suggest_with_ollama(
    resume: Resume,
    facts: list[Fact],
    base_url: str,
    model: str,
) -> list[JobSuggestion] | None:
    evidence = {
        "label": resume.basics.label,
        "summary": (resume.basics.summary or "")[:600],
        "titles": [f.value for f in facts if f.type == "title"][:10],
        "skills": sorted(tools_set(facts))[:24],
        "recent_roles": [
            {"position": w.position, "employer": w.name, "highlights": w.highlights[:2]}
            for w in resume.work[:4]
        ],
        "skill_groups": [g.name for g in resume.skills if g.name],
    }
    prompt = SUGGEST_SYSTEM + "\n\nKANIT:\n" + json.dumps(evidence, ensure_ascii=False)
    try:
        response = httpx.post(
            base_url.rstrip("/") + "/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "stream": False,
                "format": "json",
                "options": {"temperature": 0.3, "num_predict": 700},
            },
            timeout=90.0,
        )
        response.raise_for_status()
        raw = response.json().get("response", "")
        data = json.loads(raw) if raw.strip().startswith("{") else _extract_json(raw)
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    items = data.get("suggestions") or data.get("roles") or []
    if not isinstance(items, list):
        return None
    out: list[JobSuggestion] = []
    corpus = _corpus(resume).lower()
    for item in items:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or item.get("role") or "").strip()
        rationale = str(item.get("rationale") or item.get("reason") or "").strip()
        if len(title) < 3 or len(rationale) < 8:
            continue
        # Soft grounding: title tokens should relate to label/skills/titles
        if not _suggestion_grounded(title, rationale, corpus):
            continue
        out.append(JobSuggestion(title=title[:120], rationale=rationale[:220]))
        if len(out) >= 8:
            break
    return out if len(out) >= 3 else None


def _extract_json(raw: str) -> dict:
    start, end = raw.find("{"), raw.rfind("}")
    if start >= 0 and end > start:
        return json.loads(raw[start : end + 1])
    raise ValueError("no json")


def _corpus(resume: Resume) -> str:
    parts = [resume.basics.summary, resume.basics.label]
    for w in resume.work:
        parts.extend([w.position, w.name, *w.highlights[:3]])
    for g in resume.skills:
        parts.extend([g.name, *g.keywords])
    return "\n".join(p for p in parts if p)


def _suggestion_grounded(title: str, rationale: str, corpus: str) -> bool:
    blob = f"{title} {rationale}".lower()
    # Reject obvious invention markers
    banned = ("blockchain quantum", "fortune 500 ceo", "nobel")
    if any(b in blob for b in banned):
        return False
    # At least one content token (≥4 chars) from title appears in corpus, or soft role words
    tokens = [t for t in title.lower().replace("/", " ").split() if len(t) >= 4]
    if not tokens:
        return True
    hits = sum(1 for t in tokens if t in corpus)
    soft = ("geliştirici", "developer", "mühendis", "engineer", "analist", "analyst", "yönetici", "manager")
    if any(s in title.lower() for s in soft):
        return True
    return hits >= 1 or len(tokens) <= 2


def _heuristic_suggestions(resume: Resume, facts: list[Fact]) -> list[JobSuggestion]:
    suggestions: list[JobSuggestion] = []
    seen: set[str] = set()

    def add(title: str, rationale: str) -> None:
        key = title.lower().strip()
        if not key or key in seen:
            return
        seen.add(key)
        suggestions.append(JobSuggestion(title=title.strip(), rationale=rationale.strip()))

    label = (resume.basics.label or "").strip()
    if label:
        add(label, "Master CV'deki mevcut unvan / profesyonel etiket.")

    for work in resume.work[:4]:
        if work.position:
            add(work.position, f"Son rollerden: {work.name or 'deneyim'} altında yer alıyor.")

    owned = {t.lower() for t in tools_set(facts)}
    corpus = _corpus(resume)
    found = {c for c, _ in find_skills_in_text(corpus)}
    for skill_keys, title, rationale in SKILL_ROLE_HINTS:
        if any(k.lower() in owned or k in found for k in skill_keys):
            add(title, rationale)

    # Skill group names as soft roles
    for group in resume.skills:
        name = (group.name or "").strip()
        if name and name.lower() not in {"core", "temel", "ek", "additional", "yetenekler", "skills"}:
            add(f"{name} uzmanı", f"Beceri grubu «{name}» CV'de tanımlı.")

    if len(suggestions) < 5 and label:
        add(f"Kıdemli {label}", "Mevcut unvanın kıdemli varyasyonu (deneyim derinliğine göre).")
        add(f"{label} (sözleşmeli / freelance)", "Aynı yetkinlik setiyle proje bazlı roller.")

    # Pad with generic grounded fallbacks from tools
    tools = sorted(tools_set(facts))[:3]
    if tools and len(suggestions) < 5:
        add(
            "Yazılım geliştirici",
            f"Öne çıkan araçlar: {', '.join(tools)}.",
        )

    return suggestions[:8]
