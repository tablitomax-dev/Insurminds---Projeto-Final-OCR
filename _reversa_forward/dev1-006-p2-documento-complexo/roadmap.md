# Roadmap: Documento complexo — estrutura, cláusulas e tabelas (NG-01)

> Identificador: `dev1-006-p2-documento-complexo`
> Data: `2026-10-01`
> Requirements: `_reversa_forward/dev1-006-p2-documento-complexo/requirements.md`
> Confidência: 🟢 CONFIRMADO, 🟡 INFERIDO, 🔴 LACUNA

## 1. Resumo da abordagem

A feature entra como **delta aditivo** no pipeline documental: um módulo puro novo de estrutura (`domain/structure.py`) detecta marcadores Cláusula/Artigo/Seção/Epígrafe e mantém o "marcador vigente" atravessando páginas; `build_chunk_metadata` passa a receber esse literal em vez de fixar `None`. Um adapter novo (`infrastructure/layout.py`) encapsula o PP-StructureV3 com import lazy e saída normalizada (regiões heading/table/text), usado por padrão só em páginas sem texto nativo suficiente e estensível a todas as páginas por flag (`layout_mode="all"`). Tabelas vindas do layout são serializadas como texto do chunk com marcador `[TABELA]` — o chunker (`chunk_text`, `CHUNK_MAX_CHARS=800`, `CHUNK_OVERLAP=100`) **não muda** (RN-06). Sem o motor disponível, tudo degrada para a heurística pura de texto e o fluxo existente segue intacto (RN-05). Nenhum contrato do `shared_kernel` muda de forma.

## 2. Princípios aplicados

`.reversa/principles.md` ausente neste projeto — nenhum princípio ativo para verificar. Os princípios operacionais vigentes são as regras do `_reversa_sdd/learning/aprendizados.md` §5, respeitadas por construção (RN-06 sem caixa postal; T-2a em logs; dependências externas só em `infrastructure/**`).

| Princípio | Como a feature se relaciona | Status |
|-----------|------------------------------|--------|
| n/a (sem `principles.md`) | — | — |

## 3. Decisões técnicas

| ID | Decisão | Justificativa | Alternativas descartadas | Confidência |
|----|---------|---------------|--------------------------|-------------|
| D-01 | Detecção de seções em **domínio puro novo** `domain/structure.py`: regex de família fechada de marcadores (Cláusula/Artigo/Seção/Epígrafe), só no início de linha, com máquina de estado "marcador vigente" entre páginas | Determinístico/testável sem dependências (RNF-06); literal do documento preservado (clarify 2026-10-01) | heurística ampla de linhas em destaque (falsos positivos); detecção via LLM (custo, T-2a) | 🟢 |
| D-02 | Tabelas serializadas **como texto do chunk** com marcador `[TABELA]`, vindo das regiões do motor de layout | Decisão do clarify (2026-10-01): corte preservado, sem caixa postal ao Dev 2 | chunk dedicado por tabela (mudaria corte/contagem — zona de contrato); só marcar sem estruturar (não atende RF-03) | 🟢 |
| D-03 | `build_chunk_metadata` ganha parâmetro `section_name: str \| None = None` | Assinatura interna do domínio, não contrato; default `None` preserva comportamento atual | novo construtor/metadata subclass (complexidade sem valor) | 🟢 |
| D-04 | Flag de processamento `layout_mode: Literal["scanned", "all"] = "scanned"` propagada de `public_api.process_document` → `DocumentProcessingService` | Decisão do clarify: default econômico + liberdade do operador; kwarg default é retrocompatível | booleano `layout_all_pages` (menos autoexplicativo); config global (oculta decisão por documento) | 🟢 |
| D-05 | Adapter `infrastructure/layout.py::PpStructureLayoutEngine` com import lazy + saída normalizada `LayoutRegion(kind, text, order)` e fakes determinísticos nos testes | Mesmo padrão de `extractors.py`/`indexing.py`; core importável sem Paddle (arquitetura vigiada por teste) | import direto do Paddle no domínio (viola RNF-06); lib de tabelas dedicada (dependência nova pesada) | 🟢 |
| D-06 | `source_type="PP_STRUCTURE"` apenas para páginas analisadas pelo motor; a heurística de seções roda em **todas** as páginas (independente do motor) | Literal já previsto no contrato (shared-kernel RF-06); seção é texto, não depende de layout | marcar `PP_STRUCTURE` em página sem motor (mentiria a fonte) | 🟢 |
| D-07 | Motor ausente/falho → degradação silenciosa para heurística de texto + tabelas como texto corrido; nunca `FAILED` | RN-05/RF-05; o ambiente Windows/CPU do time tem limitação conhecida do Paddle | falhar o processamento (derruba fluxo existente); retry do motor (custo sem garantia) | 🟢 |

## 4. Premissas

Nenhuma — os 2 marcadores `[DÚVIDA]` do requirements foram resolvidos na sessão de `/reversa-clarify` (2026-10-01) e viraram RN-02/03/04. As decisões da sessão estão em `requirements.md#9 Esclarecimentos`.

