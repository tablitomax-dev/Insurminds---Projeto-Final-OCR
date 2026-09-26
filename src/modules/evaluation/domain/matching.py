"""Regras determinísticas de acerto por campo (RF-03) — puras (A-08).

Reuso das regras da análise: o escalar comparável vem da normalização do
`policy_analysis` (via fachada — `normalize_field_value`); o critério de
acerto é decidido aqui:

- escalar numérico: igualdade exata;
- texto/data normalizada: **substring literal** sobre o escalar normalizado
  (OQ-02 = substring, ancoragem literal — coerente com `domain/anchoring.py`
  do policy_analysis);
- evidência: a citação esperada deve ser substring literal de algum dos
  textos das evidências citadas pelo fato extraído.

Módulo puro: stdlib apenas, sem LLM e sem I/O.
"""

from typing import Any

from shared_kernel.contracts import FactStatus

from .models import MatchResult


def match_value(expected_scalar: Any, extracted_scalar: Any) -> bool:
    """Acerto de valor: igualdade numérica ou substring literal (OQ-02)."""
    if expected_scalar is None or extracted_scalar is None:
        return False
    if isinstance(expected_scalar, bool) or isinstance(extracted_scalar, bool):
        return expected_scalar == extracted_scalar
    if isinstance(expected_scalar, (int, float)) and isinstance(extracted_scalar, (int, float)):
        return float(expected_scalar) == float(extracted_scalar)
    if isinstance(expected_scalar, str) and isinstance(extracted_scalar, str):
        return expected_scalar.strip() in extracted_scalar
    return expected_scalar == extracted_scalar


def evidence_matches(quote: str | None, source_texts: list[str]) -> bool:
    """Acerto de evidência: a citação esperada existe em um texto citado."""
    if not quote:
        return True
    needle = quote.strip()
    return any(needle in text for text in source_texts if isinstance(text, str))


def classify_entry(
    expected_status: FactStatus,
    extracted_status: FactStatus | None,
    expected_scalar: Any,
    extracted_scalar: Any,
) -> tuple[MatchResult, str | None]:
    """Classifica o campo: `correto`/`divergente`/`ausente`/`inconclusivo`.

    EC-03: extração `AMBIGUOUS`/`NEEDS_REVIEW` é `inconclusivo` — nunca conta
    como acerto. `NOT_FOUND` extraído casa com `NOT_FOUND` esperado.
    """
    if extracted_status is None:
        return "nao_avaliado", "campo não avaliado"
    if extracted_status == "NOT_FOUND":
        if expected_status == "NOT_FOUND":
            return "correto", None
        return "ausente", "campo não encontrado na apólice"
    if extracted_status in ("AMBIGUOUS", "NEEDS_REVIEW"):
        return "inconclusivo", "extração sinalizada para revisão humana (EC-03)"
    if expected_status == "NOT_FOUND":
        return "divergente", "campo extraído mas não esperado na referência"
    if match_value(expected_scalar, extracted_scalar):
        return "correto", None
    return "divergente", "valor divergente do esperado"
