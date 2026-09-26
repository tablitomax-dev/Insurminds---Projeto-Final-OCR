"""Adapter DuckDB do repositório de fatos (RF-05, schema em data-delta.md).

`import duckdb` é lazy: sem a lib a instanciação falha com
`RuntimeError("dependência ausente: duckdb")`. Serialização de `value`,
`normalized_value` e `evidence_ids` em JSON.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import cast

from shared_kernel.contracts import EvidenceRef, ExtractedFact

from ..domain.catalog import FIELD_CATALOG
from ..domain.comparison import ComparisonResult, FieldComparison
from ..domain.review import ReviewAction, ReviewDecision

#: Caminho padrão do banco local (data-delta §2).
DEFAULT_DB_PATH = "data/facts.duckdb"

_CATALOG_ORDER = {code: index for index, code in enumerate(FIELD_CATALOG)}

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS policies (
  policy_id VARCHAR PRIMARY KEY,
  seguradora VARCHAR,
  vigencia_inicio DATE,
  vigencia_fim DATE
);
CREATE TABLE IF NOT EXISTS documents (
  document_id VARCHAR PRIMARY KEY,
  policy_id VARCHAR NOT NULL,
  file_path VARCHAR
);
CREATE TABLE IF NOT EXISTS facts (
  fact_id VARCHAR PRIMARY KEY,
  policy_id VARCHAR NOT NULL,
  field_code VARCHAR NOT NULL,
  status VARCHAR NOT NULL,
  value JSON,
  normalized_value JSON,
  confidence DOUBLE,
  evidence_ids JSON,
  requires_human_review BOOLEAN,
  created_at TIMESTAMP
);
CREATE TABLE IF NOT EXISTS comparisons (
  comparison_id VARCHAR NOT NULL,
  policy_id_a VARCHAR NOT NULL,
  policy_id_b VARCHAR NOT NULL,
  field_code VARCHAR NOT NULL,
  direction VARCHAR NOT NULL,
  result JSON,
  explanation TEXT,
  created_at TIMESTAMP,
  PRIMARY KEY (comparison_id, field_code)
);
CREATE TABLE IF NOT EXISTS evidences (
  evidence_id VARCHAR PRIMARY KEY,
  policy_id VARCHAR NOT NULL,
  document_id VARCHAR NOT NULL,
  payload JSON,
  created_at TIMESTAMP
);
CREATE TABLE IF NOT EXISTS reviews (
  review_id VARCHAR PRIMARY KEY,
  policy_id VARCHAR NOT NULL,
  field_code VARCHAR NOT NULL,
  fact_id VARCHAR NOT NULL,
  action VARCHAR NOT NULL,
  reviewer VARCHAR NOT NULL,
  original_value JSON,
  corrected_value JSON,
  evidence_ids JSON,
  note VARCHAR,
  reviewed_at VARCHAR
);
"""


