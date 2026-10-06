"""Montagem das fachadas públicas — único ponto de wiring do projeto (D2-P1-4)."""

from __future__ import annotations

from modules.document_processing.public_api import (
    DocumentProcessingFacade,
    create_default_document_processing,
)
from modules.policy_analysis.public_api import (
    PolicyAnalysisFacade,
    create_default_policy_analysis,
)


def build_facades(
    db_path: str = "exports/policy_analysis.duckdb",
    model_name: str | None = None,
    api_key: str | None = None,
) -> tuple[DocumentProcessingFacade, PolicyAnalysisFacade]:
    """Monta as duas fachadas do pipeline na ordem documental → análise.

    `model_name=None` resolve via env `LLM_MODEL` (ex.: `xiaomi/mimo-v2.6-pro`
    no OpenRouter) com fallback `gemini-3.8-flash`; a chave segue o provedor
    (`OPENROUTER_API_KEY` ou `GEMINI_API_KEY`).

    Levanta `RuntimeError`/`ImportError` quando dependências reais (LLM,
    DuckDB) estão ausentes — quem chama decide o tratamento (a UI mostra
    erro sanitizado, os testes usam wiring manual com fakes).
    """
    document = create_default_document_processing()
    policy = create_default_policy_analysis(
        document_processing_facade=document,
        db_path=db_path,
        output_dir="exports",
        model_name=model_name,
        api_key=api_key,
    )
    return document, policy
