"""RF-01/D2-P0-1: ancoragem de citação (funções puras do domínio)."""

from modules.policy_analysis.domain.anchoring import (
    collect_excerpts,
    extract_quoted_segments,
    unanchored_excerpts,
)

CHUNK = "Limite Agregado: R$ 1.000.000,00 por período."


def test_collect_excerpts_pega_raw_text_e_ignora_escalares():
    payload = {"scalar": 1000000.0, "currency": "BRL", "raw_text": "R$ 1.000.000,00"}

    assert collect_excerpts(payload) == ["R$ 1.000.000,00"]


def test_collect_excerpts_achata_listas_e_ninhos():
    payload = {"details": {"excerpt": ["trecho um", "trecho dois"]}, "trecho": "trecho três"}

    assert collect_excerpts(payload) == ["trecho um", "trecho dois", "trecho três"]


def test_collect_excerpts_descarta_trechos_vazios():
    assert collect_excerpts({"raw_text": "   "}) == []
    assert collect_excerpts(None) == []


def test_citacao_real_e_ancorada():
    assert unanchored_excerpts(["R$ 1.000.000,00"], [CHUNK]) == []


def test_citacao_inventada_nao_e_ancorada():
    assert unanchored_excerpts(["R$ 9.999.999,99"], [CHUNK]) == ["R$ 9.999.999,99"]


def test_multiplas_citacoes_todas_sao_ancoradas():
    excerpts = ["R$ 1.000.000,00", "R$ 7.777.777,77"]
    chunks = [CHUNK, "Franquia: R$ 10.000,00 por sinistro."]

    assert unanchored_excerpts(excerpts, chunks) == ["R$ 7.777.777,77"]


def test_ancoragem_exige_substring_literal():
    # Diferença de caixa/acentuação não ancora — a guarda é substring exata.
    assert unanchored_excerpts(["limite agregado: r$ 1.000.000,00"], [CHUNK]) != []


def test_extract_quoted_segments_de_texto_livre():
    text = 'A apólice registra "R$ 1.000.000,00" e a outra «R$ 500,00».'

    assert extract_quoted_segments(text) == ["R$ 1.000.000,00", "R$ 500,00"]


def test_extract_quoted_segments_sem_aspas_devolve_vazio():
    assert extract_quoted_segments("explicação sem citação literal") == []
