from __future__ import annotations

import io
import json
import re
from pdfminer.high_level import extract_text
from pdfminer.layout import LAParams
from docx import Document

from app.schemas import (
    Basics,
    CertificateItem,
    EducationItem,
    ProjectItem,
    Resume,
    SkillItem,
    WorkItem,
)
from app.services.language import detect_language
from app.services.sanitize import sanitize_resume

EMAIL_RE = re.compile(r"[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}", re.I)
PHONE_RE = re.compile(r"(?:\+\d{1,3}[\s\-]?)?(?:\(?\d{3}\)?[\s\-]?)?\d{3}[\s\-]?\d{2,4}[\s\-]?\d{2,4}")
URL_RE = re.compile(r"https?://[^\s)]+", re.I)
LINKEDIN_RE = re.compile(r"(?:https?://)?(?:www\.)?linkedin\.com/in/[A-Za-z0-9\-_/]+", re.I)

MONTHS = (
    "january|february|march|april|may|june|july|august|september|october|november|december|"
    "jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec|"
    "ocak|şubat|subat|mart|nisan|mayıs|mayis|haziran|temmuz|ağustos|agustos|"
    "eylül|eylul|ekim|kasım|kasim|aralık|aralik|"
    "oca|şub|sub|nis|haz|tem|ağu|agu|eyl|eki|kas|ara"
)
DATE_TOKEN = rf"(?:(?:{MONTHS})[.\s\-]*\d{{4}}|\d{{1,2}}[./\-]\d{{4}}|\d{{4}}(?:[./\-]\d{{1,2}})?)"
RANGE_RE = re.compile(
    rf"({DATE_TOKEN})\s*[-–—]\s*({DATE_TOKEN}|present|current|now|today|günümüz|gunumuz|halen|devam|hala)",
    re.I,
)

SECTION_MAP = {
    "experience": "work",
    "work experience": "work",
    "work history": "work",
    "employment": "work",
    "professional experience": "work",
    "iş deneyimi": "work",
    "is deneyimi": "work",
    "deneyim": "work",
    "çalışma deneyimi": "work",
    "education": "education",
    "eğitim": "education",
    "egitim": "education",
    "academic": "education",
    "skills": "skills",
    "technical skills": "skills",
    "core skills": "skills",
    "yetenekler": "skills",
    "beceriler": "skills",
    "teknik beceriler": "skills",
    "projects": "projects",
    "projeler": "projects",
    "selected projects": "projects",
    "certificates": "certificates",
    "certifications": "certificates",
    "sertifikalar": "certificates",
    "summary": "summary",
    "profile": "summary",
    "professional summary": "summary",
    "özet": "summary",
    "ozet": "summary",
    "profil": "summary",
    "about": "summary",
    "languages": "languages",
    "diller": "languages",
}


def _fold_header(line: str) -> str:
    cleaned = re.sub(r"[^A-Za-zÇĞİÖŞÜçğıöşü ]+", " ", line).strip().lower()
    return re.sub(r"\s+", " ", cleaned)


def _is_section_header(line: str) -> bool:
    return _fold_header(line) in SECTION_MAP and len(line) < 48


def _is_bullet(line: str) -> bool:
    return bool(re.match(r"^([\-•●▪◦*–—]\s*|\d{1,2}[.)]\s+)", line.strip()))


def _strip_bullet(line: str) -> str:
    return re.sub(r"^([\-•●▪◦*–—]+\s*|\d{1,2}[.)]\s+)", "", line.strip())


def extract_plain_text(data: bytes, filename: str) -> str:
    name = filename.lower()
    if name.endswith(".pdf"):
        return (
            extract_text(
                io.BytesIO(data),
                laparams=LAParams(char_margin=2.2, line_margin=0.55, word_margin=0.15, boxes_flow=0.5),
            )
            or ""
        )
    if name.endswith(".docx"):
        document = Document(io.BytesIO(data))
        return "\n".join(p.text for p in document.paragraphs)
    if name.endswith(".json"):
        return data.decode("utf-8", errors="replace")
    return data.decode("utf-8", errors="replace")


def parse_resume_bytes(data: bytes, filename: str) -> Resume:
    name = filename.lower()
    if name.endswith(".json"):
        payload = json.loads(data.decode("utf-8"))
        return sanitize_resume(Resume.model_validate(payload))
    text = extract_plain_text(data, filename)
    return parse_resume_text(text)


def parse_resume_text(text: str) -> Resume:
    text = text.replace("\x00", " ")
    lines = [_clean_line(line) for line in text.splitlines()]
    lines = [line for line in lines if line]
    lines = _reflow_lines(lines)
    sections = _split_sections(lines)

    basics = _parse_basics(sections.get("_preamble", []))
    if "summary" in sections:
        summary_lines = [
            line for line in sections["summary"] if not EMAIL_RE.search(line) and not PHONE_RE.search(line)
        ]
        basics.summary = " ".join(summary_lines).strip()
        if not basics.name:
            recovered = _parse_basics(sections.get("_preamble", []) + summary_lines[:3])
            basics.name = recovered.name
            basics.label = basics.label or recovered.label

    work = _parse_work(sections.get("work", []))
    education = _parse_education(sections.get("education", []))
    skills = _parse_skills(sections.get("skills", []))
    projects = _parse_projects(sections.get("projects", []))
    certificates = _parse_certificates(sections.get("certificates", []))

    if not work and not education:
        work = _parse_work(lines)

    return sanitize_resume(
        Resume(
            basics=basics,
            work=work,
            education=education,
            skills=skills,
            projects=projects,
            certificates=certificates,
            meta={"source": "heuristic", "language": detect_language(text)},
        )
    )


