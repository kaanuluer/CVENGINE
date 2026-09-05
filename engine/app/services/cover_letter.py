from __future__ import annotations

import re
from datetime import datetime

import httpx
from rapidfuzz import fuzz

from app.schemas import JobAnalysis, MatchResult, Resume, ResumeLanguage
from app.services.language import language_capitalize
from app.services.match import highlight_entries
from app.services.ollama import ollama_available

SLOP = {
    "leverage", "passionate", "delve", "synergy", "cutting-edge",
    "results-driven", "excited to", "thrilled", "perfect fit",
    "game-changer", "rockstar", "ninja", "guru",
}


def build_cover_letter(
    resume: Resume,
    analysis: JobAnalysis,
    match: MatchResult | None = None,
    company: str = "",
    role: str = "",
    *,
    ollama_url: str = "",
    ollama_model: str = "llama3.1",
    prefer_ollama: bool = True,
) -> tuple[str, bool]:
    """Return (letter, used_ollama). Ollama is preferred whenever the daemon is up."""
    language: ResumeLanguage = analysis.language
    company = (company or analysis.company or "").strip()
    role = (role or analysis.title or resume.basics.label or "").strip()
    evidence = _evidence_lines(resume, match, language)
    skills = _overlap_skills(resume, analysis)
    years = _years(resume)
    name = resume.basics.name.strip() or ("Aday" if language == "tr" else "Applicant")
    city = (resume.basics.location.city or "").strip()

    if language == "tr":
        draft = _letter_tr(name, city, company, role, years, evidence, skills)
    else:
        draft = _letter_en(name, city, company, role, years, evidence, skills)
    draft = draft.strip() + "\n"

    if prefer_ollama and ollama_url and ollama_available(ollama_url):
        polished = generate_cover_letter_with_ollama(
            draft,
            resume,
            analysis,
            company=company,
            role=role,
            evidence=evidence,
            skills=skills,
            years=years,
            base_url=ollama_url,
            model=ollama_model,
        )
        if polished:
            return polished, True
    return draft, False


def generate_cover_letter_with_ollama(
    draft: str,
    resume: Resume,
    analysis: JobAnalysis,
    *,
    company: str,
    role: str,
    evidence: list[str],
    skills: list[str],
    years: int | None,
    base_url: str,
    model: str,
) -> str | None:
    language = analysis.language
    lang_name = "Turkish" if language == "tr" else "English"
    facts = {
        "candidate_name": resume.basics.name,
        "city": resume.basics.location.city or "",
        "current_label": resume.basics.label or "",
        "company": company,
        "role": role,
        "years": years,
        "evidence_bullets": evidence,
        "overlapping_skills": skills,
        "language": language,
    }
    prompt = (
        f"Write a polished professional cover letter in {lang_name}.\n"
        "Use ONLY the facts below. Do not invent employers, tools, metrics, titles, or achievements.\n"
        "Connect the evidence to the job in clear, specific prose — not a bullet dump.\n"
        "Avoid cliches: leverage, passionate, delve, synergy, cutting-edge, results-driven, "
        "excited, thrilled, perfect fit, game-changer, rockstar, ninja, guru.\n"
        "Keep greeting, body paragraphs, and sign-off. Return only the letter text.\n\n"
        f"FACTS (JSON-like):\n{facts!r}\n\n"
        f"DRAFT TO IMPROVE:\n{draft}\n"
    )
    try:
        response = httpx.post(
            base_url.rstrip("/") + "/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.4, "num_predict": 900},
            },
            timeout=90.0,
        )
        response.raise_for_status()
        polished = (response.json().get("response") or "").strip()
    except Exception:
        return None
    polished = _strip_fences(polished)
    if not polished or len(polished) < 120:
        return None
    if not _letter_grounded(polished, resume, original=draft, company=company, role=role):
        # One repair pass: ask model to stick closer to draft facts
        repaired = _repair_cover_letter(polished, draft, base_url, model, lang_name)
        if repaired and _letter_grounded(repaired, resume, original=draft, company=company, role=role):
            polished = repaired
        else:
            return None
    lowered = polished.lower()
    if any(word in lowered for word in SLOP):
        return None
    if resume.basics.name and resume.basics.name.split()[0].lower() not in polished.lower():
        # Ensure name still appears (header or sign-off)
        polished = f"{resume.basics.name}\n\n{polished}"
        if not polished.rstrip().endswith(resume.basics.name):
            sign = "Saygılarımla," if language == "tr" else "Sincerely,"
            polished = polished.rstrip() + f"\n\n{sign}\n{resume.basics.name}"
    return polished + ("\n" if not polished.endswith("\n") else "")


def _repair_cover_letter(bad: str, draft: str, base_url: str, model: str, lang_name: str) -> str | None:
    prompt = (
        f"Rewrite the cover letter in {lang_name}. Keep every fact from the DRAFT. "
        "Do not add new employers, tools, or metrics. Return only the letter.\n\n"
        f"DRAFT:\n{draft}\n\nBAD DRAFT:\n{bad}\n"
    )
    try:
        response = httpx.post(
            base_url.rstrip("/") + "/api/generate",
            json={"model": model, "prompt": prompt, "stream": False, "options": {"temperature": 0.2}},
            timeout=60.0,
        )
        response.raise_for_status()
        text = _strip_fences((response.json().get("response") or "").strip())
    except Exception:
        return None
    return text if text and len(text) >= 120 else None


