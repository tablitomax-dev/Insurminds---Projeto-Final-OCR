"""Regras mínimas por campo do catálogo (RF-03, D2-P0-3) — puras e determinísticas.

Regras implementadas (A-08: mesma entrada, mesma saída — sem LLM):
- `valor_positivo`: valores numéricos > 0 (limites e franquia);
- `moeda_conhecida`: moeda coerente para valores monetários (código conhecido);
- `moeda_consistente`: moedas dos campos monetários da mesma apólice coincidem;
- `enum_base_territorial`: `base_territorial` dentro do enum razoável fechado;
- `vigencia_ordem`: `vigencia_inicio <= vigencia_fim` (regra cruzada).

Falha de regra nunca vira `FOUND`: o consumidor rebaixa o fato para
`NEEDS_REVIEW` com o motivo registrado. Os motivos citam apenas regra e
campo — nunca o valor extraído (T-2a: nada de texto de apólice em mensagem).
"""

from dataclasses import dataclass
from typing import Any

from shared_kernel.contracts import ExtractedFact

from .catalog import FieldSpec, get_field_spec
from .comparison import normalize_value

#: Campos monetários do catálogo (regras de valor e de moeda).
MONETARY_CODES = frozenset({"limite_agregado", "limite_por_sinistro", "franquia"})

#: Moedas razoáveis para o vertical slice (códigos ISO 4217 usuais em D&O).
KNOWN_CURRENCIES = frozenset({"BRL", "USD", "EUR", "GBP", "JPY", "CAD", "CHF", "AUD"})

#: Chaves de moeda dentro de `value`/`normalized_value`.
_CURRENCY_KEYS = ("currency", "moeda")

#: Enum razoável (fechado) de `base_territorial`, em forma normalizada
#: (minúsculas, sem espaços nas bordas). Valor fora do enum → revisão humana.
BASE_TERRITORIAL_VALUES = frozenset(
    {
        "brasil",
        "eua",
        "estados unidos",
        "canadá",
        "europa",
        "américa latina",
        "américa do sul",
        "américa do norte",
        "mundo",
        "mundial",
        "worldwide",
        "internacional",
        "exterior",
    }
)

#: Campos de vigência usados na regra cruzada de ordem.
_VIGENCIA_INICIO = "vigencia_inicio"
_VIGENCIA_FIM = "vigencia_fim"

#: Spec de data reusada para ler os escalares de vigência.
_DATE_SPEC = get_field_spec(_VIGENCIA_INICIO)


@dataclass(frozen=True)
class RuleViolation:
    """Violação de regra de campo: regra, campo e motivo (sem o valor extraído)."""

    rule: str
    field_code: str
    reason: str


def validate_fact(
    spec: FieldSpec,
    fact: ExtractedFact,
    others: dict[str, ExtractedFact] | None = None,
) -> list[RuleViolation]:
    """Aplica as regras mínimas do campo (regra pura, determinística).

    `others` traz os demais fatos da MESMA apólice (por `field_code`), usados
    pelas regras cruzadas (`vigencia_ordem`, `moeda_consistente`). Fato
    `NOT_FOUND` não afirma valor e não recebe regras.
    """
    if fact.status == "NOT_FOUND":
        return []
    related = others or {}
    violations: list[RuleViolation] = []
    if spec.value_type == "numeric":
        violations.extend(_positive_value(spec, fact))
    if spec.code in MONETARY_CODES:
        violations.extend(_known_currency(spec, fact))
        violations.extend(_consistent_currency(spec, fact, related))
    if spec.code == "base_territorial":
        violations.extend(_territorial_enum(spec, fact))
    if spec.code in (_VIGENCIA_INICIO, _VIGENCIA_FIM):
        violations.extend(_vigencia_order(spec, fact, related))
    return violations


