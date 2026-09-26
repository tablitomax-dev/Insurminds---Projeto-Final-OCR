"""Modelos do módulo `evaluation` (spec evaluation §9) — validados por Pydantic.

Artefatos versionados: `ReferenceCase` (apólice sintética + fatos esperados),
`EvaluationReportEntry` e `EvaluationReport`. Nada de contrato novo para fatos:
os fatos trafegam como `ExtractedFact` do `shared_kernel` (RF-06).
"""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from shared_kernel.contracts import FactStatus

#: Ressalva obrigatória do relatório (RF-04): o golden set sintético mede
#: regressão e NÃO valida os riscos R1/R3 do PRD (formatos por seguradora).
SYNTHETIC_CAVEAT = (
    "golden set sintético mede regressão; NÃO valida R1/R3 do PRD "
    "(formatos por seguradora) — validação com apólices reais/anonimizadas "
    "pendente (D2-P1-3)"
)

#: Decisão OQ-02 registrada: acerto de texto livre = substring literal.
OQ_02_DECISION = "substring (ancoragem literal)"

#: Resultado do campo na avaliação (EC-03: inconclusivo nunca conta como acerto).
MatchResult = Literal[
    "correto",
    "divergente",
    "ausente",
    "inconclusivo",
    "nao_avaliado",
]

_FORBID = ConfigDict(extra="forbid")


class ReferenceChunk(BaseModel):
    """Chunk de texto da apólice sintética de referência."""

    model_config = _FORBID

    chunk_id: str
    page_number: int = Field(ge=1)
    text: str = Field(min_length=1)


class ExpectedFact(BaseModel):
    """Fato esperado por `field_code`, com a citação esperada na evidência."""

    model_config = _FORBID

    field_code: str
    status: FactStatus
    expected_value: dict[str, Any] | None = None
    evidence_quote: str | None = None

    @model_validator(mode="after")
    def _value_matches_status(self) -> "ExpectedFact":
        """EC-01: referência fora do contrato é rejeitada na fronteira."""
        if self.status == "FOUND" and not self.expected_value:
            raise ValueError("fato FOUND esperado exige expected_value")
        if self.status == "NOT_FOUND" and self.expected_value:
            raise ValueError("fato NOT_FOUND esperado não pode ter expected_value")
        return self


class ReferenceCase(BaseModel):
    """Caso de referência: apólice sintética + fatos esperados (RF-01)."""

    model_config = _FORBID

    case_id: str
    policy_id: str
    chunks: list[ReferenceChunk] = Field(min_length=1)
    expected_facts: list[ExpectedFact] = Field(min_length=1)

    @model_validator(mode="after")
    def _unique_field_codes(self) -> "ReferenceCase":
        """EC-04: o mesmo `field_code` não pode repetir no caso."""
        codes = [fact.field_code for fact in self.expected_facts]
        duplicated = sorted({code for code in codes if codes.count(code) > 1})
        if duplicated:
            raise ValueError(f"field_code repetido na referência: {duplicated}")
        return self


class ReferenceSet(BaseModel):
    """Conjunto de referência versionado (RF-01, RNF-04)."""

    model_config = _FORBID

    reference_version: str = Field(min_length=1)
    oq_02: str = Field(min_length=1)
    cases: list[ReferenceCase] = Field(min_length=1)


class EvaluationEntry(BaseModel):
    """Resultado por campo de uma execução (campo correto? evidência correta?)."""

    model_config = _FORBID

    case_id: str
    policy_id: str
    field_code: str
    expected_status: FactStatus
    extracted_status: FactStatus | None
    expected_scalar: Any = None
    extracted_scalar: Any = None
    result: MatchResult
    evidence_ok: bool | None = None
    evidence_ids: list[str] = Field(default_factory=list)
    detail: str | None = None


class EvaluationTotals(BaseModel):
    """Agregado da execução (relatório por campo)."""

    model_config = _FORBID

    total_cases: int
    correct: int
    divergent: int
    absent: int
    inconclusive: int
    not_evaluated: int
    evidence_correct: int


class EvaluationReport(BaseModel):
    """Relatório estruturado por execução (RF-04, RNF-01/RNF-04)."""

    model_config = _FORBID

    run_id: str
    reference_version: str
    generated_at: str
    oq_02: str
    caveat: str
    entries: list[EvaluationEntry]
    totals: EvaluationTotals
