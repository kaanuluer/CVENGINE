from __future__ import annotations

import re
from collections import Counter

from rapidfuzz import fuzz

from app.schemas import GateIssue, Resume

# Tailored CV must stay recognizably the same document as the master.
CONSISTENCY_TARGET = 75.0

_WEAVE_PREFIX_RE = re.compile(
    r"^[\w.+#/,\- ]{2,60}(?:\s+ile:|\s+with:|\s*\([^)]{2,40}\)\.?$)",
    re.I,
)
_TR_MARKERS = re.compile(
    r"\b(ve|ile|için|olan|olarak|geliştirdim|yönettim|azalttım|artırdım|kurdum|yaptım)\b",
    re.I,
)
_EN_MARKERS = re.compile(
    r"\b(the|and|with|for|built|led|managed|improved|reduced|delivered|using)\b",
    re.I,
)


def check_consistency(master: Resume, tailored: Resume) -> tuple[float, list[GateIssue]]:
    """Score how faithfully the tailored CV preserves master identity and internal style."""
    issues: list[GateIssue] = []
    score = 100.0

    score -= _employer_drift(master, tailored, issues)
    score -= _education_drift(master, tailored, issues)
    score -= _highlight_drift(master, tailored, issues)
    score -= _summary_drift(master, tailored, issues)
    score -= _internal_style(tailored, issues)
    score -= _sentence_quality(tailored, issues)

    score = max(0.0, min(100.0, score))
    if score < CONSISTENCY_TARGET and not any(i.code == "consistency_low" for i in issues):
        issues.append(
            GateIssue(
                code="consistency_low",
                message=f"Master–üretilen CV tutarlılığı düşük ({score:.0f} < {CONSISTENCY_TARGET:.0f})",
                severity="block" if score < 60 else "warn",
            )
        )
    return round(score, 1), issues


def _employer_drift(master: Resume, tailored: Resume, issues: list[GateIssue]) -> float:
    master_names = {_norm(w.name) for w in master.work if w.name}
    tailored_names = {_norm(w.name) for w in tailored.work if w.name}
    if not master_names:
        return 0.0
    missing = master_names - tailored_names
    penalty = 0.0
    if missing:
        issues.append(
            GateIssue(
                code="employer_dropped",
                message="Master CV'deki işveren(ler) üretilen CV'de yok: " + ", ".join(sorted(missing)[:4]),
                severity="block",
            )
        )
        penalty += min(40.0, 15.0 * len(missing))
    # Extra employers are already blocked by groundedness; light warn here if any slip through.
    extra = tailored_names - master_names
    if extra:
        issues.append(
            GateIssue(
                code="employer_added",
                message="Üretilen CV'ye master'da olmayan işveren eklendi",
                severity="warn",
            )
        )
        penalty += 8.0
    return penalty


def _education_drift(master: Resume, tailored: Resume, issues: list[GateIssue]) -> float:
    master_schools = {_norm(e.institution) for e in master.education if e.institution}
    tailored_schools = {_norm(e.institution) for e in tailored.education if e.institution}
    if not master_schools:
        return 0.0
    missing = master_schools - tailored_schools
    if not missing:
        return 0.0
    issues.append(
        GateIssue(
            code="education_dropped",
            message="Master CV'deki eğitim kaydı üretilen CV'de eksik",
            severity="block",
        )
    )
    return min(25.0, 12.0 * len(missing))


def _highlight_drift(master: Resume, tailored: Resume, issues: list[GateIssue]) -> float:
    master_highlights = [h.strip() for w in master.work for h in w.highlights if h.strip()]
    tailored_highlights = [h.strip() for w in tailored.work for h in w.highlights if h.strip()]
    if not master_highlights or not tailored_highlights:
        return 0.0

    orphan = 0
    weak = 0
    for highlight in tailored_highlights:
        core = _strip_weave(highlight)
        best = max(fuzz.token_set_ratio(core, original) for original in master_highlights)
        if best < 55:
            orphan += 1
        elif best < 68:
            weak += 1

    penalty = 0.0
    if orphan:
        issues.append(
            GateIssue(
                code="highlight_drift",
                message=f"{orphan} madde master CV cümlelerinden aşırı sapıyor",
                severity="block" if orphan >= 2 else "warn",
            )
        )
        penalty += min(35.0, 12.0 * orphan)
    if weak >= 3:
        issues.append(
            GateIssue(
                code="highlight_loose",
                message="Birden fazla madde master metinden belirgin şekilde uzaklaşmış",
                severity="warn",
            )
        )
        penalty += 6.0
    return penalty


