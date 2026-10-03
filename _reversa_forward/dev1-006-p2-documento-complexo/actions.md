# Actions: Documento complexo — estrutura, cláusulas e tabelas (NG-01)

> Identificador: `dev1-006-p2-documento-complexo`
> Data: `2026-10-01`
> Roadmap: `_reversa_forward/dev1-006-p2-documento-complexo/roadmap.md`
> Convenções: IDs `T001`+ estáveis (nunca reciclados); ação atômica = um turno de agente; teste primeiro na lógica determinística (A-04); gate `T-1` antes de todo PR (ritual do plano Dev 1 §5).

## Resumo

| Métrica | Valor |
|---------|-------|
| Total de ações | 15 |
| Paralelizáveis (`[//]`) | 7 (`T001`, `T002`, `T003`, `T005`, `T008`, `T012`, `T014`) |
| Maior cadeia de dependência | 6 (`T003` → `T006` → `T009` → `T010` → `T013` → `T015`) |

## Fase 1, Preparação

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| T001 | Porta de layout em `application/ports.py`: dataclass `LayoutRegion(kind: Literal["heading","table","text"], text, order)` + exceção `LayoutError` (mensagem sanitizada T-2a) + contrato duck-typed do engine (`analyze(page_text) -> list[LayoutRegion]`) | - | `[//]` | `src/modules/document_processing/application/ports.py` | 🟢 | `[X]` |
| T002 | `build_chunk_metadata` ganha parâmetro `section_name: str \| None = None` (default preserva comportamento atual; docstring deixa de citar OQ-03) | - | `[//]` | `src/modules/document_processing/domain/processing.py` | 🟢 | `[X]` |

## Fase 2, Testes

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| T003 | Testes do detector de seções (TDD do núcleo): literal preservado; marcador só no início de linha; família fechada Cláusula/Artigo/Seção/Epígrafe (rejeita "Seção" em texto corrido); marcador vigente atravessa páginas; `None` antes do primeiro marcador | - | `[//]` | `tests/modules/document_processing/test_structure.py` | 🟢 | `[X]` |
| T004 | Testes da serialização de tabela: marcador `[TABELA]` + linhas/colunas em ordem; região não-tabela ignorada; tabela vazia não vira marcador órfão | - | - | `tests/modules/document_processing/test_structure.py` | 🟢 | `[X]` |
| T005 | Teste de `build_chunk_metadata` com `section_name` (literal vai ao metadado; default `None` inalterado) | T002 | `[//]` | `tests/modules/document_processing/test_processing.py` | 🟢 | `[X]` |

## Fase 3, Núcleo

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| T006 | `domain/structure.py`: `detect_section_markers(text) -> list[SectionMarker]` (regex da família fechada, âncora em início de linha, captura do literal) + `current_section(state, text)` — máquina de estado "marcador vigente" que atravessa páginas (puro, stdlib) | T003 | - | `src/modules/document_processing/domain/structure.py` | 🟢 | `[X]` |
| T007 | `domain/structure.py`: `serialize_table(regions) -> str` — serializa regiões `table` em texto com marcador `[TABELA]` e colunas separadas, em ordem de leitura (puro) | T004 | - | `src/modules/document_processing/domain/structure.py` | 🟢 | `[X]` |

