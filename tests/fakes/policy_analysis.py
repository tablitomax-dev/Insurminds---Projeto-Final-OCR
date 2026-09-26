"""Fakes do módulo policy_analysis (nenhuma dependência externa)."""

from __future__ import annotations

from modules.policy_analysis.application.ports import LlmOutputError
from modules.policy_analysis.domain.catalog import FIELD_CATALOG
from modules.policy_analysis.domain.comparison import ComparisonResult
from modules.policy_analysis.domain.review import ReviewDecision
from shared_kernel.contracts import (
    EvidenceRef,
    ExtractedFact,
    ExtractionRequest,
    RetrievalQuery,
    RetrievalResult,
)

#: Ordem estável do catálogo — mesma ordenação usada pelos adapters reais.
_CATALOG_ORDER = {code: index for index, code in enumerate(FIELD_CATALOG)}


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


class FakeEvidenceRetriever:
    """Retriever fake com evidências configuráveis (porta `EvidenceRetriever`).

    `evidences_by_policy` filtra por `query.policy_id`; sem ele, devolve a
    lista inteira em toda consulta.
    """

    def __init__(
        self,
        evidences: list[EvidenceRef] | None = None,
        evidences_by_policy: dict[str, list[EvidenceRef]] | None = None,
    ) -> None:
        self.evidences = list(evidences or [])
        self.evidences_by_policy = {
            policy_id: list(items)
            for policy_id, items in (evidences_by_policy or {}).items()
        }
        self.queries: list[RetrievalQuery] = []

    def retrieve(self, query: RetrievalQuery) -> RetrievalResult:
        self.queries.append(query)
        if self.evidences_by_policy:
            selected = list(self.evidences_by_policy.get(query.policy_id, []))
        else:
            selected = list(self.evidences)
        return RetrievalResult(
            query=query,
            evidences=selected,
            retrieval_run_id=f"retr_{len(self.queries):04d}",
        )


class FakeLlmExtractor:
    """Extrator fake scriptável: devolve `result` ou levanta `error` (porta `LlmExtractor`)."""

    def __init__(self, result: object = None, error: Exception | None = None) -> None:
        self.result = result
        self.error = error
        self.requests: list[ExtractionRequest] = []

    def extract(self, request: ExtractionRequest) -> ExtractedFact:
        self.requests.append(request)
        if self.error is not None:
            raise self.error
        if self.result is None:
            raise AssertionError("FakeLlmExtractor não configurado (result ou error)")
        return self.result  # type: ignore[return-value]


class ScriptedLlmExtractor:
    """Extrator fake determinístico por `(policy_id, field_code)` (porta `LlmExtractor`).

    Cada payload aceita `status`, `value`, `normalized_value`, `confidence`,
    `requires_human_review` e `anchor` (trecho literal usado para escolher as
    evidências citadas — ancoragem coerente com D2-P0-1). Usado pelo golden
    set e pelo E2E de revisão: sem custo de LLM real, mesma entrada → mesmo
    output.
    """

    def __init__(self, outputs: dict[tuple[str, str], dict]) -> None:
        self.outputs = dict(outputs)
        self.requests: list[ExtractionRequest] = []

    def extract(self, request: ExtractionRequest) -> ExtractedFact:
        self.requests.append(request)
        payload = self.outputs[(request.policy_id, request.field_code)]
        status = payload.get("status", "FOUND")
        return ExtractedFact(
            fact_id=f"fact_{request.policy_id}_{request.field_code}",
            policy_id=request.policy_id,
            field_code=request.field_code,
            status=status,
            value=payload.get("value"),
            normalized_value=payload.get("normalized_value"),
            confidence=float(payload.get("confidence", 0.9)),
            evidence_ids=[] if status == "NOT_FOUND" else _cite_evidences(request, payload.get("anchor")),
            requires_human_review=bool(payload.get("requires_human_review", False)),
        )


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


class FakeExplanationGenerator:
    """Gerador de explicação fake scriptável (porta `ExplanationGenerator`)."""

    def __init__(
        self,
        text: str = "Explicação da diferença",
        cited_ids: list[str] | None = None,
        error: Exception | None = None,
    ) -> None:
        self.text = text
        self.cited_ids = list(cited_ids or [])
        self.error = error
        self.calls: list[tuple[str, str, list[EvidenceRef], list[EvidenceRef]]] = []

    def explain(
        self,
        field_code: str,
        direction: str,
        fact_a: ExtractedFact | None,
        fact_b: ExtractedFact | None,
        evidences_a: list[EvidenceRef],
        evidences_b: list[EvidenceRef],
    ) -> tuple[str, list[str]]:
        self.calls.append((field_code, direction, evidences_a, evidences_b))
        if self.error is not None:
            raise self.error
        return self.text, list(self.cited_ids)


class InMemoryFactRepository:
    """Repositório em memória (porta `FactRepository`) para os testes."""

    def __init__(self) -> None:
        self.facts: dict[tuple[str, str], ExtractedFact] = {}
        self.evidences: dict[str, EvidenceRef] = {}
        self.comparisons: dict[str, ComparisonResult] = {}
        self.reviews: dict[str, ReviewDecision] = {}

    def upsert_fact(self, fact: ExtractedFact) -> None:
        self.facts[(fact.policy_id, fact.field_code)] = fact

    def get_facts(self, policy_id: str) -> list[ExtractedFact]:
        selected = [fact for (owner, _), fact in self.facts.items() if owner == policy_id]
        return _sort_facts(selected)

    def get_fact(self, policy_id: str, field_code: str) -> ExtractedFact | None:
        return self.facts.get((policy_id, field_code))

    def list_review_queue(self, policy_id: str | None = None) -> list[ExtractedFact]:
        selected = [
            fact
            for fact in self.facts.values()
            if (policy_id is None or fact.policy_id == policy_id) and _needs_review(fact)
        ]
        return _sort_facts(selected)

    def save_evidence(self, evidence: EvidenceRef) -> None:
        self.evidences[evidence.evidence_id] = evidence

    def get_evidence(self, evidence_id: str) -> EvidenceRef | None:
        return self.evidences.get(evidence_id)

    def save_comparison(self, result: ComparisonResult) -> None:
        self.comparisons[result.comparison_id] = result

    def get_comparison(self, comparison_id: str) -> ComparisonResult | None:
        return self.comparisons.get(comparison_id)

    def save_review(self, decision: ReviewDecision) -> None:
        self.reviews[decision.review_id] = decision

    def list_reviews(
        self, policy_id: str | None = None, field_code: str | None = None
    ) -> list[ReviewDecision]:
        selected = [
            decision
            for decision in self.reviews.values()
            if (policy_id is None or decision.policy_id == policy_id)
            and (field_code is None or decision.field_code == field_code)
        ]
        return sorted(selected, key=lambda decision: decision.reviewed_at)


def _needs_review(fact: ExtractedFact) -> bool:
    return fact.status in ("AMBIGUOUS", "NEEDS_REVIEW") or fact.requires_human_review


def _sort_facts(facts: list[ExtractedFact]) -> list[ExtractedFact]:
    return sorted(
        facts,
        key=lambda fact: (_CATALOG_ORDER.get(fact.field_code, len(_CATALOG_ORDER)), fact.field_code),
    )


__all__ = [
    "FakeEvidenceRetriever",
    "FakeExplanationGenerator",
    "FakeLlmExtractor",
    "InMemoryFactRepository",
    "LlmOutputError",
    "ScriptedLlmExtractor",
    "make_evidence",
    "make_fact",
]