def _clean_line(line: str) -> str:
    return re.sub(r"[ \t]+", " ", line.replace("\u00a0", " ")).strip()


def _reflow_lines(lines: list[str]) -> list[str]:
    """Rebuild lines when a PDF extractor dumped one word per line."""
    out: list[str] = []
    acc = ""

    def flush() -> None:
        nonlocal acc
        if acc.strip():
            out.append(acc.strip())
        acc = ""

    for line in lines:
        stripped = line.strip()
        if _is_section_header(stripped) or RANGE_RE.search(stripped):
            flush()
            out.append(stripped)
            continue
        if _is_bullet(stripped):
            body = _strip_bullet(stripped)
            flush()
            if body:
                out.append(stripped)
            else:
                acc = "• "
            continue
        tokens = stripped.split()
        if EMAIL_RE.search(stripped) or PHONE_RE.search(stripped) or URL_RE.search(stripped):
            flush()
            out.append(stripped)
            continue
        if len(tokens) <= 2:
            if acc.startswith("•") or acc.endswith("•"):
                acc = f"{acc} {stripped}".strip()
            elif acc:
                flush()
                acc = stripped
            else:
                acc = stripped
            continue
        if acc and (acc.endswith("•") or not acc.endswith((".", "!", "?", ":"))):
            acc = f"{acc} {stripped}".strip()
            if acc.endswith((".", "!", "?")) or len(acc.split()) >= 22:
                flush()
            continue
        flush()
        out.append(stripped)
    flush()
    return out


def _split_sections(lines: list[str]) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {"_preamble": []}
    current = "_preamble"
    for line in lines:
        header = _fold_header(line)
        mapped = SECTION_MAP.get(header)
        if mapped and _is_section_header(line):
            current = mapped
            sections.setdefault(current, [])
            continue
        sections.setdefault(current, []).append(line)
    return sections


def _parse_basics(lines: list[str]) -> Basics:
    blob = "\n".join(lines)
    email_match = EMAIL_RE.search(blob)
    phone_match = PHONE_RE.search(blob)
    url_match = LINKEDIN_RE.search(blob) or URL_RE.search(blob)
    name = ""
    label = ""
    for line in lines[:8]:
        if EMAIL_RE.search(line) or PHONE_RE.search(line) or URL_RE.search(line):
            continue
        if _fold_header(line) in SECTION_MAP:
            continue
        if len(line) < 72 and not RANGE_RE.search(line) and not _is_bullet(line):
            if not name and 1 <= len(line.split()) <= 5:
                name = line
            elif not label and line != name and len(line.split()) <= 8:
                label = line
                break
    return Basics(
        name=name,
        label=label,
        email=email_match.group(0) if email_match else "",
        phone=phone_match.group(0) if phone_match else "",
        url=url_match.group(0) if url_match else "",
        summary="",
    )


def _parse_work(lines: list[str]) -> list[WorkItem]:
    items: list[WorkItem] = []
    current: WorkItem | None = None
    buffer: list[str] = []

    def flush_buffer() -> None:
        nonlocal buffer, current
        if current is None:
            buffer = []
            return
        if buffer and not current.name:
            current.name, current.position = _split_org_title(buffer[0])
            if len(buffer) > 1 and not current.position:
                current.position = buffer[1]
        buffer = []

    for line in lines:
        range_match = RANGE_RE.search(line)
        if range_match:
            leftover = RANGE_RE.sub("", line).strip(" |,·-–—")
            start, end = range_match.group(1), range_match.group(2)
            if current is None:
                current = WorkItem(startDate=_normalize_date(start), endDate=_normalize_date(end))
                if leftover:
                    current.name, current.position = _split_org_title(leftover)
                elif buffer:
                    current.name, current.position = _split_org_title(buffer[0])
                    for extra in buffer[1:]:
                        if _is_bullet(extra):
                            body = _strip_bullet(extra)
                            if body:
                                current.highlights.append(body)
                        elif not current.position and len(extra.split()) <= 8 and not extra.endswith("."):
                            current.position = extra
                        else:
                            current.highlights.append(extra)
                buffer = []
                continue
            flush_buffer()
            if current and (current.highlights or current.name or current.startDate):
                items.append(current)
            current = WorkItem(startDate=_normalize_date(start), endDate=_normalize_date(end))
            if leftover:
                current.name, current.position = _split_org_title(leftover)
            continue
        if current is None:
            buffer.append(line)
            continue
        if _is_bullet(line):
            text = _strip_bullet(line)
            if text:
                current.highlights.append(text)
            continue
        if not current.name:
            current.name, current.position = _split_org_title(line)
        elif not current.position and not _is_bullet(line) and len(line.split()) <= 8:
            current.position = line
        elif current.highlights and not current.highlights[-1].endswith((".", "!", "?", ";", ":")):
            current.highlights[-1] = f"{current.highlights[-1]} {line}".strip()
        else:
            current.highlights.append(line)

    flush_buffer()
    if current:
        items.append(current)
    if not items and buffer:
        name, position = _split_org_title(buffer[0])
        items.append(WorkItem(name=name, position=position, highlights=buffer[1:]))
    return [item for item in items if item.name or item.position or item.highlights]


