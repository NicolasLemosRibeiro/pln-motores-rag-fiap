"""Gera os conjuntos sinteticos e referencias manuais do projeto."""

from __future__ import annotations

import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
RNG = random.Random(42)


SENSORS = {
    "temperatura_enrolamento": ("TMP", "°C", 72.0),
    "vibracao_mancal": ("VIB", " mm/s RMS", 2.2),
    "corrente_fase": ("CUR", " A", 390.0),
    "resistencia_isolamento": ("ISO", " MΩ", 30.0),
    "pressao_oleo": ("PRS", " bar", 3.5),
}


def reference_summary(row: dict) -> str:
    sensor_names = {
        "temperatura_enrolamento": "temperatura dos enrolamentos",
        "vibracao_mancal": "vibração do mancal",
        "corrente_fase": "corrente de fase",
        "resistencia_isolamento": "resistência de isolamento",
        "pressao_oleo": "pressão de óleo",
    }
    urgency = {
        "leve": "Foi observado um desvio leve",
        "moderado": "Foi identificado um alerta moderado",
        "critico": "Foi identificado um alerta crítico",
    }[row["severidade"]]
    direction = "acima" if row["desvio"] >= 0 else "abaixo"
    action = {
        "leve": "Manter o acompanhamento e conferir o item na próxima ronda.",
        "moderado": "Realizar inspeção direcionada e verificar a tendência antes de elevar a carga.",
        "critico": "Priorizar uma parada segura e uma inspeção imediata antes de reenergizar.",
    }[row["severidade"]]
    sign = "+" if row["desvio"] > 0 else ""
    return (
        f"{urgency} no {row['equipamento_id']}: {sensor_names[row['sensor_tipo']]} ficou "
        f"{sign}{row['desvio']:g}{row['unidade']} {direction} da referência durante "
        f"{row['janela_horas']} horas. {action}"
    )


def make_alerts() -> pd.DataFrame:
    base_time = datetime(2026, 8, 18, 6, tzinfo=timezone(timedelta(hours=-3)))
    severity_values = {
        "leve": [8, 9, 10, -6],
        "moderado": [14, 16, 18, -12],
        "critico": [22, 26, 31, -24],
    }
    rows = []
    equipment = ["Motor MT-042", "Motor MT-017", "Motor MT-105"]
    sensor_types = list(SENSORS)
    for i in range(30):
        severity = ["leve", "moderado", "critico"][i % 3]
        sensor_type = sensor_types[i % len(sensor_types)]
        prefix, unit, baseline = SENSORS[sensor_type]
        deviation = float(RNG.choice(severity_values[severity]))
        if sensor_type == "vibracao_mancal":
            deviation = round(deviation / 6, 1)
        elif sensor_type == "corrente_fase":
            deviation = deviation * 2
        elif sensor_type == "resistencia_isolamento":
            deviation = -abs(deviation)
        elif sensor_type == "pressao_oleo":
            deviation = round(-abs(deviation) / 10, 1)
        ts = base_time + timedelta(hours=i * 4)
        row = {
            "alert_id": f"ALT-{i+1:04d}",
            "severidade": severity,
            "equipamento_id": equipment[i % len(equipment)],
            "sensor_tipo": sensor_type,
            "sensor_id": f"{prefix}-{42 + i % 3:03d}-{i%2+1}",
            "desvio": deviation,
            "unidade": unit,
            "baseline": baseline,
            "valor_atual": round(baseline + deviation, 1),
            "janela_horas": [1, 3, 6][i % 3],
            "timestamp": ts.isoformat(),
        }
        row["resumo_referencia"] = reference_summary(row)
        rows.append(row)
    return pd.DataFrame(rows)


