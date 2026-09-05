from __future__ import annotations

from pathlib import Path

from contextlib import asynccontextmanager

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response

from app.config import API_HOST, API_PORT, exports_dir
from app.database import get_engine
from app.schemas import (
    AnalyzeRequest,
    ApplicationIn,
    ApplicationPatch,
    CoverExportRequest,
    ExportRequest,
    JobIn,
    ProfileIn,
    Resume,
    RunRequest,
    RunResponse,
    SettingsIn,
    TemplateName,
)
from app.services.export_cover import build_cover_docx, build_cover_pdf, write_cover_docx, write_cover_pdf
from app.services.export_docx import build_docx, write_docx
from app.services.export_pdf import build_pdf, write_pdf
from app.services.jd import analyze_jd
from app.services.match import match_resume
from app.services.parser import parse_resume_bytes
from app.services.pipeline import run_pipeline
from app import store

@asynccontextmanager
async def lifespan(_app: FastAPI):
    get_engine()
    yield


app = FastAPI(title="CVENGINE", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "tauri://localhost", "http://tauri.localhost"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict:
    settings = store.get_settings()
    return {"ok": True, "ollama": settings.ollama_available, "version": "0.1.0"}


@app.get("/api/templates")
def templates() -> list[dict]:
    return [
        {"id": "classic", "name": "Classic ATS", "description": "Calibri/Helvetica, maksimum parse güvenliği"},
        {"id": "executive", "name": "Executive", "description": "Daha geniş boşluk, isim vurgusu, tek sütun"},
        {"id": "compact", "name": "Compact", "description": "Tek sayfa yoğunluğu, hâlâ ATS-güvenli"},
    ]


@app.get("/api/settings")
def get_settings():
    return store.get_settings()


@app.put("/api/settings")
def put_settings(body: SettingsIn):
    patch = {k: v for k, v in body.model_dump().items() if v is not None}
    return store.update_settings(patch)


@app.get("/api/profiles")
def list_profiles():
    return store.list_profiles()


@app.post("/api/profiles")
def create_profile(body: ProfileIn):
    return store.create_profile(body.name, body.resume)


@app.get("/api/profiles/{profile_id}")
def get_profile(profile_id: str):
    row = store.get_profile(profile_id)
    if not row:
        raise HTTPException(404, "Profil bulunamadı")
    return row


@app.put("/api/profiles/{profile_id}")
def update_profile(profile_id: str, body: ProfileIn):
    row = store.update_profile(profile_id, body.name, body.resume)
    if not row:
        raise HTTPException(404, "Profil bulunamadı")
    return row


@app.delete("/api/profiles/{profile_id}")
def delete_profile(profile_id: str):
    if not store.delete_profile(profile_id):
        raise HTTPException(404, "Profil bulunamadı")
    return {"ok": True}


@app.post("/api/profiles/parse")
async def parse_profile(file: UploadFile = File(...), name: str | None = None):
    data = await file.read()
    try:
        resume = parse_resume_bytes(data, file.filename or "resume.txt")
    except Exception as exc:
        raise HTTPException(400, f"Dosya okunamadı: {exc}") from exc
    display = name or (resume.basics.name or file.filename or "Master CV")
    return store.create_profile(display, resume)


@app.get("/api/jobs")
def list_jobs():
    return store.list_jobs()


@app.post("/api/jobs")
def create_job(body: JobIn):
    analysis = analyze_jd(body.raw_text, company=body.company, title=body.title)
    return store.create_job(body.raw_text, analysis, body.company, body.title)


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    row = store.get_job(job_id)
    if not row:
        raise HTTPException(404, "İlan bulunamadı")
    return row


@app.post("/api/analyze")
def analyze(body: AnalyzeRequest):
    resume: Resume | None = body.resume
    if body.profile_id:
        profile = store.get_profile(body.profile_id)
        if not profile:
            raise HTTPException(404, "Profil bulunamadı")
        resume = profile.resume
    if resume is None:
        raise HTTPException(400, "profile_id veya resume gerekli")
    analysis = analyze_jd(body.job_text)
    match = match_resume(resume, analysis)
    return {"analysis": analysis, "match": match}


@app.get("/api/applications")
def list_applications():
    return store.list_applications()


@app.post("/api/applications")
def create_application(body: ApplicationIn):
    return store.create_application(body.profile_id, body.job_id, body.company, body.role, body.notes)


@app.get("/api/applications/{application_id}")
def get_application(application_id: str):
    row = store.get_application(application_id)
    if not row:
        raise HTTPException(404, "Başvuru bulunamadı")
    return row


@app.patch("/api/applications/{application_id}")
def patch_application(application_id: str, body: ApplicationPatch):
    row = store.patch_application(application_id, **body.model_dump())
    if not row:
        raise HTTPException(404, "Başvuru bulunamadı")
    return row


@app.delete("/api/applications/{application_id}")
def delete_application(application_id: str):
    if not store.delete_application(application_id):
        raise HTTPException(404, "Başvuru bulunamadı")
    return {"ok": True}


@app.post("/api/applications/run", response_model=RunResponse)
def run_application(body: RunRequest):
    profile = store.get_profile(body.profile_id)
    if not profile:
        raise HTTPException(404, "Profil bulunamadı")
    settings = store.get_settings()
    result = run_pipeline(
        profile.resume,
        body.job_text,
        template=body.template,
        company=body.company,
        role=body.role,
        use_ollama=body.use_ollama,
        ollama_url=settings.ollama_url,
        ollama_model=settings.ollama_model,
        roundtrip=True,
    )
    job = store.create_job(
        body.job_text,
        result.analysis,
        body.company or result.analysis.company,
        body.role or result.analysis.title,
    )
    application = store.create_application(
        body.profile_id,
        job.id,
        job.company,
        job.title,
    )
    tailored = None
    if body.save:
        pdf_path = None
        docx_path = None
        cover_pdf_path = None
        cover_docx_path = None
        if result.scores.passed or True:
            stem = f"{application.id}_{body.template}"
            pdf_path = str(exports_dir() / f"{stem}.pdf")
            docx_path = str(exports_dir() / f"{stem}.docx")
            write_pdf(Path(pdf_path), result.resume, body.template, result.language)
            write_docx(Path(docx_path), result.resume, body.template, result.language)
            cover_pdf_path, cover_docx_path = _write_cover_files(stem, result.cover_letter)
        tailored = store.save_tailored(
            application.id,
            body.template,
            result.resume,
            result.scores.model_dump(),
            result.fact_map,
            [d.model_dump() for d in result.diff],
            pdf_path,
            docx_path,
            result.used_ollama,
            result.cover_letter,
            cover_pdf_path,
            cover_docx_path,
            result.language,
            result.baseline_scores.model_dump() if result.baseline_scores else None,
        )
        application = store.get_application(application.id) or application
    return RunResponse(application=application, job=job, result=result, tailored=tailored)


@app.post("/api/applications/{application_id}/retarget")
def retarget(application_id: str, template: TemplateName = "classic", use_ollama: bool = False):
    application = store.get_application(application_id)
    if not application or not application.job_id:
        raise HTTPException(404, "Başvuru veya ilan bulunamadı")
    profile = store.get_profile(application.profile_id)
    job = store.get_job(application.job_id)
    if not profile or not job:
        raise HTTPException(404, "Profil veya ilan bulunamadı")
    settings = store.get_settings()
    result = run_pipeline(
        profile.resume,
        job.raw_text,
        template=template,
        company=application.company,
        role=application.role,
        use_ollama=use_ollama,
        ollama_url=settings.ollama_url,
        ollama_model=settings.ollama_model,
    )
    stem = f"{application.id}_{template}"
    pdf_path = str(exports_dir() / f"{stem}.pdf")
    docx_path = str(exports_dir() / f"{stem}.docx")
    write_pdf(Path(pdf_path), result.resume, template, result.language)
    write_docx(Path(docx_path), result.resume, template, result.language)
    cover_pdf_path, cover_docx_path = _write_cover_files(stem, result.cover_letter)
    tailored = store.save_tailored(
        application.id,
        template,
        result.resume,
        result.scores.model_dump(),
        result.fact_map,
        [d.model_dump() for d in result.diff],
        pdf_path,
        docx_path,
        result.used_ollama,
        result.cover_letter,
        cover_pdf_path,
        cover_docx_path,
        result.language,
        result.baseline_scores.model_dump() if result.baseline_scores else None,
    )
    application = store.get_application(application_id)
    return {"application": application, "result": result, "tailored": tailored}


@app.post("/api/export")
def export_resume(body: ExportRequest):
    filename = f"resume.{body.format}"
    if body.format == "pdf":
        data = build_pdf(body.resume, body.template, body.language)
        return Response(
            content=data,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    data = build_docx(body.resume, body.template, body.language)
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.post("/api/export/cover")
def export_cover(body: CoverExportRequest):
    if not body.text.strip():
        raise HTTPException(400, "Ön yazı boş")
    filename = f"cover-letter.{body.format}"
    if body.format == "pdf":
        return Response(
            content=build_cover_pdf(body.text),
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    return Response(
        content=build_cover_docx(body.text),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/api/files")
def download_file(path: str):
    file_path = Path(path).expanduser().resolve()
    allowed = exports_dir().resolve()
    if allowed not in file_path.parents and file_path.parent != allowed:
        raise HTTPException(403, "Yalnızca export klasörü")
    if not file_path.exists():
        raise HTTPException(404, "Dosya yok")
    media = "application/pdf" if file_path.suffix == ".pdf" else "application/octet-stream"
    return FileResponse(file_path, media_type=media, filename=file_path.name)


def _write_cover_files(stem: str, letter: str) -> tuple[str | None, str | None]:
    if not letter.strip():
        return None, None
    pdf_path = str(exports_dir() / f"{stem}_cover.pdf")
    docx_path = str(exports_dir() / f"{stem}_cover.docx")
    write_cover_pdf(Path(pdf_path), letter)
    write_cover_docx(Path(docx_path), letter)
    return pdf_path, docx_path


def run() -> None:
    import uvicorn

    uvicorn.run("app.main:app", host=API_HOST, port=API_PORT, reload=False)


if __name__ == "__main__":
    run()