def _split_org_title(line: str) -> tuple[str, str]:
    for sep in ["  ·  ", " · ", " — ", " – ", " - ", " | ", ", "]:
        if sep in line:
            left, right = line.split(sep, 1)
            return left.strip(), right.strip()
    return line.strip(), ""


def _parse_education(lines: list[str]) -> list[EducationItem]:
    items: list[EducationItem] = []
    current = EducationItem()
    for line in lines:
        range_match = RANGE_RE.search(line)
        if range_match:
            if current.institution or current.area:
                items.append(current)
                current = EducationItem()
            current.startDate = _normalize_date(range_match.group(1))
            current.endDate = _normalize_date(range_match.group(2))
            leftover = RANGE_RE.sub("", line).strip(" |,-–—")
            if leftover:
                current.institution = leftover
            continue
        if not current.institution:
            current.institution = line
        elif not current.area:
            parts = [p.strip() for p in re.split(r"[,|–—-]", line) if p.strip()]
            if len(parts) >= 2:
                current.studyType, current.area = parts[0], " ".join(parts[1:])
            else:
                current.area = line
        else:
            current.courses.append(line)
    if current.institution or current.area:
        items.append(current)
    return items


def _parse_skills(lines: list[str]) -> list[SkillItem]:
    items: list[SkillItem] = []
    blob = " ".join(lines)
    if ":" in blob:
        for line in lines:
            if ":" in line:
                name, rest = line.split(":", 1)
                kws = [k.strip() for k in re.split(r"[,;/|]", rest) if k.strip()]
                items.append(SkillItem(name=name.strip(), keywords=kws))
            elif items:
                items[-1].keywords.extend([k.strip() for k in re.split(r"[,;/|]", line) if k.strip()])
        return items
    keywords = [k.strip() for k in re.split(r"[,;/|•]", blob) if k.strip()]
    if keywords:
        items.append(SkillItem(name="Skills", keywords=keywords))
    return items


def _parse_projects(lines: list[str]) -> list[ProjectItem]:
    items: list[ProjectItem] = []
    current = ProjectItem()
    for line in lines:
        if _is_bullet(line) and current.name:
            current.highlights.append(_strip_bullet(line))
            continue
        if current.name:
            items.append(current)
            current = ProjectItem(name=line)
        else:
            current.name = line
    if current.name:
        items.append(current)
    return items


def _parse_certificates(lines: list[str]) -> list[CertificateItem]:
    items: list[CertificateItem] = []
    for line in lines:
        if not line:
            continue
        parts = [p.strip() for p in re.split(r"[,|–—-]", line) if p.strip()]
        items.append(CertificateItem(name=parts[0], issuer=parts[1] if len(parts) > 1 else ""))
    return items


MONTH_NUM = {
    "jan": "01", "january": "01", "oca": "01", "ocak": "01",
    "feb": "02", "february": "02", "şub": "02", "sub": "02", "şubat": "02", "subat": "02",
    "mar": "03", "march": "03", "mart": "03",
    "apr": "04", "april": "04", "nis": "04", "nisan": "04",
    "may": "05", "mayıs": "05", "mayis": "05",
    "jun": "06", "june": "06", "haz": "06", "haziran": "06",
    "jul": "07", "july": "07", "tem": "07", "temmuz": "07",
    "aug": "08", "august": "08", "ağu": "08", "agu": "08", "ağustos": "08", "agustos": "08",
    "sep": "09", "sept": "09", "september": "09", "eyl": "09", "eylül": "09", "eylul": "09",
    "oct": "10", "october": "10", "eki": "10", "ekim": "10",
    "nov": "11", "november": "11", "kas": "11", "kasım": "11", "kasim": "11",
    "dec": "12", "december": "12", "ara": "12", "aralık": "12", "aralik": "12",
}


def _normalize_date(raw: str) -> str:
    text = raw.strip()
    if re.match(r"(present|current|now|today|günümüz|gunumuz|halen|devam|hala)", text, re.I):
        return ""
    year = re.search(r"\d{4}", text)
    if not year:
        return text
    yyyy = year.group(0)
    month = "01"
    folded = text.lower()
    for key, num in MONTH_NUM.items():
        if re.search(rf"\b{key}\b", folded):
            month = num
            break
    else:
        m = re.search(r"(?:^|[./\-])(\d{1,2})[./\-]", text)
        if m and 1 <= int(m.group(1)) <= 12:
            month = f"{int(m.group(1)):02d}"
    return f"{yyyy}-{month}"