EVENT_PATTERNS = {
    "manutenção corretiva": [
        "substituído rolamento após falha confirmada", "reparado cabo rompido e motor liberado",
        "trocado ventilador danificado após parada", "corrigida conexão queimada no borne",
        "executado reparo emergencial no acoplamento", "substituído sensor defeituoso após alarme",
    ],
    "manutenção preventiva": [
        "realizada inspeção preventiva semanal", "executada lubrificação programada dos mancais",
        "limpeza trimestral das entradas de ar", "verificado torque das conexões conforme plano",
        "medida resistência de isolamento na parada programada", "alinhamento conferido na rotina preventiva",
    ],
    "anomalia elétrica": [
        "corrente elevada e desequilíbrio entre fases", "queda de resistência de isolamento do enrolamento",
        "sobretensão intermitente registrada no painel", "borne aquecido com tensão desequilibrada",
        "proteção de sobrecorrente atuou durante partida", "falha elétrica suspeita na fase B",
    ],
    "anomalia mecânica": [
        "vibração elevada no mancal lado acoplado", "ruído metálico e aquecimento do rolamento",
        "desalinhamento observado no acoplamento", "folga mecânica detectada na base",
        "indício de desbalanceamento no espectro", "pressão de óleo baixa no sistema de lubrificação",
    ],
    "operação normal": [
        "motor operando estável dentro do baseline", "correntes equilibradas e temperatura normal",
        "vibração sem alteração durante o turno", "equipamento disponível sem alarmes ativos",
        "partida concluída e parâmetros estabilizados", "ronda sem desvios ou ruídos anormais",
    ],
}


def make_events() -> pd.DataFrame:
    qualifiers = [
        "no Motor MT-042", "durante o turno da manhã", "registrado pelo operador",
        "com ordem de serviço aberta", "após análise de tendência", "no conjunto principal",
    ]
    rows = []
    idx = 1
    for category, patterns in EVENT_PATTERNS.items():
        for i in range(40):
            text = f"{patterns[i % len(patterns)]} {qualifiers[(i * 2 + idx) % len(qualifiers)]}."
            rows.append({"event_id": f"EVT-{idx:04d}", "texto": text, "categoria": category})
            idx += 1
    RNG.shuffle(rows)
    return pd.DataFrame(rows)


