"""Serviço de extração de fatos por campo (RF-02, RF-03, RF-09)."""

from uuid import uuid4

from shared_kernel.contracts import (
    ExtractedFact,
    ExtractionRequest,
    RetrievalQuery,
)
from shared_kernel.version import CONTRACTS_VERSION

from ..domain.catalog import get_field_spec
from ..domain.comparison import normalize_value
from .ports import EvidenceRetriever, FactRepository, LlmExtractor, LlmOutputError

#: Quantidade de evidências recuperadas por campo (top_k do retrieval).
TOP_K = 5


class ExtractionService:
    """Orquestra retrieval + extração por LLM + validação + persistência."""

    def __init__(
        self,
        retriever: EvidenceRetriever,
        llm_extractor: LlmExtractor,
        repository: FactRepository,
    ) -> None:
        self._retriever = retriever
        self._llm_extractor = llm_extractor
        self._repository = repository

    def extract_field(self, policy_id: str, field_code: str) -> ExtractedFact:
        """Extrai um campo de uma apólice, sempre ancorado em evidência (RF-03)."""
        spec = get_field_spec(field_code)
        query = RetrievalQuery(
            query=spec.semantic,
            policy_id=policy_id,
            field_code=field_code,
            top_k=TOP_K,
        )
        result = self._retriever.retrieve(query)
        for evidence in result.evidences:
            self._repository.save_evidence(evidence)

        if not result.evidences:
            # Fluxo alternativo A: nada encontrado na apólice.
            fact = ExtractedFact(
                fact_id=f"fact_{uuid4().hex}",
                policy_id=policy_id,
                field_code=field_code,
                status="NOT_FOUND",
                value=None,
                normalized_value=None,
                confidence=0.0,
                evidence_ids=[],
                requires_human_review=False,
            )
            self._repository.upsert_fact(fact)
            return fact

        request = ExtractionRequest(
            policy_id=policy_id,
            field_code=field_code,
            evidences=result.evidences,
            schema_version=CONTRACTS_VERSION,
        )
        fact = self._validate_output(self._llm_extractor.extract(request), request)
        if fact.status == "FOUND" and not fact.normalized_value:
            fact = fact.model_copy(
                update={"normalized_value": normalize_value(spec, fact.value)}
            )
        self._repository.upsert_fact(fact)
        return fact

    def get_facts(self, policy_id: str) -> list[ExtractedFact]:
        """Fatos já extraídos de uma apólice."""
        return self._repository.get_facts(policy_id)

    def get_review_queue(self, policy_id: str | None = None) -> list[ExtractedFact]:
        """Fatos sinalizados para revisão humana (RF-04)."""
        return self._repository.list_review_queue(policy_id)

    def _validate_output(self, output: object, request: ExtractionRequest) -> ExtractedFact:
        """Valida a saída do LLM contra o contrato (RF-09/RN-05).

        O fato deve ser um `ExtractedFact` válido e citar apenas `evidence_id`
        recebidos no request (o LLM não inventa ID — RF-03). Inválido →
        `LlmOutputError` sem persistir nada.
        """
        try:
            fact = output if isinstance(output, ExtractedFact) else ExtractedFact.model_validate(output)
        except Exception as exc:
            raise LlmOutputError(f"saída do LLM fora do schema ExtractedFact: {exc}") from exc
        received_ids = {evidence.evidence_id for evidence in request.evidences}
        if not set(fact.evidence_ids) <= received_ids:
            raise LlmOutputError(
                "saída do LLM cita evidence_id inexistente nas evidências recebidas: "
                f"{sorted(set(fact.evidence_ids) - received_ids)}"
            )
        return fact
