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
    assert compare_field(DATE, _fact_a({"scalar": "2025-01-01"}, DATE), _fact_b({"scalar": "2024-01-01"}, DATE)).direction == "maior"
    assert compare_field(DATE, _fact_a({"scalar": "2023-06-30"}, DATE), _fact_b({"scalar": "2024-01-01"}, DATE)).direction == "menor"


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
