"""Fachada pública do policy_analysis (spec §8, RF-01..RF-08).

ÚNICA entrada do módulo para o resto do sistema (workflow/app/Streamlit):
`extract_field`, `get_facts`, `compare_policies`, `explain_difference`,
`export_comparison` — mais as operações de revisão humana (RF-04).

Extensões de governança/observabilidade (features 003/004 do ciclo anterior,
**reimplementadas sobre esta arquitetura** por decisão do humano em 2026-09-29 —
a arquitetura do Dev 2 prevalece e as costuras são aditivas): `list_issues`,
`get_quality_report`, `get_comparison_quality_report`, `get_usage_metrics`.
"""

from __future__ import annotations

from uuid import uuid4

from shared_kernel.contracts import EvidenceRef, ExtractedFact

from .application.comparison_service import ComparisonService
from .application.errors import ClassifiedError
from .application.explanation import ExplanationService
from .application.export import ExportService
from .application.extraction import ExtractionService
from .application.quality import QualityService, QualitySignalLog
from .application.review import ReviewService
from .domain.insurer_detection import detect_insurer
from .domain.metrics import UsageMetricsCollector, UsageSummary
from .domain.models import ComparisonResult, Explanation, ReviewItem
from .domain.quality import SEVERITY_ORDER, Issue, QualityReport, Severity
from .infrastructure.duckdb_repository import PolicyAnalysisRepository
from .infrastructure.pricing import PRICE_REFERENCE_DATE

#: Revisor registrado quando a decisão vem do Agente IA sobre indicação humana.
AGENT_REVIEWER = "Analista via Agente IA"


