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
"""Serviço de extração de fatos por campo (RF-02, RF-03, RF-09).

Guardas pós-LLM (D2-P0-1/D2-P0-3/T-2a): o output do LLM só vira fato depois
de validado contra o contrato, ancorado no texto real das evidências e aprovado
nas regras mínimas por campo. Mensagens de erro são sanitizadas — tipo do erro,
nomes de campos e IDs, nunca valores (texto de apólice não vaza).
"""

import re
from uuid import uuid4

from shared_kernel.contracts import (
    EvidenceRef,
    ExtractedFact,
    ExtractionRequest,
    RetrievalQuery,
)
from shared_kernel.version import CONTRACTS_VERSION

from ..domain.anchoring import QUOTE_KEYS, collect_excerpts, unanchored_excerpts
from ..domain.catalog import FieldSpec, get_field_spec
from ..domain.comparison import normalize_value
from ..domain.rules import RuleViolation, validate_fact
from .ports import EvidenceRetriever, FactRepository, LlmExtractor, LlmOutputError
from .quality import QualitySignalLog

#: Quantidade de evidências recuperadas por campo (top_k do retrieval).
TOP_K = 5

#: Chave em `value` onde o motivo do rebaixe para revisão é registrado.
RULE_VIOLATIONS_KEY = "rule_violations"

#: Identificador seguro para mensagem de erro (sem texto de apólice — T-2a).
_ID_PATTERN = re.compile(r"[A-Za-z0-9_.:\-]{1,64}")

#: Nome de campo seguro para mensagem de erro (nome, nunca o valor — T-2a).
_FIELD_NAME_PATTERN = re.compile(r"[A-Za-z_][A-Za-z0-9_]{0,63}")


class ExtractionService:
    """Orquestra retrieval + extração por LLM + validação + persistência."""

    def __init__(
        self,
        retriever: EvidenceRetriever,
        llm_extractor: LlmExtractor,
        repository: FactRepository,
        quality_signals: QualitySignalLog | None = None,
    ) -> None:
        self._retriever = retriever
        self._llm_extractor = llm_extractor
        self._repository = repository
        self._quality_signals = quality_signals

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
            self._repository.upsert_fact(fact)
            return fact

        request = ExtractionRequest(
            policy_id=policy_id,
            field_code=field_code,
            evidences=result.evidences,
            schema_version=CONTRACTS_VERSION,
        )
        try:
            fact = self._validate_output(self._llm_extractor.extract(request), request)
        except LlmOutputError as error:
            # Sinal CRÍTICO para o QualityReport (D2-P1-1b) — motivo já sanitizado.
            if self._quality_signals is not None:
                self._quality_signals.record_extraction_failure(
                    policy_id, field_code, str(error)
                )
            raise
        if fact.status == "FOUND" and not fact.normalized_value:
            fact = fact.model_copy(
                update={"normalized_value": normalize_value(spec, fact.value)}
            )
        fact = self._apply_field_rules(spec, fact)
        self._repository.upsert_fact(fact)
        return fact

    def get_facts(self, policy_id: str) -> list[ExtractedFact]:
        """Fatos já extraídos de uma apólice."""
        return self._repository.get_facts(policy_id)

    def get_review_queue(self, policy_id: str | None = None) -> list[ExtractedFact]:
        """Fatos sinalizados para revisão humana (RF-04)."""
        return self._repository.list_review_queue(policy_id)

    def get_evidence(self, evidence_id: str) -> EvidenceRef | None:
        """Evidência persistida na extração (rastreabilidade do fato/revisão)."""
        return self._repository.get_evidence(evidence_id)

    def _validate_output(self, output: object, request: ExtractionRequest) -> ExtractedFact:
        """Valida a saída do LLM: schema, IDs recebidos e ancoragem (RF-09/RF-01).

        O fato deve ser um `ExtractedFact` válido, citar apenas `evidence_id`
        recebidos no request (o LLM não inventa ID — RF-03) e ancorar todo
        excerpt no texto das evidências citadas (D2-P0-1). Inválido →
        `LlmOutputError` sanitizado (T-2a) sem persistir nada.
        """
        try:
            fact = output if isinstance(output, ExtractedFact) else ExtractedFact.model_validate(output)
        except Exception as exc:
            raise LlmOutputError(_schema_error_message(exc, request)) from exc
        received_ids = {evidence.evidence_id for evidence in request.evidences}
        unknown_ids = set(fact.evidence_ids) - received_ids
        if unknown_ids:
            listed = ", ".join(sorted(_safe_id(evidence_id) for evidence_id in unknown_ids))
            raise LlmOutputError(
                "EXTRACT: saída do LLM cita evidence_id inexistente nas evidências recebidas"
                f" (ids={listed} quantidade={len(unknown_ids)}"
                f" policy_id={_safe_id(request.policy_id)} field_code={_safe_id(request.field_code)})"
            )
        self._anchor_output(fact, request)
        return fact

    def _anchor_output(self, fact: ExtractedFact, request: ExtractionRequest) -> None:
        """Ancoragem de citação (RF-01, D2-P0-1): todo excerpt existe no chunk citado.

        Com múltiplas evidências citadas, TODOS os excerpts são ancorados na
        união dos textos citados. `FOUND` sem excerpt verificável também falha
        (sem ancoragem nunca vira `FOUND`). Sem ancoragem → `LlmOutputError`.
        """
        if fact.status == "NOT_FOUND":
            return
        excerpts = collect_excerpts(fact.value) + collect_excerpts(fact.normalized_value)
        if fact.status == "FOUND" and not excerpts:
            raise LlmOutputError(
                "EXTRACT: fato FOUND sem trecho literal para ancoragem (raw_text)"
                f" (policy_id={_safe_id(request.policy_id)}"
                f" field_code={_safe_id(request.field_code)} fact_id={_safe_id(fact.fact_id)})"
            )
        cited = {
            evidence.evidence_id: evidence.quoted_text for evidence in request.evidences
        }
        source_texts = [
            cited[evidence_id] for evidence_id in fact.evidence_ids if evidence_id in cited
        ]
        missing = unanchored_excerpts(excerpts, source_texts)
        if missing:
            raise LlmOutputError(
                "EXTRACT: citação do LLM fora do texto da evidência citada"
                f" (quantidade={len(missing)} campos={_quote_fields(fact)}"
                f" policy_id={_safe_id(request.policy_id)}"
                f" field_code={_safe_id(request.field_code)} fact_id={_safe_id(fact.fact_id)})"
            )

    def _apply_field_rules(self, spec: FieldSpec, fact: ExtractedFact) -> ExtractedFact:
        """Regras mínimas por campo (RF-03, D2-P0-3): falha nunca vira `FOUND`.

        Violação rebaixa o fato para `NEEDS_REVIEW` com `requires_human_review`
        e registra o motivo em `value["rule_violations"]` — o contrato v1.0.0
        não tem campo de motivo (`Issue` é aditivo, backlog D2-P1-1).
        """
        others = {
            other.field_code: other
            for other in self._repository.get_facts(fact.policy_id)
            if other.field_code != fact.field_code
        }
        violations = validate_fact(spec, fact, others)
        return _demote(fact, violations)


