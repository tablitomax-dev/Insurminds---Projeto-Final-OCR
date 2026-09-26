"""Casos de uso de extração de fatos (RF-02, RF-03, RF-09, RN-02, RN-05).

Fluxo: catálogo valida o `field_code` → evidências via `EvidenceSource` →
agente multi-campo → validação total da saída (nada de fato sem evidência
real) → normalização por tipo → persistência. Saída inválida nunca vira fato
(RF-09): vira `ClassifiedError` reexecutável.
"""

from __future__ import annotations

import uuid

from pydantic import ValidationError

from shared_kernel.contracts import ExtractedFact, ExtractionRequest

from ..domain.field_catalog import UnknownFieldCodeError, get_field
from ..domain.value_types import NormalizationError, normalize_value
from .errors import ClassifiedError

SCHEMA_VERSION = "1.0"


class ExtractionService:
    """Extração de campos do catálogo para uma apólice."""

    def __init__(self, evidence_source, agent, repo):
        self._evidence_source = evidence_source
        self._agent = agent
        self._repo = repo

    def extract_field(self, policy_id: str, field_code: str) -> ExtractedFact:
        return self.extract_fields(policy_id, [field_code])[0]

    def extract_fields(self, policy_id: str, field_codes: list[str]) -> list[ExtractedFact]:
        for code in field_codes:
            get_field(code)  # RN-05: rejeita field_code fora do catálogo na fronteira

        evidences = self._evidence_source.get_evidences(policy_id)
        known_ids = {ev.evidence_id for ev in evidences}
        requests = [
            ExtractionRequest(
                policy_id=policy_id,
                field_code=code,
                evidences=evidences,
                schema_version=SCHEMA_VERSION,
            )
            for code in field_codes
        ]

        run_id = str(uuid.uuid4())
        raw_list = self._agent.extract(requests, run_id)  # falha do provedor → ClassifiedError
        raw_by_code = {
            raw.get("field_code"): raw for raw in raw_list if isinstance(raw, dict)
        }

        facts = []
        for req in requests:
            raw = raw_by_code.get(req.field_code)
            fact = self._build_fact(req, raw, known_ids)
            self._repo.upsert_fact(fact, run_id=run_id, schema_version=SCHEMA_VERSION)
            facts.append(fact)
        return facts

    def get_facts(self, policy_id: str) -> list[ExtractedFact]:
        return self._repo.get_facts(policy_id)

    def _build_fact(
        self, req: ExtractionRequest, raw: dict | None, known_ids: set[str]
    ) -> ExtractedFact:
        fact_id = f"FAC-{req.policy_id}-{req.field_code}"

        if raw is None:
            # Campo ausente na saída/agente = NOT_FOUND (EC-03), nunca erro.
            return ExtractedFact(
                fact_id=fact_id,
                policy_id=req.policy_id,
                field_code=req.field_code,
                status="NOT_FOUND",
                value=None,
                normalized_value=None,
                confidence=0.0,
                evidence_ids=[],
                requires_human_review=False,
            )

        evidence_ids = raw.get("evidence_ids") or []
        if not set(evidence_ids) <= known_ids:
            # RN-02: o LLM não inventa ID de evidência.
            raise ClassifiedError(
                "EVIDENCE_UNKNOWN",
                f"evidence_ids fora do pedido em {req.field_code}: {evidence_ids}",
                retriable=True,
            )

        status = raw.get("status")
        value = raw.get("value")
        requires_review = bool(raw.get("requires_human_review", False))
        normalized_value = None

        if status == "FOUND" and value is not None:
            try:
                normalized_value = normalize_value(get_field(req.field_code), value)
            except NormalizationError:
                # EC-04: valor não normalizável → NEEDS_REVIEW, não erro.
                status = "NEEDS_REVIEW"
                requires_review = True

        try:
            return ExtractedFact.model_validate(
                {
                    "fact_id": fact_id,
                    "policy_id": req.policy_id,
                    "field_code": req.field_code,
                    "status": status,
                    "value": value,
                    "normalized_value": normalized_value,
                    "confidence": raw.get("confidence", 0.0),
                    "evidence_ids": evidence_ids,
                    "requires_human_review": requires_review,
                }
            )
        except ValidationError as exc:
            raise ClassifiedError(
                "LLM_SCHEMA_INVALID",
                f"saída do LLM fora do contrato em {req.field_code}: {exc}",
                retriable=True,
            ) from exc