def _strip_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:\w+)?\n?", "", text)
        text = re.sub(r"\n?```$", "", text)
    return text.strip()


def _evidence_lines(resume: Resume, match: MatchResult | None, language: ResumeLanguage) -> list[str]:
    scored: list[tuple[float, str]] = []
    if match and match.highlight_scores:
        lookup = {path: text for path, text in highlight_entries(resume)}
        for path, score in match.highlight_scores.items():
            text = lookup.get(path)
            if text:
                scored.append((score, text))
        scored.sort(key=lambda item: -item[0])
    if not scored:
        for work in resume.work:
            for highlight in work.highlights:
                scored.append((0, highlight))
    unique: list[str] = []
    seen: set[str] = set()
    for _, text in scored:
        key = text.lower()
        if key in seen or len(text) < 24:
            continue
        seen.add(key)
        unique.append(_as_sentence(text, language))
        if len(unique) == 3:
            break
    return unique


def _as_sentence(text: str, language: ResumeLanguage = "en") -> str:
    text = text.strip().rstrip(".")
    if text:
        text = language_capitalize(text, language)
    return text + "."


def _overlap_skills(resume: Resume, analysis: JobAnalysis) -> list[str]:
    owned = {kw.lower() for group in resume.skills for kw in group.keywords}
    owned.update(h.lower() for work in resume.work for h in work.highlights)
    picked: list[str] = []
    for skill in analysis.required_skills + analysis.preferred_skills:
        if skill.lower() in owned or any(skill.lower() in blob for blob in owned):
            surface = analysis.surface_forms.get(skill, skill)
            if surface not in picked:
                picked.append(surface)
        if len(picked) >= 6:
            break
    if not picked:
        picked = [kw for group in resume.skills for kw in group.keywords][:6]
    return picked


def _years(resume: Resume) -> int | None:
    years = []
    for work in resume.work:
        if work.startDate[:4].isdigit():
            years.append(int(work.startDate[:4]))
    if not years:
        return None
    return max(1, datetime.now().year - min(years))


def _letter_en(name: str, city: str, company: str, role: str, years: int | None, evidence: list[str], skills: list[str]) -> str:
    target = f"the {role} role" if role else "this role"
    at = f" at {company}" if company else ""
    greeting = f"Dear {company} Hiring Team," if company else "Dear Hiring Manager,"
    exp = f" with {years}+ years of relevant experience" if years else ""
    opener = (
        f"I am writing to apply for {target}{at}{exp}. "
        f"The requirements in the posting align with work I have already delivered, and I am applying with evidence rather than generic claims."
    )
    middle = " ".join(evidence) if evidence else "My recent work focuses on the same problems described in the posting."
    if skills:
        middle += " Directly relevant tools from my background include " + ", ".join(skills) + "."
    close = (
        "I would welcome the chance to discuss how this experience maps to your roadmap. "
        "Thank you for your time and consideration."
    )
    signoff = "Sincerely,"
    header = "\n".join(p for p in [name, city] if p)
    return "\n\n".join([header, greeting, opener, middle, close, f"{signoff}\n{name}"])


def _letter_tr(name: str, city: str, company: str, role: str, years: int | None, evidence: list[str], skills: list[str]) -> str:
    target = f"{role} pozisyonu" if role else "bu pozisyon"
    at = f"{company} bünyesindeki " if company else ""
    greeting = "Sayın Yetkili,"
    exp = f" {years}+ yıllık ilgili deneyimimle " if years else " "
    opener = (
        f"{at}{target} için başvuruyorum.{exp}"
        f"İlandaki beklentiler, daha önce teslim ettiğim işlerle örtüşüyor; mektupta yalnızca kanıtlanmış deneyime yer veriyorum."
    )
    middle = " ".join(evidence) if evidence else "Son dönem işlerim, ilanda tarif edilen problemlerle aynı hatta."
    if skills:
        middle += " Özgeçmişimde yer alan ve ilanla kesişen araçlar: " + ", ".join(skills) + "."
    close = (
        "Bu deneyimin ekibinize nasıl katkı vereceğini konuşmaktan memnuniyet duyarım. "
        "Zaman ayırdığınız için teşekkür ederim."
    )
    signoff = "Saygılarımla,"
    header = "\n".join(p for p in [name, city] if p)
    return "\n\n".join([header, greeting, opener, middle, close, f"{signoff}\n{name}"])


def _letter_grounded(
    letter: str,
    resume: Resume,
    original: str | None = None,
    company: str = "",
    role: str = "",
) -> bool:
    del company, role
    blob = _resume_blob(resume).lower()
    for metric in re.findall(r"\d+(?:[.,]\d+)?%", letter):
        if metric.lower() not in blob and metric not in (original or "").lower():
            return False
    # Stay recognizably based on the evidence draft; allow freer narrative than CV bullets.
    if original and fuzz.token_set_ratio(letter, original) < 45:
        return False
    # Reject empty/near-empty or prompt leakage
    lowered = letter.lower()
    if "facts (json" in lowered or "draft to improve" in lowered:
        return False
    return True


def _resume_blob(resume: Resume) -> str:
    parts = [resume.basics.summary, resume.basics.name, resume.basics.label]
    for work in resume.work:
        parts.extend([work.name, work.position, *work.highlights])
    for skill in resume.skills:
        parts.extend(skill.keywords)
    return "\n".join(p for p in parts if p)
