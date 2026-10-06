"""RAG por seções do markdown: split, ranqueamento por campo e cache (RN-02)."""

from __future__ import annotations

from modules.policy_analysis.infrastructure.duckdb_repository import PolicyAnalysisRepository
from modules.policy_analysis.infrastructure.markdown_source import (
    MAX_QUOTED_CHARS,
    MarkdownSectionEvidenceSource,
    split_markdown_sections,
)


class StubDocumentFacade:
    """Fachada de `document_processing` roteirizada: conta extrações de markdown."""

    fingerprint = "fp-stub-1"

    def __init__(self, pages: list[str]):
        self._pages = pages
        self.extract_calls = 0
        self.requested: tuple | None = None

    def extract_markdown(self, file_path, max_pages):
        self.extract_calls += 1
        self.requested = (file_path, max_pages)
        return list(self._pages)


class CountingRepository(PolicyAnalysisRepository):
    """Repo real que conta leituras de markdown (prova do cache em memória)."""

    def __init__(self):
        super().__init__(":memory:")
        self.reads = 0

    def get_markdown_pages(self, policy_id: str):
        self.reads += 1
        return super().get_markdown_pages(policy_id)


# --- split por headings -------------------------------------------------------


def test_split_secoes_por_headings_com_abertura_sem_titulo():
    markdown = (
        "Apólice D&O — condições gerais.\n\n"
        "# Cobertura\nLimite de R$ 5.000.000 por sinistro.\n\n"
        "## Franquia\nFranquia de R$ 50.000 por sinistro.\n"
    )

    sections = split_markdown_sections(markdown, page_number=1)

    assert [(s.title, s.page_number, s.index) for s in sections] == [
        (None, 1, 0),
        ("Cobertura", 1, 1),
        ("Franquia", 1, 2),
    ]
    assert sections[0].text == "Apólice D&O — condições gerais."
    assert sections[1].text == "Limite de R$ 5.000.000 por sinistro."
    assert sections[2].text == "Franquia de R$ 50.000 por sinistro."


def test_split_descarta_corpos_vazios_e_paginas_sem_texto():
    sections = split_markdown_sections("# Título sem corpo\n\n# Com corpo\ntexto útil\n", page_number=2)
    assert [(s.title, s.text, s.index) for s in sections] == [("Com corpo", "texto útil", 0)]
    assert split_markdown_sections("   \n\n", page_number=1) == []


def test_split_pagina_sem_heading_e_um_bloco_de_abertura():
    sections = split_markdown_sections("texto corrido sem headings", page_number=3)
    assert [(s.title, s.text, s.page_number) for s in sections] == [
        (None, "texto corrido sem headings", 3)
    ]


# --- seleção de evidências ---------------------------------------------------


def _repo_com_pagina(markdown: str, policy_id: str = "POL-A", page_number: int = 1):
    repo = PolicyAnalysisRepository(":memory:")
    repo.upsert_markdown_page(policy_id, page_number, markdown, "fp-1")
    return repo


def test_selecao_por_field_code_rankeia_secao_relevante_primeiro():
    markdown = (
        "# Objeto\nCláusula sobre responsabilidade dos administradores.\n\n"
        "# Operações\nProcessos administrativos em curso.\n\n"
        "# Franquia contratada\n"
        "A franquia/deducível é de R$ 50.000,00 a cargo do segurado por sinistro, antes da cobertura.\n"
    )
    source = MarkdownSectionEvidenceSource(_repo_com_pagina(markdown), top_sections=2)

    evidences = source.get_evidences("POL-A", field_code="franquia")

    assert len(evidences) == 2  # teto `top_sections`
    assert evidences[0].section_name == "Franquia contratada"
    assert evidences[0].retrieval_score is not None and evidences[0].retrieval_score > 0
    assert evidences[0].retrieval_score > (evidences[1].retrieval_score or 0.0)


