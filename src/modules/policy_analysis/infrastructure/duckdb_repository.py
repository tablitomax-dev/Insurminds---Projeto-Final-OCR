"""Persistência DuckDB do policy_analysis (RF-05, D-06).

Schema auto-criado na primeira execução (`CREATE TABLE IF NOT EXISTS`).
IDs são os do `shared_kernel` — a mesma `evidence_id`/`document_id` dos chunks
indexados pelo Dev 1 (consistência banco↔índice, resumo §14). Upsert é
DELETE+INSERT em transação: re-extração e re-comparação nunca duplicam
(EC-06).
"""

from __future__ import annotations

import json
from datetime import date, datetime

import duckdb

from shared_kernel.contracts import ExtractedFact

from ..domain.models import ComparisonResult, FieldComparison, ReviewItem

_SCHEMA = """
CREATE TABLE IF NOT EXISTS policies (
    policy_id VARCHAR PRIMARY KEY,
    seguradora VARCHAR,
    vigencia_inicio DATE,
    vigencia_fim DATE,
    fonte_documentos VARCHAR,
    created_at TIMESTAMP
);
CREATE TABLE IF NOT EXISTS documents (
    document_id VARCHAR PRIMARY KEY,
    policy_id VARCHAR,
    nome_fonte VARCHAR
);
CREATE TABLE IF NOT EXISTS facts (
    fact_id VARCHAR PRIMARY KEY,
    policy_id VARCHAR,
    field_code VARCHAR,
    status VARCHAR,
    value VARCHAR,
    normalized_value VARCHAR,
    confidence DOUBLE,
    evidence_ids VARCHAR,
    requires_human_review BOOLEAN,
    revisao_status VARCHAR,
    revisao_decisao VARCHAR,
    revisao_por VARCHAR,
    revisao_em VARCHAR,
    run_id VARCHAR,
    schema_version VARCHAR
);
CREATE TABLE IF NOT EXISTS comparisons (
    comparison_id VARCHAR,
    policy_id_a VARCHAR,
    policy_id_b VARCHAR,
    field_code VARCHAR,
    resultado VARCHAR,
    valor_a VARCHAR,
    valor_b VARCHAR,
    direcao VARCHAR,
    evidencias_a VARCHAR,
    evidencias_b VARCHAR,
    explicacao VARCHAR,
    created_at TIMESTAMP,
    PRIMARY KEY (comparison_id, field_code)
);
"""


#: Migrações versionadas do schema (D2-P2-3). A baseline `001` é o schema
#: atual (4 tabelas). Para evoluir: acrescentar `{N: SQL}` e bumpar — cada
#: migração roda uma vez e fica registrada em `schema_migrations`. Os
#: `CREATE ... IF NOT EXISTS` mantêm a adoção de bancos antigos idempotente.
_MIGRATIONS: dict[int, str] = {
    1: _SCHEMA,
}

