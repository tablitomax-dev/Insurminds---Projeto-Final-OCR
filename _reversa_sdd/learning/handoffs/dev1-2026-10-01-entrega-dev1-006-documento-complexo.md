# Handoff Dev 1 → Dev 2 — feature `dev1-006-p2-documento-complexo` (NG-01, 2026-10-01)

> **Autor:** Dev 1 (pbena + assistente) · **Destinatário:** Dev 2 (leitura do assistente de IA)
> **Branch:** `feat/dev1-006-p2-documento-complexo` (base: `main`)
> **Ciclo:** Reversa forward completo — `/reversa-requirements` → `/reversa-clarify` → `/reversa-plan` → `/reversa-to-do` → `/reversa-coding` → `/reversa-sync` (adendo `_reversa_sdd/addenda/dev1-006-p2-documento-complexo.md`)
> **Gate `T-1`:** verde 3× consecutivas — `ruff` All checks passed · `mypy` Success (68 arquivos) · `pytest` **323 passed, 4 skipped** (20 testes novos).

## 1. Escopo: o que mudou (quadrado do Dev 1, `document_processing`)

Entrega do **NG-01** (o item "fase posterior" do `document-processing.md#4`), escopo "completo com PP-StructureV3" decidido pelo humano (2026-10-01):

- `domain/structure.py` (novo, puro): detecção de marcadores de seção — família fechada **Cláusula/Artigo/Seção/Epígrafe**, só em início de linha, **literal do documento** (sem normalização) + serialização de tabela `[TABELA]` (TSV → `célula | célula`).
- `infrastructure/layout.py` (novo): `PpStructureLayoutEngine` (PP-StructureV3) com import lazy, normalização defensiva do SDK e erro tipado sanitizado (`LayoutError`, T-2a).
- `application/ports.py`: `LayoutRegion`, `LayoutError`, `LayoutEngine` (porta `analyze_page(file_path, page_number)`, espelhando `OcrEngine`).
- `application/service.py`: seção vigente atravessa páginas (chunks herdam o literal); caminho de layout com `layout_mode="scanned"` (default) / `"all"`; `source_type="PP_STRUCTURE"` em páginas analisadas; **degradação RN-05** — motor ausente/falho nunca vira `FAILED`.
- `domain/processing.py`: `build_chunk_metadata(..., section_name=None)` — default inalterado.
- `public_api.py`: `process_document(..., layout_mode="scanned")` retrocompatível + wiring opcional do motor.

## 2. O que isso significa para o seu quadrado (`policy_analysis`)

1. **`EvidenceRef.section_name` passa a vir preenchido** (literal da cláusula/artigo/seção) — o `llm_agent.py` de vocês já renderiza `" seção {ev.section_name}"` quando existe; agora o dado existe de verdade.
2. **`RetrievalQuery.section_name` ganha valor de fato** — o filtro por seção (que já existia no contrato) passa a encontrar evidências reais.
3. **`quoted_text` pode conter o marcador `[TABELA]`** seguido da tabela serializada (`limite | 1000000`) — a ancoragem literal (`domain/anchoring.py`) continua funcionando (o texto é literal do chunk); só fiquem cientes de que tabelas agora chegam estruturadas em texto.
4. **`source_type="PP_STRUCTURE"`** (literal previsto no contrato desde a Fase 0) começa a circular — quem lê `source_type` deve tratá-lo como terceiro valor possível.

## 3. Testes (novos, verdes)

- `tests/modules/document_processing/test_structure.py` (10): literal preservado; âncora em início de linha; família fechada; seção vigente entre peças/páginas; marcador no início da peça; serialização `[TABELA]`; tabela vazia não vira marcador órfão; composição em ordem de leitura.
- `tests/modules/document_processing/test_domain.py` (+2): `section_name` literal no metadado; default `None`.
- `tests/modules/document_processing/test_service.py` (+8): literal herdado pelos chunks; `None` antes do 1º marcador + estado entre páginas; **filtro por seção no retrieval (RF-04)**; `PP_STRUCTURE` + tabela serializada; flag `"all"`; default não analisa nativa; **degradação sem `FAILED`**; **anti-vazamento T-2a** (literal de seção/tabela nunca em log).

## 4. Passos anti-conflito de merge

- Nenhuma mudança de contrato: `shared_kernel/contracts.py` **intocado**; `CONTRACTS_VERSION` segue `1.1.0` — **nenhuma caixa postal** (RN-06).
- Chunking e limiares inalterados (`CHUNK_MAX_CHARS=800`, `CHUNK_OVERLAP=100`, `MIN_NATIVE_TEXT_CHARS=40`) — o corte que vocês consomem não mudou; a tabela entra como texto do chunk.
- Assinaturas retrocompatíveis: `build_chunk_metadata` e `process_document` só ganharam parâmetros com default.
- Branch do `D1-P2-1` (`feat/d1-p2-1-metrica-embedding`, métrica de embeddings) é **independente** — arquivos distintos, zero conflito entre os dois PRs.

## 5. Relatório de áreas compartilhadas tocadas

| Zona | Ação |
|------|------|
| `src/shared_kernel/**` | **NÃO TOCADO.** |
| `src/modules/policy_analysis/**`, `src/ui/**` | **NÃO TOCADOS.** |
| `_reversa_sdd/addenda/dev1-006-p2-documento-complexo.md` | Novo adendo do `/reversa-sync` (ponte greenfield: PRD §5, NG-01, OQ-03, decisão PP-Structure, RF-04). |
| `_reversa_forward/dev1-006-p2-documento-complexo/` | Feature completa (requirements/roadmap/investigation/data-delta/onboarding/actions/decisions/regression-watch/legacy-impact/progress.jsonl). |
| `.reversa/active-requirements.json` | Estado do Reversa aponta para a feature (o anterior estava corrompido — dois objetos colados — e foi tratado como ausente pelo skill). |

## 6. Decisões do humano registradas nesta entrega

- **Escopo "completo com PP-StructureV3"** (2026-10-01): NG-01 inteiro, revertendo a decisão "PP-Structure fora" do spec.
- **Clarify (4 respostas):** tabela serializada no chunk com `[TABELA]`; layout default em páginas sem texto nativo + flag `"all"`; `section_name` **literal**; marcadores **Cláusula/Artigo/Seção/Epígrafe** (sem heurística ampla).
- **Headings do layout não criam seção** (consequência da família fechada — registrado em `decisions.md` E-02).

## 7. Observações de review (não bloqueantes)

1. A sobreposição de chunks (`CHUNK_OVERLAP=100`) pode cortar uma tabela entre dois chunks — aceito (E-07): o conteúdo continua recuperável em ambos.
2. A normalização do SDK do PP-StructureV3 é defensiva (3 formatos aceitos, E-06); o opt-in `-m integration` valida contra o SDK real quando houver Paddle no ambiente.
