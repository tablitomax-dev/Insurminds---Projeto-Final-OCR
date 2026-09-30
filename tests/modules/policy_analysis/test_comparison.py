"""T008 — Comparador determinístico (RN-01, RN-04, RN-06, OQ-03)."""

from __future__ import annotations

from decimal import Decimal

from modules.policy_analysis.domain.comparison import (
    compare_facts,
    comparison_id as make_comparison_id,
)
from modules.policy_analysis.domain.field_catalog import get_field
from shared_kernel.contracts import ExtractedFact


def make_fact(
    code: str,
    normalized: dict | None,
    status: str = "FOUND",
    evidence: tuple[str, ...] = ("EV-1",),
    review: bool = False,
    policy_id: str = "POL-A",
) -> ExtractedFact:
    return ExtractedFact(
        fact_id="FAC-TEST",
        policy_id=policy_id,
        field_code=code,
        status=status,
        value=None,
        normalized_value=normalized,
        confidence=0.9,
        evidence_ids=list(evidence),
        requires_human_review=review,
    )


def test_money_maior_menor_igual():
    field = get_field("limite_agregado")
    a = make_fact("limite_agregado", {"amount": "5000000.00", "currency": "BRL"})
    b = make_fact("limite_agregado", {"amount": "3000000.00", "currency": "BRL"}, policy_id="POL-B")
    assert compare_facts(field, a, b).resultado == "MAIOR"
    assert compare_facts(field, b, a).resultado == "MENOR"
    assert compare_facts(field, a, a).resultado == "IGUAL"


def test_money_converte_moeda_estrangeira_com_taxa():
    field = get_field("limite_agregado")
    a = make_fact("limite_agregado", {"amount": "100.00", "currency": "USD"})
    b = make_fact("limite_agregado", {"amount": "300.00", "currency": "BRL"}, policy_id="POL-B")
    result = compare_facts(field, a, b, currency_rates={"USD": Decimal("5")})
    assert result.resultado == "MAIOR"  # 500 BRL > 300 BRL


def test_number_compara_por_valor():
    field = get_field("prazo_notificacao_sinistro")
    a = make_fact("prazo_notificacao_sinistro", {"number": "60"})
    b = make_fact("prazo_notificacao_sinistro", {"number": "30"}, policy_id="POL-B")
    assert compare_facts(field, a, b).resultado == "MAIOR"


def test_date_compara_por_data():
    field = get_field("retroatividade")
    a = make_fact("retroatividade", {"date": "2015-01-01"})
    b = make_fact("retroatividade", {"date": "2018-06-01"}, policy_id="POL-B")
    result = compare_facts(field, a, b)
    assert result.resultado == "MENOR"
    assert result.direcao == "B"


def test_period_compara_duracao_e_janelas_diferentes():
    field = get_field("vigencia")
    a = make_fact("vigencia", {"start": "2025-01-01", "end": "2026-01-01"})
    b_long = make_fact("vigencia", {"start": "2025-01-01", "end": "2027-01-01"}, policy_id="POL-B")
    b_shifted = make_fact("vigencia", {"start": "2026-01-01", "end": "2027-01-01"}, policy_id="POL-B")

    assert compare_facts(field, a, b_long).resultado == "MENOR"
    assert compare_facts(field, a, a).resultado == "IGUAL"
    assert compare_facts(field, a, b_shifted).resultado == "DIVERGENTE"


def test_texto_igual_apos_normalizacao_e_divergente_caso_contrario():
    field = get_field("extensao_territorial")
    a = make_fact("extensao_territorial", {"text": "Mundial"})
    same = make_fact("extensao_territorial", {"text": "MUNDIAL"}, policy_id="POL-B")
    different = make_fact("extensao_territorial", {"text": "Brasil"}, policy_id="POL-B")

    assert compare_facts(field, a, same).resultado == "IGUAL"
    result = compare_facts(field, a, different)
    assert result.resultado == "DIVERGENTE"
    assert result.direcao == "n/a"


def test_ausente_e_diferenca_por_omissao_nunca_erro():
    field = get_field("limite_defesa_custos")
    a = make_fact("limite_defesa_custos", {"amount": "500000.00", "currency": "BRL"})
    not_found = make_fact("limite_defesa_custos", None, status="NOT_FOUND", evidence=(), policy_id="POL-B")

    assert compare_facts(field, a, not_found).resultado == "AUSENTE_B"
    assert compare_facts(field, not_found, a).resultado == "AUSENTE_A"
    assert compare_facts(field, not_found, not_found).resultado == "AUSENTES_AMBOS"
    assert compare_facts(field, a, None).resultado == "AUSENTE_B"


def test_fato_ambiguo_aguarda_revisao():
    field = get_field("indice_reajuste")
    a = make_fact("indice_reajuste", None, status="AMBIGUOUS", evidence=("EV-10", "EV-11"), review=True)
    b = make_fact("indice_reajuste", {"number": "4"}, policy_id="POL-B")

    result = compare_facts(field, a, b)
    assert result.resultado == "AGUARDANDO_REVISAO"
    assert result.direcao == "n/a"


def test_comparacao_e_deterministica_e_idempotente():
    field = get_field("franquia")
    a = make_fact("franquia", {"amount": "50000.00", "currency": "BRL"})
    b = make_fact("franquia", {"amount": "25000.00", "currency": "BRL"}, policy_id="POL-B")

    first = compare_facts(field, a, b)
    second = compare_facts(field, a, b)
    assert first == second

    assert make_comparison_id("POL-A", "POL-B") == make_comparison_id("POL-A", "POL-B")
    assert make_comparison_id("POL-A", "POL-B") != make_comparison_id("POL-B", "POL-A")
