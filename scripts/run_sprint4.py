"""Executa indexacao, avaliacao RAG e tres cenarios demonstrativos."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from pln_motores.assistant import TroubleshootingAssistant
from pln_motores.rag import TechnicalRAG


def main(use_embeddings: bool = False) -> None:
    out = ROOT / "outputs"
    out.mkdir(exist_ok=True)
    qa = json.loads((ROOT / "data" / "perguntas_troubleshooting.json").read_text(encoding="utf-8"))
    model = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2" if use_embeddings else None
    rag = TechnicalRAG(embedding_model=model).build(ROOT / "data" / "documentos_tecnicos")
    assistant = TroubleshootingAssistant(rag)

    retrieval = rag.evaluate_retrieval(qa, top_k=4)
    conversational = assistant.evaluate(qa, top_k=4)

    scenarios = [
        {
            "cenario": "anomalia elétrica",
            "question": "A corrente das fases está desequilibrada. O que verifico e quando devo parar?",
            "context": {
                "tipo_equipamento": "motor", "equipamento_id": "Motor MT-042",
                "tipo_anomalia": "elétrica", "sensor_tipo": "corrente_fase", "severidade": "moderado",
                "resumo_alerta": "Alerta moderado: corrente 12% acima do equilíbrio esperado no sensor CUR-042-1.",
            },
        },
        {
            "cenario": "anomalia mecânica",
            "question": "A vibração do mancal subiu e surgiu ruído metálico. Qual é a ação segura?",
            "context": {
                "tipo_equipamento": "motor", "equipamento_id": "Motor MT-042",
                "tipo_anomalia": "mecânica", "sensor_tipo": "vibracao_mancal", "severidade": "critico",
                "resumo_alerta": "Alerta crítico: vibração 8,1 mm/s RMS no sensor VIB-042-1.",
            },
        },
        {
            "cenario": "manutenção preventiva",
            "question": "Quais verificações devo executar na manutenção trimestral?",
            "context": {
                "tipo_equipamento": "motor", "equipamento_id": "Motor MT-042",
                "tipo_anomalia": "preventiva", "severidade": "leve",
                "resumo_alerta": "Sem alerta crítico; tendência leve de temperatura nas duas últimas rondas.",
            },
        },
    ]
    demo = []
    for scenario in scenarios:
        assistant.history.clear()
        result = assistant.ask(scenario["question"], scenario["context"])
        demo.append({**scenario, **{k: v for k, v in result.items() if k != "prompt"}})

    metrics = {
        "backend": rag.backend,
        "chunks_indexados": len(rag.chunks),
        "retrieval": {k: v for k, v in retrieval.items() if k != "details"},
        "assistant": {k: v for k, v in conversational.items() if k != "details"},
        "evaluation_size": len(qa),
        "limitations": [
            "As métricas locais são proxies lexicais transparentes; uma avaliação com especialistas e LLM-judge é recomendada.",
            "O corpus é sintético e cobre apenas motores MT Série 040.",
            "O fallback extrativo reduz alucinação, mas pode produzir respostas menos naturais que um LLM.",
        ],
    }
    (out / "metricas_sprint4.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "avaliacao_detalhada_rag.json").write_text(
        json.dumps({"retrieval": retrieval["details"], "assistant": conversational["details"]}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (out / "demonstracao_cenarios.json").write_text(json.dumps(demo, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(metrics, ensure_ascii=False, indent=2))
    for item in demo:
        print(f"\n[{item['cenario']}]\n{item['answer']}")


if __name__ == "__main__":
    main()

