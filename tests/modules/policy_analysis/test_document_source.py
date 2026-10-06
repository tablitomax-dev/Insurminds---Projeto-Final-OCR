"""Adaptador de evidências do document_processing: merge e teto do contrato."""

from __future__ import annotations

from modules.policy_analysis.infrastructure.document_processing_source import (
    DocumentProcessingEvidenceSource,
)
from shared_kernel.contracts import EvidenceRef, RetrievalResult


class StubDocumentFacade:
    """Fachada roteirizada: devolve uma evidência nova + uma repetida por consulta."""

    def __init__(self):
        self.queries = []

    def retrieve_evidence(self, query):
        self.queries.append(query)
        number = len(self.queries)
        evidences = [
            EvidenceRef(
                evidence_id=f"ev_{number}",
                policy_id=query.policy_id,
                document_id="doc",
                page_number=number,
                quoted_text=f"trecho {number}",
                source_type="NATIVE_TEXT",
            ),
            EvidenceRef(
                evidence_id="ev_shared",
                policy_id=query.policy_id,
                document_id="doc",
                page_number=1,
                quoted_text="comum",
                source_type="NATIVE_TEXT",
            ),
        ]
        return RetrievalResult(query=query, evidences=evidences, retrieval_run_id=f"r{number}")


def test_top_k_nunca_passa_do_teto_do_contrato():
    facade = StubDocumentFacade()
    source = DocumentProcessingEvidenceSource(top_k=999, facade=facade)

    source.get_evidences("pol_a", field_code="franquia")

    assert facade.queries[0].top_k == 20  # clamp para o teto do `RetrievalQuery`


def test_sem_field_code_mescla_consultas_com_dedupe():
    facade = StubDocumentFacade()
    source = DocumentProcessingEvidenceSource(top_k=20, facade=facade)

    evidences = source.get_evidences("pol_a")

    assert len(facade.queries) == 1 + len(DocumentProcessingEvidenceSource._BREADTH_QUERIES)
    ids = [ev.evidence_id for ev in evidences]
    assert len(ids) == len(set(ids))  # sem duplicatas no merge
    assert "ev_shared" in ids
    assert all(ev.policy_id == "pol_a" for ev in evidences)


def test_com_field_code_faz_uma_consulta_so():
    facade = StubDocumentFacade()
    source = DocumentProcessingEvidenceSource(facade=facade)

    source.get_evidences("pol_a", field_code="franquia")

    assert len(facade.queries) == 1
    assert facade.queries[0].field_code == "franquia"
