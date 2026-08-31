"""Pipeline RAG com chunking semantico, filtros e re-ranking contextual."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Iterable

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.neighbors import NearestNeighbors

from .metrics import PORTUGUESE_STOPWORDS


@dataclass
class Chunk:
    chunk_id: str
    document: str
    heading: str
    text: str
    equipment_types: list[str]
    anomaly_types: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _metadata_from_text(text: str) -> tuple[list[str], list[str]]:
    lowered = text.lower()
    equipment = [x for x in ["motor", "mancal", "painel", "ventilador"] if x in lowered]
    anomalies = []
    mapping = {
        "elétrica": ["corrente", "tensão", "isolamento", "elétric", "fase"],
        "mecânica": ["vibração", "mancal", "alinhamento", "desbalanceamento", "mecânic"],
        "térmica": ["temperatura", "aquecimento", "refrigeração", "térmic"],
        "preventiva": ["preventiva", "inspeção programada", "lubrificação"],
    }
    for name, terms in mapping.items():
        if any(t in lowered for t in terms):
            anomalies.append(name)
    return equipment or ["motor"], anomalies


def chunk_markdown(path: str | Path, max_chars: int = 1200, overlap_chars: int = 160) -> list[Chunk]:
    """Divide Markdown por cabecalhos e depois por paragrafos, preservando contexto."""
    path = Path(path)
    text = path.read_text(encoding="utf-8")
    sections: list[tuple[str, str]] = []
    current_heading = path.stem
    buffer: list[str] = []
    for line in text.splitlines():
        if re.match(r"^#{1,4}\s+", line):
            if buffer:
                sections.append((current_heading, "\n".join(buffer).strip()))
            current_heading = re.sub(r"^#{1,4}\s+", "", line).strip()
            buffer = []
        else:
            buffer.append(line)
    if buffer:
        sections.append((current_heading, "\n".join(buffer).strip()))

    chunks: list[Chunk] = []
    for heading, body in sections:
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", body) if p.strip()]
        current = ""
        parts: list[str] = []
        for paragraph in paragraphs:
            candidate = f"{current}\n\n{paragraph}".strip()
            if current and len(candidate) > max_chars:
                parts.append(current)
                current = current[-overlap_chars:] + "\n\n" + paragraph
            else:
                current = candidate
        if current:
            parts.append(current)
        for i, part in enumerate(parts):
            full_text = f"{heading}\n{part}".strip()
            digest = hashlib.sha1(f"{path.name}|{heading}|{i}".encode()).hexdigest()[:10]
            equipment, anomalies = _metadata_from_text(full_text)
            chunks.append(Chunk(digest, path.name, heading, full_text, equipment, anomalies))
    return chunks


class TechnicalRAG:
    """Retriever hibrido: embedding opcional + TF-IDF + bonus de contexto."""

    def __init__(self, embedding_model: str | None = None):
        self.embedding_model_name = embedding_model
        self.embedding_model = None
        self.backend = "tfidf"
        self.chunks: list[Chunk] = []
        self.vectorizer: TfidfVectorizer | None = None
        self.matrix = None
        self.heading_matrix = None
        self.index = None

    def build(self, document_dir: str | Path) -> "TechnicalRAG":
        paths = sorted(Path(document_dir).glob("*.md"))
        if not paths:
            raise ValueError(f"Nenhum documento Markdown encontrado em {document_dir}")
        self.chunks = [chunk for path in paths for chunk in chunk_markdown(path)]
        corpus = [c.text for c in self.chunks]
        if self.embedding_model_name:
            try:
                from sentence_transformers import SentenceTransformer
                self.embedding_model = SentenceTransformer(self.embedding_model_name)
                self.matrix = np.asarray(self.embedding_model.encode(corpus, normalize_embeddings=True))
                self.heading_matrix = np.asarray(self.embedding_model.encode([c.heading for c in self.chunks], normalize_embeddings=True))
                try:
                    import faiss
                    self.index = faiss.IndexFlatIP(self.matrix.shape[1])
                    self.index.add(self.matrix.astype("float32"))
                    self.backend = "sentence-transformers+faiss"
                except Exception:
                    self.index = NearestNeighbors(metric="cosine").fit(self.matrix)
                    self.backend = "sentence-transformers+sklearn-nn"
            except Exception:
                self.embedding_model = None
        if self.embedding_model is None:
            self.vectorizer = TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True)
            self.matrix = self.vectorizer.fit_transform(corpus)
            self.heading_matrix = self.vectorizer.transform([c.heading for c in self.chunks])
            self.index = NearestNeighbors(metric="cosine").fit(self.matrix)
            self.backend = "tfidf+sklearn-nn"
        return self

    def _base_scores(self, query: str) -> np.ndarray:
        if self.embedding_model is not None:
            query_vec = np.asarray(self.embedding_model.encode([query], normalize_embeddings=True))
            if "faiss" in self.backend:
                distances, indices = self.index.search(query_vec.astype("float32"), len(self.chunks))
                scores = np.zeros(len(self.chunks), dtype=float)
                scores[indices[0]] = distances[0]
                return scores
            distances, indices = self.index.kneighbors(query_vec, n_neighbors=len(self.chunks))
            scores = np.zeros(len(self.chunks), dtype=float)
            scores[indices[0]] = 1.0 - distances[0]
            return scores
        query_vec = self.vectorizer.transform([query])
        distances, indices = self.index.kneighbors(query_vec, n_neighbors=len(self.chunks))
        scores = np.zeros(len(self.chunks), dtype=float)
        scores[indices[0]] = 1.0 - distances[0]
        return scores

    def _heading_scores(self, query: str) -> np.ndarray:
        if self.embedding_model is not None:
            query_vec = np.asarray(self.embedding_model.encode([query], normalize_embeddings=True))
            return (self.heading_matrix @ query_vec[0]).astype(float)
        query_vec = self.vectorizer.transform([query])
        return cosine_similarity(query_vec, self.heading_matrix)[0]

    def retrieve(self, query: str, operational_context: dict[str, Any] | None = None, top_k: int = 4) -> list[dict[str, Any]]:
        if not self.chunks:
            raise RuntimeError("Índice ainda não construído")
        context = operational_context or {}
        scores = self._base_scores(query)
        heading_scores = self._heading_scores(query)
        anomaly = str(context.get("tipo_anomalia", "")).lower()
        equipment = str(context.get("tipo_equipamento", "motor")).lower()
        sensor = str(context.get("sensor_tipo", "")).replace("_", " ").lower()
        severity = str(context.get("severidade", "")).lower()
        query_terms = set(re.findall(r"[a-zà-ÿ0-9]+", (query + " " + sensor).lower())).difference(PORTUGUESE_STOPWORDS)

        reranked = []
        for i, chunk in enumerate(self.chunks):
            text_terms = set(re.findall(r"[a-zà-ÿ0-9]+", chunk.text.lower())).difference(PORTUGUESE_STOPWORDS)
            lexical = len(query_terms & text_terms) / max(1, len(query_terms))
            metadata_bonus = 0.0
            if anomaly and any(anomaly.startswith(a[:4]) or a.startswith(anomaly[:4]) for a in chunk.anomaly_types):
                metadata_bonus += 0.18
            if equipment and equipment in chunk.equipment_types:
                metadata_bonus += 0.06
            if severity == "critico" and any(x in chunk.text.lower() for x in ["parada", "desenerg", "não reenergizar"]):
                metadata_bonus += 0.05
            final_score = 0.50 * float(scores[i]) + 0.20 * lexical + 0.30 * float(heading_scores[i]) + 0.55 * metadata_bonus
            reranked.append({
                **chunk.to_dict(), "base_score": float(scores[i]),
                "heading_score": float(heading_scores[i]), "score": final_score,
            })
        reranked.sort(key=lambda x: x["score"], reverse=True)
        return reranked[:top_k]

    def evaluate_retrieval(self, qa_items: Iterable[dict[str, Any]], top_k: int = 4) -> dict[str, Any]:
        rows = []
        for item in qa_items:
            results = self.retrieve(item["question"], item.get("operational_context"), top_k=top_k)
            expected = set(item["relevant_sections"])
            flags = [r["heading"] in expected for r in results]
            rows.append({
                "id": item["id"],
                "precision_at_k": sum(flags) / top_k,
                "precision_at_1": float(flags[0]),
                "hit_at_k": float(any(flags)),
                "mrr": next((1.0/(i+1) for i, ok in enumerate(flags) if ok), 0.0),
                "retrieved": [r["heading"] for r in results],
            })
        return {
            "precision_at_k": float(np.mean([r["precision_at_k"] for r in rows])),
            "precision_at_1": float(np.mean([r["precision_at_1"] for r in rows])),
            "hit_at_k": float(np.mean([r["hit_at_k"] for r in rows])),
            "mrr": float(np.mean([r["mrr"] for r in rows])),
            "details": rows,
        }
