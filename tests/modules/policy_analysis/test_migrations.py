"""T-migrations — DuckDB defensivo (D2-P2-3): baseline versionada e idempotente."""

from __future__ import annotations

from modules.policy_analysis.infrastructure.duckdb_repository import (
    PolicyAnalysisRepository,
)


def _versions(repo) -> list[int]:
    return sorted(
        row[0] for row in repo._con.execute("SELECT version FROM schema_migrations").fetchall()
    )


def test_baseline_001_registrada_na_criacao():
    repo = PolicyAnalysisRepository(":memory:")
    assert _versions(repo) == [1, 2]


def test_tabelas_do_schema_existem():
    repo = PolicyAnalysisRepository(":memory:")
    tables = {
        row[0]
        for row in repo._con.execute("SELECT table_name FROM information_schema.tables").fetchall()
    }
    for expected in (
        "policies",
        "documents",
        "facts",
        "comparisons",
        "schema_migrations",
        "document_markdown",
        "extra_findings",
    ):
        assert expected in tables


def test_init_schema_e_idempotente_nao_duplica_migracao():
    repo = PolicyAnalysisRepository(":memory:")
    repo.init_schema()  # segunda execução não reaplica nem quebra
    assert _versions(repo) == [1, 2]


def test_migracao_aplicada_uma_vez_mesmo_reabrindo_banco(tmp_path):
    db = str(tmp_path / "pa.duckdb")
    PolicyAnalysisRepository(db)
    repo2 = PolicyAnalysisRepository(db)  # reabre: não reaplica
    assert _versions(repo2) == [1, 2]
