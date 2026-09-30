"""Fixtures de PDF do modo offline (D1-P1-2a) — stdlib puro, roda sempre.

Sem marker `integration`: não exige dependência externa nem rede.

Receita das fixtures (geradas em 2026-09-27 por script stdlib — zlib é a única
compressão usada; a premissa de gerar com PyMuPDF do roadmap caiu porque `fitz`
não está disponível no ambiente):

1. `aplice_digital.pdf` — PDF 1.4 escrito à mão: 1 página A4 (MediaBox
   595×842), fonte base-14 Helvetica, content stream **sem compressão** com
   operadores de texto (`BT ... /F1 12 Tf ... (linha) Tj ... ET`) trazendo uma
   apólice D&O sintética (segurado, vigência, limite agregado, franquia).
2. `aplice_escaneada.pdf` — "escaneado" gerado **do digital** pela receita
   raster: a mesma página convertida em **imagem única** RGB 298×421 px (fundo
   branco com faixas escuras nas posições das linhas de texto do digital;
   pixels comprimidos com zlib) embutida como XObject `/Subtype /Image`
   (`/FlateDecode`) e desenhada com `q 595 0 0 842 0 0 cm /Im0 Do Q` — nenhum
   operador de texto, nenhuma camada de texto extraível.
"""

import re
import zlib
from pathlib import Path

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
DIGITAL = FIXTURES / "aplice_digital.pdf"
ESCANEADO = FIXTURES / "aplice_escaneada.pdf"

#: Limite declarado da feature: cada PDF fixture tem menos de 100 KB.
MAX_FIXTURE_BYTES = 100 * 1024

_OBJETO = re.compile(rb"(\d+)\s+0\s+obj(.*?)endobj", re.DOTALL)
_STREAM = re.compile(rb"stream\r?\n(.*?)\r?\nendstream", re.DOTALL)
#: Operadores de texto do modelo de conteúdo do PDF (camada de texto).
_OPERADORES_TEXTO = re.compile(rb"(?:^|\s)(BT|ET|Tj|TJ|Td|Tf)(?:\s|$)")


def _objetos(pdf_bytes: bytes) -> list[bytes]:
    return [corpo for _, corpo in _OBJETO.findall(pdf_bytes)]


def _conteudo_do_stream(corpo: bytes) -> bytes:
    """Conteúdo do stream do objeto, descomprimido quando FlateDecode."""
    match = _STREAM.search(corpo)
    if match is None:
        return b""
    dados = match.group(1)
    if b"/FlateDecode" in corpo:
        return zlib.decompress(dados)
    return dados


def test_fixtures_existem_e_sao_pequenas():
    for caminho in (DIGITAL, ESCANEADO):
        dados = caminho.read_bytes()
        assert dados.startswith(b"%PDF-")
        assert len(dados) < MAX_FIXTURE_BYTES


def test_digital_tem_camada_de_texto():
    streams = [_conteudo_do_stream(corpo) for corpo in _objetos(DIGITAL.read_bytes())]
    conteudo = b"\n".join(streams)
    assert _OPERADORES_TEXTO.search(conteudo)  # BT/Tj presentes
    assert b"Limite Agregado: R$ 1.000.000,00" in conteudo  # texto extraível
    assert b"/Font" in DIGITAL.read_bytes()


def test_escaneado_e_imagem_unica_sem_camada_de_texto():
    dados = ESCANEADO.read_bytes()
    objetos = _objetos(dados)
    imagens = [corpo for corpo in objetos if b"/Subtype /Image" in corpo]
    assert len(imagens) == 1  # página-imagem única
    assert b"/Font" not in dados  # nenhum recurso de fonte
    for corpo in objetos:
        conteudo = _conteudo_do_stream(corpo)
        assert _OPERADORES_TEXTO.search(conteudo) is None  # nada de BT/Tj/TJ
    assert b"/Im0 Do" in dados  # a página é a imagem desenhada
