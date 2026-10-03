# Adendo: Documento complexo — estrutura, cláusulas e tabelas (NG-01)

> Identificador: `dev1-006-p2-documento-complexo`
> Data: `2026-10-01`
> Cenário: **greenfield** (âncora `prd.md` + specs em `sdd/`)
> Este adendo ponteia a extração para o estado atual do código. Não corrige nenhum artefato original.

## Vigência

Vigente desde 2026-10-01.

## Resumo da entrega

A feature implementou o **NG-01** do `document-processing` (o item "fase posterior"): reconhecimento de estrutura de documento para apólices D&O — seções e cláusulas viram `section_name` real nos chunks (OQ-03 resolvida), tabelas são serializadas no texto do chunk com marcador `[TABELA]`, e o pipeline ganha análise de layout (PP-StructureV3) com `source_type="PP_STRUCTURE"`, default em páginas sem texto nativo e flag `layout_mode="all"` para todas. Sem o motor disponível/falho, tudo degrada para heurística de texto (nunca `FAILED`). **15/15 ações concluídas** em `_reversa_forward/dev1-006-p2-documento-complexo/actions.md`; gate `T-1` verde 3× (323 passed, 4 skipped).

## Impacto por artefato da extração

| Artefato | Seção | Tipo de impacto | Delta |
|----------|-------|-----------------|-------|
| `_reversa_sdd/prd.md` | §5 (itens "fase posterior") | regra-alterada | "PP-StructureV3 (layout avançado)" e "processamento de tabelas" deixam de ser fase posterior: entregues como motor de layout opcional + tabela serializada — escopo "completo com PP-StructureV3" (decisão do humano, 2026-10-01) |
| `_reversa_sdd/sdd/document-processing.md` | §4 NG-01 | regra-alterada | NG-01 entregue (PP-StructureV3 + tabelas + cláusulas/`section_name`); ler o escopo efetivo em `_reversa_forward/dev1-006-p2-documento-complexo/requirements.md` |
| `_reversa_sdd/sdd/document-processing.md` | §14 OQ-03 | regra-alterada | **OQ-03 RESOLVIDA:** `section_name` = literal do marcador vigente (família fechada Cláusula/Artigo/Seção/Epígrafe, início de linha); `None` antes do primeiro marcador; atravessa páginas |
| `_reversa_sdd/sdd/document-processing.md` | §15 Decisões | regra-alterada | A decisão "PaddleOCR básico nesta versão; PP-Structure fora" foi **revertida**: o motor PP-StructureV3 entra opcional, com degradação graciosa quando ausente/falho |
| `_reversa_sdd/sdd/document-processing.md` | §6.1 RF-04 / §8 | regra-alterada | `build_chunk_metadata` preenche `section_name`; `process_document` ganha `layout_mode: "scanned"\|"all"` (default retrocompatível); chunking/limiares **inalterados** (RN-06 — sem caixa postal) |
| `_reversa_sdd/sdd/document-processing.md` | §10 Dependências | componente-novo | Novos: `domain/structure.py` (detecção de marcadores + serialização `[TABELA]`, puro) e `infrastructure/layout.py` (`PpStructureLayoutEngine`, import lazy, erro sanitizado T-2a) |
| `_reversa_sdd/sdd/shared-kernel-contracts.md` | RF-06 (`ChunkMetadata`) | delta-de-dados | `section_name` (opcional) e o literal `PP_STRUCTURE` passam a ser **preenchidos de fato**; contrato sem mudança de forma nem de versão (segue `1.1.0`) |

## Regras sob vigilância

W001–W006 — ver `_reversa_forward/dev1-006-p2-documento-complexo/regression-watch.md` (watch principal vazio no cenário greenfield; observações sem peso de regressão até a re-extração confirmar).

## Fontes

- `_reversa_forward/dev1-006-p2-documento-complexo/legacy-impact.md`
- `_reversa_forward/dev1-006-p2-documento-complexo/regression-watch.md`
- `_reversa_forward/dev1-006-p2-documento-complexo/requirements.md`
- `_reversa_forward/dev1-006-p2-documento-complexo/roadmap.md`
- `_reversa_forward/dev1-006-p2-documento-complexo/decisions.md`
- `_reversa_forward/dev1-006-p2-documento-complexo/progress.jsonl`