## Fase 4, Integração

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| T008 | `infrastructure/layout.py::PpStructureLayoutEngine`: import lazy do Paddle (padrão de `extractors.py`), normaliza saída do SDK em `LayoutRegion`, erro externo vira `LayoutError` com só o tipo (T-2a) + `FakeLayoutEngine` determinístico em `tests/fakes/` | T001 | `[//]` | `src/modules/document_processing/infrastructure/layout.py`, `tests/fakes/document_processing.py` | 🟢 | `[X]` |
| T009 | `application/service.py`: estado do marcador vigente entre páginas + `section_name` (literal) em todo `build_chunk_metadata` — heurística sempre ativa, independente do motor | T006 | - | `src/modules/document_processing/application/service.py` | 🟢 | `[X]` |
| T010 | `application/service.py`: caminho de layout — `layout_mode` `"scanned"` (default, páginas sem texto nativo) / `"all"`; página analisada → tabela serializada no texto do chunk + `source_type="PP_STRUCTURE"`; motor ausente/falho degrada para texto puro sem `FAILED` (RN-05) | T007, T008, T009 | - | `src/modules/document_processing/application/service.py` | 🟢 | `[X]` |
| T011 | `public_api.py`: `process_document(..., layout_mode: Literal["scanned","all"] = "scanned")` com repasse ao serviço (kwarg default é retrocompatível) | T010 | - | `src/modules/document_processing/public_api.py` | 🟢 | `[X]` |
| T012 | Testes de serviço — cenários de seção: chunk herda literal do marcador vigente; chunk antes do 1º marcador → `None`; `RetrievalQuery(section_name=...)` filtra por seção (RF-04) | T009 | `[//]` | `tests/modules/document_processing/test_service.py` | 🟢 | `[X]` |
| T013 | Testes de serviço — cenários de layout/tabela: `source_type="PP_STRUCTURE"` na página analisada; flag `"all"` estende às nativas; tabela serializada com `[TABELA]`; degradação sem motor conclui sem `FAILED` | T010 | - | `tests/modules/document_processing/test_service.py` | 🟢 | `[X]` |

## Fase 5, Polimento

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| T014 | Teste anti-vazamento (T-2a/RN-07): nenhum log/métrica do fluxo novo carrega `section_name`, texto de tabela ou trecho de apólice — espelha `test_metrica_de_embedding_nunca_carrega_texto_de_aplice` | T010 | `[//]` | `tests/modules/document_processing/test_service.py` | 🟢 | `[X]` |
| T015 | Registro de decisões (A-10: literal sem normalização; serialização `[TABELA]` no chunk; sobreposição pode cortar tabela — aceito; degradação RN-05) + `regression-watch.md` com os cenários sob vigilância | T012, T013 | - | `_reversa_forward/dev1-006-p2-documento-complexo/` | 🟢 | `[X]` |

## Checklist de encerramento (ritual — plano Dev 1 §5)

- [X] Granularidade registrada nesta tabela (feito no cabeçalho).
- [X] Teste primeiro na lógica determinística (A-04): fases 2 antes/conjunta à 3.
- [X] Gate `T-1` verde antes do PR (`ruff` + `mypy` + `pytest`) — ver Notas de execução.
- [X] Nenhuma mudança de contrato/caixa postal (RN-06 confirmada — `shared_kernel` intocado).
- [X] Handoff §5.6 publicado em `_reversa_sdd/learning/handoffs/` ao concluir (`dev1-2026-10-01-entrega-dev1-006-documento-complexo.md`, no commit da entrega).

## Notas de execução

<!-- Reservado para /reversa-coding registrar avisos ou observações que surgiram durante a execução. -->

- **T005 executado em `tests/modules/document_processing/test_domain.py`** — o alvo real dos testes de domínio (o `test_processing.py` da tabela não existe; corrigido aqui como nota, sem reciclar IDs).
- **TDD pegou um bug real:** o regex do detector usava `^` sem `re.MULTILINE` — só ancorava no início da string, não de cada linha. Corrigido para `re.IGNORECASE | re.MULTILINE` quando os testes do T003 falharam (3 vermelhos → verdes).
- **Decisões de execução (A-10)** registradas em `decisions.md` (E-01..E-07), incluindo: headings do layout não criam seção (família fechada do clarify manda); `LayoutRegion` em `application/ports.py` (correção refletida no `data-delta.md`); degradação do motor com `except Exception` (RN-05).
- **Assinatura da porta:** o contrato do motor ficou `analyze_page(file_path, page_number) -> list[LayoutRegion]` (espelhando `OcrEngine`) em vez de `analyze(page_text)` — o motor precisa da página renderizada, como o OCR.
- **Gate T-1:** verificado ao fim da rodada (resultado no relatório do `/reversa-coding`).

## Histórico de alterações

| Data | Alteração | Autor |
|------|-----------|-------|
| 2026-10-01 | Versão inicial gerada por `/reversa-to-do` | reversa |
| 2026-10-01 | `/reversa-coding`: 15/15 ações concluídas (`[X]`); notas de execução preenchidas | reversa |
