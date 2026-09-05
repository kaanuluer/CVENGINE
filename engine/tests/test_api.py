from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("CVENGINE_DATA_DIR", str(tmp_path / "data"))
    from app.database import reset_engine
    from app.main import app

    reset_engine()
    with TestClient(app) as test_client:
        yield test_client
    reset_engine()


def test_health(client: TestClient):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["ok"] is True


def test_ollama_status_endpoint(client: TestClient):
    response = client.get("/api/settings/ollama?verify=false")
    assert response.status_code == 200
    body = response.json()
    assert "available" in body
    assert "models" in body
    assert "status_label_tr" in body
    assert body["status"] in {"connected", "model_ok", "model_missing", "offline"}


def test_job_suggestions_endpoint(client: TestClient):
    resume_path = Path(__file__).parent / "fixtures" / "resume_en.json"
    parsed = client.post(
        "/api/profiles/parse",
        files={"file": ("resume.json", resume_path.read_bytes(), "application/json")},
    )
    assert parsed.status_code == 200
    profile_id = parsed.json()["id"]
    res = client.post(f"/api/profiles/{profile_id}/job-suggestions")
    assert res.status_code == 200
    body = res.json()
    assert len(body["suggestions"]) >= 3
    assert body["source"] in {"ollama", "heuristic"}
    assert all(s.get("title") and s.get("rationale") for s in body["suggestions"])


def test_parse_and_run(client: TestClient):
    resume_path = Path(__file__).parent / "fixtures" / "resume_en.json"
    jd = (Path(__file__).parent / "fixtures" / "jd_en.txt").read_text(encoding="utf-8")
    parsed = client.post(
        "/api/profiles/parse",
        files={"file": ("resume.json", resume_path.read_bytes(), "application/json")},
    )
    assert parsed.status_code == 200
    profile_id = parsed.json()["id"]
    run = client.post(
        "/api/applications/run",
        json={
            "profile_id": profile_id,
            "job_text": jd,
            "template": "classic",
            "use_ollama": False,
            "save": True,
        },
    )
    assert run.status_code == 200
    body = run.json()
    assert body["result"]["scores"]["groundedness"] >= 80
    assert body["result"]["baseline_scores"]["ats"] >= 0
    assert body["result"]["scores"]["ats"] >= body["result"]["baseline_scores"]["ats"]
    assert body["tailored"]["baseline_scores"]["ats"] == body["result"]["baseline_scores"]["ats"]
    assert body["result"]["cover_letter"]
    assert "Ada Meridian" in body["result"]["cover_letter"]
    assert body["tailored"]["cover_letter"]
    assert body["tailored"]["cover_pdf_path"]
    cover = client.post(
        "/api/export/cover",
        json={"text": body["result"]["cover_letter"], "format": "pdf"},
    )
    assert cover.status_code == 200
    assert cover.content.startswith(b"%PDF")
    apps = client.get("/api/applications")
    assert apps.status_code == 200
    assert len(apps.json()) == 1
    app_id = apps.json()[0]["id"]
    patched = client.patch(f"/api/applications/{app_id}", json={"status": "applied"})
    assert patched.json()["status"] == "applied"
