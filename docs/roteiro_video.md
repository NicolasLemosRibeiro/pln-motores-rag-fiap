# Roteiro do vídeo demonstrativo (3 a 5 minutos)

## 0:00-0:30 — Abertura

Apresente o objetivo: converter sinais numéricos em narrativas rastreáveis e usar o estado operacional como contexto de um assistente RAG fundamentado em documentos técnicos.

## 0:30-1:05 — Sprint 3

Execute as células de carregamento e geração de alertas. Mostre um alerta leve, um moderado e um crítico. Destaque equipamento, magnitude, janela, recomendação e referência do sensor. Exiba F1 por categoria, ROUGE e um trecho do relatório operacional.

## 1:05-1:35 — Arquitetura RAG

Mostre o chunking por cabeçalhos, o backend Sentence Transformers + FAISS e um exemplo de recuperação. Explique o re-ranking com tipo de anomalia, sensor, equipamento e severidade. Apresente o Qwen 3B e o fluxo de guardrail: geração, validação, revisão e fallback.

## 1:35-2:20 — Cenário 1: anomalia elétrica

Pergunta: “A corrente das fases está desequilibrada. O que verifico e quando devo parar?” Execute a pergunta no assistente. Mostre o alerta de 12%, a regra documental acima de 10%, as citações e o modo de geração registrado.

## 2:20-3:05 — Cenário 2: anomalia mecânica

Pergunta: “A vibração do mancal subiu e surgiu ruído metálico. Qual é a ação segura?” Mostre a parada segura e explique que uma tentativa do LLM negou esse critério, foi detectada pelo guardrail e substituída por resposta rastreável.

## 3:05-3:45 — Cenário 3: manutenção preventiva

Pergunta: “Quais verificações devo executar na manutenção trimestral?” Mostre a lista fundamentada, a fonte e o nível de confiança. Em seguida, pergunte “E o que devo registrar ao concluir essa manutenção?” e mostre que o turno anterior foi injetado na memória.

## 3:45-4:25 — Limites

Mostre as métricas finais: Precision@1 0,900; Hit@3 1,000; MRR 0,950; faithfulness 0,724; answer relevancy 0,572. Explique que 3 respostas foram aceitas diretamente, 3 após revisão e 14 usaram fallback. Faça uma pergunta fora do escopo e destaque corpus sintético, proxies e necessidade de validação de engenharia.

## 4:25-4:40 — Encerramento

Mostre os dois notebooks, os JSONs da execução Qwen e o relatório final. Após gravar a tela, publique como “não listado” no YouTube e substitua o marcador do README pelo link.
