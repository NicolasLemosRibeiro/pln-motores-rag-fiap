# Limites e estratégias de mitigação

## Escopo conhecido

O corpus demonstra somente motores elétricos MT Série 040 e utiliza documentos, limites e dados sintéticos. A solução não deve ser usada para comandar equipamentos, autorizar trabalho energizado ou substituir documentação do fabricante, normas, análise de risco e profissionais habilitados.

## Situações fora do escopo

- Perguntas sobre outros ativos, marcas, tensões ou componentes não presentes no corpus.
- Definição de torque, tolerância ou limite que não esteja explicitamente documentado.
- Diagnóstico conclusivo a partir de um único sensor.
- Instruções para burlar bloqueio, proteção ou intertravamento.
- Decisões autônomas de parada, partida ou retorno ao serviço.

## Falhas e alucinações observáveis

- Um LLM pode combinar dois procedimentos corretos em uma sequência incorreta.
- Termos próximos, como temperatura de mancal e de enrolamento, podem ser confundidos.
- Um contexto operacional muito longo pode suprimir uma ressalva de segurança.
- Métricas automáticas podem considerar uma paráfrase plausível como correta mesmo quando falta uma condição importante.
- Na execução real, o Qwen omitiu citações, inferiu ações não realizadas e chegou a negar uma parada segura exigida pelo manual para vibração com ruído metálico.
- O proxy lexical de faithfulness aprovou inicialmente uma resposta semanticamente contraditória, demonstrando que sobreposição de palavras não é suficiente para validar segurança.

## Mitigações implementadas

- Prompt restritivo, citações obrigatórias e nível de confiança.
- Resposta explícita de insuficiência quando a recuperação é fraca.
- Filtro e re-ranking pelo tipo de anomalia, equipamento, sensor e severidade.
- Memória curta limitada aos últimos quatro turnos.
- Rastreabilidade até alerta, sensor, timestamp, documento e seção.
- Fallback extrativo para demonstração sem API, reduzindo liberdade de geração.
- Conjunto de 20 perguntas com gabarito e seções relevantes.
- Chat template oficial do Qwen e contrato de saída com estrutura e citações obrigatórias.
- Validação pós-geração de citações, sustentação, abstenção indevida, ações temporais e critérios de parada segura.
- Segunda tentativa automática e fallback rastreável quando o LLM continua reprovado; na avaliação, 14 de 20 respostas acionaram esse fallback.

## Mitigações recomendadas para produção

- Substituir o corpus sintético por documentos controlados e versionados.
- Validar respostas e gabaritos com engenharia de manutenção e segurança.
- Implementar controle de acesso, logging, versionamento de prompts e trilha de auditoria.
- Adotar testes adversariais, avaliação humana periódica e limiar de abstenção calibrado.
- Usar RAGAS ou avaliador independente como complemento, nunca como única evidência de qualidade.
