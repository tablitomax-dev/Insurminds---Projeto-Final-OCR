"""T013 — Export Markdown standalone com todos os campos do catálogo (RF-08, OQ-04 revisada)."""

from __future__ import annotations

from modules.policy_analysis.application.export import ExportService
from modules.policy_analysis.domain.field_catalog import all_codes
from modules.policy_analysis.domain.models import ComparisonResult, FieldComparison
from modules.policy_analysis.domain.value_types import normalize_text
from modules.policy_analysis.infrastructure.duckdb_repository import PolicyAnalysisRepository

LABELS = {
    "limite_agregado": "Limite agregado",
    "limite_por_sinistro": "Limite por sinistro",
    "franquia": "Franquia/deducível",
    "vigencia": "Vigência",
    "prazo_notificacao_sinistro": "Prazo de notificação de sinistro",
    "extensao_territorial": "Extensão territorial",
    "exclusoes_chave": "Exclusões-chave",
    "limite_defesa_custos": "Limite de defesa de custos",
    "retroatividade": "Retroatividade (claims-made)",
    "indice_reajuste": "Índice de reajuste/correção",
}


def build_full_comparison() -> ComparisonResult:
    campos = []
    for code in all_codes():
        ausente = code == "limite_defesa_custos"
        campos.append(
            FieldComparison(
                field_code=code,
                resultado="AUSENTE_B" if ausente else "IGUAL",
                valor_a=None if ausente else {"valor": "A"},
                valor_b=None,
                direcao="n/a" if ausente else "igual",
                evidencias_a=[],
                evidencias_b=[],
                explicacao=None if ausente else f"Sem diferença em {code}.",
            )
        )
    return ComparisonResult(
        comparison_id="CMP-EXPORT-1",
        policy_id_a="POL-A",
        policy_id_b="POL-B",
        campos=tuple(campos),
    )


def test_export_gera_markdown_standalone_com_os_10_campos(tmp_path):
    repo = PolicyAnalysisRepository(":memory:")
    repo.upsert_comparison(build_full_comparison())
    service = ExportService(repo, output_dir=str(tmp_path))

    path = service.export_comparison("CMP-EXPORT-1")

    assert path.endswith(".md")
    text = open(path, encoding="utf-8").read()
    assert text.startswith("#")  # documento standalone, abre em qualquer lugar
    assert len(text) > 500

    normalized = normalize_text(text)
    for code in all_codes():
        assert normalize_text(LABELS[code]) in normalized, f"campo {code} ausente no export"
    assert "ausente_b" in normalized  # campo ausente sinalizado, não omitido
    assert "cmp-export-1" in normalized  # ComparisonId no documento


def test_export_e_idempotente(tmp_path):
    repo = PolicyAnalysisRepository(":memory:")
    repo.upsert_comparison(build_full_comparison())
    service = ExportService(repo, output_dir=str(tmp_path))

    first = service.export_comparison("CMP-EXPORT-1")
    second = service.export_comparison("CMP-EXPORT-1")
    assert first == second
