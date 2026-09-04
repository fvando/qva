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

    # Última tentativa: o JSON pode ter sido cortado (max_tokens). Tenta reparar
    # fechando strings/chavetas abertas a partir do primeiro '{'.
    if start != -1:
        repaired = _repair_truncated_json(text[start:])
        if repaired is not None:
            return repaired

    raise JsonExtractionError("nenhum objeto JSON válido no texto do LLM")


def _repair_truncated_json(s: str) -> dict | None:
    """Fecha aspas e chavetas/parênteses abertos num JSON truncado."""
    in_str = False
    escape = False
    stack: list[str] = []
    for ch in s:
        if escape:
            escape = False
            continue
        if ch == "\\" and in_str:
            escape = True
            continue
        if ch == '"':
            in_str = not in_str
            continue
        if in_str:
            continue
        if ch in "{[":
            stack.append("}" if ch == "{" else "]")
        elif ch in "}]" and stack:
            stack.pop()

    fixed = s.rstrip()
    # remove uma vírgula/dois-pontos pendente no fim
    fixed = fixed.rstrip(",: \n\t")
    if in_str:
        fixed += '"'
    fixed += "".join(reversed(stack))
    try:
        parsed = json.loads(fixed)
        return parsed if isinstance(parsed, dict) else None
    except (json.JSONDecodeError, TypeError):
        return None


def clamp01(value) -> float:
    """Converte para float e limita ao intervalo [0.0, 1.0]. Não-numérico -> 0.0."""
    try:
        f = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(1.0, f))
