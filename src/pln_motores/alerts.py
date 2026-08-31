"""Geracao deterministica e rastreavel de narrativas de alerta."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping


SEVERITY_LABELS = {
    "leve": "Atenção: desvio leve",
    "moderado": "Alerta moderado",
    "critico": "ALERTA CRÍTICO",
}

RECOMMENDATIONS = {
    "temperatura_enrolamento": {
        "leve": "Acompanhar a tendência e confirmar a ventilação do motor na próxima ronda.",
        "moderado": "Recomenda-se verificar o sistema de refrigeração e a carga aplicada.",
        "critico": "Reduzir a carga com segurança e inspecionar imediatamente refrigeração, enrolamentos e proteções térmicas.",
    },
    "vibracao_mancal": {
        "leve": "Acompanhar a tendência e verificar fixações na próxima inspeção.",
        "moderado": "Recomenda-se inspecionar alinhamento, fixações e condição dos mancais.",
        "critico": "Planejar parada segura imediata e verificar mancais, alinhamento e possível desbalanceamento.",
    },
    "corrente_fase": {
        "leve": "Confirmar estabilidade da carga e equilíbrio entre fases.",
        "moderado": "Recomenda-se medir o desequilíbrio entre fases e revisar conexões elétricas.",
        "critico": "Isolar o equipamento conforme procedimento e inspecionar alimentação, conexões e proteção contra sobrecorrente.",
    },
    "resistencia_isolamento": {
        "leve": "Programar nova medição de isolamento e acompanhar a tendência.",
        "moderado": "Recomenda-se inspecionar umidade, contaminação e integridade do isolamento.",
        "critico": "Não reenergizar antes da avaliação elétrica e do teste de isolamento conforme procedimento aplicável.",
    },
    "pressao_oleo": {
        "leve": "Acompanhar a tendência e confirmar o nível do lubrificante.",
        "moderado": "Recomenda-se verificar nível, vazamentos e circuito de lubrificação.",
        "critico": "Executar parada segura e verificar imediatamente o sistema de lubrificação.",
    },
}

SENSOR_NAMES = {
    "temperatura_enrolamento": "temperatura do enrolamento",
    "vibracao_mancal": "vibração do mancal",
    "corrente_fase": "corrente de fase",
    "resistencia_isolamento": "resistência de isolamento",
    "pressao_oleo": "pressão do óleo",
}


@dataclass(frozen=True)
class AlertNarrative:
    text: str
    trace_id: str
    severity: str


def _signed(value: float, unit: str) -> str:
    sign = "+" if value > 0 else ""
    return f"{sign}{value:g}{unit}"


def _format_timestamp(value: Any) -> str:
    if isinstance(value, datetime):
        dt = value
    else:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return dt.strftime("%d/%m/%Y às %H:%M")


def gerar_resumo_alerta(alerta: Mapping[str, Any], incluir_rastreabilidade: bool = True) -> AlertNarrative:
    """Converte os parametros de um alerta em narrativa tecnica em portugues.

    Campos obrigatorios: alert_id, severidade, equipamento_id, sensor_tipo,
    sensor_id, desvio, unidade, janela_horas e timestamp.
    """
    required = {
        "alert_id", "severidade", "equipamento_id", "sensor_tipo", "sensor_id",
        "desvio", "unidade", "janela_horas", "timestamp",
    }
    missing = sorted(required.difference(alerta))
    if missing:
        raise ValueError(f"Campos obrigatórios ausentes: {', '.join(missing)}")

    severity = str(alerta["severidade"]).lower()
    sensor_type = str(alerta["sensor_tipo"])
    if severity not in SEVERITY_LABELS:
        raise ValueError(f"Severidade inválida: {severity}")
    if sensor_type not in SENSOR_NAMES:
        raise ValueError(f"Tipo de sensor não suportado: {sensor_type}")

    title = SEVERITY_LABELS[severity]
    sensor_name = SENSOR_NAMES[sensor_type]
    deviation = _signed(float(alerta["desvio"]), str(alerta["unidade"]))
    direction = "acima" if float(alerta["desvio"]) >= 0 else "abaixo"
    recommendation = RECOMMENDATIONS[sensor_type][severity]
    timestamp = _format_timestamp(alerta["timestamp"])
    trace_id = f"{alerta['alert_id']}|{alerta['sensor_id']}|{alerta['timestamp']}"

    if severity == "leve":
        text = (
            f"{title} no {alerta['equipamento_id']}. A {sensor_name} variou {deviation} "
            f"{direction} do baseline nas últimas {int(alerta['janela_horas'])} horas, "
            f"com registro em {timestamp}. {recommendation}"
        )
    elif severity == "moderado":
        text = (
            f"{title} detectado no {alerta['equipamento_id']}. A {sensor_name} apresentou "
            f"desvio de {deviation} {direction} do baseline nas últimas "
            f"{int(alerta['janela_horas'])} horas, com registro em {timestamp}. {recommendation}"
        )
    else:
        text = (
            f"{title} no {alerta['equipamento_id']}: a {sensor_name} atingiu desvio de "
            f"{deviation} {direction} do baseline nas últimas {int(alerta['janela_horas'])} horas "
            f"({timestamp}). Há risco de dano ou indisponibilidade. {recommendation}"
        )

    if incluir_rastreabilidade:
        text += f" [Fonte: alerta {alerta['alert_id']}; sensor {alerta['sensor_id']}]"
    return AlertNarrative(text=text, trace_id=trace_id, severity=severity)

