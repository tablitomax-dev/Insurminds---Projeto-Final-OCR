"""Jornada E2E do vertical slice com fakes (RF-01..RF-09 do requirements).

Fluxo: 2 PDFs → texto nativo/OCR → chunks → indexação → retrieval →
extração → comparação determinística (`ComparisonResult.campos`) →
explicação rastreável (`Explanation.text`/`evidence_ids`) → export standalone
(`export_comparison` devolve o caminho do `.md`). Nenhuma dependência externa.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from fakes.document_processing import (
    FakeEmbedder,
    FakeOcrEngine,
    FakeTextExtractor,
    InMemoryVectorIndex,
    RecordingStatusSink,
)
from modules.document_processing.domain.processing import PageText
from modules.document_processing.public_api import create_document_processing
from modules.policy_analysis.infrastructure.llm_agent import FixtureExplanationAgent
from modules.policy_analysis.public_api import (
    ClassifiedError,
    create_document_processing_evidence_source,
    create_policy_analysis,
)

POL_A, POL_B = "pol_acme", "pol_bravo"
DOC_A, DOC_B = "doc_acme", "doc_bravo"

#: Valores esperados por (policy_id, field_code) — o agente fake extrai daqui.
_VALUES = {
    (POL_A, "limite_agregado"): {"amount": 1_000_000.0, "currency": "BRL"},
    (POL_B, "limite_agregado"): {"amount": 500_000.0, "currency": "BRL"},
    (POL_A, "franquia"): {"amount": 10_000.0, "currency": "BRL"},
}
#: Campos sem valor na apólice (fluxo alternativo A).
_NOT_FOUND = {(POL_B, "franquia")}
#: Campos ambíguos que devem cair na fila de revisão (RF-04).
_AMBIGUOUS = {(POL_A, "prazo_notificacao_sinistro")}

_PDF_HEADER = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"


def _write_fake_pdf(tmp_path, name: str) -> str:
    path = tmp_path / name
    path.write_bytes(_PDF_HEADER + b"conteudo sintetico de teste\n")
    return str(path)


class _AutoExtractionAgent:
    """Agente fake multi-campo: monta a saída a partir do próprio request."""

    def extract(self, requests, run_id):
        return [_raw_for(request) for request in requests]


def _raw_for(request) -> dict:
    key = (request.policy_id, request.field_code)
    evidence_ids = [evidence.evidence_id for evidence in request.evidences][:2]
    if key in _NOT_FOUND:
        return {
            "field_code": request.field_code,
            "status": "NOT_FOUND",
            "value": None,
            "confidence": 0.0,
            "evidence_ids": [],
            "requires_human_review": False,
        }
    if key in _AMBIGUOUS:
        return {
            "field_code": request.field_code,
            "status": "AMBIGUOUS",
            # Trecho LITERAL do chunk recuperado: citação ancorada (D2-P0-1).
            "value": {"raw_text": "Prazo de notificação: 30 dias."},
            "confidence": 0.4,
            "evidence_ids": evidence_ids,
            "requires_human_review": True,
        }
    return {
        "field_code": request.field_code,
        "status": "FOUND",
        "value": dict(_VALUES[key]),
        "confidence": 0.92,
        "evidence_ids": evidence_ids,
        "requires_human_review": False,
    }


def _stack(tmp_path, explanation_agent=None):
    """Monta as duas fachadas com fakes e devolve um dicionário de contexto."""
    file_a = _write_fake_pdf(tmp_path, "apolice_acme.pdf")
    file_b = _write_fake_pdf(tmp_path, "apolice_bravo.pdf")

    pages_a = [
        PageText(page_number=1, text="Limite Agregado: R$ 1.000.000,00 por período. "),
        PageText(
            page_number=2,
            text="Franquia: R$ 10.000,00 por sinistro. Prazo de notificação: 30 dias. ",
        ),
    ]
    pages_b = [
        PageText(page_number=1, text="Limite Agregado: R$ 500.000,00 por período. "),
        PageText(page_number=2, text=""),  # página escaneada → OCR
    ]

    text_extractor = FakeTextExtractor(pages_by_path={file_a: pages_a, file_b: pages_b})
    ocr_engine = FakeOcrEngine(
        default_result=("Apólice digitalizada — sem cláusula de franquia", 0.93)
    )
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

    policy_facade = create_policy_analysis(
        create_document_processing_evidence_source(doc_facade),
        _AutoExtractionAgent(),
        explanation_agent or FixtureExplanationAgent(),
        db_path=":memory:",
        output_dir=str(tmp_path / "exports"),
    )

    return {
        "file_a": file_a,
        "file_b": file_b,
        "doc": doc_facade,
        "policy": policy_facade,
        "index": vector_index,
        "status_sink": status_sink,
        "ocr_engine": ocr_engine,
    }


def test_jornada_completa_com_2_apolices(tmp_path):
    stack = _stack(tmp_path)
    policy = stack["policy"]
    doc = stack["doc"]

    # 1. Processa as duas apólices (RF-01..RF-03, RF-06)
    status_a = doc.process_document(DOC_A, POL_A, stack["file_a"])
    status_b = doc.process_document(DOC_B, POL_B, stack["file_b"])
    assert status_a.stage == "INDEXED"
    assert status_b.stage == "INDEXED"

    stages_a = [
        status.stage
        for status in stack["status_sink"].statuses
        if status.document_id == DOC_A
    ]
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
    ambiguous = policy.extract_field(POL_A, "prazo_notificacao_sinistro")
    assert ambiguous.status == "AMBIGUOUS"
    queue = policy.list_review_queue(POL_A)
    assert [item.fact.field_code for item in queue] == ["prazo_notificacao_sinistro"]
    assert queue[0].fact.evidence_ids

    # 5. Comparação determinística campo a campo (RF-06, RN-01)
    comparison = policy.compare_policies(POL_A, POL_B)
    codes = [field["code"] for field in policy.list_fields()]
    resultados = {campo.field_code: campo.resultado for campo in comparison.campos}
    assert len(comparison.campos) == len(codes)  # inclui os ausentes
    assert resultados["limite_agregado"] == "MAIOR"
    assert comparison.campo("limite_agregado").direcao == "A"
    assert resultados["franquia"] == "AUSENTE_B"
    assert resultados["prazo_notificacao_sinistro"] == "AGUARDANDO_REVISAO"
    assert resultados["vigencia"] == "AUSENTES_AMBOS"

    # Determinismo: nova comparação reproduz os mesmos resultados
    again = policy.compare_policies(POL_A, POL_B)
    assert {
        campo.field_code: campo.resultado for campo in again.campos
    } == resultados

    # 6. Explicação com evidência citada dos dois lados (RF-07)
    explanation = policy.explain_difference(comparison.comparison_id, "limite_agregado")
    campo = comparison.campo("limite_agregado")
    assert explanation.comparison_id == comparison.comparison_id
    assert explanation.field_code == "limite_agregado"
    assert explanation.text
    assert set(explanation.evidence_ids) <= set(campo.evidencias_a) | set(
        campo.evidencias_b
    )
    assert set(explanation.evidence_ids) & set(campo.evidencias_a)
    assert set(explanation.evidence_ids) & set(campo.evidencias_b)

    # 7. Export standalone com todos os campos do catálogo (RF-08)
    export_path = policy.export_comparison(comparison.comparison_id)
    assert export_path.endswith(".md")
    path = Path(export_path)
    assert path.parent == tmp_path / "exports"
    content = path.read_text(encoding="utf-8")
    for field_code in codes:
        assert field_code in content
    assert comparison.comparison_id in content

    # 8. Idempotência: reprocessar A não duplica chunks (RF-09, RN-04)
    chunks_before = len(stack["index"].records)
    doc.process_document(DOC_A, POL_A, stack["file_a"])
    assert len(stack["index"].records) == chunks_before


def test_explanacao_sem_evidencia_eh_rejeitada(tmp_path):
    stack = _stack(
        tmp_path,
        explanation_agent=FixtureExplanationAgent(
            {"limite_agregado": {"text": "Explicação qualquer sem citação.", "evidence_ids": []}}
        ),
    )
    policy = stack["policy"]
    doc = stack["doc"]
    doc.process_document(DOC_A, POL_A, stack["file_a"])
    doc.process_document(DOC_B, POL_B, stack["file_b"])
    policy.extract_field(POL_A, "limite_agregado")
    policy.extract_field(POL_B, "limite_agregado")
    comparison = policy.compare_policies(POL_A, POL_B)

    with pytest.raises(ClassifiedError) as excinfo:
        policy.explain_difference(comparison.comparison_id, "limite_agregado")
    assert excinfo.value.code == "EXPLANATION_NOT_CITED"