def _summary_drift(master: Resume, tailored: Resume, issues: list[GateIssue]) -> float:
    master_summary = (master.basics.summary or "").strip()
    tailored_summary = (tailored.basics.summary or "").strip()
    if not master_summary:
        return 0.0
    if not tailored_summary:
        issues.append(
            GateIssue(code="summary_empty", message="Üretilen CV özeti boş", severity="warn")
        )
        return 8.0
    # Allow denser JD-aligned summary, but keep some overlap with master evidence.
    ratio = fuzz.token_set_ratio(master_summary, tailored_summary)
    # Also compare against master highlights as evidence pool
    master_pool = " ".join(
        [master_summary, *[h for w in master.work for h in w.highlights[:3]]]
    )
    pool_ratio = fuzz.token_set_ratio(master_pool, tailored_summary)
    best = max(ratio, pool_ratio)
    if best < 40:
        issues.append(
            GateIssue(
                code="summary_drift",
                message="Özet master CV içeriğinden aşırı sapıyor",
                severity="block",
            )
        )
        return 20.0
    if best < 55:
        issues.append(
            GateIssue(
                code="summary_loose",
                message="Özet master CV ile zayıf örtüşüyor",
                severity="warn",
            )
        )
        return 8.0
    # Detect duplicated openers from amplify loops
    if re.search(r"(.{20,90}?)\.\s+\1", tailored_summary):
        issues.append(
            GateIssue(
                code="summary_duplicate",
                message="Özette tekrarlayan cümle / giriş kalıbı var",
                severity="warn",
            )
        )
        return 6.0
    return 0.0


def _internal_style(tailored: Resume, issues: list[GateIssue]) -> float:
    highlights = [h.strip() for w in tailored.work for h in w.highlights if h.strip()]
    if len(highlights) < 2:
        return 0.0
    penalty = 0.0

    # Language mixture inside the tailored CV
    tr_n = sum(1 for h in highlights if _TR_MARKERS.search(h))
    en_n = sum(1 for h in highlights if _EN_MARKERS.search(h))
    if tr_n >= 2 and en_n >= 2 and min(tr_n, en_n) / max(tr_n, en_n) > 0.45:
        issues.append(
            GateIssue(
                code="mixed_language",
                message="Üretilen CV maddelerinde TR/EN karışık anlatım var",
                severity="warn",
            )
        )
        penalty += 8.0

    # Formulaic weave prefixes dominating the voice
    woven = sum(1 for h in highlights if _WEAVE_PREFIX_RE.search(h) or " ile: " in h)
    if woven >= max(3, len(highlights) // 2):
        issues.append(
            GateIssue(
                code="formulaic_structure",
                message="Çok sayıda madde aynı yapay kalıpla başlıyor; cümle yapısı bozulmuş",
                severity="warn",
            )
        )
        penalty += 10.0

    # Repeated openings
    openings = [" ".join(h.split()[:3]).lower() for h in highlights if len(h.split()) >= 3]
    counts = Counter(openings)
    repeated = [k for k, n in counts.items() if n >= 3 and k]
    if repeated:
        issues.append(
            GateIssue(
                code="repeated_openers",
                message="Aynı cümle açılışı defalarca tekrarlanıyor",
                severity="warn",
            )
        )
        penalty += 8.0

    return penalty


def _sentence_quality(tailored: Resume, issues: list[GateIssue]) -> float:
    highlights = [h.strip() for w in tailored.work for h in w.highlights if h.strip()]
    if not highlights:
        return 0.0
    penalty = 0.0
    lengths = [len(h.split()) for h in highlights]
    avg = sum(lengths) / len(lengths)
    weird = [n for n in lengths if n < 4 or n > max(40, avg * 3)]
    if len(weird) >= 2:
        issues.append(
            GateIssue(
                code="sentence_length",
                message="Madde uzunlukları tutarsız (çok kısa veya aşırı uzun cümleler)",
                severity="warn",
            )
        )
        penalty += 6.0

    broken = 0
    for h in highlights:
        if re.search(r"\b(\w+)\s+\1\b", h, re.I):
            broken += 1
        if "ile: ile:" in h.lower() or h.count(" ile: ") > 1:
            broken += 1
        if h.endswith(" ile:") or h.endswith(" with:"):
            broken += 1
    if broken:
        issues.append(
            GateIssue(
                code="broken_sentence",
                message=f"{broken} maddede bozuk / yarım cümle yapısı var",
                severity="block" if broken >= 2 else "warn",
            )
        )
        penalty += min(24.0, 10.0 * broken)
    return penalty


def _strip_weave(highlight: str) -> str:
    text = highlight.strip()
    text = re.sub(r"^[\w.+#/,\- ]{2,50}\s+ile:\s*", "", text, flags=re.I)
    text = re.sub(r"^[\w.+#/,\- ]{2,50}\s+with:\s*", "", text, flags=re.I)
    text = re.sub(r"\s*\([^)]{2,50}\)\.?$", "", text)
    return text.strip() or highlight.strip()


def _norm(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").strip().lower())