_MIGRATIONS_TABLE = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at TIMESTAMP
);
"""


def _dumps(value) -> str | None:
    return None if value is None else json.dumps(value, ensure_ascii=False, sort_keys=True)


def _loads(value) -> dict | None:
    return None if value is None else json.loads(value)


class PolicyAnalysisRepository:
    """Repositório das apólices, fatos e comparações."""

    def __init__(self, db_path: str = ":memory:"):
        self._con = duckdb.connect(db_path)
        self.init_schema()

    def init_schema(self) -> None:
        self._con.execute(_MIGRATIONS_TABLE)
        applied = {
            row[0] for row in self._con.execute("SELECT version FROM schema_migrations").fetchall()
        }
        for version in sorted(_MIGRATIONS):
            if version in applied:
                continue
            self._con.execute(_MIGRATIONS[version])
            self._con.execute(
                "INSERT INTO schema_migrations (version, applied_at) VALUES (?, now())",
                [version],
            )

    # --- apólices e documentos -------------------------------------------------

    def upsert_policy(self, policy: dict) -> None:
        self._con.execute("DELETE FROM policies WHERE policy_id = ?", [policy["policy_id"]])
        self._con.execute(
            "INSERT INTO policies VALUES (?, ?, ?, ?, ?, ?)",
            [
                policy["policy_id"],
                policy.get("seguradora"),
                _as_date(policy.get("vigencia_inicio")),
                _as_date(policy.get("vigencia_fim")),
                policy.get("fonte_documentos"),
                datetime.utcnow(),
            ],
        )

    def upsert_document(self, document: dict) -> None:
        self._con.execute("DELETE FROM documents WHERE document_id = ?", [document["document_id"]])
        self._con.execute(
            "INSERT INTO documents VALUES (?, ?, ?)",
            [document["document_id"], document["policy_id"], document.get("nome_fonte")],
        )

    # --- fatos -----------------------------------------------------------------

    def upsert_fact(
        self,
        fact: ExtractedFact,
        run_id: str,
        schema_version: str = "1.0",
        revisao_status: str | None = None,
    ) -> None:
        status_revisao = revisao_status or ("PENDENTE" if fact.requires_human_review else "CONFIRMADO")
        self._con.execute("DELETE FROM facts WHERE fact_id = ?", [fact.fact_id])
        self._con.execute(
            "INSERT INTO facts VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                fact.fact_id,
                fact.policy_id,
                fact.field_code,
                fact.status,
                _dumps(fact.value),
                _dumps(fact.normalized_value),
                fact.confidence,
                _dumps(fact.evidence_ids),
                fact.requires_human_review,
                status_revisao,
                None,
                None,
                None,
                run_id,
                schema_version,
            ],
        )

    def get_facts(self, policy_id: str, field_code: str | None = None) -> list[ExtractedFact]:
        sql = "SELECT * FROM facts WHERE policy_id = ?"
        params: list = [policy_id]
        if field_code is not None:
            sql += " AND field_code = ?"
            params.append(field_code)
        sql += " ORDER BY field_code"
        return [self._row_to_fact(row) for row in self._con.execute(sql, params).fetchall()]

    def get_review_item(self, fact_id: str) -> ReviewItem | None:
        rows = self._con.execute("SELECT * FROM facts WHERE fact_id = ?", [fact_id]).fetchall()
        return self._row_to_review(rows[0]) if rows else None

    def get_review_items(self, policy_id: str | None = None) -> list[ReviewItem]:
        sql = "SELECT * FROM facts"
        params: list = []
        if policy_id is not None:
            sql += " WHERE policy_id = ?"
            params.append(policy_id)
        sql += " ORDER BY field_code"
        return [self._row_to_review(row) for row in self._con.execute(sql, params).fetchall()]

    def record_review(
        self,
        fact_id: str,
        revisao_status: str,
        revisao_decisao: dict,
        revisao_por: str,
        revisao_em: str,
        *,
        new_value: dict | None = None,
        new_normalized_value: dict | None = None,
        new_status: str | None = None,
        requires_human_review: bool = False,
    ) -> None:
        sets = [
            "revisao_status = ?",
            "revisao_decisao = ?",
            "revisao_por = ?",
            "revisao_em = ?",
            "requires_human_review = ?",
        ]
        params: list = [
            revisao_status,
            _dumps(revisao_decisao),
            revisao_por,
            revisao_em,
            requires_human_review,
        ]
        if new_value is not None:
            sets.append("value = ?")
            params.append(_dumps(new_value))
        if new_normalized_value is not None:
            sets.append("normalized_value = ?")
            params.append(_dumps(new_normalized_value))
        if new_status is not None:
            sets.append("status = ?")
            params.append(new_status)
        params.append(fact_id)
        self._con.execute(f"UPDATE facts SET {', '.join(sets)} WHERE fact_id = ?", params)

    # --- comparações -----------------------------------------------------------

    def upsert_comparison(self, result: ComparisonResult) -> None:
        self._con.execute("DELETE FROM comparisons WHERE comparison_id = ?", [result.comparison_id])
        for campo in result.campos:
            self._con.execute(
                "INSERT INTO comparisons VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    result.comparison_id,
                    result.policy_id_a,
                    result.policy_id_b,
                    campo.field_code,
                    campo.resultado,
                    _dumps(campo.valor_a),
                    _dumps(campo.valor_b),
                    campo.direcao,
                    _dumps(list(campo.evidencias_a)),
                    _dumps(list(campo.evidencias_b)),
                    campo.explicacao,
                    datetime.utcnow(),
                ],
            )

    def get_comparison(self, comparison_id: str) -> ComparisonResult | None:
        rows = self._con.execute(
            "SELECT * FROM comparisons WHERE comparison_id = ? ORDER BY field_code", [comparison_id]
        ).fetchall()
        if not rows:
            return None
        campos = tuple(
            FieldComparison(
                field_code=row[3],
                resultado=row[4],
                valor_a=_loads(row[5]),
                valor_b=_loads(row[6]),
                direcao=row[7],
                evidencias_a=tuple(_loads(row[8]) or []),
                evidencias_b=tuple(_loads(row[9]) or []),
                explicacao=row[10],
            )
            for row in rows
        )
        return ComparisonResult(
            comparison_id=rows[0][0],
            policy_id_a=rows[0][1],
            policy_id_b=rows[0][2],
            campos=campos,
        )

    def update_explanation(self, comparison_id: str, field_code: str, explicacao: str) -> None:
        self._con.execute(
            "UPDATE comparisons SET explicacao = ? WHERE comparison_id = ? AND field_code = ?",
            [explicacao, comparison_id, field_code],
        )

    # --- conversões -------------------------------------------------------------

    @staticmethod
    def _row_to_fact(row) -> ExtractedFact:
        return ExtractedFact(
            fact_id=row[0],
            policy_id=row[1],
            field_code=row[2],
            status=row[3],
            value=_loads(row[4]),
            normalized_value=_loads(row[5]),
            confidence=row[6],
            evidence_ids=_loads(row[7]) or [],  # type: ignore[arg-type]  # JSON desserializado
            requires_human_review=bool(row[8]),
        )

    def _row_to_review(self, row) -> ReviewItem:
        return ReviewItem(
            fact=self._row_to_fact(row),
            revisao_status=row[9],
            revisao_decisao=_loads(row[10]),
            revisao_por=row[11],
            revisao_em=row[12],
        )


def _as_date(value) -> date | None:
    if value is None or isinstance(value, date):
        return value
    return datetime.strptime(str(value), "%Y-%m-%d").date()