def test_sem_field_code_segue_ordem_de_leitura_com_teto():
    markdown = "\n".join(f"# Seção {i}\nCorpo {i}.\n" for i in range(25))
    source = MarkdownSectionEvidenceSource(_repo_com_pagina(markdown))

    evidences = source.get_evidences("POL-A")

    assert len(evidences) == 20  # teto de leitura
    assert [ev.section_name for ev in evidences[:3]] == ["Seção 0", "Seção 1", "Seção 2"]
    assert all(ev.retrieval_score is None for ev in evidences)


def test_corpo_longo_e_truncado_com_sufixo():
    source = MarkdownSectionEvidenceSource(_repo_com_pagina("# Longa\n" + "x" * 5000))

    evidence = source.get_evidences("POL-A")[0]

    assert evidence.quoted_text == "x" * MAX_QUOTED_CHARS + "…"


def test_ids_e_citacoes_vem_somente_do_markdown():
    pages = [
        (1, "# Produto\nApólice D&O SUSEP 12345.\n"),
        (2, "# Prazos\nNotificação em até 30 dias.\n"),
    ]
    repo = PolicyAnalysisRepository(":memory:")
    for page_number, markdown in pages:
        repo.upsert_markdown_page("POL-A", page_number, markdown, "fp-1")
    source = MarkdownSectionEvidenceSource(repo)

    evidences = source.get_evidences("POL-A")

    assert [ev.evidence_id for ev in evidences] == [
        "ev_md_POL-A:p1:s0",
        "ev_md_POL-A:p2:s0",
    ]
    for evidence in evidences:
        page_text = dict(pages)[evidence.page_number]
        assert evidence.quoted_text.rstrip("…") in page_text  # nunca inventa conteúdo
        assert evidence.policy_id == "POL-A"
        assert evidence.source_type == "PP_STRUCTURE"


# --- cache (repo durável + memória) ------------------------------------------


def test_cache_no_repo_evita_nova_extracao():
    facade = StubDocumentFacade(["# P1\nTexto um.\n", "# P2\nTexto dois.\n"])
    repo = PolicyAnalysisRepository(":memory:")
    source = MarkdownSectionEvidenceSource(repo, document_facade=facade)

    primeiras = source.get_evidences("POL-A")
    segundas = source.get_evidences("POL-A")
    # Nova instância sem fachada: o repo já tem o markdown, não há o que extrair.
    de_fora = MarkdownSectionEvidenceSource(repo).get_evidences("POL-A")

    assert facade.extract_calls == 1
    assert [ev.evidence_id for ev in primeiras] == [ev.evidence_id for ev in segundas]
    assert [ev.evidence_id for ev in primeiras] == [ev.evidence_id for ev in de_fora]
    assert facade.requested == ("POL-A", 200)
    fingerprints = [
        row[0] for row in repo._con.execute("SELECT fingerprint FROM document_markdown").fetchall()
    ]
    assert fingerprints == ["fp-stub-1", "fp-stub-1"]


def test_fingerprint_do_construtor_usado_quando_a_fachada_nao_tem():
    class FacadeSemFingerprint:
        def extract_markdown(self, file_path, max_pages):
            return ["# P1\nTexto.\n"]

    repo = PolicyAnalysisRepository(":memory:")
    source = MarkdownSectionEvidenceSource(
        repo, document_facade=FacadeSemFingerprint(), fingerprint="fp-ctor"
    )

    source.get_evidences("POL-A")

    fingerprints = [
        row[0] for row in repo._con.execute("SELECT fingerprint FROM document_markdown").fetchall()
    ]
    assert fingerprints == ["fp-ctor"]


def test_cache_em_memoria_nao_relê_o_repo():
    repo = CountingRepository()
    repo.upsert_markdown_page("POL-A", 1, "# P1\nTexto.\n", "fp-1")
    source = MarkdownSectionEvidenceSource(repo)

    source.get_evidences("POL-A")
    source.get_sections("POL-A")

    assert repo.reads == 1
