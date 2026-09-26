"""RF-06/RF-07/RF-08: ComparisonService (compare, explain, export) com fakes."""

import pytest

from fakes.policy_analysis import (
    FakeExplanationGenerator,
    InMemoryFactRepository,
    make_evidence,
    make_fact,
)
from modules.policy_analysis.application.comparison import ComparisonService
from modules.policy_analysis.application.ports import LlmOutputError
from modules.policy_analysis.domain.catalog import FIELD_CATALOG
from shared_kernel.errors import ContractNotFound

EXPECTED_DIRECTIONS = {
    "limite_agregado": "menor",
    "limite_por_sinistro": "ausente_ambas",
    "franquia": "ausente_ambas",
    "vigencia_inicio": "ausente_a",
    "vigencia_fim": "ausente_ambas",
    "base_territorial": "igual",
    "retroatividade": "ausente_ambas",
    "prazo_notificacao": "ausente_ambas",
    "exclusoes_chave": "ausente_ambas",
    "nome_segurado": "ausente_b",
}


def _seeded_service(**generator_kwargs):
    repository = InMemoryFactRepository()
    repository.upsert_fact(
        make_fact("pol_a", "limite_agregado", value={"scalar": 1000.0}, evidence_ids=["ev_a_agg"])
    )
    repository.upsert_fact(
        make_fact("pol_b", "limite_agregado", value={"scalar": 2000.0}, evidence_ids=["ev_b_agg"])
    )
    repository.upsert_fact(
        make_fact("pol_a", "base_territorial", value={"scalar": "Brasil"}, evidence_ids=["ev_a_base"])
    )
    repository.upsert_fact(
        make_fact("pol_b", "base_territorial", value={"scalar": "brasil"}, evidence_ids=["ev_b_base"])
    )
    repository.upsert_fact(
        make_fact("pol_a", "nome_segurado", value={"scalar": "ACME"}, evidence_ids=["ev_a_nome"])
    )
    repository.upsert_fact(
        make_fact("pol_b", "vigencia_inicio", value={"scalar": "2025-01-01"}, evidence_ids=["ev_b_vig"])
    )
    for evidence_id in ("ev_a_agg", "ev_b_agg", "ev_a_base", "ev_b_base", "ev_a_nome", "ev_b_vig"):
        repository.save_evidence(make_evidence(evidence_id))
    generator = FakeExplanationGenerator(**generator_kwargs)
    service = ComparisonService(repository=repository, explanation_generator=generator)
    return service, repository, generator


def test_comparacao_gera_dez_linhas_com_todos_os_campos():
    service, repository, _ = _seeded_service()

    result = service.compare_policies("pol_a", "pol_b")

    assert result.comparison_id.startswith("cmp_")
    assert result.policy_id_a == "pol_a"
    assert result.policy_id_b == "pol_b"
    assert [row.field_code for row in result.rows] == list(FIELD_CATALOG)
    assert {row.field_code: row.direction for row in result.rows} == EXPECTED_DIRECTIONS
    assert repository.get_comparison(result.comparison_id) == result


def test_comparacao_e_deterministica():
    service, _, _ = _seeded_service()

    first = service.compare_policies("pol_a", "pol_b")
    second = service.compare_policies("pol_a", "pol_b")

    assert [(row.field_code, row.direction) for row in first.rows] == [
        (row.field_code, row.direction) for row in second.rows
    ]


def test_comparacao_inexistente_gera_contract_not_found():
    service, _, _ = _seeded_service()

    with pytest.raises(ContractNotFound):
        service.explain_difference("cmp_inexistente", "franquia")


def test_explicacao_sem_evidence_id_citado_e_rejeitada():
    service, _, _ = _seeded_service(cited_ids=[])
    comparison = service.compare_policies("pol_a", "pol_b")

    with pytest.raises(LlmOutputError):
        service.explain_difference(comparison.comparison_id, "limite_agregado")


def test_explicacao_com_evidence_id_inventado_e_rejeitada():
    service, _, _ = _seeded_service(cited_ids=["ev_fantasma"])
    comparison = service.compare_policies("pol_a", "pol_b")

    with pytest.raises(LlmOutputError):
        service.explain_difference(comparison.comparison_id, "limite_agregado")


def test_explicacao_precisa_citar_os_dois_lados():
    service, _, _ = _seeded_service(cited_ids=["ev_a_agg"])
    comparison = service.compare_policies("pol_a", "pol_b")

    with pytest.raises(LlmOutputError):
        service.explain_difference(comparison.comparison_id, "limite_agregado")


def test_explicacao_valida_e_aceita():
    service, _, generator = _seeded_service(
        text="O limite agregado de A é menor que o de B.",
        cited_ids=["ev_a_agg", "ev_b_agg"],
    )
    comparison = service.compare_policies("pol_a", "pol_b")

    text, cited_ids = service.explain_difference(comparison.comparison_id, "limite_agregado")

    assert text == "O limite agregado de A é menor que o de B."
    assert cited_ids == ["ev_a_agg", "ev_b_agg"]
    field_code, direction, evidences_a, evidences_b = generator.calls[0]
    assert field_code == "limite_agregado"
    assert direction == "menor"
    assert [evidence.evidence_id for evidence in evidences_a] == ["ev_a_agg"]
    assert [evidence.evidence_id for evidence in evidences_b] == ["ev_b_agg"]


def test_explicacao_de_lado_unilateral_e_valida():
    service, _, _ = _seeded_service(cited_ids=["ev_a_nome"])
    comparison = service.compare_policies("pol_a", "pol_b")

    _, cited_ids = service.explain_difference(comparison.comparison_id, "nome_segurado")

    assert cited_ids == ["ev_a_nome"]


def test_export_escreve_markdown_com_todos_os_campos(tmp_path):
    service, _, _ = _seeded_service()
    comparison = service.compare_policies("pol_a", "pol_b")

    export_path = service.export_comparison(comparison.comparison_id, export_dir=tmp_path)

    assert export_path == tmp_path / f"{comparison.comparison_id}.md"
    content = export_path.read_text(encoding="utf-8")
    assert comparison.comparison_id in content
    assert "pol_a" in content and "pol_b" in content
    for code in FIELD_CATALOG:
        assert code in content
    assert "menor" in content
    assert "ausente_ambas" in content
    assert content.count("explicação não gerada") == 10


def test_export_inclui_explicacao_quando_ja_gerada(tmp_path):
    service, _, _ = _seeded_service(
        text="Diferença relevante para o analista.",
        cited_ids=["ev_a_agg", "ev_b_agg"],
    )
    comparison = service.compare_policies("pol_a", "pol_b")
    service.explain_difference(comparison.comparison_id, "limite_agregado")

    export_path = service.export_comparison(comparison.comparison_id, export_dir=tmp_path)
    content = export_path.read_text(encoding="utf-8")

    assert "Diferença relevante para o analista." in content
    assert content.count("explicação não gerada") == 9
