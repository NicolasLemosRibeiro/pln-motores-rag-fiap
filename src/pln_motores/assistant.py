"""Assistente de troubleshooting fundamentado, com memoria curta."""

from __future__ import annotations

import re
from collections import deque
from typing import Any, Callable

import numpy as np

from .metrics import PORTUGUESE_STOPWORDS, answer_relevancy, sentence_support


SYSTEM_PROMPT = """Você é um assistente técnico especialista em motores elétricos.
Responda em português técnico claro, somente com base no contexto documental e operacional fornecido.
Não invente estado, ação já executada, dimensão do motor, valor, limite, causa ou diagnóstico.
Não trate severidade como nível de confiança. A confiança depende apenas da suficiência das evidências.
Priorize segurança: não instrua intervenção energizada e não substitua procedimentos locais.
Responda diretamente à pergunta, distinguindo verificações recomendadas de critérios de parada.
Cite somente fontes efetivamente usadas, no formato exato [arquivo > seção].
Se faltar evidência, declare explicitamente que não há informação suficiente.
Finalize exatamente com: Confiança: alta, média ou baixa — justificativa breve baseada nas evidências."""


class TroubleshootingAssistant:
    def __init__(self, rag, llm: Callable[[str], str] | None = None, memory_turns: int = 4):
        self.rag = rag
        self.llm = llm
        self.history: deque[tuple[str, str]] = deque(maxlen=memory_turns)

    def _prompt(self, question: str, results: list[dict[str, Any]], operational_context: dict[str, Any]) -> str:
        history = "\n".join(f"Operador: {q}\nAssistente: {a}" for q, a in self.history) or "Sem histórico."
        docs = "\n\n".join(
            f"FONTE {i+1}: [{r['document']} > {r['heading']}]\n{r['text']}" for i, r in enumerate(results)
        )
        output_contract = """CONTRATO OBRIGATÓRIO DE SAÍDA:
- Use no máximo 180 palavras.
- Não crie uma seção de notas e não acrescente recomendações para outros equipamentos.
- Não afirme que uma ação já ocorreu se o contexto não disser isso.
- Toda orientação factual deve ter uma citação de uma fonte recuperada no mesmo parágrafo.
- Se a pergunta pedir critério de parada e a documentação não definir parada imediata para a condição, diga isso explicitamente.
- Use exatamente estes rótulos, nesta ordem:
Situação atual:
Verificações recomendadas:
Critério de parada:
Confiança: alta, média ou baixa — justificativa baseada nas evidências."""
        return (
            f"{SYSTEM_PROMPT}\n\nCONTEXTO OPERACIONAL:\n{operational_context}\n\n"
            f"HISTÓRICO RECENTE:\n{history}\n\nDOCUMENTOS RECUPERADOS:\n{docs}\n\n"
            f"{output_contract}\n\nPERGUNTA DO OPERADOR: {question}\nRESPOSTA:"
        )

    @staticmethod
    def _unsupported_identifiers(
        question: str,
        results: list[dict[str, Any]],
        operational_context: dict[str, Any],
    ) -> list[str]:
        """Identifica modelos/codigos citados que nao aparecem nas evidencias."""
        identifiers = re.findall(r"\b[A-Z]{2,}(?:-[A-Z0-9]+|\d{2,})\b", question.upper())
        evidence = " ".join(
            [str(operational_context)]
            + [f"{item['document']} {item['heading']} {item['text']}" for item in results]
        ).upper()
        return [identifier for identifier in identifiers if identifier not in evidence]

    def _grounded_fallback(self, question: str, results: list[dict[str, Any]], operational_context: dict[str, Any]) -> str:
        if not results or results[0]["score"] < 0.04:
            return "Não há informação suficiente nos documentos recuperados para responder com segurança. Confiança: baixa — evidência documental insuficiente."
        query_terms = set(re.findall(r"[a-zà-ÿ0-9]+", question.lower())).difference(
            PORTUGUESE_STOPWORDS | {"não", "sem", "devo", "porque", "após"}
        )
        situation_text = f"{question} {operational_context.get('resumo_alerta', '')}".lower()
        temporal_intent = any(term in question.lower() for term in ["após", "depois", "ao concluir", "ao finalizar"])
        safety_trigger = any(
            trigger in situation_text
            for trigger in ["ruído metálico", "fumaça", "odor de isolamento", "proteção repetida"]
        )
        stop_intent = (
            bool(query_terms & {"parar", "parada", "desligar", "interromper"})
            or str(operational_context.get("severidade", "")).lower() == "critico"
            or safety_trigger
        )
        if stop_intent:
            query_terms.update({"parada", "reduzir", "carga", "segura", "imediata"})

        candidates = []
        for source_rank, source in enumerate(results):
            sentences = [
                s.strip() for s in re.split(r"(?<=[.!?])\s+", source["text"].replace("\n", " "))
                if len(s.split()) > 4
            ]
            for sentence_rank, sentence in enumerate(sentences):
                terms = set(re.findall(r"[a-zà-ÿ0-9]+", sentence.lower()))
                lexical = len(query_terms & terms) / max(1, len(query_terms))
                stop_score = 0.35 if stop_intent and terms & {"parada", "reduzir", "carga", "imediata"} else 0.0
                temporal_score = (
                    1.00
                    if temporal_intent and any(term in sentence.lower() for term in ["após", "depois", "retorno"])
                    else 0.0
                )
                candidates.append({
                    "sentence": sentence,
                    "source": source,
                    "lexical": lexical,
                    "source_rank": source_rank,
                    "sentence_rank": sentence_rank,
                    "score": lexical + 0.25 * float(source["score"]) + stop_score + temporal_score,
                    "temporal_score": temporal_score,
                    "stop": bool(terms & {"parada", "parar", "reduzir", "imediata"}),
                })
        embedding_model = getattr(self.rag, "embedding_model", None)
        if embedding_model is not None and candidates:
            selection_query = f"{question} {operational_context.get('sensor_tipo', '')}"
            vectors = np.asarray(
                embedding_model.encode(
                    [selection_query] + [item["sentence"] for item in candidates],
                    normalize_embeddings=True,
                )
            )
            semantic_scores = vectors[1:] @ vectors[0]
            for item, semantic in zip(candidates, semantic_scores):
                stop_score = 0.35 if stop_intent and item["stop"] else 0.0
                position_bonus = 0.10 / (1 + item["sentence_rank"])
                source_bonus = 0.08 / (1 + item["source_rank"])
                item["score"] = (
                    0.62 * float(semantic)
                    + 0.15 * item["lexical"]
                    + 0.15 * float(item["source"]["score"])
                    + position_bonus
                    + source_bonus
                    + stop_score
                    + item["temporal_score"]
                )
        candidates.sort(key=lambda item: item["score"], reverse=True)

        def cited(item: dict[str, Any]) -> str:
            source = item["source"]
            return f"{item['sentence']} [{source['document']} > {source['heading']}]"

        used: set[str] = set()
        selected = []
        # Preserva contexto local: a melhor sentenca do primeiro chunk e sua continuacao.
        top_source = [candidate for candidate in candidates if candidate["source_rank"] == 0]
        local_context = []
        if top_source:
            anchor = top_source[0]
            ordered_source = sorted(top_source, key=lambda item: item["sentence_rank"])
            anchor_position = ordered_source.index(anchor)
            local_context.append(anchor)
            if anchor_position > 0:
                local_context.append(ordered_source[anchor_position - 1])
            if anchor_position + 1 < len(ordered_source):
                local_context.append(ordered_source[anchor_position + 1])
        for item in local_context:
            normalized = item["sentence"].lower()
            if normalized not in used:
                selected.append(item)
                used.add(normalized)
        for item in candidates:
            normalized = item["sentence"].lower()
            if normalized not in used:
                selected.append(item)
                used.add(normalized)
            if len(selected) == 4:
                break

        alert = operational_context.get("resumo_alerta")
        situation = f"Situação atual: {alert}" if alert else "Situação atual: considere o estado operacional informado."
        verification_items = [item for item in selected if not item["stop"]][:3]
        if not verification_items:
            verification_items = selected[:2]
        verification = "\n".join(f"- {cited(item)}" for item in verification_items)

        parts = [situation, f"Verificações recomendadas:\n{verification}"]
        if stop_intent:
            stop_items = [item for item in candidates if item["stop"]][:2]
            if stop_items:
                stop_text = "\n".join(f"- {cited(item)}" for item in stop_items)
            else:
                stop_text = "A documentação recuperada não define parada imediata para esta condição."
            parts.append(f"Critério de parada:\n{stop_text}")

        confidence = "alta" if results[0]["score"] >= 0.35 and len(selected) >= 2 else "média"
        parts.append(f"Confiança: {confidence} — resposta limitada às evidências recuperadas e ao contexto operacional.")
        return "\n\n".join(parts)

    @staticmethod
    def _grounding_issues(
        answer: str,
        results: list[dict[str, Any]],
        contexts: list[str],
        question: str,
        operational_context: dict[str, Any],
    ) -> list[str]:
        allowed = {f"[{r['document']} > {r['heading']}]" for r in results}
        cited = set(re.findall(r"\[[^\[\]]+ > [^\[\]]+\]", answer))
        issues = []
        if not cited:
            issues.append("nenhuma citação documental no corpo da resposta")
        elif not cited.issubset(allowed):
            issues.append("citação que não corresponde aos chunks recuperados")
        if "Confiança:" not in answer:
            issues.append("nível de confiança ausente")
        if sentence_support(answer, contexts) < 0.60:
            issues.append("sustentação documental abaixo de 0,60")
        lowered_answer = answer.lower()
        abstention_phrases = [
            "não há informação suficiente",
            "sem informações específicas",
            "não há evidência suficiente",
        ]
        if (
            results
            and float(results[0]["score"]) >= 0.25
            and any(phrase in lowered_answer for phrase in abstention_phrases)
        ):
            issues.append("abstenção indevida apesar de evidência relevante recuperada")
        evidence_text = " ".join(r["text"] for r in results).lower()
        question_terms = set(re.findall(r"[a-zà-ÿ0-9]+", question.lower())).difference(
            PORTUGUESE_STOPWORDS | {"não", "sem", "devo", "porque"}
        )
        temporal_intent = any(term in question.lower() for term in ["após", "depois", "ao concluir", "ao finalizar"])
        if temporal_intent:
            temporal_sentences = [
                sentence.strip()
                for sentence in re.split(r"(?<=[.!?])\s+", evidence_text.replace("\n", " "))
                if any(term in sentence for term in ["após", "depois"])
            ]
            answer_terms = set(re.findall(r"[a-zà-ÿ0-9]+", lowered_answer))
            action_covered = False
            for sentence in temporal_sentences:
                action_terms = set(re.findall(r"[a-zà-ÿ0-9]+", sentence)).difference(
                    PORTUGUESE_STOPWORDS
                    | question_terms
                    | {"após", "depois", "cada", "correção", "corrigir"}
                )
                if len(answer_terms & action_terms) >= min(2, max(1, len(action_terms))):
                    action_covered = True
                    break
            if temporal_sentences and not action_covered:
                issues.append("ação posterior solicitada não corresponde ao procedimento recuperado")
        situation_text = f"{question} {operational_context.get('resumo_alerta', '')}".lower()
        safety_trigger = any(
            trigger in situation_text
            for trigger in ["ruído metálico", "fumaça", "odor de isolamento", "proteção repetida"]
        )
        if safety_trigger and "parada segura" in evidence_text:
            if "parada segura" not in lowered_answer or "não há parada" in lowered_answer:
                issues.append("contradição com critério documental obrigatório de parada segura")
        return issues

    def ask(self, question: str, operational_context: dict[str, Any] | None = None, top_k: int = 4) -> dict[str, Any]:
        context = operational_context or {}
        results = self.rag.retrieve(question, context, top_k=top_k)
        prompt = self._prompt(question, results, context)
        source_contexts = [r["text"] for r in results] + [str(context)]
        unsupported = self._unsupported_identifiers(question, results, context)
        if unsupported:
            identifiers = ", ".join(unsupported)
            answer = (
                "Não há informação suficiente nos documentos recuperados para responder "
                f"com segurança sobre {identifiers}. "
                "Confiança: baixa — o identificador consultado não consta nas evidências disponíveis."
            )
            self.history.append((question, answer))
            return {
                "answer": answer,
                "sources": [],
                "confidence": "baixa",
                "faithfulness_proxy": 1.0,
                "generation_mode": "scope_abstention",
                "validation_issues": [f"identificador não documentado: {identifiers}"],
                "prompt": prompt,
            }
        generation_mode = "extractive"
        validation_issues: list[str] = []
        if self.llm:
            answer = self.llm(prompt)
            generation_mode = "llm"
            validation_issues = self._grounding_issues(
                answer, results, source_contexts, question, context
            )
            if validation_issues:
                repair_prompt = (
                    f"{prompt}\n\nA RESPOSTA ANTERIOR FOI REJEITADA POR: "
                    f"{'; '.join(validation_issues)}.\n"
                    "Reescreva do zero, copie apenas fatos presentes nas fontes, use as citações exatas "
                    "e obedeça integralmente ao contrato de saída.\n\n"
                    f"RESPOSTA REJEITADA:\n{answer}\n\nRESPOSTA CORRIGIDA:"
                )
                revised = self.llm(repair_prompt)
                revised_issues = self._grounding_issues(
                    revised, results, source_contexts, question, context
                )
                if revised_issues:
                    answer = self._grounded_fallback(question, results, context)
                    generation_mode = "guardrail_fallback"
                    validation_issues = revised_issues
                else:
                    answer = revised
                    generation_mode = "llm_revised"
                    validation_issues = []
        else:
            answer = self._grounded_fallback(question, results, context)
        self.history.append((question, answer))
        faithfulness = sentence_support(answer, source_contexts)
        return {
            "answer": answer,
            "sources": [f"{r['document']} > {r['heading']}" for r in results],
            "confidence": "alta" if faithfulness >= 0.75 else "média" if faithfulness >= 0.45 else "baixa",
            "faithfulness_proxy": faithfulness,
            "generation_mode": generation_mode,
            "validation_issues": validation_issues,
            "prompt": prompt,
        }

    def evaluate(self, qa_items: list[dict[str, Any]], top_k: int = 4) -> dict[str, Any]:
        details = []
        for item in qa_items:
            self.history.clear()
            result = self.ask(item["question"], item.get("operational_context", {}), top_k=top_k)
            retrieved = self.rag.retrieve(item["question"], item.get("operational_context", {}), top_k=top_k)
            expected = set(item["relevant_sections"])
            context_precision = sum(r["heading"] in expected for r in retrieved) / top_k
            details.append({
                "id": item["id"],
                "faithfulness": result["faithfulness_proxy"],
                "answer_relevancy": answer_relevancy(result["answer"], item["reference_answer"]),
                "context_precision": context_precision,
                "answer": result["answer"],
            })
        mean = lambda key: sum(x[key] for x in details) / len(details)
        return {
            "faithfulness": mean("faithfulness"),
            "answer_relevancy": mean("answer_relevancy"),
            "context_precision": mean("context_precision"),
            "details": details,
            "method_note": "Faithfulness mede suporte sentencial no documento + contexto operacional; answer relevancy combina cobertura lexical do gabarito e cosseno TF-IDF; use RAGAS/LLM-judge como validação complementar.",
        }
