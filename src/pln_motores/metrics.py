"""Metricas leves e explicitas para geracao e RAG."""

from __future__ import annotations

import re
from collections import Counter
from typing import Iterable, Sequence

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


def tokenize(text: str) -> list[str]:
    return re.findall(r"[a-zà-ÿ0-9]+", text.lower())


def _ngrams(tokens: list[str], n: int) -> Counter:
    return Counter(tuple(tokens[i:i+n]) for i in range(max(0, len(tokens)-n+1)))


def rouge_n_f1(prediction: str, reference: str, n: int = 1) -> float:
    pred, ref = _ngrams(tokenize(prediction), n), _ngrams(tokenize(reference), n)
    overlap = sum((pred & ref).values())
    precision = overlap / max(1, sum(pred.values()))
    recall = overlap / max(1, sum(ref.values()))
    return 0.0 if precision + recall == 0 else 2 * precision * recall / (precision + recall)


def rouge_l_f1(prediction: str, reference: str) -> float:
    a, b = tokenize(prediction), tokenize(reference)
    dp = [0] * (len(b) + 1)
    for x in a:
        previous = 0
        for j, y in enumerate(b, start=1):
            old = dp[j]
            dp[j] = previous + 1 if x == y else max(dp[j], dp[j-1])
            previous = old
    lcs = dp[-1]
    p, r = lcs / max(1, len(a)), lcs / max(1, len(b))
    return 0.0 if p + r == 0 else 2 * p * r / (p + r)


def evaluate_rouge(predictions: Sequence[str], references: Sequence[str]) -> dict[str, float]:
    if len(predictions) != len(references):
        raise ValueError("Predições e referências devem ter o mesmo tamanho")
    scores = {
        "rouge1": [rouge_n_f1(p, r, 1) for p, r in zip(predictions, references)],
        "rouge2": [rouge_n_f1(p, r, 2) for p, r in zip(predictions, references)],
        "rougeL": [rouge_l_f1(p, r) for p, r in zip(predictions, references)],
    }
    return {k: float(np.mean(v)) for k, v in scores.items()}


def text_similarity(a: str, b: str) -> float:
    vectorizer = TfidfVectorizer(ngram_range=(1, 2))
    matrix = vectorizer.fit_transform([a, b])
    return float(cosine_similarity(matrix[0], matrix[1])[0, 0])


PORTUGUESE_STOPWORDS = {
    "a", "ao", "aos", "as", "com", "como", "da", "das", "de", "deve", "do", "dos",
    "e", "em", "entre", "esse", "esta", "está", "no", "nos", "na", "nas", "o", "os",
    "ou", "para", "por", "qual", "quais", "que", "se", "ser", "um", "uma",
}


def answer_relevancy(answer: str, reference: str) -> float:
    """Proxy lexical: cobertura do gabarito combinada a similaridade cosseno.

    A cobertura evita punir uma resposta correta por incluir passos de seguranca,
    contexto operacional e citacao alem da resposta curta de referencia.
    """
    ref_terms = set(tokenize(reference)).difference(PORTUGUESE_STOPWORDS)
    answer_terms = set(tokenize(answer)).difference(PORTUGUESE_STOPWORDS)
    coverage = len(ref_terms & answer_terms) / max(1, len(ref_terms))
    return 0.7 * coverage + 0.3 * text_similarity(answer, reference)


def sentence_support(answer: str, contexts: Iterable[str], threshold: float = 0.08) -> float:
    """Proxy auditavel de faithfulness: fracao de sentencas apoiadas no contexto."""
    context = " ".join(contexts)
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", answer) if len(tokenize(s)) >= 3]
    if not sentences:
        return 0.0
    supported = [text_similarity(s, context) >= threshold for s in sentences]
    return sum(supported) / len(supported)
