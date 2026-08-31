"""Executa todos os artefatos e metricas da Sprint 3."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from pln_motores.alerts import gerar_resumo_alerta
from pln_motores.classification import EventClassifier
from pln_motores.metrics import evaluate_rouge
from pln_motores.reports import gerar_relatorio_operacional


def checklist(narratives: list[str], alerts: pd.DataFrame) -> dict:
    rows = []
    for text, (_, alert) in zip(narratives, alerts.iterrows()):
        checks = {
            "clareza": len(text.split()) <= 75 and "." in text,
            "precisao": str(alert["equipamento_id"]) in text and str(alert["sensor_id"]) in text,
            "utilidade": any(term in text.lower() for term in ["verificar", "acompanhar", "inspecionar", "parada", "isolar"]),
            "rastreabilidade": "[Fonte:" in text,
        }
        rows.append({"alert_id": alert["alert_id"], **checks})
    frame = pd.DataFrame(rows)
    return {column: float(frame[column].mean()) for column in frame.columns if column != "alert_id"}


def main() -> None:
    out = ROOT / "outputs"
    out.mkdir(exist_ok=True)
    alerts = pd.read_csv(ROOT / "data" / "alertas_teste.csv")
    events = pd.read_csv(ROOT / "data" / "eventos_rotulados.csv")

    narratives = [gerar_resumo_alerta(row).text for row in alerts.to_dict("records")]
    alerts["resumo_gerado"] = narratives
    alerts.to_csv(out / "alertas_com_resumos.csv", index=False, encoding="utf-8-sig")
    rouge = evaluate_rouge(narratives, alerts["resumo_referencia"].tolist())

    classifier = EventClassifier(random_state=42)
    classification = classifier.evaluate_holdout(events)
    classification.test_predictions.to_csv(out / "predicoes_classificador.csv", index=False, encoding="utf-8-sig")

    report = gerar_relatorio_operacional(alerts.to_dict("records"), periodo="semanal")
    (out / "relatorio_operacional.txt").write_text(report, encoding="utf-8")
    metrics = {
        "dataset": {"alertas": len(alerts), "eventos": len(events), "holdout": len(classification.test_predictions)},
        "rouge": rouge,
        "checklist_textos": checklist(narratives, alerts),
        "classificacao": {
            "macro_f1": classification.macro_f1,
            "weighted_f1": classification.weighted_f1,
            "f1_por_categoria": classification.per_category_f1,
        },
        "limitations": [
            "Dados simulados e balanceados podem superestimar o desempenho do classificador.",
            "Referências de resumo foram escritas para o mesmo domínio e não medem preferência de operadores reais.",
        ],
    }
    (out / "metricas_sprint3.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(metrics, ensure_ascii=False, indent=2))
    print("\nRELATÓRIO\n", report)


if __name__ == "__main__":
    main()

