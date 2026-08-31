"""Utilitarios para avaliacao incremental no Google Colab."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from .metrics import answer_relevancy


DEFAULT_WEAK_IDS = {"TS-04", "TS-10", "TS-11", "TS-12", "TS-19"}


def _evaluation_row(item: dict[str, Any], result: dict[str, Any], rag, top_k: int) -> dict[str, Any]:
    retrieved = rag.retrieve(
        item["question"],
        item.get("operational_context", {}),
        top_k=top_k,
    )
    expected = set(item["relevant_sections"])
    hits = [chunk["heading"] in expected for chunk in retrieved]
    return {
        "id": item["id"],
        "question": item["question"],
        "reference_answer": item["reference_answer"],
        "answer": result["answer"],
        "generation_mode": result["generation_mode"],
        "validation_issues": result["validation_issues"],
        "faithfulness": result["faithfulness_proxy"],
        "answer_relevancy": answer_relevancy(result["answer"], item["reference_answer"]),
        "context_precision": sum(hits) / len(hits),
        "precision_at_1": float(hits[0]),
        "hit_at_3": float(any(hits)),
        "mrr": next((1.0 / position for position, hit in enumerate(hits, start=1) if hit), 0.0),
        "retrieved_sections": [chunk["heading"] for chunk in retrieved],
        "sources": result["sources"],
    }


def summarize_metrics(evaluation: list[dict[str, Any]], rag, top_k: int = 3) -> dict[str, Any]:
    return {
        "modelo": "Qwen/Qwen2.5-3B-Instruct",
        "backend_retrieval": rag.backend,
        "evaluation_size": len(evaluation),
        "top_k": top_k,
        "faithfulness": sum(item["faithfulness"] for item in evaluation) / len(evaluation),
        "answer_relevancy": sum(item["answer_relevancy"] for item in evaluation) / len(evaluation),
        "context_precision": sum(item["context_precision"] for item in evaluation) / len(evaluation),
        "precision_at_1": sum(item["precision_at_1"] for item in evaluation) / len(evaluation),
        "hit_at_3": sum(item["hit_at_3"] for item in evaluation) / len(evaluation),
        "mrr": sum(item["mrr"] for item in evaluation) / len(evaluation),
        "generation_modes": dict(Counter(item["generation_mode"] for item in evaluation)),
    }


def reprocess_cases(
    qa_items: list[dict[str, Any]],
    evaluation: list[dict[str, Any]],
    assistant,
    rag,
    checkpoint_path: str | Path,
    metrics_path: str | Path,
    cached_results: dict[str, dict[str, Any]] | None = None,
    ids: set[str] | None = None,
    top_k: int = 3,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Reprocessa casos escolhidos, persiste resultados e imprime progresso."""
    selected_ids = ids or DEFAULT_WEAK_IDS
    cached = cached_results or {}
    checkpoint_path = Path(checkpoint_path)
    metrics_path = Path(metrics_path)

    for item in qa_items:
        if item["id"] not in selected_ids:
            continue
        result = cached.get(item["id"])
        if result is None:
            assistant.history.clear()
            result = assistant.ask(
                item["question"],
                item.get("operational_context", {}),
                top_k=top_k,
            )
        new_row = _evaluation_row(item, result, rag, top_k)
        index = next(position for position, old in enumerate(evaluation) if old["id"] == item["id"])
        previous = evaluation[index]["answer_relevancy"]
        evaluation[index] = new_row
        checkpoint_path.write_text(
            json.dumps(evaluation, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(
            f"{item['id']}: {previous:.3f} -> {new_row['answer_relevancy']:.3f} "
            f"| faith={new_row['faithfulness']:.3f} | modo={new_row['generation_mode']}",
            flush=True,
        )

    order = {item["id"]: position for position, item in enumerate(qa_items)}
    evaluation.sort(key=lambda item: order[item["id"]])
    metrics = summarize_metrics(evaluation, rag, top_k=top_k)
    checkpoint_path.write_text(
        json.dumps(evaluation, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    metrics_path.write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print("\nMETRICAS ATUALIZADAS")
    print(json.dumps(metrics, ensure_ascii=False, indent=2))
    return evaluation, metrics
