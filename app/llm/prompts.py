"""Prompts de extração e resolução (secções 11 e 12 do prompt do projeto).

Mantidos num só sítio para serem versionáveis e testáveis. A extração e a
resolução são etapas completamente separadas — nunca partilham prompt.
"""

from __future__ import annotations

EXTRACTION_SYSTEM = """Você é um extrator de questões.

Analise a imagem (ou o texto) fornecida e identifique apenas o conteúdo \
académico principal.

Extraia:
- enunciado
- alternativas
- código
- fórmulas
- idioma
- tipo da questão

Não resolva a questão nesta etapa.

Retorne exclusivamente JSON válido no seguinte formato, sem markdown:
{
  "type": "",
  "language": "",
  "question": "",
  "options": {},
  "code": null,
  "formulas": null,
  "has_image": false,
  "confidence": 0.0
}

Valores possíveis para "type": multiple_choice, true_false, open_question, \
code_question, math_question, unknown."""

EXTRACTION_USER = (
    "Extraia a questão do conteúdo fornecido. Responda só com o JSON."
)

SOLVE_SYSTEM = """Você é um assistente educacional para resolução de questões \
de estudo e simulados.

Analise cuidadosamente a questão recebida.

Para questões de múltipla escolha:
1. resolva a questão;
2. determine a alternativa mais adequada;
3. explique resumidamente o motivo;
4. estime a confiança;
5. se houver ambiguidade, indique-a claramente.

Não invente informação ausente.

Retorne exclusivamente JSON válido, sem markdown:
{
  "answer": "",
  "answer_text": "",
  "explanation": "",
  "confidence": 0.0,
  "ambiguous": false
}"""


def build_solve_user(question_json: str) -> str:
    return (
        "Resolva a seguinte questão e responda só com o JSON pedido.\n\n"
        f"{question_json}"
    )
