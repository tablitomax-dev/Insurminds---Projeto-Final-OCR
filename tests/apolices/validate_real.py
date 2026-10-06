r"""Validação REAL do pipeline sobre os PDFs de `tests/apolices` (2 por rodada).

Uso (da raiz, com a chave OPENROUTER_API_KEY no ambiente):
    $env:PYTHONPATH=".tools\pylibs"; python -B tests/apolices/validate_real.py <rodada>

Rodadas (cada arquivo ao menos uma vez):
    1: AXA + Allianz 2025
    2: PORTO + Allianz 2025
    3: Allianz 2017 (JPG, convertido para PDF) + PORTO

Pipeline real: PyMuPDF + PaddleOCR (pesado, markdown via PP-StructureV3) →
cache DuckDB → RAG por seções → extração LLM (MiMo) → comparação →
Relatório D&O → export. Não é código de produto: é a bancada de validação.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

os.environ.setdefault("LLM_MODEL", "xiaomi/mimo-v2.6-pro")
# Cache dos modelos Paddle dentro do workspace (decisão E-09) — sem isto o
# Paddle tenta rebaixar tudo para o perfil do usuário e trava.
os.environ.setdefault("PADDLE_PDX_CACHE_HOME", str(ROOT / ".tools" / "paddlex-home"))

from modules.document_processing.public_api import create_document_processing  # noqa: E402
from modules.policy_analysis.infrastructure.document_processing_source import (  # noqa: E402
    DocumentProcessingEvidenceSource,
)
from modules.policy_analysis.infrastructure.llm_agent import (  # noqa: E402
    InsurerNameAgent,
    LLMExplanationAgent,
    LLMExtraFindingsAgent,
    LLMQuestionAgent,
    LLMReviewAgent,
    MultiFieldExtractionAgent,
    PydanticAIClient,
)
from modules.policy_analysis.infrastructure.report_agent import LLMReportAgent  # noqa: E402
from modules.policy_analysis.public_api import PolicyAnalysisFacade  # noqa: E402

APOLICES = ROOT / "tests" / "apolices"

FILES = {
    "AXA": APOLICES / "AXA_D&O - teste.pdf",
    "ALLIANZ2025": APOLICES / "Allianz Condições_Gerais- 2025_teste.pdf",
    "PORTO": APOLICES / "PORTO_D&O_teste.pdf",
    "ALLIANZ2017_JPG": APOLICES / "Allianz Condições_Gerais- 2017_teste_pages-to-jpg-0063.jpg",
}

ROUNDS = {
    1: ["AXA", "ALLIANZ2025"],
    2: ["PORTO", "ALLIANZ2025"],
    3: ["ALLIANZ2017_JPG", "PORTO"],
}


def to_pdf(path: Path) -> Path:
    """Imagem (JPG/PNG) vira PDF de uma página; PDF segue direto."""
    if path.suffix.lower() == ".pdf":
        return path
    import fitz  # PyMuPDF

    doc = fitz.open(str(path))
    pdf_bytes = doc.convert_to_pdf()
    doc.close()
    handle = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
    handle.write(pdf_bytes)
    handle.close()
    return Path(handle.name)


def build_facades():
    """Fachadas reais: OCR pesado (PP-StructureV3 markdown) + LLM MiMo."""
    from fakes.document_processing import FakeEmbedder, InMemoryVectorIndex, RecordingStatusSink
    from modules.document_processing.infrastructure.extractors import (
        PaddleOcrEngine,
        PyMuPdfTextExtractor,
    )
    from modules.document_processing.infrastructure.layout import PpStructureLayoutEngine

    try:
        layout = PpStructureLayoutEngine()
    except Exception as exc:  # noqa: BLE001 — avisa e degrada
        print(f"[aviso] PP-StructureV3 indisponível ({type(exc).__name__}); markdown = texto/OCR")
        layout = None

    document = create_document_processing(
        text_extractor=PyMuPdfTextExtractor(),
        ocr_engine=PaddleOcrEngine(),
        embedder=FakeEmbedder(),
        vector_index=InMemoryVectorIndex(),
        status_sink=RecordingStatusSink(),
        layout_engine=layout,
    )
    client = PydanticAIClient()
    policy = PolicyAnalysisFacade(
        DocumentProcessingEvidenceSource(top_k=20, facade=document),
        MultiFieldExtractionAgent(client),
        LLMExplanationAgent(client),
        db_path=":memory:",
        output_dir=str(ROOT / "exports" / "validation"),
        insurer_agent=InsurerNameAgent(client),
        question_agent=LLMQuestionAgent(client),
        review_agent=LLMReviewAgent(client),
        extra_findings_agent=LLMExtraFindingsAgent(client),
        report_agent=LLMReportAgent(client),
    )
    return document, policy


def main() -> None:
    round_number = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    keys = ROUNDS[round_number]
    print(f"=== Rodada {round_number}: {keys} ===", flush=True)
    document, policy = build_facades()
    summary: dict = {"rodada": round_number, "arquivos": {}}

    for key in keys:
        path = to_pdf(FILES[key])
        policy_id = key.lower()
        entry: dict = {"arquivo": FILES[key].name}
        t0 = time.time()
        print(f"[{key}] processando {FILES[key].name} ...", flush=True)
        try:
            status = document.process_document(
                document_id=f"doc_{policy_id}", policy_id=policy_id, file_path=str(path)
            )
            entry["processamento"] = {
                "stage": status.stage,
                "progresso": status.progress,
                "mensagem": status.message,
            }
            print(f"[{key}] processado: {status.stage}", flush=True)
            if status.stage == "FAILED":
                entry["tempo_s"] = round(time.time() - t0, 1)
                summary["arquivos"][key] = entry
                continue

            t1 = time.time()
            markdown_pages = document.extract_markdown(str(path))
            policy.store_markdown(
                policy_id,
                list(enumerate(markdown_pages, start=1)),
                file_path=str(path),
            )
            entry["markdown"] = {
                "paginas": len(markdown_pages),
                "chars": sum(len(p) for p in markdown_pages),
                "tabelas_md": sum(1 for p in markdown_pages if "|" in p and "---" in p),
                "tempo_s": round(time.time() - t1, 1),
            }
            print(
                f"[{key}] markdown: {entry['markdown']['paginas']} pág, "
                f"{entry['markdown']['chars']} chars, {entry['markdown']['tabelas_md']} tabelas",
                flush=True,
            )

            t2 = time.time()
            preview = document.extract_preview(str(path), max_pages=2)
            insurer = policy.identify_insurer(policy_id, preview)
            entry["seguradora"] = insurer
            entry["seguradora_tempo_s"] = round(time.time() - t2, 1)
            print(f"[{key}] seguradora: {insurer}", flush=True)

            t3 = time.time()
            codes = [f["code"] for f in policy.list_fields()]
            facts = policy.extract_fields(policy_id, codes)
            entry["extracao"] = {
                "FOUND": sum(1 for f in facts if f.status == "FOUND"),
                "NOT_FOUND": sum(1 for f in facts if f.status == "NOT_FOUND"),
                "NEEDS_REVIEW": sum(1 for f in facts if f.status == "NEEDS_REVIEW"),
                "valores": {
                    f.field_code: (f.normalized_value or f.value) for f in facts if f.status == "FOUND"
                },
                "tempo_s": round(time.time() - t3, 1),
            }
            print(
                f"[{key}] extração: {entry['extracao']['FOUND']} FOUND, "
                f"{entry['extracao']['NOT_FOUND']} NOT_FOUND, "
                f"{entry['extracao']['NEEDS_REVIEW']} NEEDS_REVIEW "
                f"({entry['extracao']['tempo_s']}s)",
                flush=True,
            )

            t4 = time.time()
            extras = policy.extract_extra_findings(policy_id)
            entry["extras"] = [
                {"label": e.get("label"), "value": e.get("value"), "evidence_ids": e.get("evidence_ids")}
                for e in extras
            ]
            entry["extras_tempo_s"] = round(time.time() - t4, 1)
            print(f"[{key}] extras: {len(extras)} achados", flush=True)
        except Exception as exc:  # noqa: BLE001 — a validação registra e segue
            entry["erro"] = f"{type(exc).__name__}: {exc}"
            print(f"[{key}] ERRO: {entry['erro']}", flush=True)
        entry["tempo_total_s"] = round(time.time() - t0, 1)
        summary["arquivos"][key] = entry
        print(f"[{key}] concluído em {entry['tempo_total_s']}s")

    if all(summary["arquivos"][k].get("processamento", {}).get("stage") != "FAILED" for k in keys):
        a, b = (k.lower() for k in keys)
        t5 = time.time()
        try:
            comparison = policy.compare_policies(a, b)
            entry = summary["comparacao"] = {
                "id": comparison.comparison_id,
                "campos": {
                    c.field_code: {"resultado": c.resultado, "direcao": c.direcao}
                    for c in comparison.campos
                },
            }
            entry["tempo_s"] = round(time.time() - t5, 1)

            t6 = time.time()
            report = policy.build_report([a, b])
            path = policy.export_report(report)
            summary["relatorio"] = {
                "id": report.report_id,
                "linhas_matriz": len(report.rows),
                "tabelas": len(report.tables),
                "cenarios": len(report.scenarios),
                "ranking_informativo": report.ranking.informative_only,
                "motivo": report.ranking.motivo_sem_vencedora,
                "totais": {s.policy_id: s.total for s in report.ranking.scores},
                "checklist_ok": sum(1 for v in report.checklist.values() if v),
                "checklist_total": len(report.checklist),
                "export": path,
                "tempo_s": round(time.time() - t6, 1),
            }
        except Exception as exc:  # noqa: BLE001
            summary["erro_comparacao_relatorio"] = f"{type(exc).__name__}: {exc}"

    out = ROOT / "tests" / "apolices" / f"validation_round{round_number}.json"
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
    print(f"\nSalvo em {out}")


if __name__ == "__main__":
    main()
