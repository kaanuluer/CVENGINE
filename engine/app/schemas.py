from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from app.config import OLLAMA_DEFAULT


class Location(BaseModel):
    address: str = ""
    postalCode: str = ""
    city: str = ""
    countryCode: str = ""
    region: str = ""


class ProfileLink(BaseModel):
    network: str = ""
    username: str = ""
    url: str = ""


class Basics(BaseModel):
    name: str = ""
    label: str = ""
    image: str = ""
    email: str = ""
    phone: str = ""
    url: str = ""
    summary: str = ""
    location: Location = Field(default_factory=Location)
    profiles: list[ProfileLink] = Field(default_factory=list)


class WorkItem(BaseModel):
    name: str = ""
    position: str = ""
    url: str = ""
    startDate: str = ""
    endDate: str = ""
    summary: str = ""
    highlights: list[str] = Field(default_factory=list)
    location: str = ""


class EducationItem(BaseModel):
    institution: str = ""
    url: str = ""
    area: str = ""
    studyType: str = ""
    startDate: str = ""
    endDate: str = ""
    score: str = ""
    courses: list[str] = Field(default_factory=list)


class SkillItem(BaseModel):
    name: str = ""
    level: str = ""
    keywords: list[str] = Field(default_factory=list)


class ProjectItem(BaseModel):
    name: str = ""
    startDate: str = ""
    endDate: str = ""
    description: str = ""
    highlights: list[str] = Field(default_factory=list)
    url: str = ""
    keywords: list[str] = Field(default_factory=list)


class CertificateItem(BaseModel):
    name: str = ""
    date: str = ""
    issuer: str = ""
    url: str = ""


class LanguageItem(BaseModel):
    language: str = ""
    fluency: str = ""


class AwardItem(BaseModel):
    title: str = ""
    date: str = ""
    awarder: str = ""
    summary: str = ""


class Resume(BaseModel):
    schema_url: str | None = Field(default=None, alias="$schema")
    basics: Basics = Field(default_factory=Basics)
    work: list[WorkItem] = Field(default_factory=list)
    volunteer: list[WorkItem] = Field(default_factory=list)
    education: list[EducationItem] = Field(default_factory=list)
    awards: list[AwardItem] = Field(default_factory=list)
    certificates: list[CertificateItem] = Field(default_factory=list)
    publications: list[dict[str, Any]] = Field(default_factory=list)
    skills: list[SkillItem] = Field(default_factory=list)
    languages: list[LanguageItem] = Field(default_factory=list)
    interests: list[dict[str, Any]] = Field(default_factory=list)
    references: list[dict[str, Any]] = Field(default_factory=list)
    projects: list[ProjectItem] = Field(default_factory=list)
    meta: dict[str, Any] = Field(default_factory=dict)

    model_config = {"populate_by_name": True}


TemplateName = Literal["classic", "executive", "compact"]
AppStatus = Literal["draft", "applied", "interview", "offer", "rejected"]
ResumeLanguage = Literal["en", "tr"]


class Fact(BaseModel):
    id: str
    type: str
    value: str
    source_path: str
    extra: dict[str, Any] = Field(default_factory=dict)


class JobAnalysis(BaseModel):
    language: ResumeLanguage = "en"
    title: str = ""
    company: str = ""
    seniority: str = ""
    keywords: list[str] = Field(default_factory=list)
    required_skills: list[str] = Field(default_factory=list)
    preferred_skills: list[str] = Field(default_factory=list)
    surface_forms: dict[str, str] = Field(default_factory=dict)


class GapItem(BaseModel):
    skill: str
    in_resume: bool
    weight: Literal["required", "preferred"] = "required"


class MatchResult(BaseModel):
    overall: float
    keyword_coverage: float
    semantic: float
    gaps: list[GapItem] = Field(default_factory=list)
    highlight_scores: dict[str, float] = Field(default_factory=dict)


