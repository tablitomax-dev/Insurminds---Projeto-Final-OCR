"""Jornada E2E do vertical slice com fakes (RF-01..RF-09 do requirements).

Fluxo: 2 PDFs → texto nativo/OCR → chunks → indexação → retrieval →
extração de `limite_agregado` → comparação determinística → explicação
com evidência → export standalone. Nenhuma dependência externa.
"""

from __future__ import annotations

import pytest

from fakes.document_processing import (
    FakeEmbedder,
    FakeOcrEngine,
    FakeTextExtractor,
    InMemoryVectorIndex,
    RecordingStatusSink,
)
from fakes.policy_analysis import FakeExplanationGenerator, FakeLlmExtractor, InMemoryFactRepository
from modules.document_processing.domain.processing import PageText
from modules.document_processing.public_api import create_document_processing
from modules.policy_analysis.application.ports import LlmOutputError
from modules.policy_analysis.domain.catalog import FIELD_CATALOG
from modules.policy_analysis.infrastructure.document_retriever import DocumentProcessingRetriever
from modules.policy_analysis.public_api import create_policy_analysis
from shared_kernel.contracts import ExtractedFact

POL_A, POL_B = "pol_acme", "pol_bravo"
DOC_A, DOC_B = "doc_acme", "doc_bravo"

#: Valores esperados por (policy_id, field_code) — o LLM fake extrai daqui.
_VALUES = {
    (POL_A, "limite_agregado"): {"amount": 1_000_000.0, "currency": "BRL", "raw_text": "R$ 1.000.000,00"},
    (POL_B, "limite_agregado"): {"amount": 500_000.0, "currency": "BRL", "raw_text": "R$ 500.000,00"},
    (POL_A, "franquia"): {"amount": 10_000.0, "currency": "BRL", "raw_text": "R$ 10.000,00"},
}
#: Campos sem valor na apólice (fluxo alternativo A).
_NOT_FOUND = {(POL_B, "franquia")}
#: Campos ambíguos que devem cair na fila de revisão (RF-04).
_AMBIGUOUS = {(POL_A, "prazo_notificacao")}

_PDF_HEADER = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"


def _write_fake_pdf(tmp_path, name: str) -> str:
    path = tmp_path / name
    path.write_bytes(_PDF_HEADER + b"conteudo sintetico de teste\n")
    return str(path)


def _llm_result_for(request) -> ExtractedFact:
    key = (request.policy_id, request.field_code)
    evidence_ids = [evidence.evidence_id for evidence in request.evidences][:2]
    if key in _NOT_FOUND:
        return ExtractedFact(
            fact_id=f"fact_{request.policy_id}_{request.field_code}",
            policy_id=request.policy_id,
            field_code=request.field_code,
            status="NOT_FOUND",
            value=None,
            normalized_value=None,
            confidence=0.0,
            evidence_ids=[],
            requires_human_review=False,
        )
    if key in _AMBIGUOUS:
        return ExtractedFact(
            fact_id=f"fact_{request.policy_id}_{request.field_code}",
            policy_id=request.policy_id,
            field_code=request.field_code,
            status="AMBIGUOUS",
            value={"raw_text": "prazo nao claro na apólice"},
            normalized_value=None,
            confidence=0.4,
            evidence_ids=evidence_ids,
            requires_human_review=True,
        )
    return ExtractedFact(
        fact_id=f"fact_{request.policy_id}_{request.field_code}",
        policy_id=request.policy_id,
        field_code=request.field_code,
        status="FOUND",
        value=dict(_VALUES[key]),
        normalized_value=None,
        confidence=0.92,
        evidence_ids=evidence_ids,
        requires_human_review=False,
    )


class _AutoLlmExtractor(FakeLlmExtractor):
    """FakeLlmExtractor que constrói a resposta a partir do próprio request."""

    def extract(self, request):
        self.requests.append(request)
        return _llm_result_for(request)


@pytest.fixture()
def stack(tmp_path):
    """Monta as duas fachadas com fakes e devolve um dicionário de contexto."""
    file_a = _write_fake_pdf(tmp_path, "apolice_acme.pdf")
    file_b = _write_fake_pdf(tmp_path, "apolice_bravo.pdf")

    pages_a = [
        PageText(page_number=1, text="Limite Agregado: R$ 1.000.000,00 por período. "),
        PageText(page_number=2, text="Franquia: R$ 10.000,00 por sinistro. Prazo de notificação: 30 dias. "),
    ]
    pages_b = [
        PageText(page_number=1, text="Limite Agregado: R$ 500.000,00 por período. "),
        PageText(page_number=2, text=""),  # página escaneada → OCR
    ]

    text_extractor = FakeTextExtractor(pages_by_path={file_a: pages_a, file_b: pages_b})
    ocr_engine = FakeOcrEngine(default_result=("Apólice digitalizada — sem cláusula de franquia", 0.93))
    embedder = FakeEmbedder()
    vector_index = InMemoryVectorIndex()
    status_sink = RecordingStatusSink()

    doc_facade = create_document_processing(
        text_extractor=text_extractor,
        ocr_engine=ocr_engine,
        embedder=embedder,
        vector_index=vector_index,
        status_sink=status_sink,
    )

    repository = InMemoryFactRepository()
    explainer = FakeExplanationGenerator()
    llm = _AutoLlmExtractor(result=None)
    policy_facade = create_policy_analysis(
        retriever=DocumentProcessingRetriever(doc_facade),
        llm_extractor=llm,
        repository=repository,
        explanation_generator=explainer,
    )

    return {
        "file_a": file_a,
        "file_b": file_b,
        "doc": doc_facade,
        "policy": policy_facade,
        "index": vector_index,
        "status_sink": status_sink,
        "ocr_engine": ocr_engine,
        "repository": repository,
        "explainer": explainer,
        "llm": llm,
    }


