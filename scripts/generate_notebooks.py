"""Cria os dois notebooks Colab a partir de celulas versionaveis."""

from __future__ import annotations

from pathlib import Path
import nbformat as nbf


ROOT = Path(__file__).resolve().parents[1]


def notebook(title: str):
    nb = nbf.v4.new_notebook()
    nb["metadata"] = {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python", "version": "3"},
        "colab": {"name": title, "provenance": []},
    }
    return nb


SETUP = """from pathlib import Path
import sys, json

candidates = [Path.cwd(), Path.cwd().parent, Path('/content/pln_motores_rag')]
ROOT = next((p for p in candidates if (p / 'src' / 'pln_motores').exists()), None)
if ROOT is None:
    raise FileNotFoundError('Abra o notebook na raiz do repositório ou clone o projeto em /content/pln_motores_rag.')
sys.path.insert(0, str(ROOT / 'src'))
(ROOT / 'outputs').mkdir(exist_ok=True)
print('Raiz do projeto:', ROOT)
"""


def sprint3():
    nb = notebook("sprint3_pln_alertas.ipynb")
    nb.cells = [
        nbf.v4.new_markdown_cell("""# Sprint 3 — PLN para alertas e estado operacional

Este notebook executa a geração de narrativas para três níveis de urgência, a classificação supervisionada de eventos, a avaliação F1/ROUGE/checklist e um relatório operacional rastreável. Os dados são sintéticos e reproduzíveis."""),
        nbf.v4.new_markdown_cell("""## Preparação

No Colab, clone ou envie a pasta completa do projeto. As dependências centrais são leves. Se necessário, execute `%pip install pandas scikit-learn matplotlib`."""),
        nbf.v4.new_code_cell(SETUP),
        nbf.v4.new_code_cell("""import pandas as pd
import matplotlib.pyplot as plt
from IPython.display import display, Markdown

from pln_motores.alerts import gerar_resumo_alerta
from pln_motores.classification import EventClassifier
from pln_motores.metrics import evaluate_rouge
from pln_motores.reports import gerar_relatorio_operacional

alerts = pd.read_csv(ROOT / 'data' / 'alertas_teste.csv')
events = pd.read_csv(ROOT / 'data' / 'eventos_rotulados.csv')
print(f'{len(alerts)} alertas e {len(events)} eventos carregados.')"""),
        nbf.v4.new_markdown_cell("""## 1. Geração de resumos textuais

Os templates variam tom, vocabulário e recomendação conforme severidade. Toda narrativa inclui alerta e sensor de origem."""),
        nbf.v4.new_code_cell("""alerts['resumo_gerado'] = [gerar_resumo_alerta(row).text for row in alerts.to_dict('records')]
examples = alerts.groupby('severidade', sort=False).head(1)[
    ['severidade', 'equipamento_id', 'sensor_id', 'resumo_gerado']
]
display(examples)"""),
        nbf.v4.new_markdown_cell("""### Avaliação ROUGE e checklist

ROUGE compara os textos com referências redigidas manualmente. O checklist automático verifica clareza operacional, precisão de identificadores, utilidade e rastreabilidade. Uma revisão humana continua necessária."""),
        nbf.v4.new_code_cell("""rouge = evaluate_rouge(alerts['resumo_gerado'].tolist(), alerts['resumo_referencia'].tolist())
check_rows = []
for row in alerts.to_dict('records'):
    text = row['resumo_gerado']
    check_rows.append({
        'alert_id': row['alert_id'],
        'clareza': len(text.split()) <= 75 and '.' in text,
        'precisao': row['equipamento_id'] in text and row['sensor_id'] in text,
        'utilidade': any(t in text.lower() for t in ['verificar', 'acompanhar', 'inspecionar', 'parada', 'isolar']),
        'rastreabilidade': '[Fonte:' in text,
    })
check_df = pd.DataFrame(check_rows)
checklist = check_df.drop(columns='alert_id').mean().to_dict()
display(pd.DataFrame({'ROUGE': rouge}), pd.DataFrame({'Checklist': checklist}))"""),
        nbf.v4.new_markdown_cell("""## 2. Classificação textual de eventos

O classificador é ajustado sobre TF-IDF de unigramas/bigramas e regressão logística balanceada. A separação holdout é estratificada e fixada por semente."""),
        nbf.v4.new_code_cell("""classifier = EventClassifier(random_state=42)
result = classifier.evaluate_holdout(events, test_size=0.25)
f1_table = pd.Series(result.per_category_f1, name='F1').sort_values()
display(f1_table.to_frame())
ax = f1_table.plot.barh(figsize=(8, 3.4), xlim=(0, 1.05), title=f'F1 por categoria — macro F1={result.macro_f1:.3f}')
ax.set_xlabel('F1-score')
plt.tight_layout()
plt.show()"""),
        nbf.v4.new_markdown_cell("""## 3. Relatório operacional rastreável

Cada afirmação factual inclui alerta, sensor, valor e timestamp. As recomendações são preliminares."""),
        nbf.v4.new_code_cell("""report = gerar_relatorio_operacional(alerts.to_dict('records'), periodo='semanal')
display(Markdown(report.replace('\\n\\n', '\\n\\n')))
alerts.to_csv(ROOT / 'outputs' / 'alertas_com_resumos.csv', index=False, encoding='utf-8-sig')
(ROOT / 'outputs' / 'relatorio_operacional.txt').write_text(report, encoding='utf-8')"""),
        nbf.v4.new_markdown_cell("""## 4. Síntese dos resultados e limites

- O conjunto sintético balanceado é adequado à demonstração, mas tende a superestimar o F1.
- ROUGE mede sobreposição lexical e não substitui revisão humana de segurança/clareza.
- Antes de produção, os templates, limites e rótulos devem ser validados com operadores e engenharia de manutenção."""),
        nbf.v4.new_code_cell("""summary = {
    'rouge': rouge,
    'checklist': checklist,
    'macro_f1': result.macro_f1,
    'weighted_f1': result.weighted_f1,
    'f1_por_categoria': result.per_category_f1,
}
print(json.dumps(summary, ensure_ascii=False, indent=2))"""),
    ]
    return nb