class GateIssue(BaseModel):
    code: str
    message: str
    severity: Literal["block", "warn"] = "warn"


class ScoreBlock(BaseModel):
    parse: float
    keyword: float
    semantic: float
    evidence: float
    groundedness: float
    consistency: float = 100.0
    overall: float
    ats: float = 0
    passed: bool
    issues: list[GateIssue] = Field(default_factory=list)


class DiffChange(BaseModel):
    path: str
    kind: Literal["added", "removed", "changed", "moved"]
    before: str | None = None
    after: str | None = None


class TailorResult(BaseModel):
    resume: Resume
    analysis: JobAnalysis
    match: MatchResult
    scores: ScoreBlock
    diff: list[DiffChange] = Field(default_factory=list)
    fact_map: dict[str, list[str]] = Field(default_factory=dict)
    template: TemplateName = "classic"
    used_ollama: bool = False
    ollama_rolled_back: bool = False
    language: ResumeLanguage = "en"
    cover_letter: str = ""
    cover_used_ollama: bool = False
    baseline_scores: ScoreBlock | None = None


class ProfileIn(BaseModel):
    name: str
    resume: Resume


class ProfileOut(BaseModel):
    id: str
    name: str
    resume: Resume
    created_at: str
    updated_at: str


class JobIn(BaseModel):
    raw_text: str
    company: str = ""
    title: str = ""


class JobOut(BaseModel):
    id: str
    title: str
    company: str
    raw_text: str
    analysis: JobAnalysis
    created_at: str


class ApplicationIn(BaseModel):
    profile_id: str
    job_id: str | None = None
    company: str = ""
    role: str = ""
    status: AppStatus = "draft"
    notes: str = ""


class ApplicationPatch(BaseModel):
    status: AppStatus | None = None
    notes: str | None = None
    company: str | None = None
    role: str | None = None


class TailoredOut(BaseModel):
    id: str
    application_id: str
    template: TemplateName
    resume: Resume
    scores: ScoreBlock
    fact_map: dict[str, list[str]]
    diff: list[DiffChange] = Field(default_factory=list)
    pdf_path: str | None = None
    docx_path: str | None = None
    cover_letter: str = ""
    cover_pdf_path: str | None = None
    cover_docx_path: str | None = None
    language: ResumeLanguage = "en"
    used_ollama: bool = False
    created_at: str
    baseline_scores: ScoreBlock | None = None


class ApplicationOut(BaseModel):
    id: str
    profile_id: str
    job_id: str | None
    company: str
    role: str
    status: AppStatus
    notes: str
    created_at: str
    updated_at: str
    latest: TailoredOut | None = None
    keyword_score: float | None = None
    overall_score: float | None = None
    baseline_ats: float | None = None
    tailored_ats: float | None = None


class RunRequest(BaseModel):
    profile_id: str
    job_text: str
    company: str = ""
    role: str = ""
    template: TemplateName = "classic"
    use_ollama: bool = False
    save: bool = True


class RunResponse(BaseModel):
    application: ApplicationOut
    job: JobOut
    result: TailorResult
    tailored: TailoredOut | None = None


class SettingsOut(BaseModel):
    language: ResumeLanguage = "tr"
    ollama_url: str = OLLAMA_DEFAULT
    ollama_model: str = "llama3.1"
    default_template: TemplateName = "classic"
    ollama_available: bool = False


class SettingsIn(BaseModel):
    language: ResumeLanguage | None = None
    ollama_url: str | None = None
    ollama_model: str | None = None
    default_template: TemplateName | None = None


class ExportRequest(BaseModel):
    resume: Resume
    template: TemplateName = "classic"
    format: Literal["pdf", "docx"] = "pdf"
    language: ResumeLanguage = "en"


class CoverExportRequest(BaseModel):
    text: str
    format: Literal["pdf", "docx"] = "pdf"


class AnalyzeRequest(BaseModel):
    profile_id: str | None = None
    resume: Resume | None = None
    job_text: str
