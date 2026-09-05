from __future__ import annotations

import math
import re
from collections import Counter

import numpy as np

STOP = {
    "the", "and", "for", "with", "you", "our", "will", "are", "this", "that",
    "from", "your", "have", "has", "was", "were", "not", "but", "all", "any",
    "can", "may", "job", "role", "team", "work", "working", "ability",
    "ve", "ile", "için", "icin", "bir", "bu", "olan", "olarak", "gibi",
    "daha", "çok", "cok", "en", "de", "da", "deneyimli",
}


def tokenize(text: str) -> list[str]:
    return [t for t in re.findall(r"[A-Za-zÇĞİÖŞÜçğıöşü0-9+.#]{2,}", text.lower()) if t not in STOP]


def tfidf_matrix(docs: list[str]) -> tuple[list[str], np.ndarray]:
    tokenized = [tokenize(doc) for doc in docs]
    vocab: list[str] = sorted({tok for doc in tokenized for tok in doc})
    if not vocab:
        return [], np.zeros((len(docs), 0))
    index = {t: i for i, t in enumerate(vocab)}
    tf = np.zeros((len(docs), len(vocab)), dtype=float)
    for r, tokens in enumerate(tokenized):
        counts = Counter(tokens)
        n = max(len(tokens), 1)
        for tok, c in counts.items():
            tf[r, index[tok]] = c / n
    df = np.count_nonzero(tf > 0, axis=0)
    idf = np.log((1 + len(docs)) / (1 + df)) + 1.0
    return vocab, tf * idf


def cosine(a: np.ndarray, b: np.ndarray) -> float:
    denom = float(np.linalg.norm(a) * np.linalg.norm(b))
    if denom == 0:
        return 0.0
    return float(np.dot(a, b) / denom)


def cosine_to_query(docs: list[str], query: str) -> list[float]:
    matrix_docs = [*docs, query]
    _, matrix = tfidf_matrix(matrix_docs)
    if matrix.size == 0:
        return [0.0] * len(docs)
    q = matrix[-1]
    return [round(cosine(matrix[i], q), 4) for i in range(len(docs))]


def extract_keywords(text: str, limit: int = 24) -> list[str]:
    tokens = tokenize(text)
    if not tokens:
        return []
    grams: list[str] = []
    for n in (1, 2):
        for i in range(len(tokens) - n + 1):
            grams.append(" ".join(tokens[i : i + n]))
    counts = Counter(grams)
    scored: list[tuple[str, float]] = []
    for gram, count in counts.items():
        words = gram.split()
        if all(len(w) <= 2 for w in words):
            continue
        score = count * (1.4 if len(words) == 2 else 1.0) * math.log(1 + len(gram))
        scored.append((gram, score))
    scored.sort(key=lambda x: (-x[1], x[0]))
    out: list[str] = []
    seen: set[str] = set()
    for gram, _ in scored:
        if gram in seen:
            continue
        seen.add(gram)
        out.append(gram)
        if len(out) >= limit:
            break
    return out


def split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+|\n+", text.strip())
    return [p.strip() for p in parts if len(p.strip()) > 20]


def extractive_summary(candidates: list[str], query: str, limit: int = 3) -> str:
    unique = []
    seen: set[str] = set()
    for sentence in candidates:
        key = sentence.lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(sentence)
    if not unique:
        return ""
    scores = cosine_to_query(unique, query)
    ranked = [s for s, _ in sorted(zip(unique, scores), key=lambda x: -x[1])]
    picked = ranked[:limit]
    # Keep original relative order for readability
    order = {s: i for i, s in enumerate(unique)}
    picked.sort(key=lambda s: order[s])
    return " ".join(picked)
