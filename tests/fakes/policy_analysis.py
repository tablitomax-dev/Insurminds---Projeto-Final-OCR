"""Fakes do módulo policy_analysis (mundo novo — nenhuma dependência externa).

Reaproveita os fakes do próprio módulo (`MockEvidenceSource`,
`FixtureExtractionAgent`, `FixtureExplanationAgent`) e acrescenta os helpers
usados pelos testes (`make_evidence`, `make_fact`) mais agentes scriptáveis no
contrato novo (`extract(requests, run_id) -> list[dict]` bruto).
"""

from __future__ import annotations

from modules.policy_analysis.application.errors import ClassifiedError
from modules.policy_analysis.domain.models import ComparisonResult
from modules.policy_analysis.infrastructure.evidence_source import MockEvidenceSource
from modules.policy_analysis.infrastructure.llm_agent import (
    FixtureExplanationAgent,
    FixtureExtractionAgent,
)
from shared_kernel.contracts import (
    EvidenceRef,
    ExtractedFact,
    ExtractionRequest,
)


def make_evidence(
    evidence_id: str,
    policy_id: str = "pol_a",
    document_id: str = "doc_1",
    *,
    page_number: int = 1,
    quoted_text: str = "Trecho da apólice",
    source_type: str = "NATIVE_TEXT",
) -> EvidenceRef:
    """Monta um `EvidenceRef` válido com o mínimo necessário."""
    return EvidenceRef(
        evidence_id=evidence_id,
        policy_id=policy_id,
        document_id=document_id,
        page_number=page_number,
        quoted_text=quoted_text,
        source_type=source_type,
    )


def make_fact(
    policy_id: str,
    field_code: str,
    *,
    status: str = "FOUND",
    value: dict | None = None,
    normalized_value: dict | None = None,
    confidence: float = 0.9,
    evidence_ids: list[str] | None = None,
    requires_human_review: bool = False,
    fact_id: str | None = None,
) -> ExtractedFact:
    """Monta um `ExtractedFact` válido (ids determinísticos para os testes)."""
    if evidence_ids is None:
        evidence_ids = [] if status == "NOT_FOUND" else [f"ev_{policy_id}_{field_code}"]
    return ExtractedFact(
        fact_id=fact_id or f"fact_{policy_id}_{field_code}",
        policy_id=policy_id,
        field_code=field_code,
        status=status,
        value=value,
        normalized_value=normalized_value,
        confidence=confidence,
        evidence_ids=list(evidence_ids),
        requires_human_review=requires_human_review,
    )


class FailingExtractionAgent:
    """Agente que sempre falha na extração (erro scriptado, ex. `ClassifiedError`)."""

    def __init__(self, error: Exception | None = None) -> None:
        self.error = error or ClassifiedError(
            "LLM_SCHEMA_INVALID", "saída do LLM fora do schema", retriable=True
        )
        self.calls = 0

    def extract(self, requests: list[ExtractionRequest], run_id: str) -> list[dict]:
        self.calls += 1
        raise self.error


class ScriptedExtractionAgent:
    """Extração determinística por `(policy_id, field_code)` (saída bruta do agente).

    Cada payload aceita `status`, `value`, `confidence`, `requires_human_review`
    e `anchor` (trecho literal usado para escolher as evidências citadas —
    ancoragem coerente com OQ-02). Usado pelo golden set: sem custo de LLM
    real, mesma entrada → mesmo output.
    """

    def __init__(self, outputs: dict[tuple[str, str], dict]) -> None:
        self.outputs = dict(outputs)
        self.calls = 0

    def extract(self, requests: list[ExtractionRequest], run_id: str) -> list[dict]:
        self.calls += 1
        raw_list: list[dict] = []
        for request in requests:
            payload = self.outputs[(request.policy_id, request.field_code)]
            status = payload.get("status", "FOUND")
            raw_list.append(
                {
                    "field_code": request.field_code,
                    "status": status,
                    "value": payload.get("value"),
                    "confidence": float(payload.get("confidence", 0.9)),
                    "evidence_ids": []
                    if status == "NOT_FOUND"
                    else _cite_evidences(request, payload.get("anchor")),
                    "requires_human_review": bool(payload.get("requires_human_review", False)),
                }
            )
        return raw_list


def _cite_evidences(request: ExtractionRequest, anchor: str | None) -> list[str]:
    """Cita as evidências cujo texto contém a âncora (ou as duas primeiras)."""
    if anchor:
        matching = [
            evidence.evidence_id
            for evidence in request.evidences
            if anchor in evidence.quoted_text
        ]
        if matching:
            return matching
    return [evidence.evidence_id for evidence in request.evidences][:2]


class InMemoryFactRepository:
    """Repositório em memória (duck-typed p/ `QualityService`) para os testes.

    Além de `get_facts`, expõe `get_evidence`/`get_comparison` — o repo DuckDB
    do módulo não tem `get_evidence` (evidências vivem no `EvidenceSource`);
    este fake cobre o caminho em que o `Issue` carrega `evidence_ref`.
    """

    def __init__(self) -> None:
        self.facts: dict[tuple[str, str], ExtractedFact] = {}
        self.evidences: dict[str, EvidenceRef] = {}
        self.comparisons: dict[str, ComparisonResult] = {}

    def upsert_fact(self, fact: ExtractedFact) -> None:
        self.facts[(fact.policy_id, fact.field_code)] = fact

    def get_facts(self, policy_id: str) -> list[ExtractedFact]:
        return [fact for (owner, _), fact in self.facts.items() if owner == policy_id]

    def get_fact(self, policy_id: str, field_code: str) -> ExtractedFact | None:
        return self.facts.get((policy_id, field_code))

    def save_evidence(self, evidence: EvidenceRef) -> None:
        self.evidences[evidence.evidence_id] = evidence

    def get_evidence(self, evidence_id: str) -> EvidenceRef | None:
        return self.evidences.get(evidence_id)

    def save_comparison(self, result: ComparisonResult) -> None:
        self.comparisons[result.comparison_id] = result

    def get_comparison(self, comparison_id: str) -> ComparisonResult | None:
        return self.comparisons.get(comparison_id)


class SlotFallback(dict):
    """Dict de fixtures com fallback por ordem de primeiro uso (demo/UI).

    A UI deriva o `policy_id` do nome do PDF; o demo não conhece os nomes de
    antemão, então ids desconhecidos recebem a próxima fixture na ordem de
    registro (1ª apólice → 1ª fixture, 2ª → 2ª). Ids conhecidos casam exato.
    """

    def __init__(self, mapping: dict) -> None:
        super().__init__(mapping)
        self._values = list(mapping.values())
        self._assigned: dict = {}

    def get(self, key, default=None):  # type: ignore[override]
        if dict.__contains__(self, key):
            return dict.get(self, key)
        if key in self._assigned:
            return self._assigned[key]
        if not self._values:
            return default
        value = self._values[len(self._assigned) % len(self._values)]
        self._assigned[key] = value
        return value


__all__ = [
    "FailingExtractionAgent",
    "FixtureExplanationAgent",
    "FixtureExtractionAgent",
    "InMemoryFactRepository",
    "MockEvidenceSource",
    "ScriptedExtractionAgent",
    "SlotFallback",
    "make_evidence",
    "make_fact",
]
