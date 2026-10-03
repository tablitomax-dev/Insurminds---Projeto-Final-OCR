"""Testes da formatação das evidências na tela de consulta (etapa 5 do escopo)."""

from __future__ import annotations

from shared_kernel.contracts import EvidenceRef
from ui.logic import format_evidence_rows


def _evidence(**overrides) -> EvidenceRef:
    payload = {
        "evidence_id": "ev_doc_pol_acme:p1:c0",
        "policy_id": "pol_acme",
        "document_id": "doc_pol_acme",
        "page_number": 3,
        "chunk_id": "doc_pol_acme:p1:c0",
        "section_name": "Cláusula 7 — Limites",
        "quoted_text": "O limite de responsabilidade é de R$ 2.000.000,00 por sinistro.",
        "retrieval_score": 0.95,
        "ocr_confidence": None,
        "source_type": "NATIVE_TEXT",
    }
    payload.update(overrides)
    return EvidenceRef(**payload)


def test_linhas_trazem_colunas_para_o_analista():
    rows = format_evidence_rows([_evidence()])

    assert rows == [
        {
            "apólice": "pol_acme",
            "página": "3",
            "seção": "Cláusula 7 — Limites",
            "trecho": "O limite de responsabilidade é de R$ 2.000.000,00 por sinistro.",
            "score": "0,95",
            "origem": "texto nativo",
        }
    ]


def test_score_em_pt_br_com_duas_casas():
    rows = format_evidence_rows([_evidence(retrieval_score=1.0)])

    assert rows[0]["score"] == "1,00"


def test_ausencias_viram_traco():
    rows = format_evidence_rows(
        [_evidence(section_name=None, retrieval_score=None, source_type="PADDLEOCR")]
    )

    row = rows[0]
    assert row["seção"] == "—"
    assert row["score"] == "—"
    assert row["origem"] == "OCR (PaddleOCR)"


def test_trecho_curto_passa_inteiro():
    rows = format_evidence_rows([_evidence(quoted_text="cobertura mundial")])

    assert rows[0]["trecho"] == "cobertura mundial"


def test_trecho_longo_e_resumido_com_reticencias():
    longo = "franquia aplicável " * 30
    rows = format_evidence_rows([_evidence(quoted_text=longo)])

    trecho = rows[0]["trecho"]
    assert trecho.endswith("…")
    assert len(trecho) <= 161


def test_trecho_fica_em_uma_unica_linha():
    rows = format_evidence_rows([_evidence(quoted_text="linha um\nlinha dois\nlinha três")])

    assert rows[0]["trecho"] == "linha um linha dois linha três"


def test_nenhum_simbolo_de_json_nas_linhas():
    rows = format_evidence_rows([_evidence(), _evidence(page_number=12)])

    for row in rows:
        for value in row.values():
            assert "{" not in value
            assert '"' not in value


def test_lista_vazia_devolve_lista_vazia():
    assert format_evidence_rows([]) == []