def test_jornada_completa_com_2_apolices(stack, tmp_path):
    policy = stack["policy"]
    doc = stack["doc"]

    # 1. Processa as duas apólices (RF-01..RF-03, RF-06)
    status_a = doc.process_document(DOC_A, POL_A, stack["file_a"])
    status_b = doc.process_document(DOC_B, POL_B, stack["file_b"])
    assert status_a.stage == "INDEXED"
    assert status_b.stage == "INDEXED"

    stages_a = [status.stage for status in stack["status_sink"].statuses if status.document_id == DOC_A]
    # Apólice A é toda digital → sem estágio de OCR
    assert stages_a == ["RECEIVED", "TEXT_EXTRACTED", "INDEXED"]
    # Apólice B tem página escaneada → OCR de fato disparado
    assert stack["ocr_engine"].calls == [(stack["file_b"], 2)]

    # 2. Extração do campo demonstrativo com evidência (RF-05)
    fact_a = policy.extract_field(POL_A, "limite_agregado")
    fact_b = policy.extract_field(POL_B, "limite_agregado")
    assert fact_a.status == "FOUND" and fact_a.evidence_ids
    assert fact_b.status == "FOUND" and fact_b.evidence_ids
    assert fact_a.normalized_value is not None

    # 3. Franquia: presente em A, ausente em B → NOT_FOUND sem evidência (RN-02)
    franquia_a = policy.extract_field(POL_A, "franquia")
    franquia_b = policy.extract_field(POL_B, "franquia")
    assert franquia_a.status == "FOUND" and franquia_a.evidence_ids
    assert franquia_b.status == "NOT_FOUND" and franquia_b.evidence_ids == []

    # 4. Fila de revisão com evidência anexa (RF-04)
    ambiguous = policy.extract_field(POL_A, "prazo_notificacao")
    assert ambiguous.status == "AMBIGUOUS"
    queue = policy.get_review_queue(POL_A)
    assert [fact.field_code for fact in queue] == ["prazo_notificacao"]
    assert queue[0].evidence_ids

    # 5. Comparação determinística campo a campo (RF-07, RN-01)
    comparison = policy.compare_policies(POL_A, POL_B)
    directions = {row.field_code: row.direction for row in comparison.rows}
    assert len(comparison.rows) == len(FIELD_CATALOG)  # inclui os ausentes
    assert directions["limite_agregado"] == "maior"
    assert directions["franquia"] == "ausente_b"
    assert directions["vigencia_inicio"] == "ausente_ambas"

    # Determinismo: nova comparação reproduz as mesmas direções
    again = policy.compare_policies(POL_A, POL_B)
    assert {row.field_code: row.direction for row in again.rows} == directions

    # 6. Explicação com evidência citada dos dois lados (RF-08)
    stack["explainer"].cited_ids = [fact_a.evidence_ids[0], fact_b.evidence_ids[0]]
    stack["explainer"].text = (
        f"O limite agregado de A ({fact_a.evidence_ids[0]}) supera o de B ({fact_b.evidence_ids[0]})."
    )
    text, cited = policy.explain_difference(comparison.comparison_id, "limite_agregado")
    assert cited == [fact_a.evidence_ids[0], fact_b.evidence_ids[0]]
    assert "superior" in text or "supera" in text

    # 7. Export standalone com todos os campos do catálogo (RF-08)
    export_path = policy.export_comparison(comparison.comparison_id, export_dir=tmp_path / "exports")
    content = export_path.read_text(encoding="utf-8")
    for field_code in FIELD_CATALOG:
        assert field_code in content
    assert comparison.comparison_id in content

    # 8. Idempotência: reprocessar A não duplica chunks (RF-09, RN-04)
    chunks_before = len(stack["index"].records)
    doc.process_document(DOC_A, POL_A, stack["file_a"])
    assert len(stack["index"].records) == chunks_before


def test_explanacao_sem_evidencia_eh_rejeitada(stack):
    policy = stack["policy"]
    doc = stack["doc"]
    doc.process_document(DOC_A, POL_A, stack["file_a"])
    doc.process_document(DOC_B, POL_B, stack["file_b"])
    policy.extract_field(POL_A, "limite_agregado")
    policy.extract_field(POL_B, "limite_agregado")
    comparison = policy.compare_policies(POL_A, POL_B)

    stack["explainer"].cited_ids = []
    stack["explainer"].text = "Explicação qualquer sem citação."
    with pytest.raises(LlmOutputError):
        policy.explain_difference(comparison.comparison_id, "limite_agregado")