class DuckDbFactRepository:
    """Implementação DuckDB da porta `FactRepository`."""

    def __init__(self, db_path: str = DEFAULT_DB_PATH) -> None:
        try:
            import duckdb
        except ImportError as exc:
            raise RuntimeError("dependência ausente: duckdb") from exc
        if db_path != ":memory:":
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = duckdb.connect(db_path)
        self._conn.execute(_SCHEMA_SQL)

    def upsert_fact(self, fact: ExtractedFact) -> None:
        """Idempotente por `(policy_id, field_code)` (RN-04): delete + insert."""
        self._conn.execute(
            "DELETE FROM facts WHERE fact_id = ? OR (policy_id = ? AND field_code = ?)",
            [fact.fact_id, fact.policy_id, fact.field_code],
        )
        self._conn.execute(
            """
            INSERT INTO facts (
              fact_id, policy_id, field_code, status, value, normalized_value,
              confidence, evidence_ids, requires_human_review, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                fact.fact_id,
                fact.policy_id,
                fact.field_code,
                fact.status,
                _dump(fact.value),
                _dump(fact.normalized_value),
                fact.confidence,
                _dump(fact.evidence_ids),
                fact.requires_human_review,
                datetime.now(timezone.utc),
            ],
        )

    def get_facts(self, policy_id: str) -> list[ExtractedFact]:
        rows = self._conn.execute(
            "SELECT fact_id, policy_id, field_code, status, value, normalized_value,"
            " confidence, evidence_ids, requires_human_review FROM facts WHERE policy_id = ?",
            [policy_id],
        ).fetchall()
        return _sort_facts([_row_to_fact(row) for row in rows])

    def get_fact(self, policy_id: str, field_code: str) -> ExtractedFact | None:
        rows = self._conn.execute(
            "SELECT fact_id, policy_id, field_code, status, value, normalized_value,"
            " confidence, evidence_ids, requires_human_review FROM facts"
            " WHERE policy_id = ? AND field_code = ?",
            [policy_id, field_code],
        ).fetchall()
        return _row_to_fact(rows[0]) if rows else None

    def list_review_queue(self, policy_id: str | None = None) -> list[ExtractedFact]:
        sql = (
            "SELECT fact_id, policy_id, field_code, status, value, normalized_value,"
            " confidence, evidence_ids, requires_human_review FROM facts"
            " WHERE (status IN ('AMBIGUOUS', 'NEEDS_REVIEW') OR requires_human_review)"
        )
        params: list[str] = []
        if policy_id is not None:
            sql += " AND policy_id = ?"
            params.append(policy_id)
        rows = self._conn.execute(sql, params).fetchall()
        return _sort_facts([_row_to_fact(row) for row in rows])

    def save_evidence(self, evidence: EvidenceRef) -> None:
        self._conn.execute(
            "DELETE FROM evidences WHERE evidence_id = ?", [evidence.evidence_id]
        )
        self._conn.execute(
            "INSERT INTO evidences (evidence_id, policy_id, document_id, payload, created_at)"
            " VALUES (?, ?, ?, ?, ?)",
            [
                evidence.evidence_id,
                evidence.policy_id,
                evidence.document_id,
                evidence.model_dump_json(),
                datetime.now(timezone.utc),
            ],
        )

    def get_evidence(self, evidence_id: str) -> EvidenceRef | None:
        rows = self._conn.execute(
            "SELECT payload FROM evidences WHERE evidence_id = ?", [evidence_id]
        ).fetchall()
        return EvidenceRef.model_validate(json.loads(rows[0][0])) if rows else None

    def save_comparison(self, result: ComparisonResult) -> None:
        """Persiste uma linha por campo (JSON por linha), com explicação nula."""
        self._conn.execute(
            "DELETE FROM comparisons WHERE comparison_id = ?", [result.comparison_id]
        )
        for row in result.rows:
            self._conn.execute(
                "INSERT INTO comparisons (comparison_id, policy_id_a, policy_id_b,"
                " field_code, direction, result, explanation, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    result.comparison_id,
                    result.policy_id_a,
                    result.policy_id_b,
                    row.field_code,
                    row.direction,
                    _dump(_row_to_dict(row)),
                    None,
                    datetime.now(timezone.utc),
                ],
            )

    def get_comparison(self, comparison_id: str) -> ComparisonResult | None:
        rows = self._conn.execute(
            "SELECT policy_id_a, policy_id_b, result FROM comparisons WHERE comparison_id = ?",
            [comparison_id],
        ).fetchall()
        if not rows:
            return None
        comparisons = sorted(
            (FieldComparison(**json.loads(row[2])) for row in rows),
            key=_catalog_key,
        )
        return ComparisonResult(
            comparison_id=comparison_id,
            policy_id_a=rows[0][0],
            policy_id_b=rows[0][1],
            rows=comparisons,
        )

    def save_review(self, decision: ReviewDecision) -> None:
        """Persiste a decisão humana (auditoria: quem decidiu, quando e o quê)."""
        self._conn.execute(
            "DELETE FROM reviews WHERE review_id = ?", [decision.review_id]
        )
        self._conn.execute(
            "INSERT INTO reviews (review_id, policy_id, field_code, fact_id, action,"
            " reviewer, original_value, corrected_value, evidence_ids, note, reviewed_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                decision.review_id,
                decision.policy_id,
                decision.field_code,
                decision.fact_id,
                decision.action,
                decision.reviewer,
                _dump(decision.original_value),
                _dump(decision.corrected_value),
                _dump(decision.evidence_ids),
                decision.note,
                decision.reviewed_at,
            ],
        )

    def list_reviews(
        self, policy_id: str | None = None, field_code: str | None = None
    ) -> list[ReviewDecision]:
        sql = (
            "SELECT review_id, policy_id, field_code, fact_id, action, reviewer,"
            " original_value, corrected_value, evidence_ids, note, reviewed_at FROM reviews"
        )
        clauses: list[str] = []
        params: list[str] = []
        if policy_id is not None:
            clauses.append("policy_id = ?")
            params.append(policy_id)
        if field_code is not None:
            clauses.append("field_code = ?")
            params.append(field_code)
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        rows = self._conn.execute(sql, params).fetchall()
        return [_row_to_review(row) for row in rows]

    def upsert_policy(
        self,
        policy_id: str,
        seguradora: str | None = None,
        vigencia_inicio: str | None = None,
        vigencia_fim: str | None = None,
    ) -> None:
        """Upsert simples da apólice (data-delta §2)."""
        self._conn.execute("DELETE FROM policies WHERE policy_id = ?", [policy_id])
        self._conn.execute(
            "INSERT INTO policies (policy_id, seguradora, vigencia_inicio, vigencia_fim)"
            " VALUES (?, ?, CAST(? AS DATE), CAST(? AS DATE))",
            [policy_id, seguradora, vigencia_inicio, vigencia_fim],
        )

    def upsert_document(self, document_id: str, policy_id: str, file_path: str | None = None) -> None:
        """Upsert simples do documento (data-delta §2)."""
        self._conn.execute("DELETE FROM documents WHERE document_id = ?", [document_id])
        self._conn.execute(
            "INSERT INTO documents (document_id, policy_id, file_path) VALUES (?, ?, ?)",
            [document_id, policy_id, file_path],
        )

    def close(self) -> None:
        self._conn.close()


def _dump(value: object) -> str | None:
    return None if value is None else json.dumps(value, ensure_ascii=False)


def _row_to_fact(row: tuple) -> ExtractedFact:
    (
        fact_id,
        policy_id,
        field_code,
        status,
        value,
        normalized_value,
        confidence,
        evidence_ids,
        requires_human_review,
    ) = row
    return ExtractedFact.model_validate(
        {
            "fact_id": fact_id,
            "policy_id": policy_id,
            "field_code": field_code,
            "status": status,
            "value": None if value is None else json.loads(value),
            "normalized_value": None if normalized_value is None else json.loads(normalized_value),
            "confidence": confidence,
            "evidence_ids": json.loads(evidence_ids),
            "requires_human_review": requires_human_review,
        }
    )


def _row_to_review(row: tuple) -> ReviewDecision:
    (
        review_id,
        policy_id,
        field_code,
        fact_id,
        action,
        reviewer,
        original_value,
        corrected_value,
        evidence_ids,
        note,
        reviewed_at,
    ) = row
    return ReviewDecision(
        review_id=review_id,
        policy_id=policy_id,
        field_code=field_code,
        fact_id=fact_id,
        action=cast(ReviewAction, action),
        reviewer=reviewer,
        reviewed_at=reviewed_at,
        original_value=None if original_value is None else json.loads(original_value),
        corrected_value=None if corrected_value is None else json.loads(corrected_value),
        evidence_ids=json.loads(evidence_ids),
        note=note,
    )


def _row_to_dict(row: FieldComparison) -> dict[str, object]:
    return {
        "field_code": row.field_code,
        "direction": row.direction,
        "value_a": row.value_a,
        "value_b": row.value_b,
        "normalized_a": row.normalized_a,
        "normalized_b": row.normalized_b,
        "fact_id_a": row.fact_id_a,
        "fact_id_b": row.fact_id_b,
        "evidence_ids_a": row.evidence_ids_a,
        "evidence_ids_b": row.evidence_ids_b,
    }


def _catalog_key(row: FieldComparison) -> tuple[int, str]:
    return (_CATALOG_ORDER.get(row.field_code, len(_CATALOG_ORDER)), row.field_code)


def _sort_facts(facts: list[ExtractedFact]) -> list[ExtractedFact]:
    return sorted(
        facts,
        key=lambda fact: (_CATALOG_ORDER.get(fact.field_code, len(_CATALOG_ORDER)), fact.field_code),
    )