def _positive_value(spec: FieldSpec, fact: ExtractedFact) -> list[RuleViolation]:
    """Valores numéricos devem ser > 0 (limites e franquia)."""
    scalar = _scalar(spec, fact)
    if scalar is not None and scalar <= 0:
        return [
            RuleViolation(
                rule="valor_positivo",
                field_code=spec.code,
                reason="valor numérico deve ser maior que zero",
            )
        ]
    return []


def _known_currency(spec: FieldSpec, fact: ExtractedFact) -> list[RuleViolation]:
    """Moeda declarada deve ser um código conhecido (coerência monetária)."""
    currency = _currency_of(fact)
    if currency is not None and currency.upper() not in KNOWN_CURRENCIES:
        return [
            RuleViolation(
                rule="moeda_conhecida",
                field_code=spec.code,
                reason="moeda do valor monetário fora dos códigos conhecidos",
            )
        ]
    return []


def _consistent_currency(
    spec: FieldSpec, fact: ExtractedFact, others: dict[str, ExtractedFact]
) -> list[RuleViolation]:
    """Moedas dos campos monetários da mesma apólice devem coincidir."""
    currency = _currency_of(fact)
    if currency is None:
        return []
    for code, other in others.items():
        if code not in MONETARY_CODES:
            continue
        other_currency = _currency_of(other)
        if other_currency is not None and other_currency.upper() != currency.upper():
            return [
                RuleViolation(
                    rule="moeda_consistente",
                    field_code=spec.code,
                    reason="moeda divergente entre campos monetários da mesma apólice",
                )
            ]
    return []


def _territorial_enum(spec: FieldSpec, fact: ExtractedFact) -> list[RuleViolation]:
    """`base_territorial` deve pertencer ao enum razoável fechado."""
    scalar = _scalar(spec, fact)
    if scalar is not None and str(scalar).strip().casefold() not in BASE_TERRITORIAL_VALUES:
        return [
            RuleViolation(
                rule="enum_base_territorial",
                field_code=spec.code,
                reason="base territorial fora do enum razoável do catálogo",
            )
        ]
    return []


def _vigencia_order(
    spec: FieldSpec, fact: ExtractedFact, others: dict[str, ExtractedFact]
) -> list[RuleViolation]:
    """`vigencia_inicio` deve ser anterior ou igual a `vigencia_fim` (regra cruzada).

    Avaliada quando o par está completo e ambos os lados são datas legíveis;
    a ordem cronológica é comparada sobre os escalar ISO (`YYYY-MM-DD`).
    """
    pair_code = _VIGENCIA_FIM if spec.code == _VIGENCIA_INICIO else _VIGENCIA_INICIO
    other = others.get(pair_code)
    if other is None or other.status == "NOT_FOUND":
        return []
    inicio, fim = (fact, other) if spec.code == _VIGENCIA_INICIO else (other, fact)
    start = _date_scalar(inicio)
    end = _date_scalar(fim)
    if start is None or end is None or start <= end:
        return []
    return [
        RuleViolation(
            rule="vigencia_ordem",
            field_code=spec.code,
            reason=f"{_VIGENCIA_INICIO} deve ser anterior ou igual a {_VIGENCIA_FIM}",
        )
    ]


def _scalar(spec: FieldSpec, fact: ExtractedFact) -> Any:
    """Escalar comparável do fato: prefere `normalized_value` e cai para `value`."""
    for payload in (fact.normalized_value, fact.value):
        normalized = normalize_value(spec, payload)
        if normalized is not None:
            return normalized.get("scalar")
    return None


def _date_scalar(fact: ExtractedFact) -> str | None:
    """Data ISO do fato de vigência (`None` quando ilegível)."""
    scalar = _scalar(_DATE_SPEC, fact)
    return scalar if isinstance(scalar, str) else None


def _currency_of(fact: ExtractedFact) -> str | None:
    for payload in (fact.value, fact.normalized_value):
        if not isinstance(payload, dict):
            continue
        for key in _CURRENCY_KEYS:
            candidate = payload.get(key)
            if isinstance(candidate, str) and candidate.strip():
                return candidate.strip()
    return None
