from __future__ import annotations

import re

from app.schemas import ResumeLanguage

TR_CHARS = set("çğıöşüÇĞİÖŞÜ")
TR_STOP = {
    "ve", "ile", "için", "bir", "bu", "olan", "olarak", "deneyim", "iş",
    "aranıyor", "aranmaktadır", "görev", "sorumluluk", "nitelik",
}
EN_STOP = {
    "the", "and", "for", "with", "you", "our", "will", "role", "job",
    "experience", "requirements", "responsibilities",
}
_TR_UPPER = str.maketrans({
    "i": "İ",
    "ı": "I",
    "ş": "Ş",
    "ğ": "Ğ",
    "ü": "Ü",
    "ö": "Ö",
    "ç": "Ç",
})
_TR_LOWER = str.maketrans({
    "İ": "i",
    "I": "ı",
    "Ş": "ş",
    "Ğ": "ğ",
    "Ü": "ü",
    "Ö": "ö",
    "Ç": "ç",
})


def detect_language(text: str) -> ResumeLanguage:
    if not text.strip():
        return "en"
    tr_char_hits = sum(1 for ch in text if ch in TR_CHARS)
    tokens = re.findall(r"[A-Za-zÇĞİÖŞÜçğıöşü]+", text.lower())
    tr_word = sum(1 for t in tokens if t in TR_STOP)
    en_word = sum(1 for t in tokens if t in EN_STOP)
    if tr_char_hits >= 2 or tr_word > en_word:
        return "tr"
    return "en"


def language_upper(text: str, language: ResumeLanguage) -> str:
    """Uppercase with Turkish i/ı mapping when the target language is TR."""
    if language == "tr":
        return text.translate(_TR_UPPER).upper()
    return text.upper()


def language_lower(text: str, language: ResumeLanguage) -> str:
    if language == "tr":
        return text.translate(_TR_LOWER).lower()
    return text.lower()


def language_capitalize(text: str, language: ResumeLanguage) -> str:
    if not text:
        return text
    return language_upper(text[0], language) + text[1:]
