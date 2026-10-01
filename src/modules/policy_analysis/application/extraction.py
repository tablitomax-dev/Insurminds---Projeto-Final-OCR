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

from ..domain.anchoring import is_anchored
from ..domain.field_catalog import FieldType, get_field
from ..domain.rules import RuleViolation, validate_fact
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

        # 1) constrói todos os fatos (guardas por campo aplicadas em _build_fact);
        #    uma invalidade (evidência inventada/saída fora do schema) aborta antes
        #    de persistir qualquer coisa — nada de fato pela metade.
        facts = [self._build_fact(req, raw_by_code.get(req.field_code), known_ids) for req in requests]
        # 2) regra cruzada entre os fatos monetários desta extração (moeda_consistente)
        self._apply_cross_field_rules(facts)
        # 3) persiste somente após todas as validações
        for fact in facts:
            self._repo.upsert_fact(fact, run_id=run_id, schema_version=SCHEMA_VERSION)
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
        spec = get_field(req.field_code)

        if status == "FOUND" and value is not None:
            try:
                normalized_value = normalize_value(spec, value)
            except NormalizationError:
                # EC-04: valor não normalizável → NEEDS_REVIEW, não erro.
                status = "NEEDS_REVIEW"
                requires_review = True

        # Guardas pós-LLM (D2-P0-1 ancoragem + D2-P0-3 regras por campo):
        # citação inventada ou regra de campo violada nunca vira FOUND.
        value, status, requires_review = self._apply_field_guards(
            spec, value, normalized_value, status, requires_review, req.evidences, evidence_ids
        )

        try:
            fact = ExtractedFact.model_validate(
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
        return fact

    def _apply_field_guards(
        self, spec, value, normalized_value, status, requires_review, evidences, evidence_ids
    ):
        """Ancoragem de citação + regras por campo; rebaixa FOUND em violação.

        Retorna (value_anotado, status, requires_review). Motivos são sanitizados
        (regra/campo/quantidade — nunca o valor, T-2a) e ficam em
        `value["rule_violations"]`/`value["anchor_violations"]` para auditoria.
        Regras avaliam o valor normalizado (determinístico); ancoragem, o valor
        bruto (onde moram as citações literais).
        """
        anchored, anchor_bad = is_anchored(value, evidences, evidence_ids)
        rule_violations: list[RuleViolation] = []
        if status == "FOUND" and normalized_value is not None:
            rule_violations = validate_fact(spec, normalized_value)

        if status == "FOUND" and ((not anchored) or rule_violations):
            status = "NEEDS_REVIEW"
            requires_review = True

        if (anchor_bad or rule_violations) and isinstance(value, dict):
            annotated = dict(value)
            if rule_violations:
                annotated["rule_violations"] = [v.to_dict() for v in rule_violations]
            if anchor_bad:
                annotated["anchor_violations"] = [
                    {"reason": f"{anchor_bad} citação(ões) não ancorada(s) no texto da evidência"}
                ]
            value = annotated
        return value, status, requires_review

    def _apply_cross_field_rules(self, facts) -> None:
        """Regra cruzada `moeda_consistente`: monetários da mesma apólice iguais.

        Inconsistência rebaixa os fatos monetários envolvidos para `NEEDS_REVIEW`.
        """
        money_indexes = [
            i
            for i, f in enumerate(facts)
            if get_field(f.field_code).field_type is FieldType.MONEY
            and f.status == "FOUND"
            and f.normalized_value is not None
        ]
        if len(money_indexes) < 2:
            return
        currencies = {
            str(facts[i].normalized_value.get("currency", "")).upper()
            for i in money_indexes
            if facts[i].normalized_value.get("currency")
        }
        if len(currencies) <= 1:
            return
        for i in money_indexes:
            fact = facts[i]
            annotated = dict(fact.value or {})
            others = [facts[j].normalized_value for j in money_indexes if j != i]
            violations = [
                v.to_dict()
                for v in validate_fact(get_field(fact.field_code), fact.normalized_value, others)
                if v.rule == "moeda_consistente"
            ]
            if not violations:
                continue
            annotated["rule_violations"] = (
                list(annotated.get("rule_violations", [])) + violations
            )
            facts[i] = fact.model_copy(
                update={
                    "status": "NEEDS_REVIEW",
                    "requires_human_review": True,
                    "value": annotated,
                }
            )