| Premissa | Origem (`requirements.md` seção) | Risco se errada |
|----------|----------------------------------|-----------------|
| n/a | — | — |

## 5. Delta arquitetural

| Componente | Arquivo de origem no legado | Tipo de mudança | Resumo |
|------------|------------------------------|-----------------|--------|
| `domain/structure.py` (novo) | `_reversa_sdd/sdd/document-processing.md#8` | componente-novo | Marcadores de seção + estado vigente + serialização de tabela (puro, stdlib) |
| `domain/processing.py` | `_reversa_sdd/sdd/document-processing.md#6.1 RF-04` | regra-alterada | `build_chunk_metadata(..., section_name=None)` — preenche o campo que hoje fixa `None` (OQ-03) |
| `application/service.py` | `_reversa_sdd/sdd/document-processing.md#6.2` | regra-alterada | Orquestra `layout_mode`, estado de seção entre páginas, serialização de tabela no texto e `source_type="PP_STRUCTURE"` |
| `infrastructure/layout.py` (novo) | `_reversa_sdd/sdd/document-processing.md#10` | componente-novo | Adapter PP-StructureV3 lazy (import na construção), saída `LayoutRegion`, erro tipado `LayoutError` sanitizado (T-2a) |
| `public_api.py` | `_reversa_sdd/sdd/document-processing.md#8` | regra-alterada | `process_document` ganha kwarg `layout_mode="scanned"` (retrocompatível) |
| `infrastructure/indexing.py` | `_reversa_sdd/sdd/shared-kernel-contracts.md#RF-06` | sem mudança | Payload já serializa `section_name` — só passa a receber valores |
| `shared_kernel/contracts.py` | `_reversa_sdd/sdd/shared-kernel-contracts.md#RF-06` | sem mudança | `section_name` opcional e literal `PP_STRUCTURE` já existem — **nenhuma caixa postal** (RN-06/aprendizados §5.2) |

## 6. Delta no modelo de dados

- Resumo das mudanças: **nenhum campo novo**. `ChunkMetadata.section_name` passa de `None` fixo a preenchido (literal do marcador); `source_type` ganha primeiro uso do literal `PP_STRUCTURE`; payload do Qdrant passa a ter `section_name` não-nulo nos chunks novos. Sem migração — chunks antigos continuam válidos e ganham `section_name` ao reprocessar (idempotência RF-09).
- Detalhe completo em: `_reversa_forward/dev1-006-p2-documento-complexo/data-delta.md`

## 7. Delta de contratos externos

| Contrato | Tipo | Arquivo de detalhe |
|----------|------|--------------------|
| nenhum | — | diretório `interfaces/` omitido (feature não toca HTTP/fila/gRPC/GraphQL; `shared_kernel` sem mudança de forma) |

## 8. Plano de migração

n/a — mudança retrocompatível (campos opcionais já existentes). Recomendação opcional: reprocessar apólices de teste para popular `section_name` (upsert idempotente já cobre).

## 9. Riscos e mitigações

| Risco | Impacto | Probabilidade | Mitigação |
|-------|---------|---------------|-----------|
| Paddle/PP-StructureV3 indisponível ou instável no Windows/CPU (bug PIR/oneDNN já documentado nos testes de OCR) | alto | médio | D-07: degradação para heurística pura; testes com motor fake; validação real opt-in (`-m integration`) com o mesmo padrão de skip do OCR |
| Falso positivo de marcador de seção (ex.: "Seção" em texto corrido) | médio | baixo | Família fechada de marcadores + âncora no início de linha; literal nunca é inventado (RN-02); caso limite vira `None`, não quebra |
| Latência com `layout_mode="all"` em PDFs longos | médio | médio | Default `"scanned"` (clarify); flag é decisão explícita do operador; métrica de embedding/latência já observável (D1-P2-1) |
| Serialização de tabela altera distribuição de tamanho dos chunks | baixo | médio | Aceito e documentado (acerto de redação do RF-03): limites de corte inalterados; conteúdo do chunk é a superfície de retrieval e melhora com tabela estruturada |
| Nome de seção literal em logs/métricas vaza texto de apólice | alto | baixo | RN-07: T-2a explícito — logs/métricas só números/IDs; teste anti-vazamento espelhando o do D1-P2-1 |

## 10. Critério de pronto

- [ ] Todas as ações do `actions.md` marcadas `[X]`
- [ ] Gate `T-1` verde 3× (`ruff` + `mypy` + `pytest`)
- [ ] Cenários Gherkin do requirements cobertos por testes determinísticos (com motor de layout fake)
- [ ] `regression-watch.md` gerado
- [ ] Handoff §5.6 publicado em `_reversa_sdd/learning/handoffs/` ao concluir

## 11. Histórico de alterações

| Data | Alteração | Autor |
|------|-----------|-------|
| 2026-10-01 | Versão inicial gerada por `/reversa-plan` (delta sobre `document-processing.md`; sem `[DÚVIDA]` pendentes) | reversa |
