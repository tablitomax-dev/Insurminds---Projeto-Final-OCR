"""Adapters de extração: PyMuPDF (texto nativo) e PaddleOCR (páginas escaneadas).

As bibliotecas externas são importadas de forma lazy; se faltarem, a
construção do adapter falha com `RuntimeError` claro — o módulo continua
importável sem nenhuma delas instalada (RNF-06).
"""

import os
import tempfile

from ..domain.processing import PageText

#: Zoom de renderização da página para o OCR (qualidade suficiente do PaddleOCR).
OCR_RENDER_DPI = 200


def _load_fitz():
    try:
        import fitz  # PyMuPDF
    except ImportError as exc:
        raise RuntimeError(
            "dependência ausente: pymupdf — instale para usar este adapter"
        ) from exc
    return fitz


def _load_paddleocr():
    try:
        import paddleocr
    except ImportError as exc:
        raise RuntimeError(
            "dependência ausente: paddleocr — instale para usar este adapter"
        ) from exc
    return paddleocr


class PyMuPdfTextExtractor:
    """Extrai o texto nativo página a página com PyMuPDF (RF-02)."""

    def __init__(self) -> None:
        self._fitz = _load_fitz()

    def extract_pages(self, file_path: str) -> list[PageText]:
        pages: list[PageText] = []
        with self._fitz.open(file_path) as document:
            for page_number, page in enumerate(document, start=1):
                pages.append(PageText(page_number=page_number, text=page.get_text() or ""))
        return pages


class PaddleOcrEngine:
    """Aplica OCR básico (PaddleOCR) a uma página renderizada (RF-03)."""

    def __init__(self, lang: str = "pt") -> None:
        self._lang = lang
        self._paddleocr = _load_paddleocr()
        self._engine = None

    def ocr_page(self, file_path: str, page_number: int) -> tuple[str, float | None]:
        fitz = _load_fitz()
        with fitz.open(file_path) as document:
            page = document.load_page(page_number - 1)
            pixmap = page.get_pixmap(dpi=OCR_RENDER_DPI)

        handle = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        image_path = handle.name
        handle.close()
        try:
            pixmap.save(image_path)
            return self._run_engine(image_path)
        finally:
            os.remove(image_path)

    def _run_engine(self, image_path: str) -> tuple[str, float | None]:
        engine = self._ensure_engine()
        texts: list[str] = []
        scores: list[float] = []
        if hasattr(engine, "predict"):
            # PaddleOCR >= 3 expõe `predict` com rec_texts/rec_scores.
            for result in engine.predict(image_path):
                texts.extend(result.get("rec_texts", []) or [])
                scores.extend(float(score) for score in (result.get("rec_scores", []) or []))
        else:
            # PaddleOCR 2.x: `ocr` devolve linhas [box, (texto, confiança)].
            results = engine.ocr(image_path)
            lines = results[0] if results else []
            for line in lines or []:
                text, score = line[1]
                texts.append(text)
                scores.append(float(score))

        joined = "\n".join(text for text in texts if text).strip()
        mean_confidence = sum(scores) / len(scores) if scores else None
        return joined, mean_confidence

    def _ensure_engine(self):
        if self._engine is None:
            self._engine = self._paddleocr.PaddleOCR(lang=self._lang)
        return self._engine
