# Solução de PLN para Alertas Operacionais e Troubleshooting RAG

## Resumo executivo

O projeto consolida as Sprints 3 e 4 em uma solução reproduzível para motores elétricos. A primeira frente transforma alertas numéricos em português técnico acessível, classifica registros em cinco categorias e produz relatórios com referência ao sensor de origem. A segunda frente indexa documentação técnica por seções coerentes, recupera evidências com re-ranking sensível ao estado do equipamento e responde perguntas com fonte, confiança e memória curta.

Todos os dados e documentos são sintéticos. A implementação é uma prova de conceito acadêmica e não autoriza atuação em ativos reais.

## Dados e rastreabilidade

O conjunto contém 30 alertas distribuídos entre níveis leve, moderado e crítico; 200 eventos balanceados nas cinco categorias; três documentos técnicos; 24 chunks; e 20 perguntas com respostas de referência e seções relevantes. Um alerta preserva `alert_id`, `sensor_id`, equipamento, timestamp, baseline, valor atual, desvio e unidade. Relatórios citam alerta, sensor, valor e horário em cada afirmação factual.

## Sprint 3 — geração e classificação

### Templates de narrativa

O nível leve usa tom de acompanhamento e ação de ronda. O moderado destaca desvio, janela e inspeção direcionada. O crítico usa vocabulário explícito de risco, parada segura ou isolamento, sem sugerir intervenção energizada. As recomendações variam por temperatura do enrolamento, vibração de mancal, corrente de fase, resistência de isolamento e pressão de óleo.

### Critérios de classificação

- Manutenção corretiva: reparo ou substituição após falha.
- Manutenção preventiva: atividade programada, inspeção, limpeza, lubrificação ou ensaio periódico.
- Anomalia elétrica: corrente, tensão, fase, isolamento, borne ou proteção elétrica.
- Anomalia mecânica: vibração, ruído, mancal, alinhamento, folga ou lubrificação.
- Operação normal: estabilidade, disponibilidade e ausência de desvios.

O modelo é uma regressão logística balanceada treinada sobre TF-IDF de unigramas e bigramas, com holdout estratificado de 25%.

### Resultados da Sprint 3

O classificador obteve macro F1 e F1 ponderado de 1,000; cada categoria teve F1 de 1,000. O resultado reflete a regularidade do conjunto sintético e não representa desempenho esperado em produção. Os resumos alcançaram ROUGE-1 0,419, ROUGE-2 0,246 e ROUGE-L 0,386. O checklist automático registrou 100% em clareza, precisão de identificadores e rastreabilidade, e 80% em utilidade lexical.

## Sprint 4 — arquitetura RAG

O chunking inicia em cabeçalhos Markdown, agrega parágrafos até 1.200 caracteres e usa sobreposição de 160 caracteres somente quando uma seção excede o limite. Cada chunk mantém documento, cabeçalho, tipos de equipamento e anomalia.

O modo offline executado gera vetores TF-IDF e constrói índice `NearestNeighbors` por cosseno. O modo semântico opcional utiliza `paraphrase-multilingual-MiniLM-L12-v2` e FAISS quando instalado. O re-ranking combina 50% de similaridade do conteúdo, 30% de similaridade do cabeçalho, 20% de cobertura lexical e bônus reduzidos por anomalia, equipamento e severidade.

## Assistente conversacional

O prompt define a persona de especialista em motores, limita respostas ao contexto, exige citações no formato `[documento > seção]`, nível de confiança e abstenção quando a evidência é insuficiente. A memória guarda quatro turnos. O contexto adicional inclui resumo do alerta, equipamento, sensor, tipo de anomalia e severidade.

O baseline permanece extrativo e auditável. A execução no Colab usou Sentence Transformers, FAISS e `Qwen/Qwen2.5-3B-Instruct` em GPU T4. O backend aplica o chat template oficial e uma camada de guardrails: valida citações, sustentação documental, abstenção indevida, cobertura de procedimentos e contradições de segurança; quando necessário, tenta revisão automática e usa fallback extrativo rastreável.

## Avaliação RAG

No baseline offline, o retriever alcançou Precision@1 de 0,850, Hit@4 de 1,000 e MRR de 0,917. Na execução semântica do Colab, com `top_k=3`, alcançou Precision@1 de 0,900, Hit@3 de 1,000, MRR de 0,950 e context precision de 0,400.

O baseline extrativo obteve faithfulness proxy de 0,887 e answer relevancy de 0,485. O assistente Qwen 3B protegido obteve faithfulness de 0,724 e answer relevancy de 0,572. Das 20 respostas finais, 3 foram aceitas diretamente do LLM, 3 foram aceitas após revisão automática e 14 acionaram o fallback rastreável. A queda de faithfulness frente ao baseline evidencia a liberdade adicional do LLM; o aumento de relevância e os bloqueios registrados mostram o efeito do pipeline híbrido. As métricas são proxies locais e devem ser complementadas por RAGAS, avaliação independente e revisão de especialistas.

## Cenários demonstrados

### Anomalia elétrica

Um alerta moderado de desequilíbrio de corrente direciona a recuperação para causas elétricas, medições das três fases, bornes, torque, aquecimento e continuidade, sempre com desenergização para acesso interno.

### Anomalia mecânica

Vibração crítica acompanhada de ruído metálico prioriza a seção de vibração de mancal e orienta parada segura, inspeção de base, acoplamento e mancal.

### Manutenção preventiva

A consulta trimestral recupera limpeza da ventilação, torque das conexões, acoplamento, alinhamento, base, tendências e inspeções com o motor desenergizado.

## Limites e mitigação

O corpus cobre somente motores MT Série 040 simulados. O sistema não define torques ou limites ausentes, não diagnostica conclusivamente com um único sensor e não controla ativos. Nos testes, o Qwen chegou a omitir citações, inventar estado operacional e negar um critério documental de parada segura. As mitigações implementadas incluem prompt restritivo, citações e confiança obrigatórias, validação pós-geração, rejeição de contradições de segurança, revisão automática, fallback extrativo, memória curta e rastreabilidade.

Para produção, é necessário substituir o corpus, validar com engenharia e segurança, controlar acesso, versionar documentos/prompts, auditar respostas, calibrar limiar de abstenção e conduzir testes adversariais.

## Reprodução e demonstração

Os dois notebooks preservam saídas reproduzíveis, e os artefatos `avaliacao_qwen_hibrido.json`, `metricas_qwen_hibrido.json` e `demonstracao_qwen_hibrido.json` registram a execução realizada no Colab. A memória foi demonstrada com pergunta de continuação e dois turnos armazenados.
