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
