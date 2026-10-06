"""Rótulos de exibição da UI: nome real da seguradora e id por nome de arquivo."""

from __future__ import annotations

from shared_kernel.contracts import EvidenceRef
from ui.logic import build_display_labels, format_evidence_rows, policy_id_from_filename


def _evidence(policy_id: str = "pol_a") -> EvidenceRef:
    return EvidenceRef(
        evidence_id="ev_1",
        policy_id=policy_id,
        document_id="doc_1",
        page_number=1,
        quoted_text="Trecho da apólice",
        source_type="NATIVE_TEXT",
    )


# --- id derivado do nome do PDF ----------------------------------------------


def test_policy_id_deriva_do_nome_do_arquivo():
    assert policy_id_from_filename("Porto Seguro 2024.pdf") == "porto_seguro_2024"
    assert policy_id_from_filename("POL-A.pdf") == "pol_a"
    assert policy_id_from_filename("apolice_b.PDF") == "apolice_b"


def test_policy_id_sem_nome_usa_fallback():
    assert policy_id_from_filename("???.pdf") == "apolice"


# --- rótulos de exibição ------------------------------------------------------


def test_labels_usam_o_nome_real_das_seguradoras():
    labels = build_display_labels(
        ["pol_a", "pol_b"],
        {"pol_a": {"name": "Porto Seguro", "year": "2024"}, "pol_b": {"name": "Allianz", "year": "2025"}},
    )
    assert labels == {"pol_a": "Porto Seguro", "pol_b": "Allianz"}


def test_labels_mesma_empresa_anos_diferentes_usam_o_ano():
    labels = build_display_labels(
        ["pol_a", "pol_b"],
        {"pol_a": {"name": "Porto Seguro", "year": "2024"}, "pol_b": {"name": "Porto Seguro", "year": "2025"}},
    )
    assert labels == {"pol_a": "Porto Seguro 2024", "pol_b": "Porto Seguro 2025"}


def test_labels_mesma_empresa_mesmo_ano_usam_sufixo_a_b():
    labels = build_display_labels(
        ["pol_a", "pol_b"],
        {"pol_a": {"name": "Porto Seguro", "year": "2024"}, "pol_b": {"name": "Porto Seguro", "year": "2024"}},
    )
    assert labels == {"pol_a": "Porto Seguro A", "pol_b": "Porto Seguro B"}


def test_labels_sem_nome_caem_no_policy_id():
    labels = build_display_labels(["pol_a", "pol_b"], {"pol_a": None, "pol_b": {"name": "Allianz"}})
    assert labels == {"pol_a": "pol_a", "pol_b": "Allianz"}


def test_format_evidence_rows_usa_os_labels_na_coluna_apolice():
    rows = format_evidence_rows([_evidence("pol_a")], {"pol_a": "Porto Seguro"})
    assert rows[0]["apólice"] == "Porto Seguro"
    rows = format_evidence_rows([_evidence("pol_a")])
    assert rows[0]["apólice"] == "pol_a"
