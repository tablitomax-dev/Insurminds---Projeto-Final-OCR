# Legacy Impact: Documento complexo — estrutura, cláusulas e tabelas (NG-01)

> Identificador: `dev1-006-p2-documento-complexo`
> Data: `2026-10-01`
> Âncora de contexto: **greenfield** (`_reversa_sdd/prd.md` + specs em `_reversa_sdd/sdd/`) — sem `architecture.md`/`domain.md`.
> Política de edição no momento da execução: `allowLegacyEdits: true`, `allowedPaths: ["src/**", "tests/**", "pyproject.toml", "requirements.txt", ".gitignore", "CLAUDE.md"]` — todos os arquivos tocados casam com `src/**`/`tests/**`.
> Adaptação: a feature é greenfield na ancoragem, mas altera código já implementado — os tipos de impacto abaixo classificam de fato (`componente-novo` × `regra-alterada`) em vez de marcar tudo como novo.

## Tabela de impacto

| Arquivo afetado | Componente (specs SDD) | Tipo | Severidade | Justificativa |
|-----------------|------------------------|------|------------|---------------|
| `src/modules/document_processing/domain/structure.py` | `document-processing` (`sdd/document-processing.md#8`) | componente-novo | MEDIUM | núcleo de estrutura: marcadores de seção (RN-02) + serialização de tabela (RN-03) |
| `src/modules/document_processing/infrastructure/layout.py` | `document-processing` (`#10`) | componente-novo | MEDIUM | adapter PP-StructureV3 lazy + normalização defensiva (E-06) |
| `src/modules/document_processing/application/ports.py` | `document-processing` (`#8`) | regra-alterada | LOW | aditivo: `LayoutRegion`, `LayoutError`, `LayoutEngine` |
| `src/modules/document_processing/domain/processing.py` | `document-processing` (`#6.1 RF-04`) | regra-alterada | LOW | `build_chunk_metadata` aceita `section_name` (default `None` inalterado) |
| `src/modules/document_processing/application/service.py` | `document-processing` (`#6.2`) | regra-alterada | MEDIUM | seção vigente entre páginas + caminho de layout (`layout_mode`) + degradação RN-05 |
| `src/modules/document_processing/public_api.py` | `document-processing` (`#8`) | regra-alterada | LOW | `process_document` ganha `layout_mode="scanned"` (retrocompatível) + wiring opcional do motor |
| `tests/fakes/document_processing.py`, `tests/fakes/__init__.py` | testes | componente-novo | LOW | `FakeLayoutEngine` determinístico |
| `tests/modules/document_processing/test_structure.py` | testes | componente-novo | LOW | testes do núcleo puro (T003/T004) |
| `tests/modules/document_processing/test_domain.py` | testes | regra-alterada | LOW | testes de `section_name` no metadado (T005) |
| `tests/modules/document_processing/test_service.py` | testes | regra-alterada | LOW | cenários Gherkin de seção/layout + anti-vazamento T-2a (T012–T014) |

## Diff conceitual por componente

- **document-processing (domínio):** nasce o módulo puro `structure.py` (família fechada de marcadores com literal preservado; estado "seção vigente" entre peças/páginas; serialização `[TABELA]` a partir de TSV). `processing.py` ganha um parâmetro opcional — nenhum comportamento anterior muda.
- **document-processing (aplicação):** `DocumentProcessingService` passa a rastrear a seção vigente durante a paginação/chunking e a consultar o motor de layout quando aplicável (`"scanned"` = só páginas sem texto nativo; `"all"` = todas), compondo o texto da página em ordem de leitura e serializando tabelas. Falha/ausência do motor degrada para o texto extraído (RN-05) — nunca `FAILED`.
- **document-processing (infraestrutura):** adapter `PpStructureLayoutEngine` com import lazy e erro tipado sanitizado (T-2a), espelhando `PaddleOcrEngine`/`GeminiEmbedder`.
- **shared_kernel:** **intocado** — `section_name` (opcional) e o literal `PP_STRUCTURE` já existiam no contrato (v1.1.0); nenhuma caixa postal necessária.

## Preservadas

Sem `domain.md` com regras 🟢 (âncora greenfield). Preservações verificáveis: contratos do `shared_kernel` sem mudança de forma/versão; chunking (`CHUNK_MAX_CHARS=800`, `CHUNK_OVERLAP=100`) e limiares (`MIN_NATIVE_TEXT_CHARS=40`, `OCR_ILLEGIBLE_CONFIDENCE=0.5`) inalterados (RN-06); idempotência RF-09 e rastreabilidade RNF-04 intactas (cobertas por testes existentes que seguem verdes).

## Modificadas

- Decisão registrada em `_reversa_sdd/sdd/document-processing.md#15` ("PaddleOCR básico nesta versão; PP-Structure fora") — **revertida** por decisão do humano (2026-10-01, escopo "completo com PP-StructureV3"): PP-StructureV3 entra como motor de layout opcional. Registrada em `regression-watch.md` (W006).
