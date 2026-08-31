"""Backends opcionais de LLM para uso no Colab ou em API compativel."""

from __future__ import annotations

import os


def qwen_local(
    model_id: str = "Qwen/Qwen2.5-3B-Instruct",
    max_new_tokens: int = 420,
    system_prompt: str | None = None,
):
    """Retorna um gerador Qwen usando o chat template oficial do modelo."""
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(model_id)
    try:
        model = AutoModelForCausalLM.from_pretrained(
            model_id,
            device_map="auto",
            dtype="auto",
        )
    except TypeError:  # Compatibilidade com versoes anteriores do Transformers.
        model = AutoModelForCausalLM.from_pretrained(
            model_id,
            device_map="auto",
            torch_dtype="auto",
        )

    base_system_prompt = system_prompt or (
        "Responda somente com base nas evidencias fornecidas. "
        "Nao invente fatos e preserve as citacoes solicitadas."
    )

    def call(prompt: str) -> str:
        messages = [
            {"role": "system", "content": base_system_prompt},
            {"role": "user", "content": prompt},
        ]
        rendered = tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
        )
        inputs = tokenizer(rendered, return_tensors="pt").to(model.device)
        with torch.inference_mode():
            output = model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                do_sample=False,
                repetition_penalty=1.05,
                pad_token_id=tokenizer.eos_token_id,
            )
        generated = output[0, inputs["input_ids"].shape[1]:]
        return tokenizer.decode(
            generated,
            skip_special_tokens=True,
            clean_up_tokenization_spaces=False,
        ).strip()

    return call


def openai_compatible(
    model: str,
    base_url: str | None = None,
    api_key_env: str = "OPENAI_API_KEY",
    max_tokens: int = 500,
    system_prompt: str | None = None,
):
    """Retorna uma funcao para APIs compativeis com o SDK OpenAI."""
    from openai import OpenAI

    api_key = os.getenv(api_key_env)
    if not api_key:
        raise RuntimeError(f"Defina a variável de ambiente {api_key_env}")
    client = OpenAI(api_key=api_key, base_url=base_url)

    def call(prompt: str) -> str:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": system_prompt or (
                        "Responda somente com base nas evidencias fornecidas e nao invente fatos."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content.strip()

    return call
