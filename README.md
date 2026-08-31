# PLN Industrial — Alertas e Troubleshooting RAG

Projeto demonstrável das Sprints 3 e 4 para motores elétricos: geração de narrativas de alertas, classificação de eventos, relatório operacional rastreável e assistente conversacional fundamentado em documentação técnica.

> Aviso: todos os documentos, limites e dados deste repositório são sintéticos. Eles não substituem manuais do fabricante, normas, procedimentos locais ou avaliação de profissionais habilitados.

## Entregáveis

- `sprint3_pln_alertas.ipynb`: resumos leve/moderado/crítico, classificador, F1, ROUGE, checklist e relatório.
- `sprint4_pln_rag.ipynb`: chunking, embeddings, índice vetorial, retriever com re-ranking, assistente, memória, 20 perguntas e três cenários.
- `data/alertas_teste.csv`: 30 alertas e resumos de referência.
- `data/eventos_rotulados.csv`: 200 eventos em cinco categorias.
- `data/perguntas_troubleshooting.json`: 20 perguntas, respostas e seções relevantes.
- `data/documentos_tecnicos/`: manual, datasheet e ficha de manutenção sintéticos.
- `docs/relatorio_final_unificado.docx`: documento técnico final.
- `docs/relatorio_final_unificado.md`: versão textual do relatório.
- `outputs/`: resultados e métricas reproduzidos, incluindo a execução Qwen 3B com guardrails no Colab.

## Execução local

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python scripts\generate_data.py
python scripts\run_sprint3.py
python scripts\run_sprint4.py
python -m pytest -q
```

Os notebooks já foram executados e salvos com as saídas. Para execução offline rápida, o RAG usa vetores TF-IDF e índice `NearestNeighbors`. A execução registrada no Colab utilizou `paraphrase-multilingual-MiniLM-L12-v2`, FAISS e `Qwen/Qwen2.5-3B-Instruct` em GPU T4.

Para instalar também os backends semânticos e de LLM no Colab, use `python -m pip install -r requirements-colab.txt`.

## Opções de LLM

O notebook da Sprint 4 oferece três backends:

1. `extractive`: fallback determinístico, offline e com baixa liberdade de geração.
2. `qwen`: `Qwen/Qwen2.5-3B-Instruct` via Transformers no Colab, com chat template oficial.
3. `api`: endpoint compatível com o SDK OpenAI, configurado por variável de ambiente.

O modo Qwen usa um guardrail híbrido: valida citações, sustentação documental, abstenção indevida e contradições de segurança; tenta uma revisão e recorre ao fallback extrativo quando a resposta continua reprovada. Chaves nunca devem ser gravadas no notebook ou no repositório.

## Resultados reproduzidos

- Classificação: macro F1 `1,000` no holdout sintético de 50 eventos.
- Resumos: ROUGE-1 `0,419`, ROUGE-2 `0,246`, ROUGE-L `0,386`.
- Baseline offline: Precision@1 `0,850`, Hit@4 `1,000`, MRR `0,917`, faithfulness `0,887` e answer relevancy `0,485`.
- Colab semântico + Qwen 3B protegido: Precision@1 `0,900`, Hit@3 `1,000`, MRR `0,950`, context precision@3 `0,400`, faithfulness `0,724` e answer relevancy `0,572`.
- Modos finais nas 20 perguntas: 3 respostas diretas do LLM, 3 revisadas automaticamente e 14 respostas pelo fallback após reprovação do LLM.

O F1 perfeito não deve ser extrapolado para produção: os eventos são sintéticos, balanceados e linguisticamente mais regulares que registros reais.

## Demonstração

As execuções dos três cenários e da conversa com memória estão preservadas no notebook da Sprint 4 e em `outputs/demonstracao_qwen_hibrido.json`.

## Estrutura

```text
pln_motores_rag/
├── sprint3_pln_alertas.ipynb
├── sprint4_pln_rag.ipynb
├── data/
├── docs/
├── outputs/
├── scripts/
├── src/pln_motores/
└── tests/
```
