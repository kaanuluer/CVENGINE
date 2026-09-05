from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from app.schemas import Resume
from app.services.job_suggestions import _heuristic_suggestions, suggest_job_types
from app.services.ollama import (
    _highlight_map,
    find_installed_model,
    ollama_available,
    pick_preferred_model,
    rewrite_summary_with_ollama,
)
from app.services.facts import extract_facts
from app.services.jd import analyze_jd
from app.services.tailor import tailor_resume

FIXTURES = Path(__file__).parent / "fixtures"


def load_resume(name: str) -> Resume:
    import json

    return Resume.model_validate(json.loads((FIXTURES / name).read_text(encoding="utf-8")))


def test_ollama_probe_does_not_require_daemon():
    assert ollama_available("http://127.0.0.1:9", timeout=0.2) is False


def test_ollama_parses_highlight_shapes():
    mapped = _highlight_map(
        {
            "highlights": {"work[0].highlights[0]": "Kept FastAPI on PostgreSQL."},
            "work": [{"highlights": [{"path": "work[1].highlights[0]", "text": "Cut latency 40%."}]}],
        }
    )
    assert mapped["work[0].highlights[0]"].startswith("Kept FastAPI")
    assert mapped["work[1].highlights[0]"].startswith("Cut latency")


def test_pick_preferred_model_order():
    models = ["mistral:latest", "llama3.1:latest", "tiny"]
    assert pick_preferred_model(models, "missing").startswith("llama3.1")
    assert find_installed_model(models, "llama3.1") == "llama3.1:latest"
    assert pick_preferred_model(models, "mistral") == "mistral:latest"


def test_heuristic_summary_is_prose_not_skill_list():
    resume = load_resume("resume_en.json")
    jd = (FIXTURES / "jd_en.txt").read_text(encoding="utf-8")
    analysis = analyze_jd(jd)
    tailored, _, _ = tailor_resume(resume, analysis)
    summary = tailored.basics.summary.lower()
    assert "yetkinlikler:" not in summary
    assert not summary.startswith("skills:")
    assert "with proven depth in" not in summary
    assert "software" in summary or "engineer" in summary or "backend" in summary


def test_rewrite_summary_rejects_ungrounded(monkeypatch):
    resume = load_resume("resume_en.json")
    jd = (FIXTURES / "jd_en.txt").read_text(encoding="utf-8")
    analysis = analyze_jd(jd)
    facts = extract_facts(resume)

    fake_response = MagicMock()
    fake_response.raise_for_status = MagicMock()
    fake_response.json.return_value = {
        "response": '{"summary": "Nobel-winning hospitality CEO who invented COBOL quantum ledgers at FakeCorp."}'
    }

    with patch("app.services.ollama.httpx.post", return_value=fake_response):
        outcome = rewrite_summary_with_ollama(
            resume, analysis, facts, "http://127.0.0.1:11434", "llama3.1", master=resume
        )
    assert outcome.status in {"rejected", "failed"}
    assert outcome.resume is None


def test_job_suggestions_heuristic_grounded():
    resume = load_resume("resume_en.json")
    facts = extract_facts(resume)
    items = _heuristic_suggestions(resume, facts)
    assert len(items) >= 3
    titles = " ".join(i.title.lower() for i in items)
    assert "software" in titles or "python" in titles or "backend" in titles or "geliştirici" in titles


def test_suggest_job_types_fallback_without_ollama():
    resume = load_resume("resume_en.json")
    out = suggest_job_types(
        resume,
        ollama_url="http://127.0.0.1:9",
        ollama_model="nope",
        prefer_ollama=True,
    )
    assert out.source == "heuristic"
    assert len(out.suggestions) >= 3
    assert out.ollama_available is False
