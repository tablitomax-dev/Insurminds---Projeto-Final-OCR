"""Lógica pura dos componentes de UI (D2-P1-1d/D2-P1-2e).

Sem `streamlit`: funções determinísticas e testáveis que os componentes
apenas apresentam. Consome tipos re-exportados pela fachada pública
(F-15 — nada de `domain`/`infrastructure` alheio).
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

from modules.policy_analysis.public_api import (
    SEVERITY_ORDER,
    Issue,
    Severity,
    UsageSummary,
)
from shared_kernel.contracts import EvidenceRef, ExtractedFact

#: Símbolos usuais para exibição monetária (ISO 4217 → leitura humana).
_CURRENCY_SYMBOLS: dict[str, str] = {
    "BRL": "R$",
    "USD": "US$",
    "EUR": "€",
    "GBP": "£",
    "JPY": "JP¥",
    "CAD": "C$",
    "CHF": "CHF",
    "AUD": "A$",
}

_ISO_DATE = re.compile(r"(\d{4})-(\d{2})-(\d{2})")

#: Origem do texto da evidência → leitura humana do analista.
_SOURCE_LABELS: dict[str, str] = {
    "NATIVE_TEXT": "texto nativo",
    "PADDLEOCR": "OCR (PaddleOCR)",
    "PP_STRUCTURE": "estrutura de layout",
}

#: Tamanho máximo do trecho na tabela da consulta (detalhe fica no expander).
_SNIPPET_LIMIT = 160


def group_by_severity(
    facts: list[ExtractedFact], issues: list[Issue]
) -> list[tuple[Severity, list[ExtractedFact]]]:
    """Agrupa a fila de revisão por severidade do `Issue` derivado (RF-02).

    Ordem `CRÍTICO` → `BAIXO`; fato sem `Issue` associado cai em `BAIXO`
    (sem sinal de qualidade). Grupos vazios não aparecem.
    """
    severity_by_key: dict[tuple[str, str], Severity] = {}
    for issue in issues:
        key = (issue.policy_id, issue.field_code)
        current = severity_by_key.get(key)
        if current is None or SEVERITY_ORDER.index(issue.severity) < SEVERITY_ORDER.index(
            current
        ):
            severity_by_key[key] = issue.severity
    groups: list[tuple[Severity, list[ExtractedFact]]] = []
    for severity in SEVERITY_ORDER:
        bucket = [
            fact
            for fact in facts
            if severity_by_key.get((fact.policy_id, fact.field_code), Severity.BAIXO)
            is severity
        ]
        if bucket:
            groups.append((severity, bucket))
    return groups


def format_usage_summary(summary: UsageSummary | None) -> dict[str, str] | None:
    """Formata o resumo de métricas para o painel — números, IDs e datas (T-2a)."""
    if summary is None:
        return None
    cost = (
        "n/d (modelo fora da tabela de preços)"
        if summary.cost_usd is None
        else f"US$ {summary.cost_usd:.6f}"
    )
    return {
        "run_id": summary.run_id,
        "chamadas de LLM": str(summary.calls),
        "tokens de entrada": str(summary.request_tokens),
        "tokens de saída": str(summary.response_tokens),
        "latência total": f"{summary.latency_ms} ms",
        "custo estimado": cost,
        "tabela de preços (ref.)": summary.price_reference_date or "n/d",
    }


# --- formatação de valores para o analista -----------------------------------


def _decimal_br(raw: object, decimals: int | None = None) -> str:
    """Número no padrão pt-BR `000.000,00` (sem zeros supérfluos se `decimals=None`)."""
    try:
        number = Decimal(str(raw))
    except (InvalidOperation, ValueError):
        return str(raw)
    sign = "-" if number < 0 else ""
    number = abs(number)
    int_part, _, frac = f"{number:f}".partition(".")
    if decimals is not None:
        frac = f"{frac:<0{decimals}}"[:decimals]
    else:
        frac = frac.rstrip("0")
    int_br = f"{int(int_part):,}".replace(",", ".")
    return f"{sign}{int_br},{frac}" if frac else f"{sign}{int_br}"


def _date_br(raw: object) -> str:
    """Data em `dd-mm-aaaa`; outro formato já legível passa direto."""
    text = str(raw).strip()
    match = _ISO_DATE.fullmatch(text)
    if match:
        year, month, day = match.groups()
        return f"{day}-{month}-{year}"
    return text


def format_value(value: dict | None, unit: str | None = None) -> str:
    """Formata o `normalized_value` para leitura humana do analista.

    Sem JSON, sem aspas, sem nomes de tipo — só a informação:
    dinheiro → `R$ 2.000.000,00`; data → `dd-mm-aaaa`; período →
    `início a fim` (sem duração); número → `30 dias` / `5%`; texto →
    como está. Ausente → `—`.
    """
    if not value:
        return "—"
    if "amount" in value:
        currency = str(value.get("currency", "")).upper()
        symbol = _CURRENCY_SYMBOLS.get(currency, currency)
        return f"{symbol} {_decimal_br(value['amount'], decimals=2)}"
    if "start" in value and "end" in value:
        return f"{_date_br(value['start'])} a {_date_br(value['end'])}"
    if "date" in value:
        return _date_br(value["date"])
    if "number" in value:
        number = _decimal_br(value["number"])
        unit_text = (unit or "").strip()
        if unit_text == "%":
            return f"{number}%"
        return f"{number} {unit_text}" if unit_text else number
    if "text" in value:
        return str(value["text"])
    # Valor fora do formato conhecido: só as informações, sem JSON.
    return ", ".join(str(part) for part in value.values() if part not in (None, "")) or "—"


# --- consulta livre às evidências -------------------------------------------


def _snippet(text: str, limit: int = _SNIPPET_LIMIT) -> str:
    """Trecho de uma linha só, cortado em `limit` caracteres com reticências."""
    flat = " ".join(text.split())
    if len(flat) <= limit:
        return flat
    return flat[:limit].rstrip() + "…"


def format_evidence_rows(evidences: list[EvidenceRef]) -> list[dict[str, str]]:
    """Formata as evidências da consulta para a tabela — sem JSON, sem tipos.

    Ausências viram `—`; o score vai em `0,00` pt-BR; o trecho aparece
    resumido (o texto completo fica no expander da tela de consulta).
    """
    rows: list[dict[str, str]] = []
    for evidence in evidences:
        score = evidence.retrieval_score
        rows.append(
            {
                "apólice": evidence.policy_id,
                "página": str(evidence.page_number),
                "seção": evidence.section_name or "—",
                "trecho": _snippet(evidence.quoted_text),
                "score": "—" if score is None else _decimal_br(score, decimals=2),
                "origem": _SOURCE_LABELS.get(evidence.source_type, evidence.source_type),
            }
        )
    return rows
