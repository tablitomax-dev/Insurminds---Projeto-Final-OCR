"""Value objects e normalização por tipo de valor (roadmap D-05, decisão OQ-03).

Regras híbridas: numérico, moeda, data e período normalizam de forma
determinística; texto livre normaliza forma (caixa, acentos, espaços) e a
semântica fica com o analista. Valores monetários usam `Decimal` (nunca
`float`) para preservar o determinismo da comparação (RNF-01).
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

MONEY_QUANT = Decimal("0.01")


class NormalizationError(ValueError):
    """Valor recebido não é normalizável para o tipo esperado (EC-04)."""


def normalize_text(text: str) -> str:
    """Normaliza forma: minúsculas, sem acentos, espaços colapsados."""
    if not isinstance(text, str) or not text.strip():
        raise NormalizationError(f"texto vazio ou inválido: {text!r}")
    lowered = text.strip().lower()
    decomposed = unicodedata.normalize("NFKD", lowered)
    without_accents = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", without_accents)


def parse_decimal(raw: object) -> Decimal:
    """Converte número/string (formatos `1000.50` ou `1.000,50`) em Decimal."""
    if isinstance(raw, bool):
        raise NormalizationError(f"booleano não é valor numérico: {raw!r}")
    if isinstance(raw, Decimal):
        return raw
    if isinstance(raw, (int, float)):
        return Decimal(str(raw))
    if isinstance(raw, str):
        cleaned = raw.strip().replace("R$", "").replace("%", "").strip()
        if "," in cleaned and "." in cleaned:
            if cleaned.rfind(",") > cleaned.rfind("."):
                cleaned = cleaned.replace(".", "").replace(",", ".")
            else:
                cleaned = cleaned.replace(",", "")
        elif "," in cleaned:
            cleaned = cleaned.replace(",", ".")
        cleaned = re.sub(r"[^\d.\-]", "", cleaned)
        try:
            return Decimal(cleaned)
        except InvalidOperation as exc:
            raise NormalizationError(f"número inválido: {raw!r}") from exc
    raise NormalizationError(f"número inválido: {raw!r}")


def parse_date(raw: object) -> date:
    """Converte data (`YYYY-MM-DD`, `DD/MM/YYYY`, `DD-MM-YYYY`) em `date`."""
    if isinstance(raw, datetime):
        return raw.date()
    if isinstance(raw, date):
        return raw
    if isinstance(raw, str):
        text = raw.strip()
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
            try:
                return datetime.strptime(text, fmt).date()
            except ValueError:
                continue
    raise NormalizationError(f"data inválida: {raw!r}")


@dataclass(frozen=True)
class Money:
    """Valor monetário com moeda explícita."""

    amount: Decimal
    currency: str = "BRL"

    def to_brl(self, rate: Decimal) -> Decimal:
        """Converte para BRL pela taxa injetada (taxa = 1 para BRL)."""
        if self.currency.upper() == "BRL":
            return self.amount.quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)
        if rate <= 0:
            raise NormalizationError(f"taxa de câmbio inválida: {rate}")
        return (self.amount * rate).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class Period:
    """Período com início e fim; duração em dias é a base da comparação."""

    start: date
    end: date

    def __post_init__(self) -> None:
        if self.end < self.start:
            raise NormalizationError(f"período invertido: {self.start} > {self.end}")

    @property
    def duration_days(self) -> int:
        return (self.end - self.start).days


# --- normalização para o formato `normalized_value` dos fatos -----------------


def normalize_money_value(raw: dict) -> dict:
    amount = parse_decimal(raw.get("amount"))
    currency = str(raw.get("currency", "BRL")).upper()
    if not re.fullmatch(r"[A-Z]{3}", currency):
        raise NormalizationError(f"moeda inválida: {raw.get('currency')!r}")
    return {"amount": str(amount.quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)), "currency": currency}


def normalize_period_value(raw: dict) -> dict:
    period = Period(parse_date(raw.get("start")), parse_date(raw.get("end")))
    return {"start": period.start.isoformat(), "end": period.end.isoformat(), "duration_days": period.duration_days}


def normalize_date_value(raw: dict) -> dict:
    return {"date": parse_date(raw.get("date")).isoformat()}


def normalize_number_value(raw: dict) -> dict:
    return {"number": str(parse_decimal(raw.get("number")))}


def normalize_text_value(raw: dict) -> dict:
    return {"text": normalize_text(str(raw.get("text", "")))}


# --- chaves comparáveis (determinísticas) ------------------------------------


def normalize_value(field, raw: dict) -> dict:
    """Normaliza o valor bruto do LLM conforme o tipo do campo (EC-04)."""
    from .field_catalog import FieldType

    dispatch = {
        FieldType.MONEY: normalize_money_value,
        FieldType.NUMBER: normalize_number_value,
        FieldType.PERIOD: normalize_period_value,
        FieldType.DATE: normalize_date_value,
        FieldType.TEXT: normalize_text_value,
    }
    return dispatch[field.field_type](raw or {})


def money_key(normalized: dict, rate: Decimal = Decimal("1")) -> Decimal:
    return Money(parse_decimal(normalized.get("amount")), str(normalized.get("currency", "BRL"))).to_brl(rate)


def period_key(normalized: dict) -> tuple[date, date]:
    period = Period(parse_date(normalized.get("start")), parse_date(normalized.get("end")))
    return period.start, period.end


def date_key(normalized: dict) -> date:
    return parse_date(normalized.get("date"))


def number_key(normalized: dict) -> Decimal:
    return parse_decimal(normalized.get("number"))


def text_key(normalized: dict) -> str:
    return normalize_text(str(normalized.get("text", "")))
