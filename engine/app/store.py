from __future__ import annotations

import json
import uuid
from typing import Any

from app.database import (
    ApplicationRow,
    CareerFactRow,
    JobRow,
    ProfileRow,
    SessionLocal,
    SettingRow,
    TailoredRow,
    utcnow,
)
from app.schemas import (
    ApplicationOut,
    Fact,
    JobAnalysis,
    JobOut,
    ProfileOut,
    Resume,
    SettingsOut,
    TailoredOut,
    ScoreBlock,
)
from app.services.ats import ats_alignment
from app.services.facts import extract_facts
from app.services.ollama import probe_ollama, resolve_working_model
from app.services.sanitize import sanitize_resume


def _uid() -> str:
    return uuid.uuid4().hex


def profile_to_out(row: ProfileRow) -> ProfileOut:
    return ProfileOut(
        id=row.id,
        name=row.name,
        resume=sanitize_resume(Resume.model_validate(json.loads(row.resume_json))),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def job_to_out(row: JobRow) -> JobOut:
    analysis = JobAnalysis.model_validate(json.loads(row.analysis_json or "{}"))
    return JobOut(
        id=row.id,
        title=row.title,
        company=row.company,
        raw_text=row.raw_text,
        analysis=analysis,
        created_at=row.created_at,
    )


def tailored_to_out(row: TailoredRow) -> TailoredOut:
    from app.schemas import DiffChange

    scores = _hydrate_scores(json.loads(row.scores_json or "{}"))
    raw_baseline = getattr(row, "baseline_scores_json", None) or ""
    baseline = _hydrate_scores(json.loads(raw_baseline)) if raw_baseline.strip() else None
    return TailoredOut(
        id=row.id,
        application_id=row.application_id,
        template=row.template,  # type: ignore[arg-type]
        resume=sanitize_resume(Resume.model_validate(json.loads(row.resume_json))),
        scores=scores,
        baseline_scores=baseline,
        fact_map=json.loads(row.fact_map_json or "{}"),
        diff=[DiffChange.model_validate(x) for x in json.loads(row.diff_json or "[]")],
        pdf_path=row.pdf_path,
        docx_path=row.docx_path,
        cover_letter=getattr(row, "cover_letter", None) or "",
        cover_pdf_path=getattr(row, "cover_pdf_path", None),
        cover_docx_path=getattr(row, "cover_docx_path", None),
        language=getattr(row, "language", None) or "en",  # type: ignore[arg-type]
        used_ollama=row.used_ollama == "1",
        created_at=row.created_at,
    )


def _hydrate_scores(raw: dict) -> ScoreBlock:
    block = ScoreBlock.model_validate(raw or {})
    if not block.ats:
        block.ats = ats_alignment(block.keyword, block.semantic)
    return block


def application_to_out(row: ApplicationRow, latest: TailoredRow | None = None) -> ApplicationOut:
    latest_out = tailored_to_out(latest) if latest else None
    return ApplicationOut(
        id=row.id,
        profile_id=row.profile_id,
        job_id=row.job_id,
        company=row.company,
        role=row.role,
        status=row.status,  # type: ignore[arg-type]
        notes=row.notes,
        created_at=row.created_at,
        updated_at=row.updated_at,
        latest=latest_out,
        keyword_score=latest_out.scores.keyword if latest_out else None,
        overall_score=latest_out.scores.overall if latest_out else None,
        baseline_ats=latest_out.baseline_scores.ats if latest_out and latest_out.baseline_scores else None,
        tailored_ats=latest_out.scores.ats if latest_out else None,
    )


def latest_tailored(session, application_id: str) -> TailoredRow | None:
    return (
        session.query(TailoredRow)
        .filter(TailoredRow.application_id == application_id)
        .order_by(TailoredRow.created_at.desc())
        .first()
    )


def create_profile(name: str, resume: Resume) -> ProfileOut:
    session = SessionLocal()
    try:
        now = utcnow()
        row = ProfileRow(
            id=_uid(),
            name=name,
            resume_json=resume.model_dump_json(),
            created_at=now,
            updated_at=now,
        )
        session.add(row)
        _replace_facts(session, row.id, extract_facts(resume))
        session.commit()
        session.refresh(row)
        return profile_to_out(row)
    finally:
        session.close()


def update_profile(profile_id: str, name: str | None, resume: Resume | None) -> ProfileOut | None:
    session = SessionLocal()
    try:
        row = session.get(ProfileRow, profile_id)
        if not row:
            return None
        if name is not None:
            row.name = name
        if resume is not None:
            row.resume_json = resume.model_dump_json()
            session.query(CareerFactRow).filter(CareerFactRow.profile_id == profile_id).delete()
            _replace_facts(session, profile_id, extract_facts(resume))
        row.updated_at = utcnow()
        session.commit()
        session.refresh(row)
        return profile_to_out(row)
    finally:
        session.close()


def _replace_facts(session, profile_id: str, facts: list[Fact]) -> None:
    for fact in facts:
        session.add(
            CareerFactRow(
                id=fact.id + profile_id[:4],
                profile_id=profile_id,
                fact_type=fact.type,
                value=fact.value,
                source_path=fact.source_path,
                extra_json=json.dumps(fact.extra, ensure_ascii=False),
            )
        )


def list_profiles() -> list[ProfileOut]:
    session = SessionLocal()
    try:
        rows = session.query(ProfileRow).order_by(ProfileRow.updated_at.desc()).all()
        return [profile_to_out(r) for r in rows]
    finally:
        session.close()


def get_profile(profile_id: str) -> ProfileOut | None:
    session = SessionLocal()
    try:
        row = session.get(ProfileRow, profile_id)
        return profile_to_out(row) if row else None
    finally:
        session.close()


def delete_profile(profile_id: str) -> bool:
    session = SessionLocal()
    try:
        row = session.get(ProfileRow, profile_id)
        if not row:
            return False
        session.delete(row)
        session.commit()
        return True
    finally:
        session.close()


def create_job(raw_text: str, analysis: JobAnalysis, company: str = "", title: str = "") -> JobOut:
    session = SessionLocal()
    try:
        row = JobRow(
            id=_uid(),
            title=title or analysis.title,
            company=company or analysis.company,
            raw_text=raw_text,
            analysis_json=analysis.model_dump_json(),
            created_at=utcnow(),
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        return job_to_out(row)
    finally:
        session.close()


def get_job(job_id: str) -> JobOut | None:
    session = SessionLocal()
    try:
        row = session.get(JobRow, job_id)
        return job_to_out(row) if row else None
    finally:
        session.close()


def list_jobs() -> list[JobOut]:
    session = SessionLocal()
    try:
        rows = session.query(JobRow).order_by(JobRow.created_at.desc()).all()
        return [job_to_out(r) for r in rows]
    finally:
        session.close()


def create_application(profile_id: str, job_id: str | None, company: str, role: str, notes: str = "") -> ApplicationOut:
    session = SessionLocal()
    try:
        now = utcnow()
        row = ApplicationRow(
            id=_uid(),
            profile_id=profile_id,
            job_id=job_id,
            company=company,
            role=role,
            status="draft",
            notes=notes,
            created_at=now,
            updated_at=now,
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        return application_to_out(row)
    finally:
        session.close()


def list_applications() -> list[ApplicationOut]:
    session = SessionLocal()
    try:
        rows = session.query(ApplicationRow).order_by(ApplicationRow.updated_at.desc()).all()
        out = []
        for row in rows:
            out.append(application_to_out(row, latest_tailored(session, row.id)))
        return out
    finally:
        session.close()


def get_application(application_id: str) -> ApplicationOut | None:
    session = SessionLocal()
    try:
        row = session.get(ApplicationRow, application_id)
        if not row:
            return None
        return application_to_out(row, latest_tailored(session, row.id))
    finally:
        session.close()


def patch_application(application_id: str, **fields: Any) -> ApplicationOut | None:
    session = SessionLocal()
    try:
        row = session.get(ApplicationRow, application_id)
        if not row:
            return None
        for key, value in fields.items():
            if value is not None and hasattr(row, key):
                setattr(row, key, value)
        row.updated_at = utcnow()
        session.commit()
        session.refresh(row)
        return application_to_out(row, latest_tailored(session, row.id))
    finally:
        session.close()


def delete_application(application_id: str) -> bool:
    session = SessionLocal()
    try:
        row = session.get(ApplicationRow, application_id)
        if not row:
            return False
        session.delete(row)
        session.commit()
        return True
    finally:
        session.close()


def save_tailored(
    application_id: str,
    template: str,
    resume: Resume,
    scores: dict,
    fact_map: dict,
    diff: list,
    pdf_path: str | None,
    docx_path: str | None,
    used_ollama: bool,
    cover_letter: str = "",
    cover_pdf_path: str | None = None,
    cover_docx_path: str | None = None,
    language: str = "en",
    baseline_scores: dict | None = None,
) -> TailoredOut:
    session = SessionLocal()
    try:
        row = TailoredRow(
            id=_uid(),
            application_id=application_id,
            template=template,
            resume_json=resume.model_dump_json(),
            scores_json=json.dumps(scores, ensure_ascii=False),
            fact_map_json=json.dumps(fact_map, ensure_ascii=False),
            diff_json=json.dumps(diff, ensure_ascii=False),
            pdf_path=pdf_path,
            docx_path=docx_path,
            cover_letter=cover_letter,
            cover_pdf_path=cover_pdf_path,
            cover_docx_path=cover_docx_path,
            language=language or "en",
            baseline_scores_json=json.dumps(baseline_scores, ensure_ascii=False) if baseline_scores else "",
            used_ollama="1" if used_ollama else "0",
            created_at=utcnow(),
        )
        session.add(row)
        app = session.get(ApplicationRow, application_id)
        if app:
            app.updated_at = utcnow()
        session.commit()
        session.refresh(row)
        return tailored_to_out(row)
    finally:
        session.close()


def get_settings() -> SettingsOut:
    session = SessionLocal()
    try:
        values = {row.key: row.value for row in session.query(SettingRow).all()}
        url = values.get("ollama_url", "http://127.0.0.1:11434")
        preferred = values.get("ollama_model", "llama3.1")
        # Soft resolve without ping on every settings read (fast)
        model, status = resolve_working_model(url, preferred, verify=False)
        return SettingsOut(
            language=values.get("language", "tr"),  # type: ignore[arg-type]
            ollama_url=url,
            ollama_model=model or preferred,
            default_template=values.get("default_template", "classic"),  # type: ignore[arg-type]
            ollama_available=status.available and bool(model),
        )
    finally:
        session.close()


def get_ollama_status(*, verify: bool = True) -> dict:
    settings = get_settings()
    status = probe_ollama(settings.ollama_url, settings.ollama_model, verify_model=verify)
    return status.as_dict()


def update_settings(patch: dict[str, str]) -> SettingsOut:
    session = SessionLocal()
    try:
        url = None
        preferred = None
        for key, value in patch.items():
            row = session.get(SettingRow, key)
            if row is None:
                session.add(SettingRow(key=key, value=value))
            else:
                row.value = value
            if key == "ollama_url":
                url = value
            if key == "ollama_model":
                preferred = value
        session.flush()
        values = {row.key: row.value for row in session.query(SettingRow).all()}
        url = url or values.get("ollama_url", "http://127.0.0.1:11434")
        preferred = preferred if preferred is not None else values.get("ollama_model", "llama3.1")
        # On save: verify and auto-pick a working installed model
        model, status = resolve_working_model(url, preferred, verify=True)
        if model and model != preferred:
            row = session.get(SettingRow, "ollama_model")
            if row is None:
                session.add(SettingRow(key="ollama_model", value=model))
            else:
                row.value = model
        elif not model and status.models:
            # Prefer listing first available even if ping failed (avoid dead configured name)
            fallback = status.models[0]
            row = session.get(SettingRow, "ollama_model")
            if row is None:
                session.add(SettingRow(key="ollama_model", value=fallback))
            else:
                row.value = fallback
        session.commit()
    finally:
        session.close()
    return get_settings()
