"""`QuestionExtractor` — extrai (e no modo texto, resolve) uma `Question`.

Estratégias (`LLM_MODE`):
  - `ocr`     — imagem → OCR → texto → modelo textual. Rápido. `extract_and_solve`
                funde extração + resolução numa só chamada.
  - `vision`  — imagem → modelo multimodal. Fiável, mas lento em CPU.
  - `hybrid`  — tenta `ocr`; se o resultado falhar as verificações (OCR fraco,
                ou o enunciado não corresponde ao texto lido → provável
                alucinação), refaz com `vision`.

Quem chama (`QuestionPipeline`) não sabe qual estratégia está ativa — recebe
sempre uma `Question` (e no caminho combinado, também o `SolveResult`).
"""

from __future__ import annotations

import asyncio
import logging

from app.config import Settings
from app.llm.base import LLMClient, LLMRequest
from app.llm.json_utils import JsonExtractionError, clamp01, extract_json_object
from app.llm.prompts import (
    COMBINED_SYSTEM,
    EXTRACTION_SYSTEM,
    EXTRACTION_USER,
    build_combined_user,
)
from app.models.question import Question, QuestionType
from app.models.result import SolveResult
from app.vision.encoding import encode_jpeg
from app.vision.ocr import OCREngine, build_ocr_engine
from app.vision.processor import ProcessedImage

logger = logging.getLogger(__name__)


class QuestionExtractionError(RuntimeError):
    """Falha ao interpretar a resposta do LLM como uma questão."""


class QuestionExtractor:
    def __init__(
        self,
        llm: LLMClient,
        settings: Settings,
        ocr: OCREngine | None = None,
        vision_llm: LLMClient | None = None,
    ) -> None:
        self._llm = llm
        self._settings = settings
        self._ocr = ocr
        # Cliente multimodal para `vision`/`hybrid`. Se não for dado e o `_llm`
        # já suportar visão, usa-se esse.
        self._vision_llm = vision_llm or (
            llm if settings.llm_supports_vision else None
        )

    # -- estratégia -----------------------------------------------------
    @property
    def _mode(self) -> str:
        m = (self._settings.llm_mode or "hybrid").lower()
        if m == "vision" and self._vision_llm is None:
            return "ocr"  # sem cliente de visão, não há como
        return m

    @property
    def supports_combined(self) -> bool:
        """No caminho de texto (ocr/hybrid) fundimos extração + resolução."""
        return self._mode in ("ocr", "hybrid")

    def _get_ocr(self) -> OCREngine:
        if self._ocr is None:
            self._ocr = build_ocr_engine()
        return self._ocr

    # -- extração isolada (modo `vision`; ou quando combined desligado) --
    async def extract(self, processed: ProcessedImage) -> Question:
        if self._mode == "vision":
            request = await self._vision_request(processed)
            response = await self._vision_llm.generate(request)
            return self._parse_question(_json(response.text))
        request = await self._ocr_request(processed)
        response = await self._llm.generate(request)
        return self._parse_question(_json(response.text))

    # -- extração + resolução numa só chamada -------------------------
    async def extract_and_solve(
        self, processed: ProcessedImage
    ) -> tuple[Question, SolveResult]:
        mode = self._mode

        if mode == "vision":
            return await self._vision_extract_and_solve(processed)

        # ocr ou hybrid: começa pelo OCR
        try:
            return await self._ocr_extract_and_solve(processed)
        except QuestionExtractionError as exc:
            if mode != "hybrid" or self._vision_llm is None:
                raise
            logger.info("HYBRID_FALLBACK_TO_VISION", extra={"model": str(exc)})
            return await self._vision_extract_and_solve(processed)

    # -- caminho OCR + texto ----------------------------------------
    async def _ocr_extract_and_solve(
        self, processed: ProcessedImage
    ) -> tuple[Question, SolveResult]:
        ocr = self._get_ocr()
        text = await asyncio.to_thread(ocr.image_to_text, processed.image)
        logger.info("OCR_DONE", extra={"model": str(len(text))})
        _guard_ocr_text(text)

        request = LLMRequest(
            system=COMBINED_SYSTEM, prompt=build_combined_user(text)
        )
        response = await self._llm.generate(request)
        data = _json(response.text)
        question = self._parse_question(data)
        result = _parse_result(data, question)
        _guard_question_matches_ocr(question, text)
        return question, result

    # -- caminho visão --------------------------------------------
    async def _vision_extract_and_solve(
        self, processed: ProcessedImage
    ) -> tuple[Question, SolveResult]:
        request = await self._vision_request(processed, combined=True)
        response = await self._vision_llm.generate(request)
        data = _json(response.text)
        question = self._parse_question(data)
        result = _parse_result(data, question)
        _guard_question_not_empty(question)
        return question, result

    async def _vision_request(
        self, processed: ProcessedImage, combined: bool = False
    ) -> LLMRequest:
        image_b64 = await asyncio.to_thread(_encode_b64, processed.image)
        system = COMBINED_SYSTEM if combined else EXTRACTION_SYSTEM
        prompt = (
            "Analise a imagem e responda só com o JSON pedido."
            if combined
            else EXTRACTION_USER
        )
        # A resposta combinada (questão + opções + explicação) é maior que uma
        # extração simples — mais folga de tokens para o JSON não sair cortado.
        return LLMRequest(
            system=system, prompt=prompt, image_b64=image_b64, max_tokens=2000
        )

    async def _ocr_request(self, processed: ProcessedImage) -> LLMRequest:
        ocr = self._get_ocr()
        text = await asyncio.to_thread(ocr.image_to_text, processed.image)
        return LLMRequest(
            system=EXTRACTION_SYSTEM,
            prompt=f"{EXTRACTION_USER}\n\nTexto reconhecido:\n{text}",
        )

    # -- parsing ----------------------------------------------------------
    @staticmethod
    def _parse_question(data: dict) -> Question:
        raw_type = str(data.get("type", "unknown")).strip().lower()
        try:
            qtype = QuestionType(raw_type)
        except ValueError:
            qtype = QuestionType.UNKNOWN

        options = data.get("options") or {}
        if not isinstance(options, dict):
            options = {}
        options = {str(k): str(v) for k, v in options.items()}

        return Question(
            type=qtype,
            language=str(data.get("language") or "pt"),
            question=str(data.get("question") or ""),
            options=options,
            code=_opt_str(data.get("code")),
            formulas=_opt_str(data.get("formulas")),
            has_image=bool(data.get("has_image", False)),
            confidence=clamp01(data.get("confidence", 0.0)),
        )


