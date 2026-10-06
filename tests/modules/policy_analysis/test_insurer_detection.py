"""Detecção determinística da seguradora (OCR-primeiro, sem custo de LLM)."""

from __future__ import annotations

from modules.policy_analysis.domain.insurer_detection import detect_insurer


def test_detecta_nome_e_ano_pela_leitura_direta():
    pages = [
        "[OCR/visão]\nPORTO SEGURO COMPANHIA DE SEGUROS\nApólice D&O\n"
        "[texto nativo]\nVigência: 01/01/2025 a 01/01/2026",
    ]
    info = detect_insurer(pages)
    assert info == {
        "name": "PORTO SEGURO COMPANHIA DE SEGUROS",
        "year": "2025",
    }


def _page(*lines: str) -> str:
    return "\n".join(lines)


def test_candidatos_contidos_sao_o_mesmo_nome():
    info = detect_insurer(
        [_page("[OCR/visão]", "Porto Seguro S.A.", "texto qualquer", "Porto Seguro")]
    )
    assert info is not None
    assert info["name"] == "Porto Seguro S.A."


def test_candidatos_divergentes_sao_caso_estranho():
    assert detect_insurer([_page("Porto Seguro", "Allianz Seguros")]) is None


def test_sem_candidato_retorna_none():
    assert detect_insurer([_page("Cláusula 7 — Limites", "Franquia de R$ 50.000,00")]) is None
    assert detect_insurer([]) is None


def test_linhas_de_marcador_sao_ignoradas():
    info = detect_insurer([_page("[OCR/visão]", "[texto nativo]", "Tokio Marine Seguros")])
    assert info == {"name": "Tokio Marine Seguros", "year": None}


def test_nome_com_digitos_e_rejeitado():
    assert detect_insurer([_page("Seguradora 24h Ltda 123")]) is None


def test_titulo_do_documento_nao_vira_nome_de_empresa():
    # Regressão: "Condições Gerais Seguro de Responsabilidade" é título, não seguradora.
    pages = [
        "[OCR/visão]\nCondições Gerais Seguro de Responsabilidade\n"
        "[texto nativo]\nVigência: 01/01/2025"
    ]
    assert detect_insurer(pages) is None


def test_titulo_nao_concorre_com_o_nome_real():
    info = detect_insurer(
        [_page("ALLIANZ SEGUROS S.A.", "Condições Gerais Seguro de Responsabilidade")]
    )
    assert info == {"name": "ALLIANZ SEGUROS S.A.", "year": None}
