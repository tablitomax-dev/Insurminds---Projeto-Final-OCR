"""RF-03/D2-P0-3: regras mínimas por campo — uma bateria por regra (domínio puro)."""

from fakes.policy_analysis import make_fact
from modules.policy_analysis.domain.catalog import get_field_spec
from modules.policy_analysis.domain.rules import validate_fact

FRANQUIA = get_field_spec("franquia")
LIMITE_AGREGADO = get_field_spec("limite_agregado")
BASE_TERRITORIAL = get_field_spec("base_territorial")
VIGENCIA_INICIO = get_field_spec("vigencia_inicio")
VIGENCIA_FIM = get_field_spec("vigencia_fim")


def _rules(violations):
    return [violation.rule for violation in violations]


def test_regra_valor_positivo():
    negativo = make_fact("pol_a", "franquia", value={"scalar": -10.0}, evidence_ids=["ev_1"])
    zero = make_fact("pol_a", "franquia", value={"scalar": 0.0}, evidence_ids=["ev_1"])
    positivo = make_fact("pol_a", "franquia", value={"scalar": 10.0}, evidence_ids=["ev_1"])

    assert _rules(validate_fact(FRANQUIA, negativo)) == ["valor_positivo"]
    assert _rules(validate_fact(FRANQUIA, zero)) == ["valor_positivo"]
    assert validate_fact(FRANQUIA, positivo) == []


def test_regra_moeda_conhecida():
    desconhecida = make_fact(
        "pol_a", "limite_agregado", value={"scalar": 1.0, "currency": "XYZ"}, evidence_ids=["ev_1"]
    )
    conhecida = make_fact(
        "pol_a", "limite_agregado", value={"scalar": 1.0, "currency": "BRL"}, evidence_ids=["ev_1"]
    )
    sem_moeda = make_fact("pol_a", "limite_agregado", value={"scalar": 1.0}, evidence_ids=["ev_1"])

    assert _rules(validate_fact(LIMITE_AGREGADO, desconhecida)) == ["moeda_conhecida"]
    assert validate_fact(LIMITE_AGREGADO, conhecida) == []
    assert validate_fact(LIMITE_AGREGADO, sem_moeda) == []


def test_regra_moeda_consistente():
    fact = make_fact(
        "pol_a", "limite_agregado", value={"scalar": 1.0, "currency": "USD"}, evidence_ids=["ev_1"]
    )
    divergente = make_fact(
        "pol_a",
        "limite_por_sinistro",
        value={"scalar": 2.0, "currency": "BRL"},
        evidence_ids=["ev_2"],
    )
    coerente = make_fact(
        "pol_a",
        "limite_por_sinistro",
        value={"scalar": 2.0, "currency": "USD"},
        evidence_ids=["ev_2"],
    )

    violacoes = validate_fact(LIMITE_AGREGADO, fact, {"limite_por_sinistro": divergente})
    assert _rules(violacoes) == ["moeda_consistente"]
    assert validate_fact(LIMITE_AGREGADO, fact, {"limite_por_sinistro": coerente}) == []


def test_regra_enum_base_territorial():
    conhecido = make_fact(
        "pol_a", "base_territorial", value={"scalar": "Brasil"}, evidence_ids=["ev_1"]
    )
    fora_do_enum = make_fact(
        "pol_a", "base_territorial", value={"scalar": "Atlântida"}, evidence_ids=["ev_1"]
    )

    assert validate_fact(BASE_TERRITORIAL, conhecido) == []
    assert _rules(validate_fact(BASE_TERRITORIAL, fora_do_enum)) == ["enum_base_territorial"]


def test_regra_vigencia_ordem():
    inicio = make_fact(
        "pol_a", "vigencia_inicio", value={"scalar": "2026-01-01"}, evidence_ids=["ev_i"]
    )
    fim_ok = make_fact(
        "pol_a", "vigencia_fim", value={"scalar": "2026-12-31"}, evidence_ids=["ev_f"]
    )
    fim_igual = make_fact(
        "pol_a", "vigencia_fim", value={"scalar": "2026-01-01"}, evidence_ids=["ev_f"]
    )
    fim_invertido = make_fact(
        "pol_a", "vigencia_fim", value={"scalar": "2025-12-31"}, evidence_ids=["ev_f"]
    )

    assert validate_fact(VIGENCIA_FIM, fim_ok, {"vigencia_inicio": inicio}) == []
    assert validate_fact(VIGENCIA_FIM, fim_igual, {"vigencia_inicio": inicio}) == []
    assert _rules(validate_fact(VIGENCIA_FIM, fim_invertido, {"vigencia_inicio": inicio})) == [
        "vigencia_ordem"
    ]
    # Par incompleto (counterpart ausente) não dispara a regra cruzada.
    assert validate_fact(VIGENCIA_INICIO, inicio) == []


def test_regra_vigencia_ordem_tambem_avalia_o_lado_inicio():
    fim = make_fact("pol_a", "vigencia_fim", value={"scalar": "2025-01-01"}, evidence_ids=["ev_f"])
    inicio_tardio = make_fact(
        "pol_a", "vigencia_inicio", value={"scalar": "2026-01-01"}, evidence_ids=["ev_i"]
    )

    violacoes = validate_fact(VIGENCIA_INICIO, inicio_tardio, {"vigencia_fim": fim})
    assert _rules(violacoes) == ["vigencia_ordem"]


def test_not_found_nao_recebe_regras():
    fact = make_fact("pol_a", "franquia", status="NOT_FOUND", value={"scalar": -1.0})

    assert validate_fact(FRANQUIA, fact) == []


def test_motivo_nao_carrega_o_valor_extraido():
    fact = make_fact(
        "pol_a", "limite_agregado", value={"scalar": 1.0, "currency": "XYZ"}, evidence_ids=["ev_1"]
    )

    for violation in validate_fact(LIMITE_AGREGADO, fact):
        assert "XYZ" not in violation.reason
        assert violation.field_code == "limite_agregado"