def _json(text: str) -> dict:
    try:
        return extract_json_object(text)
    except JsonExtractionError as exc:
        raise QuestionExtractionError(f"resposta não-JSON: {exc}") from exc


# Nº mínimo de caracteres de texto reconhecido para valer a pena chamar o LLM.
_MIN_OCR_CHARS = 25


def _guard_ocr_text(text: str) -> None:
    """Se o OCR mal leu texto, não vale a pena perguntar ao LLM — ele
    inventaria uma questão."""
    clean = " ".join(text.split())
    if len(clean) < _MIN_OCR_CHARS:
        raise QuestionExtractionError(
            "não foi possível ler texto suficiente da imagem"
        )


# Palavras comuns que não distinguem uma questão de outra — ignoradas ao
# comparar o enunciado do LLM com o texto do OCR.
_STOPWORDS = {
    "qual", "quais", "para", "pela", "pelo", "como", "onde", "quando", "porque",
    "sobre", "entre", "dos", "das", "uma", "umas", "uns", "que", "com", "sem",
    "por", "mais", "menos", "seguinte", "abaixo", "acima", "alternativa",
    "alternativas", "questao", "questoes", "resolva", "considere", "assinale",
    "marque", "correta", "incorreta", "opcao", "opcoes", "seja", "sejam",
    "este", "esta", "esse", "essa", "aquele", "aquela", "isto", "isso",
}


def _norm(s: str) -> set[str]:
    import re

    return {
        w
        for w in re.findall(r"[a-zà-ú0-9]{4,}", s.lower())
        if w not in _STOPWORDS
    }


def _guard_question_matches_ocr(question: Question, ocr_text: str) -> None:
    """Deteta alucinação: o enunciado devolvido pelo LLM tem de estar
    ancorado no texto que o OCR leu — não basta partilhar palavras soltas do
    mesmo domínio, tem de partilhar EXPRESSÕES (bigramas)."""
    import re

    q_words = [w for w in re.findall(r"[a-zà-ú0-9]+", question.question.lower())]
    q_sig = _norm(question.question)
    if len(q_sig) < 3:
        raise QuestionExtractionError("enunciado vazio ou demasiado curto")

    ocr_sig = _norm(ocr_text)
    word_overlap = len(q_sig & ocr_sig) / len(q_sig)

    # Bigramas do enunciado que também aparecem no OCR.
    q_bigrams = {f"{a} {b}" for a, b in zip(q_words, q_words[1:])}
    ocr_norm = " ".join(re.findall(r"[a-zà-ú0-9]+", ocr_text.lower()))
    bigram_hits = sum(1 for bg in q_bigrams if bg in ocr_norm)
    bigram_ratio = bigram_hits / max(len(q_bigrams), 1)

    # Alucinação se: poucas palavras significativas em comum, OU quase nenhuma
    # expressão do enunciado aparece literalmente no texto lido.
    if word_overlap < 0.35 or bigram_ratio < 0.20:
        raise QuestionExtractionError(
            "a questão devolvida não está no texto lido da imagem "
            f"(palavras {word_overlap:.0%}, expressões {bigram_ratio:.0%}) — "
            "provável alucinação"
        )


def _guard_question_not_empty(question: Question) -> None:
    if len(_norm(question.question)) < 3:
        raise QuestionExtractionError(
            "o modelo de visão não conseguiu ler uma questão nesta imagem"
        )


def _parse_result(data: dict, question: Question) -> SolveResult:
    answer = str(data.get("answer") or "").strip()
    answer_text = str(data.get("answer_text") or "").strip()
    if not answer_text and answer in question.options:
        answer_text = question.options[answer]
    return SolveResult(
        answer=answer,
        answer_text=answer_text,
        explanation=str(data.get("explanation") or "").strip(),
        confidence=clamp01(data.get("confidence", 0.0)),
        ambiguous=bool(data.get("ambiguous", False)),
    )


def _encode_b64(image) -> str:
    import base64

    return base64.b64encode(encode_jpeg(image)).decode("ascii")


def _opt_str(value) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
