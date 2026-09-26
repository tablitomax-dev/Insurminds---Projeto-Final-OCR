"""T013 — Export PDF standalone com todos os campos do catálogo (RF-08)."""

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


def test_export_gera_pdf_standalone_com_os_10_campos(tmp_path):
    repo = PolicyAnalysisRepository(":memory:")
    repo.upsert_comparison(build_full_comparison())
    service = ExportService(repo, output_dir=str(tmp_path))

    path = service.export_comparison("CMP-EXPORT-1")

    raw = open(path, "rb").read()
    assert raw.startswith(b"%PDF")
    assert len(raw) > 1000

    # a stream do PDF escapa parênteses com '\' — removemos para a busca textual
    text = normalize_text(raw.decode("latin-1").replace("\\", ""))
    for code in all_codes():
        assert normalize_text(LABELS[code]) in text, f"campo {code} ausente no export"
    assert "ausente_b" in text  # campo ausente sinalizado, não omitido
    assert "cmp-export-1" in text  # ComparisonId no documento


def test_export_e_idempotente(tmp_path):
    repo = PolicyAnalysisRepository(":memory:")
    repo.upsert_comparison(build_full_comparison())
    service = ExportService(repo, output_dir=str(tmp_path))

    first = service.export_comparison("CMP-EXPORT-1")
    second = service.export_comparison("CMP-EXPORT-1")
    assert first == second
