"""UI do analista em modo demonstração offline (sem LLM/OCR/Qdrant reais).

Uso (na raiz do repositório):
    .venv\\Scripts\\python.exe -m streamlit run run_ui_demo.py

A lógica roda real (chunking, guardas pós-LLM, comparação determinística,
revisão humana, export) com o I/O simulado pelas fixtures das apólices
sintéticas — a mesma combinação do `demo.py`. Use os `policy_id` `POL-A` e
`POL-B` (ou mantenha os padrões `pol_acme`/`pol_bravo`) para ver os fatos
das fixtures.

Este launcher fica na raiz de propósito: não é código de produto — apenas
troca o wiring do `composition_root` pelos fakes de teste antes de executar
a `src/ui/app.py` real.
"""

from __future__ import annotations

import json
import runpy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import composition_root  # noqa: E402
from fakes.document_processing import (  # noqa: E402
    FakeEmbedder,
    FakeOcrEngine,
    FakeTextExtractor,
    InMemoryVectorIndex,
    RecordingStatusSink,
)
from modules.document_processing.domain.processing import PageText  # noqa: E402
from modules.document_processing.public_api import (  # noqa: E402
    create_document_processing,
)
from modules.policy_analysis.infrastructure.evidence_source import (  # noqa: E402
    MockEvidenceSource,
)
from modules.policy_analysis.infrastructure.llm_agent import (  # noqa: E402
    FixtureExplanationAgent,
    FixtureExtractionAgent,
)
from modules.policy_analysis.public_api import PolicyAnalysisFacade  # noqa: E402

FIXTURES = ROOT / "tests" / "modules" / "policy_analysis" / "fixtures"

_DEMO_PAGES = [
    PageText(1, "APOLICE D&O — condicoes gerais da cobertura de responsabilidade."),
    PageText(2, "Anexo I — limites, franquias, vigencia e extensao territorial."),
]


def build_demo_facades(
    db_path: str = ":memory:",
    model_name: str = "fixture",
    api_key: str | None = None,
):
    """`build_facades` do composition root com I/O simulado (fixtures).

    `db_path` padrão `:memory:`: demo não persiste e não trava arquivo entre
    sessões/servidores (DuckDB exige acesso exclusivo por processo).
    """
    document = create_document_processing(
        text_extractor=FakeTextExtractor(default_pages=_DEMO_PAGES),
        ocr_engine=FakeOcrEngine(),
        embedder=FakeEmbedder(),
        vector_index=InMemoryVectorIndex(),
        status_sink=RecordingStatusSink(),
    )

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
    evidences_by_policy = {
        "POL-A": evidences_a,
        "POL-B": evidences_b,
        "pol_acme": evidences_a,
        "pol_bravo": evidences_b,
    }
    outputs_by_policy = {
        "POL-A": fixtures["a"]["llm_output"],
        "POL-B": fixtures["b"]["llm_output"],
        "pol_acme": fixtures["a"]["llm_output"],
        "pol_bravo": fixtures["b"]["llm_output"],
    }

    policy = PolicyAnalysisFacade(
        MockEvidenceSource(evidences_by_policy),
        FixtureExtractionAgent(outputs_by_policy),
        FixtureExplanationAgent({}),
        db_path=db_path,
        output_dir=str(ROOT / "exports"),
    )
    return document, policy


composition_root.build_facades = build_demo_facades
runpy.run_path(str(ROOT / "src" / "ui" / "app.py"), run_name="__main__")
