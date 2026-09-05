from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import ForeignKey, String, Text, create_engine, inspect, text as sql_text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker

from app.config import db_path


class Base(DeclarativeBase):
    pass


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class ProfileRow(Base):
    __tablename__ = "profiles"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    resume_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(String)
    updated_at: Mapped[str] = mapped_column(String)
    facts: Mapped[list[CareerFactRow]] = relationship(back_populates="profile", cascade="all, delete-orphan")


class CareerFactRow(Base):
    __tablename__ = "career_facts"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    profile_id: Mapped[str] = mapped_column(ForeignKey("profiles.id", ondelete="CASCADE"))
    fact_type: Mapped[str] = mapped_column(String)
    value: Mapped[str] = mapped_column(Text)
    source_path: Mapped[str] = mapped_column(String)
    extra_json: Mapped[str] = mapped_column(Text, default="{}")
    profile: Mapped[ProfileRow] = relationship(back_populates="facts")


class JobRow(Base):
    __tablename__ = "jobs"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    title: Mapped[str] = mapped_column(String, default="")
    company: Mapped[str] = mapped_column(String, default="")
    raw_text: Mapped[str] = mapped_column(Text)
    analysis_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[str] = mapped_column(String)


class ApplicationRow(Base):
    __tablename__ = "applications"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    profile_id: Mapped[str] = mapped_column(ForeignKey("profiles.id", ondelete="CASCADE"))
    job_id: Mapped[Optional[str]] = mapped_column(ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True)
    company: Mapped[str] = mapped_column(String, default="")
    role: Mapped[str] = mapped_column(String, default="")
    status: Mapped[str] = mapped_column(String, default="draft")
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[str] = mapped_column(String)
    updated_at: Mapped[str] = mapped_column(String)
    tailored: Mapped[list[TailoredRow]] = relationship(back_populates="application", cascade="all, delete-orphan")


class TailoredRow(Base):
    __tablename__ = "tailored_resumes"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    application_id: Mapped[str] = mapped_column(ForeignKey("applications.id", ondelete="CASCADE"))
    template: Mapped[str] = mapped_column(String, default="classic")
    resume_json: Mapped[str] = mapped_column(Text)
    scores_json: Mapped[str] = mapped_column(Text, default="{}")
    fact_map_json: Mapped[str] = mapped_column(Text, default="{}")
    diff_json: Mapped[str] = mapped_column(Text, default="[]")
    pdf_path: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    docx_path: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    cover_letter: Mapped[str] = mapped_column(Text, default="")
    cover_pdf_path: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    cover_docx_path: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    language: Mapped[str] = mapped_column(String, default="en")
    baseline_scores_json: Mapped[str] = mapped_column(Text, default="")
    used_ollama: Mapped[str] = mapped_column(String, default="0")
    created_at: Mapped[str] = mapped_column(String)
    application: Mapped[ApplicationRow] = relationship(back_populates="tailored")


class SettingRow(Base):
    __tablename__ = "settings"
    key: Mapped[str] = mapped_column(String, primary_key=True)
    value: Mapped[str] = mapped_column(Text)


_engine = None
_SessionLocal = None


def get_engine():
    global _engine, _SessionLocal
    if _engine is None:
        _engine = create_engine(f"sqlite:///{db_path()}", echo=False, future=True)
        _SessionLocal = sessionmaker(bind=_engine, autoflush=False, autocommit=False)
        Base.metadata.create_all(_engine)
        _migrate_schema(_engine)
        _seed_settings()
    return _engine


def _migrate_schema(engine) -> None:
    inspector = inspect(engine)
    if "tailored_resumes" not in inspector.get_table_names():
        return
    cols = {c["name"] for c in inspector.get_columns("tailored_resumes")}
    statements: list[str] = []
    if "cover_letter" not in cols:
        statements.append("ALTER TABLE tailored_resumes ADD COLUMN cover_letter TEXT DEFAULT ''")
    if "cover_pdf_path" not in cols:
        statements.append("ALTER TABLE tailored_resumes ADD COLUMN cover_pdf_path VARCHAR")
    if "cover_docx_path" not in cols:
        statements.append("ALTER TABLE tailored_resumes ADD COLUMN cover_docx_path VARCHAR")
    if "language" not in cols:
        statements.append("ALTER TABLE tailored_resumes ADD COLUMN language VARCHAR DEFAULT 'en'")
    if "baseline_scores_json" not in cols:
        statements.append("ALTER TABLE tailored_resumes ADD COLUMN baseline_scores_json TEXT DEFAULT ''")
    if not statements:
        return
    with engine.begin() as conn:
        for statement in statements:
            conn.execute(sql_text(statement))


def _seed_settings() -> None:
    from app.config import OLLAMA_DEFAULT

    session = SessionLocal()
    defaults = {
        "language": "tr",
        "ollama_url": OLLAMA_DEFAULT,
        "ollama_model": "llama3.1",
        "default_template": "classic",
    }
    try:
        for key, value in defaults.items():
            if session.get(SettingRow, key) is None:
                session.add(SettingRow(key=key, value=value))
        session.commit()
    finally:
        session.close()


def SessionLocal():
    get_engine()
    assert _SessionLocal is not None
    return _SessionLocal()


def reset_engine() -> None:
    global _engine, _SessionLocal
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _SessionLocal = None
