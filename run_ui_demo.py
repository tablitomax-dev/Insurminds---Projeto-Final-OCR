"""UI do analista sobre os PDFs carregados (OCR + LLM reais; embeddings/Qdrant simulados).

Uso (na raiz do repositório):
    iniciar_app.bat   (ou: python -B -m streamlit run run_ui_demo.py)

Com `LLM_REAL=1` (e a chave do provedor configurada), o pipeline lê os PDFs
enviados de verdade: texto nativo + OCR (PaddleOCR, visão) → extração,
explicação, perguntas e revisão com o modelo REAL via Pydantic AI. Modelo/chave
via env: `LLM_MODEL` (ex.: `xiaomi/mimo-v2.6-pro` no OpenRouter),
`OPENROUTER_API_KEY` ou `GEMINI_API_KEY` conforme o provedor.

A seguradora é identificada por leitura direta do OCR (barato); o caso estranho
sobe para a LLM confirmar e, sem confiança, a UI pergunta ao usuário.

Sem `LLM_REAL` (modo offline), o I/O volta a ser simulado pelas fixtures das
apólices sintéticas (mapeadas por ordem de uso — a UI deriva o `policy_id` do
nome do PDF).

Este launcher fica na raiz de propósito: não é código de produto — apenas
troca o wiring do `composition_root` pelos fakes de teste antes de executar
a `src/ui/app.py` real.
"""

from __future__ import annotations

import json
import os
import runpy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

# Cache dos modelos Paddle dentro do workspace (decisão E-09) — sem isto o
# Paddle tenta rebaixar os modelos para o perfil do usuário e trava.
os.environ.setdefault("PADDLE_PDX_CACHE_HOME", str(ROOT / ".tools" / "paddlex-home"))

import composition_root  # noqa: E402
from fakes.document_processing import (  # noqa: E402
    FakeEmbedder,
    FakeOcrEngine,
    FakeTextExtractor,
    InMemoryVectorIndex,
    RecordingStatusSink,
)
from fakes.policy_analysis import SlotFallback  # noqa: E402
from modules.document_processing.public_api import (  # noqa: E402
    create_document_processing,
)
from modules.policy_analysis.infrastructure.document_processing_source import (  # noqa: E402
    DocumentProcessingEvidenceSource,
)
from modules.policy_analysis.infrastructure.evidence_source import (  # noqa: E402
    MockEvidenceSource,
)
from modules.policy_analysis.infrastructure.llm_agent import (  # noqa: E402
    FixtureExplanationAgent,
    FixtureExtractionAgent,
    FixtureExtraFindingsAgent,
)
from modules.policy_analysis.infrastructure.report_agent import (  # noqa: E402
    FixtureReportAgent,
)
from modules.policy_analysis.public_api import PolicyAnalysisFacade  # noqa: E402

FIXTURES = ROOT / "tests" / "modules" / "policy_analysis" / "fixtures"


def _real_text_and_ocr():
    """Extrator de texto + OCR reais (o mais poderoso disponível); fakes no fallback."""
    try:
        from modules.document_processing.infrastructure.extractors import (
            PaddleOcrEngine,
            PyMuPdfTextExtractor,
        )

        return PyMuPdfTextExtractor(), PaddleOcrEngine()
    except Exception:  # noqa: BLE001 — demo degrada para os fakes offline
        return FakeTextExtractor(), FakeOcrEngine()


def _real_layout_engine():
    """PP-StructureV3 (markdown estruturado); None = degrada para texto/OCR."""
    try:
        from modules.document_processing.infrastructure.layout import PpStructureLayoutEngine

        return PpStructureLayoutEngine()
    except Exception:  # noqa: BLE001 — demo degrada sem layout
        return None


def build_demo_facades(
    db_path: str = ":memory:",
    model_name: str = "fixture",
    api_key: str | None = None,
):
    """`build_facades` do composition root sobre os PDFs carregados.

    `db_path` padrão `:memory:`: demo não persiste e não trava arquivo entre
    sessões/servidores (DuckDB exige acesso exclusivo por processo).
    """
    text_extractor, ocr_engine = _real_text_and_ocr()
    document = create_document_processing(
        text_extractor=text_extractor,
        ocr_engine=ocr_engine,
        embedder=FakeEmbedder(),
        vector_index=InMemoryVectorIndex(),
        status_sink=RecordingStatusSink(),
        layout_engine=_real_layout_engine(),
    )

    if os.environ.get("LLM_REAL") == "1":
        # Pipeline real sobre os PDFs enviados: OCR/texto indexados de verdade
        # + modelo real para extração/explicação/perguntas/revisão.
        from modules.policy_analysis.infrastructure.llm_agent import (
            InsurerNameAgent,
            LLMExplanationAgent,
            LLMExtraFindingsAgent,
            LLMQuestionAgent,
            LLMReviewAgent,
            MultiFieldExtractionAgent,
            PydanticAIClient,
        )
        from modules.policy_analysis.infrastructure.report_agent import LLMReportAgent

        client = PydanticAIClient(model_name=model_name if model_name != "fixture" else None)
        policy = PolicyAnalysisFacade(
            # top_k=20 é o teto do contrato `RetrievalQuery`; a cobertura do
            # documento vem do merge de consultas do adaptador de evidências.
            DocumentProcessingEvidenceSource(top_k=20, facade=document),
            MultiFieldExtractionAgent(client),
            LLMExplanationAgent(client),
            db_path=db_path,
            output_dir=str(ROOT / "exports"),
            insurer_agent=InsurerNameAgent(client),
            question_agent=LLMQuestionAgent(client),
            review_agent=LLMReviewAgent(client),
            extra_findings_agent=LLMExtraFindingsAgent(client),
            report_agent=LLMReportAgent(client),
        )
        return document, policy

    # Modo offline: I/O simulado pelas fixtures das apólices sintéticas
    # (`SlotFallback`: a UI deriva o `policy_id` do nome do PDF — ids
    # desconhecidos recebem a fixture por ordem de uso, 1ª apólice → POL-A).
    fixtures = {
        name: json.loads((FIXTURES / f"apolice_{name}.json").read_text(encoding="utf-8"))
        for name in ("a", "b")
    }
    evidences_a = MockEvidenceSource.from_fixture_files(
        FIXTURES / "apolice_a.json"
    ).get_evidences("POL-A")
    evidences_b = MockEvidenceSource.from_fixture_files(
        FIXTURES / "apolice_b.json"
    ).get_evidences("POL-B")
    evidences_by_policy = SlotFallback({"POL-A": evidences_a, "POL-B": evidences_b})
    outputs_by_policy = SlotFallback(
        {"POL-A": fixtures["a"]["llm_output"], "POL-B": fixtures["b"]["llm_output"]}
    )
    policy = PolicyAnalysisFacade(
        MockEvidenceSource(evidences_by_policy),
        FixtureExtractionAgent(outputs_by_policy),
        FixtureExplanationAgent({}),
        db_path=db_path,
        output_dir=str(ROOT / "exports"),
        extra_findings_agent=FixtureExtraFindingsAgent({}),
        report_agent=FixtureReportAgent(),
    )
    return document, policy


composition_root.build_facades = build_demo_facades
runpy.run_path(str(ROOT / "src" / "ui" / "app.py"), run_name="__main__")
