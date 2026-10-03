"""Testes do domínio de estrutura documental (dev1-006 — NG-01).

Detecção de marcadores de seção (literal, família fechada, início de linha),
seção vigente entre peças/páginas e serialização de tabelas (RN-02/RN-03).
"""

from types import SimpleNamespace

from modules.document_processing.domain.structure import (
    TABLE_MARKER,
    assign_sections,
    compose_page_text,
    detect_section_markers,
    serialize_table,
)


def _table(order=0, text="limite\t1000000\nfranquia\t50000"):
    return SimpleNamespace(kind="table", text=text, order=order)


# ------------------------------- T003: detector de marcadores (RN-02)


def test_marcador_e_literal_preservado():
    markers = detect_section_markers("Cláusula 5ª — FRANQUIA\nos limites seguem...")

    assert [marker.name for marker in markers] == ["Cláusula 5ª — FRANQUIA"]


def test_marcador_so_no_inicio_de_linha():
    assert detect_section_markers("no meio do texto há Cláusula citada") == []

    markers = detect_section_markers("intro\nCLÁUSULA 5ª — FRANQUIA")

    assert [marker.name for marker in markers] == ["CLÁUSULA 5ª — FRANQUIA"]


def test_familia_fechada_de_marcadores():
    text = (
        "Introdução geral\n"
        "ARTIGO 1º Do objeto\n"
        "Seção III\n"
        "EPÍGRAFE AUXILIAR\n"
        "Limite agregado"
    )

    assert [marker.name for marker in detect_section_markers(text)] == [
        "ARTIGO 1º Do objeto",
        "Seção III",
        "EPÍGRAFE AUXILIAR",
    ]


def test_secao_vigente_atravessa_pecas_e_paginas():
    sections, state = assign_sections(
        ["texto intro", "CLÁUSULA 5ª — FRANQUIA\nregras", "continuação"], initial=None
    )

    assert sections == [None, "CLÁUSULA 5ª — FRANQUIA", "CLÁUSULA 5ª — FRANQUIA"]
    # página seguinte (nova chamada) herda o estado vigente
    sections2, state2 = assign_sections(["mais regras"], initial=state)
    assert sections2 == ["CLÁUSULA 5ª — FRANQUIA"]
    assert state2 == "CLÁUSULA 5ª — FRANQUIA"


def test_marcador_no_inicio_da_peca_vale_para_ela_mesma():
    sections, _ = assign_sections(["CLÁUSULA 1ª DO OBJETO\nobjeto aqui"])

    assert sections == ["CLÁUSULA 1ª DO OBJETO"]


def test_marcador_interno_vale_para_as_pecas_seguintes():
    sections, _ = assign_sections(["pré\nCLÁUSULA 2ª\npós", "seguimento"])

    assert sections == [None, "CLÁUSULA 2ª"]


def test_antes_do_primeiro_marcador_e_none():
    sections, state = assign_sections(["só texto corrido", "mais texto"])

    assert sections == [None, None]
    assert state is None


# ------------------------------- T004: serialização de tabela (RN-03)


def test_tabela_serializada_com_marcador_e_colunas():
    rendered = serialize_table([_table(text="limite\t1000000\nfranquia\t50000")])

    assert rendered == f"{TABLE_MARKER}\nlimite | 1000000\nfranquia | 50000"


def test_regiao_nao_tabela_e_ignorada_e_tabela_vazia_nao_vira_marcador_orfao():
    text_region = SimpleNamespace(kind="text", text="trecho corrido", order=0)

    assert serialize_table([text_region]) == ""
    assert serialize_table([_table(text="\n\t\n  \t \n")]) == ""


def test_compose_page_text_ordena_regioes_e_serializa_tabelas():
    regions = [
        SimpleNamespace(kind="text", text="corpo da cláusula", order=2),
        _table(order=1),
        SimpleNamespace(kind="heading", text="CLÁUSULA 5ª — FRANQUIA", order=0),
    ]

    text = compose_page_text(regions)

    assert text.splitlines()[0] == "CLÁUSULA 5ª — FRANQUIA"
    assert TABLE_MARKER in text
    assert text.splitlines()[-1] == "corpo da cláusula"
