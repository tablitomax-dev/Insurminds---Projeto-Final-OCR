"""T009 — Repositório DuckDB: schema auto-criado, upsert idempotente, IDs (RF-05)."""

from __future__ import annotations

from modules.policy_analysis.domain.models import ComparisonResult, FieldComparison
from modules.policy_analysis.infrastructure.duckdb_repository import PolicyAnalysisRepository
from shared_kernel.contracts import ExtractedFact


def make_fact(fact_id: str = "FAC-1", code: str = "franquia") -> ExtractedFact:
    return ExtractedFact(
        fact_id=fact_id,
        policy_id="POL-A",
        field_code=code,
        status="FOUND",
        value={"amount": "50000.00"},
        normalized_value={"amount": "50000.00", "currency": "BRL"},
        confidence=0.9,
        evidence_ids=["EV-A-003"],
        requires_human_review=False,
    )


def test_schema_auto_criado_e_idempotente(tmp_path):
    db = tmp_path / "pa.duckdb"
    repo = PolicyAnalysisRepository(str(db))
    repo.init_schema()  # segunda chamada não pode falhar nem duplicar
    repo2 = PolicyAnalysisRepository(str(db))
    repo2.init_schema()
    assert repo2.get_facts("POL-A") == []


def test_upsert_fact_preserva_contrato_e_nao_duplica(tmp_path):
    repo = PolicyAnalysisRepository(":memory:")
    repo.upsert_fact(make_fact(), run_id="RUN-1")
    repo.upsert_fact(make_fact(), run_id="RUN-2")  # re-extração: mesmo fact_id

    facts = repo.get_facts("POL-A")
    assert len(facts) == 1
    fact = facts[0]
    assert fact.fact_id == "FAC-1"
    assert fact.status == "FOUND"
    assert fact.evidence_ids == ["EV-A-003"]
    assert fact.normalized_value == {"amount": "50000.00", "currency": "BRL"}
    assert fact.requires_human_review is False


def test_get_facts_filtra_por_campo(tmp_path):
    repo = PolicyAnalysisRepository(":memory:")
    repo.upsert_fact(make_fact("FAC-1", "franquia"), run_id="RUN-1")
    repo.upsert_fact(make_fact("FAC-2", "vigencia"), run_id="RUN-1")

    assert [f.field_code for f in repo.get_facts("POL-A")] == ["franquia", "vigencia"]
    assert [f.fact_id for f in repo.get_facts("POL-A", field_code="franquia")] == ["FAC-1"]


def test_comparacao_round_trip_e_idempotente(tmp_path):
    repo = PolicyAnalysisRepository(":memory:")
    campo = FieldComparison(
        field_code="franquia",
        resultado="MAIOR",
        valor_a={"amount": "50000.00", "currency": "BRL"},
        valor_b={"amount": "25000.00", "currency": "BRL"},
        direcao="A",
        evidencias_a=["EV-A-003"],
        evidencias_b=["EV-B-003"],
        explicacao=None,
    )
    result = ComparisonResult(
        comparison_id="CMP-1",
        policy_id_a="POL-A",
        policy_id_b="POL-B",
        campos=(campo,),
    )
    repo.upsert_comparison(result)
    repo.upsert_comparison(result)  # mesma comparação não duplica

    loaded = repo.get_comparison("CMP-1")
    assert loaded is not None
    assert loaded.comparison_id == "CMP-1"
    assert len(loaded.campos) == 1
    assert loaded.campos[0].resultado == "MAIOR"

    repo.update_explanation("CMP-1", "franquia", "A franquia de A é maior (EV-A-003, EV-B-003).")
    reloaded = repo.get_comparison("CMP-1")
    assert "EV-A-003" in reloaded.campos[0].explicacao


def test_review_round_trip(tmp_path):
    repo = PolicyAnalysisRepository(":memory:")
    fact = ExtractedFact(
        fact_id="FAC-AMB",
        policy_id="POL-A",
        field_code="indice_reajuste",
        status="AMBIGUOUS",
        value={"text": "4% ou 5%"},
        normalized_value=None,
        confidence=0.4,
        evidence_ids=["EV-A-010", "EV-A-011"],
        requires_human_review=True,
    )
    repo.upsert_fact(fact, run_id="RUN-1")

    pending = repo.get_review_items("POL-A")
    assert len(pending) == 1
    assert pending[0].revisao_status == "PENDENTE"
    assert pending[0].fact.evidence_ids == ["EV-A-010", "EV-A-011"]

    repo.record_review("FAC-AMB", "CONFIRMADO", {"decisao": "confirmado"}, "analista", "2026-09-26T12:00:00Z")
    items = repo.get_review_items("POL-A")
    assert items[0].revisao_status == "CONFIRMADO"
    assert items[0].revisao_por == "analista"
