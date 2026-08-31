"""Classificador supervisionado de eventos de manutencao e operacao."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, f1_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline


CATEGORIES = [
    "manutenção corretiva",
    "manutenção preventiva",
    "anomalia elétrica",
    "anomalia mecânica",
    "operação normal",
]


@dataclass
class ClassificationResult:
    macro_f1: float
    weighted_f1: float
    per_category_f1: dict[str, float]
    report: dict
    test_predictions: pd.DataFrame


class EventClassifier:
    def __init__(self, random_state: int = 42):
        self.random_state = random_state
        self.pipeline = Pipeline([
            ("tfidf", TfidfVectorizer(ngram_range=(1, 2), min_df=1, sublinear_tf=True)),
            ("clf", LogisticRegression(max_iter=2000, class_weight="balanced", random_state=random_state)),
        ])

    def fit(self, texts: Iterable[str], labels: Iterable[str]) -> "EventClassifier":
        labels = list(labels)
        unknown = sorted(set(labels).difference(CATEGORIES))
        if unknown:
            raise ValueError(f"Categorias desconhecidas: {unknown}")
        self.pipeline.fit(list(texts), labels)
        return self

    def predict(self, texts: Iterable[str]) -> list[str]:
        return self.pipeline.predict(list(texts)).tolist()

    def predict_proba(self, texts: Iterable[str]) -> pd.DataFrame:
        values = self.pipeline.predict_proba(list(texts))
        return pd.DataFrame(values, columns=self.pipeline.classes_)

    def evaluate_holdout(self, data: pd.DataFrame, test_size: float = 0.25) -> ClassificationResult:
        train, test = train_test_split(
            data,
            test_size=test_size,
            random_state=self.random_state,
            stratify=data["categoria"],
        )
        self.fit(train["texto"], train["categoria"])
        pred = self.predict(test["texto"])
        report = classification_report(
            test["categoria"], pred, labels=CATEGORIES, output_dict=True, zero_division=0
        )
        test_predictions = test.copy()
        test_predictions["predicao"] = pred
        return ClassificationResult(
            macro_f1=f1_score(test["categoria"], pred, average="macro"),
            weighted_f1=f1_score(test["categoria"], pred, average="weighted"),
            per_category_f1={c: report[c]["f1-score"] for c in CATEGORIES},
            report=report,
            test_predictions=test_predictions,
        )