"""RF-06 + RNF-01: regras determinísticas de comparação (domínio puro, sem LLM)."""

from fakes.policy_analysis import make_fact
from modules.policy_analysis.domain.catalog import get_field_spec
from modules.policy_analysis.domain.comparison import compare_field, normalize_value

NUMERIC = get_field_spec("limite_agregado")
DATE = get_field_spec("vigencia_inicio")
TEXT = get_field_spec("base_territorial")


def _fact_a(value, spec=NUMERIC):
    return make_fact("pol_a", spec.code, value=value, evidence_ids=["ev_a"])


def _fact_b(value, spec=NUMERIC):
    return make_fact("pol_b", spec.code, value=value, evidence_ids=["ev_b"])


def test_normalize_value_numeric():
    assert normalize_value(NUMERIC, {"scalar": 5}) == {"scalar": 5.0}
    assert normalize_value(NUMERIC, {"scalar": "1.000.000,00"}) == {"scalar": 1000000.0}
    assert normalize_value(NUMERIC, {"amount": 5000000.0}) == {"scalar": 5000000.0}


def test_normalize_value_date():
    assert normalize_value(DATE, {"scalar": "2025-01-31"}) == {"scalar": "2025-01-31"}
    assert normalize_value(DATE, {"scalar": "31/01/2025"}) == {"scalar": "2025-01-31"}


def test_normalize_value_text():
    assert normalize_value(TEXT, {"scalar": "  Cobertura Worldwide "}) == {"scalar": "cobertura worldwide"}


def test_normalize_value_ilegivel_retorna_none():
    assert normalize_value(NUMERIC, None) is None
    assert normalize_value(NUMERIC, {}) is None
    assert normalize_value(NUMERIC, {"scalar": "muitos milhões"}) is None
    assert normalize_value(DATE, {"scalar": "amanhã"}) is None
    assert normalize_value(TEXT, {"scalar": "   "}) is None


def test_numeric_maior_menor_igual():
    assert compare_field(NUMERIC, _fact_a({"scalar": 3000.0}), _fact_b({"scalar": 2000.0})).direction == "maior"
    assert compare_field(NUMERIC, _fact_a({"scalar": 1000.0}), _fact_b({"scalar": 2000.0})).direction == "menor"
    assert compare_field(NUMERIC, _fact_a({"scalar": 2000.0}), _fact_b({"scalar": 2000.0})).direction == "igual"


def test_date_maior_menor():
    maior = compare_field(DATE, _fact_a({"scalar": "2025-01-01"}, DATE), _fact_b({"scalar": "2024-01-01"}, DATE))
    menor = compare_field(DATE, _fact_a({"scalar": "2023-06-30"}, DATE), _fact_b({"scalar": "2024-01-01"}, DATE))
    assert maior.direction == "maior"
    assert menor.direction == "menor"


def test_text_igual_case_insensitive_e_divergente():
    igual = compare_field(TEXT, _fact_a({"scalar": "Brasil"}, TEXT), _fact_b({"scalar": "  brasil "}, TEXT))
    assert igual.direction == "igual"
    divergente = compare_field(TEXT, _fact_a({"scalar": "Brasil"}, TEXT), _fact_b({"scalar": "Argentina"}, TEXT))
    assert divergente.direction == "divergente"


def test_lado_ausente():
    assert compare_field(NUMERIC, None, _fact_b({"scalar": 1.0})).direction == "ausente_a"
    assert compare_field(NUMERIC, _fact_a({"scalar": 1.0}), None).direction == "ausente_b"


def test_not_found_conta_como_ausente():
    not_found_a = make_fact("pol_a", "limite_agregado", status="NOT_FOUND")
    not_found_b = make_fact("pol_b", "limite_agregado", status="NOT_FOUND")
    assert compare_field(NUMERIC, not_found_a, _fact_b({"scalar": 1.0})).direction == "ausente_a"
    assert compare_field(NUMERIC, _fact_a({"scalar": 1.0}), not_found_b).direction == "ausente_b"
    assert compare_field(NUMERIC, not_found_a, not_found_b).direction == "ausente_ambas"


def test_ambos_ausentes():
    assert compare_field(NUMERIC, None, None).direction == "ausente_ambas"


def test_comparacao_carrega_valores_fatos_e_evidencias():
    row = compare_field(NUMERIC, _fact_a({"scalar": 1.0}), _fact_b({"scalar": 2.0}))
    assert row.field_code == "limite_agregado"
    assert row.value_a == {"scalar": 1.0}
    assert row.value_b == {"scalar": 2.0}
    assert row.normalized_a == {"scalar": 1.0}
    assert row.normalized_b == {"scalar": 2.0}
    assert row.fact_id_a == "fact_pol_a_limite_agregado"
    assert row.fact_id_b == "fact_pol_b_limite_agregado"
    assert row.evidence_ids_a == ["ev_a"]
    assert row.evidence_ids_b == ["ev_b"]


def test_determinismo_mesma_entrada_mesma_saida():
    first = compare_field(NUMERIC, _fact_a({"scalar": 1.0}), _fact_b({"scalar": 2.0}))
    for _ in range(3):
        again = compare_field(NUMERIC, _fact_a({"scalar": 1.0}), _fact_b({"scalar": 2.0}))
        assert again == first
