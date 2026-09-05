from __future__ import annotations

from io import BytesIO
from pathlib import Path

from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from app.schemas import Resume, ResumeLanguage, TemplateName
from app.services.ats import headings_for, _fmt_date
from app.services.language import language_upper
from app.services.sanitize import sanitize_resume

NAVY = HexColor("#111827")
BLUE = HexColor("#3B82F6")
GRAY = HexColor("#4B5563")
RULE = HexColor("#D1D5DB")


def _try_register_fonts() -> dict[str, str]:
    candidates = [
        ("/System/Library/Fonts/Supplemental/Arial.ttf", "/System/Library/Fonts/Supplemental/Arial Bold.ttf"),
        ("/Library/Fonts/Arial.ttf", "/Library/Fonts/Arial Bold.ttf"),
        ("/System/Library/Fonts/Helvetica.ttc", "/System/Library/Fonts/Helvetica.ttc"),
    ]
    for regular, bold in candidates:
        if Path(regular).exists():
            try:
                pdfmetrics.registerFont(TTFont("CVE-Reg", regular))
                if Path(bold).exists() and bold != regular:
                    pdfmetrics.registerFont(TTFont("CVE-Bold", bold))
                else:
                    pdfmetrics.registerFont(TTFont("CVE-Bold", regular))
                return {"reg": "CVE-Reg", "bold": "CVE-Bold"}
            except Exception:
                continue
    return {"reg": "Helvetica", "bold": "Helvetica-Bold"}


FONTS = _try_register_fonts()


class _TemplateSpec:
    def __init__(self, name: TemplateName):
        self.name = name
        if name == "executive":
            self.margin = 22 * mm
            self.name_size = 22
            self.section_size = 11
            self.body_size = 10
            self.leading = 13
            self.gap = 10
        elif name == "compact":
            self.margin = 14 * mm
            self.name_size = 16
            self.section_size = 9.5
            self.body_size = 9
            self.leading = 11
            self.gap = 6
        else:
            self.margin = 18 * mm
            self.name_size = 18
            self.section_size = 10.5
            self.body_size = 10
            self.leading = 12.5
            self.gap = 8


def build_pdf(resume: Resume, template: TemplateName = "classic", language: ResumeLanguage = "en") -> bytes:
    resume = sanitize_resume(resume)
    spec = _TemplateSpec(template)
    buffer = BytesIO()
    page = letter
    c = canvas.Canvas(buffer, pagesize=page)
    width, height = page
    x0, y = spec.margin, height - spec.margin
    max_width = width - 2 * spec.margin

    def newline(amount: float | None = None) -> None:
        nonlocal y
        y -= amount if amount is not None else spec.leading
        if y < spec.margin + 24:
            c.showPage()
            y = height - spec.margin
            c.setFillColor(NAVY)

    def draw_wrapped(text: str, font: str, size: float, color=NAVY, indent: float = 0) -> None:
        nonlocal y
        if not text:
            return
        c.setFont(font, size)
        c.setFillColor(color)
        words = text.split()
        line = ""
        usable = max_width - indent
        for word in words:
            trial = (line + " " + word).strip()
            if c.stringWidth(trial, font, size) <= usable:
                line = trial
            else:
                c.drawString(x0 + indent, y, line)
                newline()
                c.setFont(font, size)
                line = word
        if line:
            c.drawString(x0 + indent, y, line)
            newline()

    def section(title: str) -> None:
        newline(spec.gap)
        c.setFont(FONTS["bold"], spec.section_size)
        c.setFillColor(NAVY)
        c.drawString(x0, y, language_upper(title, language))
        newline(spec.leading * 0.45)
        c.setStrokeColor(RULE if template != "executive" else BLUE)
        c.setLineWidth(0.8 if template != "executive" else 1.2)
        c.line(x0, y, x0 + max_width, y)
        newline(spec.leading * 0.7)

    h = headings_for(language)
    b = resume.basics
    c.setFillColor(NAVY)
    c.setFont(FONTS["bold"], spec.name_size)
    c.drawString(x0, y, b.name or " ")
    newline(spec.name_size * 0.7)
    if b.label:
        c.setFont(FONTS["reg"], spec.body_size + 1)
        c.setFillColor(GRAY if template != "executive" else BLUE)
        c.drawString(x0, y, b.label)
        newline()
    contact = "  ·  ".join(p for p in [b.email, b.phone, b.url, b.location.city] if p)
    draw_wrapped(contact, FONTS["reg"], spec.body_size - 0.5, GRAY)

    if b.summary:
        section(h["summary"])
        draw_wrapped(b.summary, FONTS["reg"], spec.body_size, NAVY)

    if resume.work:
        section(h["experience"])
        for work in resume.work:
            dates = " – ".join(
                p
                for p in [
                    _fmt_date(work.startDate, language),
                    _fmt_date(work.endDate, language) or ("Present" if language == "en" and work.startDate else ("Günümüz" if work.startDate else "")),
                ]
                if p
            )
            heading = "  ·  ".join(p for p in [work.position, work.name, dates] if p)
            draw_wrapped(heading, FONTS["bold"], spec.body_size, NAVY)
            for item in work.highlights:
                c.setFillColor(NAVY)
                c.setFont(FONTS["reg"], spec.body_size)
                c.drawString(x0, y, "•")
                draw_wrapped(item, FONTS["reg"], spec.body_size, NAVY, indent=12)

    if resume.education:
        section(h["education"])
        for edu in resume.education:
            left = "  ·  ".join(p for p in [edu.studyType, edu.area, edu.institution] if p)
            dates = " – ".join(p for p in [_fmt_date(edu.startDate, language), _fmt_date(edu.endDate, language)] if p)
            draw_wrapped("  ·  ".join(p for p in [left, dates] if p), FONTS["bold"], spec.body_size, NAVY)

    if resume.skills:
        section(h["skills"])
        for skill in resume.skills:
            label = f"{skill.name}: " if skill.name else ""
            draw_wrapped(label + ", ".join(skill.keywords), FONTS["reg"], spec.body_size, NAVY)

    if resume.projects:
        section(h["projects"])
        for project in resume.projects:
            c.setFont(FONTS["bold"], spec.body_size)
            c.setFillColor(NAVY)
            c.drawString(x0, y, project.name)
            newline()
            if project.description:
                draw_wrapped(project.description, FONTS["reg"], spec.body_size, NAVY)
            for item in project.highlights:
                c.drawString(x0, y, "•")
                draw_wrapped(item, FONTS["reg"], spec.body_size, NAVY, indent=12)

    if resume.certificates:
        section(h["certificates"])
        for cert in resume.certificates:
            draw_wrapped("  ·  ".join(p for p in [cert.name, cert.issuer] if p), FONTS["reg"], spec.body_size, NAVY)

    c.save()
    return buffer.getvalue()


def write_pdf(path: Path, resume: Resume, template: TemplateName = "classic", language: ResumeLanguage = "en") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(build_pdf(resume, template, language))
    return path