class PolicyAnalysisFacade:
    """API pública do módulo de análise de apólices."""

    def __init__(
        self,
        evidence_source,
        extraction_agent,
        explanation_agent,
        db_path: str = ":memory:",
        output_dir: str = "output",
        currency_rates: dict | None = None,
        usage_collector: UsageMetricsCollector | None = None,
        quality_signals: QualitySignalLog | None = None,
        insurer_agent=None,
        question_agent=None,
        review_agent=None,
        extra_findings_agent=None,
        report_agent=None,
        llm_client=None,
    ):
        self._repo = PolicyAnalysisRepository(db_path)
        self._evidence_source = evidence_source
        self._extraction = ExtractionService(evidence_source, extraction_agent, self._repo)
        self._review = ReviewService(self._repo)
        self._comparison = ComparisonService(self._repo, currency_rates)
        self._explanation = ExplanationService(self._repo, explanation_agent)
        self._export = ExportService(self._repo, output_dir)
        self._output_dir = output_dir
        self._usage = usage_collector if usage_collector is not None else UsageMetricsCollector()
        self._signals = quality_signals if quality_signals is not None else QualitySignalLog()
        self._quality = QualityService(self._repo, self._signals)
        self._insurer_agent = insurer_agent
        self._question_agent = question_agent
        self._review_agent = review_agent
        self._extra_findings_agent = extra_findings_agent
        self._report_agent = report_agent
        self._llm_client = llm_client
        self._markdown_source = None  # cache de seções em memória (repo é o durável)
        self._file_paths: dict[str, str] = {}  # policy_id → caminho do PDF

    # --- saúde do provedor de IA (banner da UI; F-15) -------------------------

    def llm_health(self) -> list[dict]:
        """Diagnóstico da cadeia de LLM: um item por nível, nunca levanta erro.

        Cada item: `{"provider", "model", "ok", "detail"}` — `detail` traz a
        causa raiz quando o nível falha (ex.: `HTTP 403 — Key limit exceeded`).
        `[]` quando não há client compatível com `health_check`.
        """
        check = getattr(self._llm_client, "health_check", None)
        if not callable(check):
            return []
        try:
            return list(check())
        except Exception:  # noqa: BLE001 — diagnóstico nunca derruba a UI
            return []

    # --- extração (RF-02, RF-03) ----------------------------------------------

    def extract_field(self, policy_id: str, field_code: str) -> ExtractedFact:
        return self.extract_fields(policy_id, [field_code])[0]

    def extract_fields(self, policy_id: str, field_codes: list[str]) -> list[ExtractedFact]:
        try:
            return self._extraction.extract_fields(policy_id, field_codes)
        except Exception as exc:
            # Sinal CRÍTICO de governança (004) antes de propagar: só o código
            # classificado do erro (sanitizado — T-2a), nunca texto de apólice.
            code = str(getattr(exc, "code", None) or type(exc).__name__)
            for field_code in field_codes:
                self._signals.record_extraction_failure(policy_id, field_code, code)
            raise

    def get_facts(self, policy_id: str) -> list[ExtractedFact]:
        return self._extraction.get_facts(policy_id)

    # --- catálogo e evidências (consumidores: UI/evaluation) ------------------

    def list_fields(self) -> list[dict[str, str]]:
        from .domain.field_catalog import all_codes, get_field

        fields = []
        for code in all_codes():
            definition = get_field(code)
            fields.append(
                {
                    "code": definition.code,
                    "label": definition.label,
                    "description": definition.description,
                    "unit": definition.unit or "",
                }
            )
        return fields

    def normalize_field_value(self, field_code: str, value: dict | None) -> dict | None:
        from .domain.field_catalog import get_field
        from .domain.value_types import normalize_value

        if value is None:
            return None
        return normalize_value(get_field(field_code), value)

    def get_evidences(self, policy_id: str, field_code: str | None = None) -> list[EvidenceRef]:
        return list(self._evidence_source.get_evidences(policy_id, field_code))

    # --- revisão humana (RF-04) ----------------------------------------------

    def list_review_queue(self, policy_id: str | None = None) -> list[ReviewItem]:
        return self._review.list_pending(policy_id)

    def list_review_decisions(self, policy_id: str | None = None) -> list[ReviewItem]:
        """Histórico de revisões decididas por humano (CONFIRMADO/CORRIGIDO/DIVERGENTE)."""
        return self._review.list_decisions(policy_id)

    def record_review_decision(
        self,
        fact_id: str,
        decision: str,
        decided_by: str,
        value: dict | str | None = None,
        note: str | None = None,
    ) -> ExtractedFact:
        return self._review.record_decision(fact_id, decision, decided_by, value, note=note)

    # --- comparação determinística (RF-06) ------------------------------------

    def compare_policies(self, policy_id_a: str, policy_id_b: str) -> ComparisonResult:
        return self._comparison.compare_policies(policy_id_a, policy_id_b)

    # --- explicação rastreável (RF-07) ----------------------------------------

    def explain_difference(self, comparison_id: str, field_code: str) -> Explanation:
        return self._explanation.explain_difference(comparison_id, field_code)

    # --- export standalone (RF-08) --------------------------------------------

    def export_comparison(self, comparison_id: str) -> str:
        return self._export.export_comparison(comparison_id)

    # --- governança da qualidade (extensão 004) -------------------------------

    def list_issues(self, policy_id: str) -> list[Issue]:
        return self._quality.list_issues(policy_id)

    def get_quality_report(self, policy_id: str) -> QualityReport:
        return self._quality.get_quality_report(policy_id)

    def get_comparison_quality_report(self, comparison_id: str) -> QualityReport:
        return self._quality.get_comparison_quality_report(comparison_id)

    # --- métricas de uso do LLM (extensão 004) --------------------------------

    def get_usage_metrics(self, run_id: str | None = None) -> UsageSummary | None:
        return self._usage.summarize(run_id, price_reference_date=PRICE_REFERENCE_DATE)

    # --- agentes inteligentes (seguradora, perguntas, revisão por mensagem) ---

    def identify_insurer(self, policy_id: str, page_texts: list[str]) -> dict | None:
        """Nome/ano da seguradora: leitura direta primeiro, LLM só no estranho.

        OCR primeiro (barato) via `detect_insurer`; o que não for confiável
        escala para a LLM confirmar. Sem confiança em nenhum dos dois →
        `None` e a UI pergunta ao usuário (EC-04: incerteza nunca vira
        palpite; falha da LLM também degrada para o humano).
        """
        detected = detect_insurer(page_texts)
        if detected is not None:
            return detected
        if self._insurer_agent is None:
            return None
        try:
            info = self._insurer_agent.identify(
                policy_id, page_texts, run_id=f"identify:{policy_id}"
            )
        except Exception:  # noqa: BLE001 — degradação: fallback é o humano
            return None
        name = (info or {}).get("name")
        if not name:
            return None
        return {"name": name, "year": (info or {}).get("year")}

    def answer_question(self, question: str, evidences: list[EvidenceRef]) -> dict:
        """Resposta do Agente Inteligente ancorada nas evidências (RAG).

        Só responde com base nas evidências fornecidas; a UI chama somente
        quando há evidências (sem base → resposta determinística na UI).
        """
        if self._question_agent is None:
            raise ClassifiedError(
                "LLM_UNAVAILABLE", "agente de perguntas não configurado", retriable=False
            )
        return self._question_agent.answer(question, evidences, run_id=uuid4().hex)

    def apply_review_feedback(self, message: str, policy_ids: list[str]) -> dict:
        """Aplica a indicação de divergências do revisor via LLM (RF-04 + agente).

        Cada correção passa pelo fluxo de revisão (`record_decision`) com
        `decided_by` do Agente e a mensagem original como nota de auditoria;
        correções inválidas são puladas com o tipo do erro (T-2a).
        """
        if self._review_agent is None:
            raise ClassifiedError(
                "LLM_UNAVAILABLE", "agente de revisão não configurado", retriable=False
            )
        facts = [
            fact for policy_id in policy_ids for fact in self._extraction.get_facts(policy_id)
        ]
        if not facts:
            return {"applied": [], "skipped": []}
        fact_index = {fact.fact_id: fact for fact in facts}
        summaries = [
            {
                "fact_id": fact.fact_id,
                "policy_id": fact.policy_id,
                "field_code": fact.field_code,
                "status": fact.status,
                "value": fact.value,
                "evidence_ids": list(fact.evidence_ids),
            }
            for fact in facts
        ]
        corrections = self._review_agent.corrections(message, summaries, run_id=uuid4().hex)
        applied: list[dict] = []
        skipped: list[dict] = []
        for item in corrections:
            fact_id = item.get("fact_id")
            value = item.get("value")
            decision = str(item.get("decision") or "").upper()
            if decision not in ("CONFIRMADO", "CORRIGIDO", "DIVERGENTE"):
                decision = "CORRIGIDO" if value is not None else "DIVERGENTE"
            if fact_id not in fact_index:
                skipped.append({"fact_id": fact_id, "reason": "UNKNOWN_FACT"})
                continue
            try:
                fact = self._review.record_decision(
                    fact_id, decision, AGENT_REVIEWER, value, note=message
                )
            except Exception as exc:  # noqa: BLE001 — motivo sanitizado (T-2a)
                skipped.append({"fact_id": fact_id, "reason": type(exc).__name__})
                continue
            applied.append(
                {"fact_id": fact.fact_id, "field_code": fact.field_code, "decision": decision}
            )
        return {"applied": applied, "skipped": skipped}

    # --- markdown e achados extras (campos fora do catálogo fechado) ------------

    def store_markdown(
        self,
        policy_id: str,
        pages: list[tuple[int, str]],
        fingerprint: str | None = None,
        file_path: str | None = None,
    ) -> None:
        """Persiste o markdown por página (cache de extração por fingerprint).

        `file_path` registra o caminho do PDF para reextração futura (cache-miss).
        """
        for page_number, markdown in pages:
            self._repo.upsert_markdown_page(policy_id, page_number, markdown, fingerprint)
        if file_path is not None:
            self._file_paths[policy_id] = file_path
        self._markdown_source = None  # invalida o cache de seções em memória

    def get_markdown_sections(self, policy_id: str) -> list[dict]:
        """Seções do markdown da apólice: `{"title", "text", "page_number"}`."""
        return [
            {"title": section.title, "text": section.text, "page_number": section.page_number}
            for section in self._section_source().get_sections(policy_id)
        ]

    def extract_extra_findings(self, policy_id: str) -> list[dict]:
        """Achados relevantes fora do catálogo fechado, com rastro de evidência.

        As evidências vêm das seções do markdown (RAG por seções); achados com
        `evidence_ids` inventados são descartados (RN-02) e a persistência é
        idempotente (EC-06: delete+insert por apólice).
        """
        if self._extra_findings_agent is None:
            raise ClassifiedError(
                "LLM_UNAVAILABLE", "agente de achados extras não configurado", retriable=False
            )
        from .infrastructure.llm_agent import validate_extra_findings

        evidences = self._section_source().get_evidences(policy_id)
        raw_findings = self._extra_findings_agent.extract(
            policy_id, evidences, run_id=uuid4().hex
        )
        known_ids = {evidence.evidence_id for evidence in evidences}
        findings = validate_extra_findings(raw_findings, known_ids)
        self._repo.delete_extra_findings(policy_id)
        for index, finding in enumerate(findings):
            self._repo.upsert_extra_finding(
                {"finding_id": f"EXF-{policy_id}-{index:03d}", "policy_id": policy_id, **finding}
            )
        return self._repo.get_extra_findings(policy_id)

    def get_extra_findings(self, policy_id: str) -> list[dict]:
        """Achados extras persistidos da apólice (`evidence_ids` como lista)."""
        return self._repo.get_extra_findings(policy_id)

    def _section_source(self):
        """Fonte de seções do markdown — repo é o cache, fachada só no cache-miss."""
        if self._markdown_source is None:
            from .infrastructure.markdown_source import MarkdownSectionEvidenceSource

            self._markdown_source = MarkdownSectionEvidenceSource(
                self._repo, file_paths=self._file_paths
            )
        return self._markdown_source

    # --- Relatório D&O (metodologia §1–§11) -----------------------------------

    def build_report(
        self,
        policy_ids: list[str],
        profile: dict | None = None,
        weights: dict[str, float] | None = None,
    ):
        """Monta o Relatório D&O (identificação, matriz, tabelas, cenários,
        ranking parametrizável com sensibilidade, conclusões e checklist).

        `profile` (opcional): `facts_available`, `perfil_completo`,
        `checklist_inputs`. `weights` (opcional) substitui os pesos padrão do
        ranking (devem somar 100). Sem agente configurado → `ClassifiedError`.
        """
        from .application.report_service import ReportService

        service = ReportService(
            self._section_source(), report_agent=self._report_agent, repo=self._repo
        )
        return service.build_report(policy_ids, profile=profile, weights=weights)

    def export_report(self, report) -> str:
        """Exporta o Relatório D&O em Markdown standalone (§5–§11) em `output_dir`."""
        from pathlib import Path

        from .infrastructure.report_export import export_report

        output_dir = Path(self._output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        return export_report(report, output_dir / f"relatorio_{report.report_id}.md")


def create_policy_analysis(
    evidence_source,
    extraction_agent,
    explanation_agent,
    *,
    db_path: str = ":memory:",
    output_dir: str = "output",
    currency_rates: dict | None = None,
    usage_collector: UsageMetricsCollector | None = None,
    quality_signals: QualitySignalLog | None = None,
) -> PolicyAnalysisFacade:
    """Monta a fachada com as portas injetadas (testes e E2E com fakes)."""
    return PolicyAnalysisFacade(
        evidence_source,
        extraction_agent,
        explanation_agent,
        db_path=db_path,
        output_dir=output_dir,
        currency_rates=currency_rates,
        usage_collector=usage_collector,
        quality_signals=quality_signals,
    )


def create_document_processing_evidence_source(document_processing_facade=None):
    """Evidências reais via fachada `document_processing` (único elo com o Dev 1)."""
    from .infrastructure.document_processing_source import DocumentProcessingEvidenceSource

    return DocumentProcessingEvidenceSource(facade=document_processing_facade)


def create_default_policy_analysis(
    document_processing_facade=None,
    db_path: str = "exports/policy_analysis.duckdb",
    output_dir: str = "exports",
    model_name: str | None = None,
    api_key: str | None = None,
    usage_collector: UsageMetricsCollector | None = None,
    quality_signals: QualitySignalLog | None = None,
) -> PolicyAnalysisFacade:
    """Monta a fachada com os adapters reais (imports lazy — exige libs instaladas).

    `model_name=None` resolve via env `LLM_MODEL` (provedor por `/` no id:
    OpenRouter para `xiaomi/mimo-v2.6-pro`; Gemini caso contrário).
    """
    from .infrastructure.llm_agent import (
        InsurerNameAgent,
        LLMExplanationAgent,
        LLMExtraFindingsAgent,
        LLMQuestionAgent,
        LLMReviewAgent,
        MultiFieldExtractionAgent,
        PydanticAIClient,
    )
    from .infrastructure.report_agent import LLMReportAgent

    collector = usage_collector if usage_collector is not None else UsageMetricsCollector()
    client = PydanticAIClient(model_name=model_name, api_key=api_key)
    return PolicyAnalysisFacade(
        create_document_processing_evidence_source(document_processing_facade),
        MultiFieldExtractionAgent(client, usage_collector=collector),
        LLMExplanationAgent(client, usage_collector=collector),
        db_path=db_path,
        output_dir=output_dir,
        usage_collector=collector,
        quality_signals=quality_signals,
        insurer_agent=InsurerNameAgent(client, usage_collector=collector),
        question_agent=LLMQuestionAgent(client, usage_collector=collector),
        review_agent=LLMReviewAgent(client, usage_collector=collector),
        extra_findings_agent=LLMExtraFindingsAgent(client, usage_collector=collector),
        report_agent=LLMReportAgent(client, usage_collector=collector),
    )


__all__ = [
    "AGENT_REVIEWER",
    "ClassifiedError",
    "ComparisonResult",
    "Explanation",
    "Issue",
    "PolicyAnalysisFacade",
    "PolicyAnalysisRepository",
    "QualityReport",
    "QualityService",
    "QualitySignalLog",
    "ReviewItem",
    "SEVERITY_ORDER",
    "Severity",
    "UsageMetricsCollector",
    "UsageSummary",
    "create_default_policy_analysis",
    "create_document_processing_evidence_source",
    "create_policy_analysis",
]
