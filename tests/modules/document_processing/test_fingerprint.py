"""Função pura de proveniência: sha256 do texto do chunk (D1-P1-1b).

Teste primeiro (A-04): determinismo, separação entre textos distintos e
estabilidade entre execuções (vetores de referência do FIPS 180-2).
"""

import re

from modules.document_processing.domain.chunk_fingerprint import compute_content_fingerprint

_HEX_64_MINUSCULO = re.compile(r"^[0-9a-f]{64}$")


def test_e_deterministico():
    texto = "Limite Agregado: R$ 1.000.000,00"
    assert compute_content_fingerprint(texto) == compute_content_fingerprint(texto)


def test_textos_distintos_geram_resumos_distintos():
    assert compute_content_fingerprint("apólice alfa") != compute_content_fingerprint("apólice bravo")
    assert compute_content_fingerprint("texto") != compute_content_fingerprint("texto ")


def test_estavel_entre_execucoes():
    # Vetores de referência do FIPS 180-2: sha256("") e sha256("abc").
    assert compute_content_fingerprint("") == (
        "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    )
    assert compute_content_fingerprint("abc") == (
        "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    )


def test_formato_hex_64_chars_minusculo():
    resumo = compute_content_fingerprint("qualquer texto de chunk")
    assert _HEX_64_MINUSCULO.match(resumo)