def make_qa() -> list[dict]:
    raw = [
        ("TS-01", "O que devo verificar primeiro quando a temperatura do enrolamento aumenta?", "Verifique carga, entradas de ar, ventilador e limpeza das aletas; depois confirme corrente e tensão por fase.", ["Sobretemperatura do enrolamento"], "térmica"),
        ("TS-02", "Quando um alerta de temperatura crítica exige parada?", "Em nível crítico ou com odor de isolamento, execute parada segura imediata.", ["Sobretemperatura do enrolamento", "Segurança, bloqueio e desenergização"], "térmica"),
        ("TS-03", "Quais causas podem provocar desequilíbrio de corrente?", "Tensão desequilibrada, conexão frouxa, contato degradado, problema no enrolamento ou carga anormal.", ["Desequilíbrio de corrente entre fases"], "elétrica"),
        ("TS-04", "Como inspecionar conexões após corrente desequilibrada?", "Desenergize e bloqueie; verifique bornes, torque, aquecimento e continuidade.", ["Desequilíbrio de corrente entre fases", "Procedimento de reaperto elétrico"], "elétrica"),
        ("TS-05", "Posso reenergizar com resistência de isolamento abaixo de 5 MΩ?", "Não. O limite simulado abaixo de 5 MΩ impede retorno ao serviço e requer avaliação elétrica.", ["Limites elétricos", "Baixa resistência de isolamento"], "elétrica"),
        ("TS-06", "O que registrar durante o ensaio de isolamento?", "Registre temperatura e umidade, aplique correção prevista e compare com o histórico.", ["Baixa resistência de isolamento"], "elétrica"),
        ("TS-07", "Quais são as causas comuns de vibração elevada?", "Desbalanceamento, desalinhamento, folga estrutural, ressonância ou degradação do mancal.", ["Vibração elevada no mancal"], "mecânica"),
        ("TS-08", "Quando a vibração elevada requer parada segura?", "Crescimento rápido combinado a ruído metálico ou temperatura alta requer parada segura.", ["Vibração elevada no mancal", "Limites de vibração"], "mecânica"),
        ("TS-09", "Quais sinais indicam falha de mancal?", "Ruído repetitivo, frequências características, aumento de temperatura e partículas no lubrificante.", ["Falha de mancal"], "mecânica"),
        ("TS-10", "Por que não devo adicionar graxa sem diagnóstico?", "Porque excesso de graxa também pode elevar a temperatura do mancal.", ["Falha de mancal", "Lubrificação de mancais"], "mecânica"),
        ("TS-11", "Como verificar desalinhamento com segurança?", "Desenergize o conjunto, verifique base e pé manco e meça desalinhamento paralelo e angular.", ["Desalinhamento do conjunto", "Procedimento de verificação de alinhamento"], "mecânica"),
        ("TS-12", "O que deve ser feito após corrigir o alinhamento?", "Reaperte na sequência definida, repita a medição e registre os valores finais.", ["Procedimento de verificação de alinhamento", "Desalinhamento do conjunto"], "mecânica"),
        ("TS-13", "Quais itens entram na inspeção preventiva semanal?", "Ruído, temperaturas, vibração, corrente por fase, ventilação, cabos e fixações.", ["Inspeção preventiva semanal"], "preventiva"),
        ("TS-14", "Quando abrir ordem mesmo sem ultrapassar o limite?", "Quando houver tendência crescente em duas leituras consecutivas.", ["Inspeção preventiva semanal"], "preventiva"),
        ("TS-15", "O que inclui a manutenção preventiva trimestral?", "Limpeza da ventilação, torque de conexões, acoplamento, alinhamento, base e revisão de tendências.", ["Manutenção preventiva trimestral"], "preventiva"),
        ("TS-16", "Qual é a sequência para inspecionar a refrigeração?", "Autorizar, desenergizar quando necessário, inspecionar e limpar, reinstalar proteções e testar registrando temperatura e corrente.", ["Procedimento de inspeção do sistema de refrigeração"], "térmica"),
        ("TS-17", "Qual torque devo usar no reaperto dos bornes?", "Use o torque definido para o terminal instalado; não há torque universal neste documento.", ["Procedimento de reaperto elétrico"], "elétrica"),
        ("TS-18", "Como substituir um mancal sem danificar o rolamento novo?", "Use ferramenta adequada e aplique força somente no anel que possui ajuste.", ["Procedimento de substituição do mancal"], "mecânica"),
        ("TS-19", "Quais critérios permitem retorno ao serviço após intervenção?", "Proteções fechadas, bloqueios formalmente removidos, testes concluídos e parâmetros estáveis abaixo dos limites.", ["Critérios de retorno ao serviço"], "preventiva"),
        ("TS-20", "Quais dados garantem rastreabilidade da manutenção?", "Ativo, sintoma, diagnóstico, ação, componente/lote, medições antes e depois, responsáveis, horário e origem do alerta.", ["Registro e rastreabilidade da manutenção"], "preventiva"),
    ]
    items = []
    for qid, question, answer, sections, anomaly in raw:
        items.append({
            "id": qid,
            "question": question,
            "reference_answer": answer,
            "relevant_sections": sections,
            "operational_context": {
                "tipo_equipamento": "motor",
                "equipamento_id": "Motor MT-042",
                "tipo_anomalia": anomaly,
                "severidade": "moderado",
            },
        })
    return items


def main() -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    make_alerts().to_csv(DATA / "alertas_teste.csv", index=False, encoding="utf-8-sig")
    make_events().to_csv(DATA / "eventos_rotulados.csv", index=False, encoding="utf-8-sig")
    (DATA / "perguntas_troubleshooting.json").write_text(
        json.dumps(make_qa(), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("Dados gerados em", DATA)


if __name__ == "__main__":
    main()

