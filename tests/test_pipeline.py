from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from pln_motores.alerts import gerar_resumo_alerta
from pln_motores.assistant import TroubleshootingAssistant
from pln_motores.classification import EventClassifier
from pln_motores.rag import TechnicalRAG
from pln_motores.reports import gerar_relatorio_operacional


ROOT = Path(__file__).resolve().parents[1]


def test_three_severity_templates_and_traceability():
    alerts = pd.read_csv(ROOT / "data" / "alertas_teste.csv")
    outputs = [gerar_resumo_alerta(alerts[alerts.severidade == s].iloc[0].to_dict()).text for s in ["leve", "moderado", "critico"]]
    assert "desvio leve" in outputs[0]
    assert "Alerta moderado" in outputs[1]
    assert "ALERTA CRÍTICO" in outputs[2]
    assert all("[Fonte:" in text for text in outputs)


def test_classifier_all_categories():
    events = pd.read_csv(ROOT / "data" / "eventos_rotulados.csv")
    result = EventClassifier().evaluate_holdout(events)
    assert set(result.per_category_f1) == set(events.categoria.unique())
    assert result.macro_f1 >= 0.75


def test_report_has_source_for_each_claim():
    alerts = pd.read_csv(ROOT / "data" / "alertas_teste.csv").head(8)
    report = gerar_relatorio_operacional(alerts.to_dict("records"))
    factual_paragraphs = [p for p in report.split("\n\n") if any(x in p for x in ["emitidos", "equipamento", "tendência", "Recomendação"])]
    assert all("[Fonte:" in p for p in factual_paragraphs)


def test_rag_hits_ground_truth():
    qa = json.loads((ROOT / "data" / "perguntas_troubleshooting.json").read_text(encoding="utf-8"))
    rag = TechnicalRAG().build(ROOT / "data" / "documentos_tecnicos")
    metrics = rag.evaluate_retrieval(qa, top_k=4)
    assert metrics["hit_at_k"] >= 0.85


def test_assistant_rejects_ungrounded_llm_answer():
    rag = TechnicalRAG().build(ROOT / "data" / "documentos_tecnicos")
    assistant = TroubleshootingAssistant(
        rag,
        llm=lambda _: "Recomendo trocar todo o motor imediatamente. Confiança: alta.",
    )
    result = assistant.ask(
        "A corrente está desequilibrada. O que verificar e quando parar?",
        {"tipo_equipamento": "motor", "tipo_anomalia": "elétrica", "severidade": "moderado"},
        top_k=3,
    )
    assert result["generation_mode"] == "guardrail_fallback"
    assert "[manual_motor_mt.md > Desequilíbrio de corrente entre fases]" in result["answer"]
    assert "trocar todo o motor" not in result["answer"]


def test_assistant_rejects_safety_contradiction():
    rag = TechnicalRAG().build(ROOT / "data" / "documentos_tecnicos")
    contradictory = (
        "Situação atual: vibração alta com ruído metálico. "
        "[manual_motor_mt.md > Vibração elevada no mancal] "
        "Critério de parada: não há parada imediata definida. "
        "Confiança: alta — evidência suficiente."
    )
    assistant = TroubleshootingAssistant(rag, llm=lambda _: contradictory)
    result = assistant.ask(
        "A vibração aumentou e surgiu ruído metálico. Qual é a ação segura?",
        {
            "tipo_equipamento": "motor",
            "tipo_anomalia": "mecânica",
            "severidade": "critico",
            "resumo_alerta": "Vibração crítica com ruído metálico.",
        },
        top_k=3,
    )
    assert result["generation_mode"] == "guardrail_fallback"
    assert "parada segura" in result["answer"].lower()
    assert "não há parada" not in result["answer"].lower()


def test_assistant_rejects_unwarranted_abstention():
    rag = TechnicalRAG().build(ROOT / "data" / "documentos_tecnicos")
    abstention = (
        "Sem informações específicas sobre a graxa. "
        "[manual_motor_mt.md > Falha de mancal] "
        "Confiança: baixa — evidência insuficiente."
    )
    assistant = TroubleshootingAssistant(rag, llm=lambda _: abstention)
    result = assistant.ask(
        "Por que não devo adicionar graxa sem diagnóstico?",
        {"tipo_equipamento": "motor", "tipo_anomalia": "mecânica", "severidade": "moderado"},
        top_k=3,
    )
    assert result["generation_mode"] == "guardrail_fallback"
    assert "excesso de lubrificante" in result["answer"].lower()


def test_fallback_answers_alignment_sequence():
    rag = TechnicalRAG().build(ROOT / "data" / "documentos_tecnicos")
    assistant = TroubleshootingAssistant(rag)
    result = assistant.ask(
        "O que deve ser feito após corrigir o alinhamento?",
        {"tipo_equipamento": "motor", "tipo_anomalia": "mecânica", "severidade": "moderado"},
        top_k=3,
    )
    lowered = result["answer"].lower()
    assert "após cada correção" in lowered
    assert "repita a medição" in lowered


def test_fallback_keeps_alignment_measurement_context():
    rag = TechnicalRAG().build(ROOT / "data" / "documentos_tecnicos")
    assistant = TroubleshootingAssistant(rag)
    question = "Como verificar desalinhamento com segurança?"
    context = {"tipo_equipamento": "motor", "tipo_anomalia": "mecânica", "severidade": "moderado"}
    retrieved = rag.retrieve(question, context, top_k=6)
    procedure = next(item for item in retrieved if item["heading"] == "Procedimento de verificação de alinhamento")
    ordered = [procedure] + [item for item in retrieved if item is not procedure]
    answer = assistant._grounded_fallback(
        question,
        ordered[:3],
        context,
    )
    lowered = answer.lower()
    assert "pé manco" in lowered
    assert "desalinhamento paralelo e angular" in lowered


def test_assistant_rejects_wrong_post_alignment_action():
    rag = TechnicalRAG().build(ROOT / "data" / "documentos_tecnicos")
    wrong = (
        "Situação atual: alinhamento corrigido. "
        "Verificações recomendadas: o motor deve ser desbloqueado. "
        "[ficha_manutencao_mt.md > Procedimento de verificação de alinhamento] "
        "Confiança: alta — evidência suficiente."
    )
    assistant = TroubleshootingAssistant(rag, llm=lambda _: wrong)
    result = assistant.ask(
        "O que deve ser feito após corrigir o alinhamento?",
        {"tipo_equipamento": "motor", "tipo_anomalia": "mecânica", "severidade": "moderado"},
        top_k=3,
    )
    lowered = result["answer"].lower()
    assert result["generation_mode"] == "guardrail_fallback"
    assert "repita a medição" in lowered
    assert "desbloqueado" not in lowered


def test_assistant_abstains_for_undocumented_model():
    rag = TechnicalRAG().build(ROOT / "data" / "documentos_tecnicos")
    assistant = TroubleshootingAssistant(
        rag,
        llm=lambda _: "Use torque de 50 Nm. Confiança: alta — procedimento conhecido.",
    )
    result = assistant.ask(
        "Qual é o torque exato do terminal de um motor de outra marca, modelo ZX-900?",
        {"tipo_equipamento": "motor"},
        top_k=3,
    )
    assert result["generation_mode"] == "scope_abstention"
    assert result["confidence"] == "baixa"
    assert "não há informação suficiente" in result["answer"].lower()
    assert "ZX-900" in result["answer"]
    assert "50 Nm" not in result["answer"]
