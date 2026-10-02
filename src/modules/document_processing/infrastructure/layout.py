"""Adapter de análise de layout: PP-StructureV3 (feature dev1-006 — NG-01).

Import lazy — `public_api` continua importável sem Paddle instalado; a
construção do adapter falha com `RuntimeError` claro quando falta dependência
(padrão de `extractors.py`). Erro externo vira `LayoutError` com mensagem
sanitizada (só tipo do erro e número da página) — nunca texto de apólice
(D1-P0-1, T-2a).

Saída normalizada em `LayoutRegion`, em ordem de leitura:
- `heading`: título/seção detectado pelo layout (literal);
- `table`: TSV (linhas `\\n`, células `\\t`) — serializado pelo domínio;
- `text`: trecho corrido.

A normalização é defensiva entre versões do SDK (mesmo cuidado do
`GeminiEmbedder`): aceita resultados já normalizados (`{"kind", "text"}`),
resumos (`{"headings"/"texts"/"tables_html"}`) e o formato do PP-StructureV3
(`table_res_list` com HTML de tabela + `overall_ocr_res.rec_texts`). O opt-in
de integração (`-m integration`) valida contra o SDK real.
"""

import os
import tempfile
from html.parser import HTMLParser

from ..application.ports import LayoutError, LayoutRegion
from .extractors import _load_fitz

#: Zoom de renderização da página para o layout (mesmo do OCR).
LAYOUT_RENDER_DPI = 200


class _TableHtmlParser(HTMLParser):
    """Converte HTML de tabela do SDK em TSV (linhas `\\n`, células `\\t`)."""

    def __init__(self) -> None:
        super().__init__()
        self.rows: list[list[str]] = []
        self._row: list[str] | None = None
        self._cell: list[str] | None = None

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag == "tr":
            self._row = []
        elif tag in ("td", "th") and self._row is not None:
            self._cell = []

    def handle_data(self, data: str) -> None:
        if self._cell is not None:
            self._cell.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag in ("td", "th") and self._cell is not None and self._row is not None:
            self._row.append(" ".join("".join(self._cell).split()))
            self._cell = None
        elif tag == "tr" and self._row is not None:
            self.rows.append(self._row)
            self._row = None


def _html_table_tsv(html: str) -> str:
    """HTML de tabela → TSV; tabela sem células renderiza string vazia."""
    parser = _TableHtmlParser()
    parser.feed(html or "")
    return "\n".join("\t".join(cells) for cells in parser.rows if any(cells))


def _text_of(value, key: str):
    """Lê `key` de dict ou objeto (defensivo entre SDKs); None quando ausente."""
    if isinstance(value, dict):
        return value.get(key)
    return getattr(value, key, None)


def _regions_from_result(result, order: int) -> list[LayoutRegion]:
    """Normaliza um resultado do SDK em `LayoutRegion` (ordem de leitura)."""
    if isinstance(result, list):
        regions: list[LayoutRegion] = []
        for index, item in enumerate(result):
            regions.extend(_regions_from_result(item, order + index))
        return regions
    if isinstance(result, dict) and "kind" in result:
        kind = result["kind"]
        text = str(result.get("text", ""))
        return [LayoutRegion(kind=kind, text=text, order=int(result.get("order", order)))]
    headings = _text_of(result, "headings") or []
    texts = _text_of(result, "texts") or []
    tables_html = _text_of(result, "tables_html") or []
    if not (headings or texts or tables_html):
        # Formato PP-StructureV3: tabelas em HTML + textos OCR em ordem.
        table_results = _text_of(result, "table_res_list") or []
        tables_html = [
            html
            for html in (_text_of(item, "pred_html") for item in table_results)
            if html
        ]
        ocr = _text_of(result, "overall_ocr_res") or {}
        texts = _text_of(ocr, "rec_texts") or []
    regions = []
    for heading in headings:
        regions.append(LayoutRegion(kind="heading", text=str(heading), order=order))
    for text in texts:
        regions.append(LayoutRegion(kind="text", text=str(text), order=order))
    for html in tables_html:
        regions.append(LayoutRegion(kind="table", text=_html_table_tsv(html), order=order))
    return regions


class PpStructureLayoutEngine:
    """Análise de layout (PP-StructureV3) de uma página renderizada (NG-01)."""

    def __init__(self, sdk_bundle: tuple[str, object] | None = None) -> None:
        self._kind, self._sdk = sdk_bundle if sdk_bundle is not None else self._load_sdk()
        self._engine = None

    @staticmethod
    def _load_sdk() -> tuple[str, object]:
        try:
            import paddleocr  # PP-StructureV3 (PaddleOCR >= 3)
        except ImportError as exc:
            raise RuntimeError(
                "dependência ausente: paddleocr — instale para usar este adapter"
            ) from exc
        return "paddleocr", paddleocr

    def analyze_page(self, file_path: str, page_number: int) -> list[LayoutRegion]:
        try:
            fitz = _load_fitz()
            with fitz.open(file_path) as document:
                page = document.load_page(page_number - 1)
                pixmap = page.get_pixmap(dpi=LAYOUT_RENDER_DPI)

            handle = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
            image_path = handle.name
            handle.close()
            try:
                pixmap.save(image_path)
                return self._run_engine(image_path)
            finally:
                os.remove(image_path)
        except Exception as exc:  # erro externo (SDK) traduzido para a porta (D1-P0-1)
            raise LayoutError(
                f"falha na análise de layout da página {page_number} ({type(exc).__name__})"
            ) from exc

    def _run_engine(self, image_path: str) -> list[LayoutRegion]:
        engine = self._ensure_engine()
        results = (
            engine.predict(input=image_path)
            if hasattr(engine, "predict")
            else engine(image_path)
        )
        regions: list[LayoutRegion] = []
        for order, result in enumerate(results or []):
            regions.extend(_regions_from_result(result, order))
        return regions

    def _ensure_engine(self):
        if self._engine is None:
            self._engine = self._sdk.PPStructureV3()
        return self._engine