def sprint4():
    nb = notebook("sprint4_pln_rag.ipynb")
    nb.cells = [
        nbf.v4.new_markdown_cell("""# Sprint 4 — RAG e assistente de troubleshooting

Pipeline completo: chunking por estrutura técnica, embeddings e índice vetorial, recuperação com re-ranking operacional, prompt fundamentado, memória curta, avaliação sobre 20 perguntas e três cenários de falha."""),
        nbf.v4.new_markdown_cell("""## Preparação e opções de backend

O modo padrão usa vetores TF-IDF e índice `NearestNeighbors`, suficiente para execução offline. A avaliação Colab versionada utilizou Sentence Transformers, FAISS e Qwen 3B em GPU T4. O assistente valida a saída do LLM, tenta revisão automática e usa fallback rastreável quando a resposta não passa nos guardrails."""),
        nbf.v4.new_code_cell(SETUP),
        nbf.v4.new_code_cell("""import json
import pandas as pd
from IPython.display import display, Markdown

from pln_motores.rag import TechnicalRAG, chunk_markdown
from pln_motores.assistant import TroubleshootingAssistant, SYSTEM_PROMPT
from pln_motores.llm_backends import qwen_local, openai_compatible

qa = json.loads((ROOT / 'data' / 'perguntas_troubleshooting.json').read_text(encoding='utf-8'))
print('Perguntas de avaliação:', len(qa))"""),
        nbf.v4.new_markdown_cell("""## 1. Chunking inteligente

Os cabeçalhos são preservados como metadados. Seções longas são divididas por parágrafos com pequena sobreposição, sem cortar arbitrariamente uma instrução."""),
        nbf.v4.new_code_cell("""documents = sorted((ROOT / 'data' / 'documentos_tecnicos').glob('*.md'))
chunks = [chunk for doc in documents for chunk in chunk_markdown(doc)]
display(pd.DataFrame([c.to_dict() for c in chunks])[
    ['chunk_id', 'document', 'heading', 'equipment_types', 'anomaly_types']
].head(10))
print('Total de chunks:', len(chunks))"""),
        nbf.v4.new_markdown_cell("""## 2. Embeddings, indexação e retriever

O score final combina similaridade vetorial do texto, similaridade do cabeçalho, cobertura lexical e bônus de metadados do estado atual. Isso permite priorizar, por exemplo, segurança e parada para um alerta crítico."""),
        nbf.v4.new_code_cell("""USE_SEMANTIC_EMBEDDINGS = False  # True no Colab com internet/GPU
embedding_model = 'sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2' if USE_SEMANTIC_EMBEDDINGS else None
rag = TechnicalRAG(embedding_model=embedding_model).build(ROOT / 'data' / 'documentos_tecnicos')
print('Backend:', rag.backend)

sample = rag.retrieve(
    'A vibração subiu com ruído metálico. O que fazer?',
    {'tipo_equipamento': 'motor', 'tipo_anomalia': 'mecânica', 'severidade': 'critico'},
    top_k=4,
)
display(pd.DataFrame(sample)[['document', 'heading', 'base_score', 'heading_score', 'score']])"""),
        nbf.v4.new_markdown_cell("""### Qualidade da recuperação

O gabarito associa cada pergunta a uma ou mais seções relevantes. Reportamos Precision@1, Precision@4, Hit@4 e MRR."""),
        nbf.v4.new_code_cell("""retrieval_metrics = rag.evaluate_retrieval(qa, top_k=4)
display(pd.Series({k: v for k, v in retrieval_metrics.items() if k != 'details'}, name='valor').to_frame())"""),
        nbf.v4.new_markdown_cell("""## 3. Assistente conversacional

O prompt exige persona técnica, fundamentação, citação, confiança, abstenção e segurança. A memória guarda somente os quatro turnos mais recentes. O guardrail rejeita citações inválidas, baixa sustentação, abstenção indevida, procedimentos temporais incorretos e contradições de parada segura."""),
        nbf.v4.new_code_cell("""print(SYSTEM_PROMPT)

LLM_BACKEND = 'extractive'  # 'extractive', 'qwen' ou 'api'
if LLM_BACKEND == 'qwen':
    # Requer: %pip install transformers accelerate torch
    llm = qwen_local(
        'Qwen/Qwen2.5-3B-Instruct',
        max_new_tokens=320,
        system_prompt=SYSTEM_PROMPT,
    )
elif LLM_BACKEND == 'api':
    # Defina OPENAI_API_KEY e ajuste o modelo/base_url conforme o provedor.
    llm = openai_compatible(model='SEU_MODELO', base_url=None)
else:
    llm = None

assistant = TroubleshootingAssistant(rag, llm=llm, memory_turns=4)"""),
        nbf.v4.new_markdown_cell("""## 4. Três cenários demonstrativos"""),
        nbf.v4.new_code_cell("""scenarios = [
    ('Anomalia elétrica', 'A corrente das fases está desequilibrada. O que verifico e quando devo parar?', {
        'tipo_equipamento': 'motor', 'equipamento_id': 'Motor MT-042', 'tipo_anomalia': 'elétrica',
        'sensor_tipo': 'corrente_fase', 'severidade': 'moderado',
        'resumo_alerta': 'Alerta moderado: corrente 12% acima do equilíbrio esperado no sensor CUR-042-1.'}),
    ('Anomalia mecânica', 'A vibração do mancal subiu e surgiu ruído metálico. Qual é a ação segura?', {
        'tipo_equipamento': 'motor', 'equipamento_id': 'Motor MT-042', 'tipo_anomalia': 'mecânica',
        'sensor_tipo': 'vibracao_mancal', 'severidade': 'critico',
        'resumo_alerta': 'Alerta crítico: vibração 8,1 mm/s RMS no sensor VIB-042-1.'}),
    ('Manutenção preventiva', 'Quais verificações devo executar na manutenção trimestral?', {
        'tipo_equipamento': 'motor', 'equipamento_id': 'Motor MT-042', 'tipo_anomalia': 'preventiva',
        'severidade': 'leve', 'resumo_alerta': 'Tendência leve de temperatura nas duas últimas rondas.'}),
]

for name, question, context in scenarios:
    assistant.history.clear()
    result = assistant.ask(question, context, top_k=3)
    display(Markdown(
        f'### {name}\\n\\n**Pergunta:** {question}\\n\\n**Resposta:** {result["answer"]}'
        f'\\n\\n**Modo de geração:** `{result["generation_mode"]}`'
    ))"""),
        nbf.v4.new_markdown_cell("""## 5. Avaliação conversacional

As métricas locais são auditáveis: faithfulness verifica suporte sentencial no documento/contexto operacional; answer relevancy combina cobertura do gabarito e cosseno TF-IDF; context precision compara as seções recuperadas ao gabarito. RAGAS ou avaliação por especialistas deve complementar esses proxies."""),
        nbf.v4.new_code_cell("""assistant_metrics = assistant.evaluate(qa, top_k=3)
display(pd.Series({k: v for k, v in assistant_metrics.items() if k not in ['details', 'method_note']}, name='valor').to_frame())
print(assistant_metrics['method_note'])"""),
        nbf.v4.new_markdown_cell("""### Execução semântica com Qwen 3B e guardrails

Os artefatos abaixo foram gerados em Google Colab com GPU T4, Sentence Transformers + FAISS, `Qwen/Qwen2.5-3B-Instruct`, `top_k=3` e validação pós-geração. Eles preservam as 20 respostas, os três cenários e a demonstração de memória."""),
        nbf.v4.new_code_cell("""qwen_metrics = json.loads((ROOT / 'outputs' / 'metricas_qwen_hibrido.json').read_text(encoding='utf-8'))
qwen_evaluation = json.loads((ROOT / 'outputs' / 'avaliacao_qwen_hibrido.json').read_text(encoding='utf-8'))
qwen_demo = json.loads((ROOT / 'outputs' / 'demonstracao_qwen_hibrido.json').read_text(encoding='utf-8'))

display(pd.Series({
    'Precision@1': qwen_metrics['precision_at_1'],
    'Hit@3': qwen_metrics['hit_at_3'],
    'MRR': qwen_metrics['mrr'],
    'Context precision@3': qwen_metrics['context_precision'],
    'Faithfulness': qwen_metrics['faithfulness'],
    'Answer relevancy': qwen_metrics['answer_relevancy'],
}, name='valor').to_frame())
display(pd.Series(qwen_metrics['generation_modes'], name='respostas').to_frame())
print('Memória injetada:', qwen_demo['demonstracao_memoria']['memoria_anterior_injetada'])
print('Turnos armazenados:', qwen_demo['demonstracao_memoria']['turnos_armazenados'])

display(pd.DataFrame(qwen_evaluation)[
    ['id', 'generation_mode', 'faithfulness', 'answer_relevancy', 'context_precision']
])

for item in qwen_demo['cenarios']:
    display(Markdown(
        f'#### {item["cenario"].capitalize()} — execução Qwen protegida'
        f'\\n\\n**Contexto:** {item["contexto"]["resumo_alerta"]}'
        f'\\n\\n**Resposta final:** {item["answer"]}'
        f'\\n\\n**Modo:** `{item["generation_mode"]}`'
    ))

memory = qwen_demo['demonstracao_memoria']
display(Markdown(
    f'#### Continuação com memória'
    f'\\n\\n**Pergunta:** {memory["pergunta_continuacao"]}'
    f'\\n\\n**Resposta:** {memory["answer"]}'
))"""),
        nbf.v4.new_markdown_cell("""## 6. Limites e teste de abstenção

O corpus é sintético e restrito. O sistema não autoriza intervenção, não inventa valores ausentes e deve declarar insuficiência quando a evidência é fraca."""),
        nbf.v4.new_code_cell("""assistant.history.clear()
outside = assistant.ask('Qual é o torque exato do terminal de um motor de outra marca, modelo ZX-900?', {'tipo_equipamento': 'motor'})
display(Markdown(outside['answer']))"""),
    ]
    return nb


def main():
    nbf.write(sprint3(), ROOT / "sprint3_pln_alertas.ipynb")
    nbf.write(sprint4(), ROOT / "sprint4_pln_rag.ipynb")
    print("Notebooks gerados.")


if __name__ == "__main__":
    main()
