"""Parsing tolerante de JSON vindo de um LLM.

Pedimos "sem markdown", mas modelos locais nem sempre obedecem: envolvem em
```json ... ```, adicionam texto antes/depois, ou põem uma frase de cortesia.
Esta função extrai o primeiro objeto JSON plausível e faz o parse.
"""

from __future__ import annotations

import json
import re

_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL | re.IGNORECASE)


class JsonExtractionError(ValueError):
    """Não foi possível extrair um objeto JSON válido do texto."""


def extract_json_object(text: str) -> dict:
    """Devolve o primeiro objeto JSON (`dict`) encontrado em `text`."""
    if not text or not text.strip():
        raise JsonExtractionError("texto vazio")

    candidates: list[str] = []

    # 1. Bloco cercado ```json ... ```
    fence = _FENCE_RE.search(text)
    if fence:
        candidates.append(fence.group(1))

    # 2. Texto inteiro
    candidates.append(text)

    # 3. Do primeiro '{' ao último '}' (apara texto à volta)
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidates.append(text[start : end + 1])

    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except (json.JSONDecodeError, TypeError):
            continue
        if isinstance(parsed, dict):
            return parsed

    raise JsonExtractionError("nenhum objeto JSON válido no texto do LLM")