def _demote(fact: ExtractedFact, violations: list[RuleViolation]) -> ExtractedFact:
    """Rebaixa o fato para revisão humana quando alguma regra falha."""
    if not violations:
        return fact
    reasons = [f"{violation.rule}: {violation.reason}" for violation in violations]
    value = dict(fact.value or {})
    value[RULE_VIOLATIONS_KEY] = reasons
    return fact.model_copy(
        update={"status": "NEEDS_REVIEW", "value": value, "requires_human_review": True}
    )


def _schema_error_message(exc: Exception, request: ExtractionRequest) -> str:
    """Mensagem sanitizada de erro de schema (T-2a).

    NUNCA `str(exc)`: o `ValidationError` do Pydantic ecoa o `input`, que pode
    conter texto de apólice. Só entram tipo do erro, nomes de campos e IDs.
    """
    return (
        "EXTRACT: saída do LLM fora do schema ExtractedFact"
        f" (tipo={type(exc).__name__} campos={_error_fields(exc)}"
        f" policy_id={_safe_id(request.policy_id)} field_code={_safe_id(request.field_code)})"
    )


def _error_fields(exc: Exception) -> str:
    """Nomes de campos problemáticos do erro (nome, nunca o valor — T-2a)."""
    errors = getattr(exc, "errors", None)
    if not callable(errors):
        return "[(desconhecido)]"
    names: list[str] = []
    for error in errors():
        loc = error.get("loc", ()) if isinstance(error, dict) else ()
        parts = [str(part) for part in loc if _FIELD_NAME_PATTERN.fullmatch(str(part))]
        name = ".".join(parts) if parts else "(modelo)"
        if name not in names:
            names.append(name)
    return "[" + ", ".join(names) + "]"


def _quote_fields(fact: ExtractedFact) -> str:
    """Nomes das chaves de excerpt do fato (nome, nunca o valor — T-2a)."""
    found = [
        key
        for payload in (fact.value, fact.normalized_value)
        if isinstance(payload, dict)
        for key in payload
        if key in QUOTE_KEYS
    ]
    return "[" + ", ".join(sorted(set(found))) + "]" if found else "[(sem excerpt)]"


def _safe_id(value: object) -> str:
    """Identificador seguro para mensagem; fora do padrão → omitido (T-2a)."""
    text = str(value)
    return text if _ID_PATTERN.fullmatch(text) else "<id omitido>"
