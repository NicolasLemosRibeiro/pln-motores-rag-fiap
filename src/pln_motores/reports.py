"""Relatorio operacional em linguagem natural com rastreabilidade."""

from __future__ import annotations

from collections import Counter
from datetime import datetime
from typing import Iterable, Mapping

from .alerts import SENSOR_NAMES


def _ref(alert: Mapping) -> str:
    return (
        f"[Fonte: {alert['alert_id']}; sensor {alert['sensor_id']}; "
        f"valor {alert['valor_atual']:g}{alert['unidade']}; {alert['timestamp']}]"
    )


def gerar_relatorio_operacional(alertas: Iterable[Mapping], periodo: str = "diário") -> str:
    items = list(alertas)
    if not items:
        return f"Relatório {periodo}: nenhum alerta registrado no período."

    severity_counts = Counter(str(a["severidade"]).lower() for a in items)
    equipment_risk = Counter(a["equipamento_id"] for a in items if a["severidade"] in {"moderado", "critico"})
    dominant_sensor = Counter(a["sensor_tipo"] for a in items).most_common(1)[0][0]
    ordered = sorted(items, key=lambda a: (a["severidade"] != "critico", -abs(float(a["desvio"]))))
    top = ordered[0]
    date_values = sorted(datetime.fromisoformat(str(a["timestamp"]).replace("Z", "+00:00")) for a in items)

    lines = [
        f"Relatório operacional {periodo} — {date_values[0]:%d/%m/%Y} a {date_values[-1]:%d/%m/%Y}.",
        (
            f"Foram emitidos {len(items)} alertas: {severity_counts['leve']} leves, "
            f"{severity_counts['moderado']} moderados e {severity_counts['critico']} críticos. "
            f"{_ref(top)}"
        ),
    ]
    if equipment_risk:
        equipment, count = equipment_risk.most_common(1)[0]
        evidence = next(a for a in items if a["equipamento_id"] == equipment and a["severidade"] in {"moderado", "critico"})
        lines.append(
            f"O equipamento com maior concentração de risco foi {equipment}, com {count} eventos moderados ou críticos. {_ref(evidence)}"
        )
    trend_evidence = next(a for a in reversed(items) if a["sensor_tipo"] == dominant_sensor)
    lines.append(
        f"A tendência predominante envolveu {SENSOR_NAMES[dominant_sensor]}, presente em "
        f"{sum(a['sensor_tipo'] == dominant_sensor for a in items)} ocorrências. {_ref(trend_evidence)}"
    )
    lines.append(
        f"Recomendação preliminar: priorizar a inspeção do {top['equipamento_id']} e validar "
        f"{SENSOR_NAMES[top['sensor_tipo']]} antes de ampliar a carga. {_ref(top)}"
    )
    lines.append("As recomendações são preliminares e não substituem procedimentos de segurança nem diagnóstico em campo.")
    return "\n\n".join(lines)

