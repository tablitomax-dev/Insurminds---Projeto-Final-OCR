# Requirements: Documento complexo — estrutura, cláusulas e tabelas (NG-01)

> Identificador: `dev1-006-p2-documento-complexo`
> Data: `2026-10-01`
> Pasta da extração reversa: `_reversa_sdd/`
> Confidência: 🟢 CONFIRMADO, 🟡 INFERIDO, 🔴 LACUNA / DÚVIDA

## 1. Resumo executivo

A feature entrega reconhecimento de **estrutura de documento** para apólices D&O: seções e cláusulas passam a virar `section_name` real nos chunks (hoje sempre `null` — OQ-03 do componente), tabelas são identificadas e preservadas de forma utilizável na evidência, e o pipeline ganha **análise de layout** (PP-StructureV3) para páginas escaneadas — o item "fase posterior" NG-01 do `document-processing`. Resolve a limitação do vertical slice em que evidências chegam sem seção/cláusula, forçando o Dev 2 e o analista a reconstruírem a posição no documento manualmente.

## 2. Contexto a partir do legado

| Fonte | Trecho relevante | Confidência |
|-------|------------------|-------------|
| `_reversa_sdd/sdd/document-processing.md#4 Non-Goals` | **NG-01:** PP-StructureV3, análise de tabelas e extração de cláusulas estruturadas ficaram para "fase posterior" (resumo §13) — esta feature é essa fase | 🟡 |
| `_reversa_sdd/sdd/document-processing.md#14 Open Questions` | **OQ-03:** `section_name` por heurística de marcadores ou `null` — adotou-se `null` no vertical slice; esta feature a resolve | 🟡 |
| `_reversa_sdd/sdd/shared-kernel-contracts.md#RF-06` | `ChunkMetadata` já prevê `section_name: str \| None` e `source_type` com literal `"PP_STRUCTURE"` além de `NATIVE_TEXT`/`PADDLEOCR` — preencher não muda forma de contrato | 🟡 |
| `_reversa_sdd/prd.md#§5` | Itens de fase posterior: "PP-StructureV3 (análise de layout avançada)" e "processamento de tabelas" | 🟡 |
| `_reversa_sdd/sdd/document-processing.md#15 Decisões` | Decisão registrada "PaddleOCR básico nesta versão; PP-Structure fora" — esta feature **reverte** essa decisão (por decisão do humano, 2026-10-01: escopo "completo com PP-StructureV3") | 🟡 |
| `_reversa_sdd/learning/plano-acao-dev1.md#fora-da-rodada` | "PP-StructureV3/`section_name` real (NG-01) — registrar como ação da próxima feature de documento complexo" | 🟢 |
| `_reversa_sdd/learning/aprendizados.md#§5.2` | Mudança de contrato só via caixa postal; chunking/limiares são contrato consumido pelo Dev 2 | 🟢 |
| `_reversa_sdd/learning/aprendizados.md#T-2a (higiene)` | Logs/métricas nunca carregam texto de apólice — só números e IDs | 🟢 |

## 3. Personas e cenários de uso

| Persona | Objetivo | Cenário-chave |
|---------|----------|---------------|
| Desenvolvedor 2 (consumidor via `public_api`) | Evidência ancorada em seção/cláusula | Consulta por `section_name` e monta `ExtractedFact` citando a cláusula de origem sem reconstruir a posição manualmente |
| Analista de cotação D&O | Localizar cláusula/tabela na evidência | A evidência exibida já mostra de qual cláusula/limite veio o trecho citado |
| Desenvolvedor (time) | Validar o pipeline de documento complexo sem rede | Testes determinísticos com motor de layout falso; integração real opt-in |

## 4. Regras de negócio novas ou alteradas

1. **RN-01:** `section_name` passa a ser preenchido quando detectável e continua `None` quando não detectável — campo opcional, retrocompatível com chunks já gravados. 🟢
   - Origem no legado: `_reversa_sdd/sdd/document-processing.md#RF-04` + `_reversa_sdd/sdd/shared-kernel-contracts.md#RF-06`
   - Tipo: alterada (resolve OQ-03)
2. **RN-02:** Cada chunk herda o marcador estrutural vigente mais recente entre **Cláusula, Artigo, Seção e Epígrafe** (escopo decidido na sessão de 2026-10-01); a detecção é determinística, **nunca inventa nome sem fonte no próprio documento** e grava o **literal do documento** como `section_name` (sem normalização). 🟢
   - Tipo: nova
3. **RN-03:** Tabelas identificadas são **serializadas dentro do texto do chunk** (linhas e colunas em ordem, precedidas pelo marcador `[TABELA]`) — decisão da sessão de 2026-10-01: corte de chunks preservado (RN-06), sem caixa postal ao Dev 2. 🟢
   - Tipo: nova
4. **RN-04:** Páginas processadas por análise de layout carregam `source_type="PP_STRUCTURE"` — literal já previsto no contrato de `ChunkMetadata`. Por padrão o motor roda **somente em páginas sem texto nativo suficiente** (mesmo critério do OCR); uma **flag** de processamento permite aplicá-lo a todas as páginas (decisão da sessão de 2026-10-01). 🟢
   - Origem no legado: `_reversa_sdd/sdd/shared-kernel-contracts.md#RF-06`
   - Tipo: nova (primeiro uso do literal)
5. **RN-05:** Sem o motor de layout disponível (dependência ausente ou ambiente sem suporte), o pipeline **degrada para detecção heurística de texto** e processa normalmente — a feature nunca derruba o fluxo existente nem vira falha de processamento. 🟡
   - Tipo: nova
6. **RN-06:** O corte de chunks e os limiares do componente **não mudam** nesta feature (zona de contrato consumido pelo Dev 2 — caixa postal do §5.2); a estrutura entra como metadado/conteúdo de chunk, não como novo algoritmo de corte. 🟢
   - Origem no legado: `_reversa_sdd/learning/aprendizados.md#§5.2`
   - Tipo: nova (restrição de escopo)
7. **RN-07:** Logs e métricas estruturados continuam sem texto de apólice (T-2a) — **incluindo nomes de seção/cláusula**; só números, IDs e tipos. 🟢
   - Origem no legado: `_reversa_sdd/learning/aprendizados.md#T-2a`
   - Tipo: nova (aplicação explícita à feature)

## 5. Requisitos Funcionais

| ID | Requisito | Prioridade | Critério de aceite | Confidência |
|----|-----------|------------|--------------------|-------------|
| RF-01 | Detectar seções/cláusulas e preencher `section_name` nos chunks | Must | Fixture com cláusulas/artigos/seções rotulados → processada, os chunks têm `section_name` igual ao **literal do marcador** vigente; chunk sem seção detectada → `section_name=None`; reprocessar produz os mesmos valores (idempotente) | 🟢 |
| RF-02 | Analisar layout de página com o motor PP-StructureV3 e atribuir `source_type="PP_STRUCTURE"` | Must | Página processada pelo motor de layout tem `source_type="PP_STRUCTURE"` em `ChunkMetadata`/evidência; por padrão só páginas sem texto nativo suficiente passam pelo motor, e a **flag** de processamento estende o motor a todas as páginas; teste determinístico com motor falso cobre os dois caminhos | 🟢 |
| RF-03 | Identificar tabelas e preservá-las na evidência de forma utilizável | Must | Fixture com tabela → a evidência recupera o conteúdo **serializado no chunk** com marcador `[TABELA]`, linhas/colunas legíveis e em ordem; os limites de corte (`CHUNK_MAX_CHARS`/`CHUNK_OVERLAP`) não mudam — a serialização entra como texto do chunk | 🟢 |
| RF-04 | Manter o filtro de retrieval por `section_name` funcionando com dados preenchidos | Must | `RetrievalQuery(section_name="...")` encontra evidências da seção e exclui as de outra seção (contrato existente, sem mudança de forma) | 🟢 |
| RF-05 | Degradar graciosamente sem o motor de layout | Must | Ambiente sem a dependência → processamento conclui com `section_name` por heurística de texto; nenhum `FAILED` causado pela ausência do motor | 🟡 |
| RF-06 | Preservar idempotência e rastreabilidade do componente (RF-09/RNF-04 atuais) | Should | Reexecutar o mesmo `document_id` mantém contagem de chunks e `section_name` estáveis; todo chunk continua rastreável a document+página | 🟢 |

## 6. Requisitos Não Funcionais

| Tipo | Requisito | Evidência ou justificativa | Confidência |
|------|-----------|----------------------------|-------------|
| Compatibilidade | Nenhuma mudança de forma em `ChunkMetadata`/`EvidenceRef`/`RetrievalQuery` — campos já existentes e opcionais; sem caixa postal nova | `_reversa_sdd/sdd/shared-kernel-contracts.md#RF-06` | 🟢 |
| Desempenho | PDF digital nativo não passa pelo motor de layout por padrão (a **flag** de layout é explícita e opt-in por processamento); a detecção heurística de seções é linear no texto da página, sem chamadas externas | Analogia com a decisão "texto nativo primeiro, OCR por página" (`document-processing.md#15`); risco R2 do PRD (custo/latência); decisão da sessão de 2026-10-01 | 🟢 |
| Segurança | Nenhum texto de apólice em log/métrica (T-2a), incluindo nomes de seção/cláusula e conteúdo de tabela | `_reversa_sdd/learning/aprendizados.md#T-2a`; PRD §6 | 🟢 |
| Isolamento de dependência | O motor de layout vive só em `infrastructure/**`, com import lazy e erro claro quando ausente (padrão dos adapters atuais) | RNF-06 do componente; `_reversa_sdd/sdd/document-processing.md#7` | 🟡 |
| Reprodutibilidade | Testes determinísticos com motor de layout falso; validação real apenas opt-in (`-m integration`), declarando o que é real e o que é fake | RN-03 da feature `dev1-005-p1-proveniencia`; aprendizado A-11 | 🟢 |

## 7. Critérios de Aceitação

```gherkin
Cenário: Chunk herda a cláusula vigente
  Dado um PDF digital com cláusulas rotuladas (ex.: "CLÁUSULA 5ª — FRANQUIA")
  Quando o documento for processado pelo pipeline
  Então os chunks posteriores ao rótulo têm section_name igual ao rótulo da cláusula
  E chunks anteriores ao primeiro rótulo têm section_name nulo

Cenário: Tabela preservada na evidência
  Dado um PDF com uma tabela de limites de cobertura
  Quando o documento for processado e a evidência for recuperada
  Então o conteúdo da tabela aparece serializado no texto do chunk com o marcador [TABELA]
  E as linhas e colunas estão legíveis e em ordem
  E os limites de corte de chunk continuam os mesmos do baseline

Cenário: Página escaneada analisada por layout
  Dado uma página escaneada sem texto nativo suficiente
  Quando o motor de layout estiver disponível
  Então os chunks da página carregam source_type "PP_STRUCTURE"

Cenário: Flag estende o layout a todas as páginas
  Dado um PDF digital com tabelas e o motor de layout disponível
  Quando o processamento for chamado com a flag de layout habilitada
  Então as páginas nativas também são analisadas e carregam source_type "PP_STRUCTURE"

Cenário: Consulta de evidência filtrada por seção
  Dado um documento processado com chunks de duas cláusulas diferentes
  Quando o Dev 2 consultar RetrievalQuery com section_name de uma delas
  Então só evidências daquela cláusula retornam, com section_name preenchido

Cenário: Degradação sem o motor de layout
  Dado um ambiente sem a dependência do motor de layout
  Quando o documento for processado
  Então o processamento conclui sem FAILED e section_name vem da heurística de texto

Cenário negativo: Página sem estrutura detectável
  Dado uma página com texto corrido, sem cláusulas, seções ou tabelas
  Quando o documento for processado
  Então os chunks têm section_name nulo e o documento é indexado normalmente
```

## 8. Prioridade MoSCoW

| Item | MoSCoW | Justificativa |
|------|--------|---------------|
| RF-01 (section_name/cláusulas) | Must | Resolve a OQ-03 e é o ganho central de rastreabilidade; sem ele a feature não existe |
| RF-02 (layout/PP_STRUCTURE) | Must | Escopo "completo" decidido pelo humano (2026-10-01); é o NG-01 nominal |
| RF-03 (tabelas) | Must | Item nominal do NG-01 e do PRD §5; tabela é onde vivem limites/coberturas |
| RF-04 (filtro por seção) | Must | Garante que o contrato existente ganha valor sem regressão para o Dev 2 |
| RF-05 (degradação graciosa) | Must | Ambientes sem o motor (Windows/CPU) são a realidade do time — feature não pode quebrar o fluxo |
| RF-06 (idempotência/rastreabilidade) | Should | Preserva garantias já entregues; verificação de regressão, não capacidade nova |

## 9. Esclarecimentos

### Sessão 2026-10-01

- **Q:** Como a tabela identificada deve entrar na evidência — serializada no texto do chunk, chunk dedicado por tabela ou só marcada?
  **R:** **Serializada dentro do texto do chunk**, com marcador `[TABELA]` e linhas/colunas em ordem. O corte de chunks fica preservado (RN-06) e não há caixa postal ao Dev 2.
- **Q:** Quando o motor de layout (PP-StructureV3) deve rodar — só páginas sem texto nativo, todas as páginas ou opt-in?
  **R:** **Default em páginas sem texto nativo suficiente** (mesmo critério do OCR), com **flag de processamento** para estender o motor a todas as páginas quando o operador quiser.
- **Q:** Qual formato do nome de seção gravado no chunk — literal, normalizado ou literal com busca insensível?
  **R:** **Literal do documento**, sem normalização — rastreabilidade fiel à fonte.
- **Q:** Quais marcadores a detecção de seções deve reconhecer — só cláusulas numeradas, cláusulas+artigos+seções ou heurística ampla?
  **R:** **Cláusula, Artigo, Seção e Epígrafe** — a estrutura típica de apólice D&O, sem heurística ampla de linhas em destaque.

## 10. Lacunas

- Nenhuma lacuna em aberto — as duas dúvidas da versão inicial (representação da tabela; regra de aplicação do layout) foram resolvidas na sessão de 2026-10-01 e registradas acima.

## 11. Histórico de alterações

| Data | Alteração | Autor |
|------|-----------|-------|
| 2026-10-01 | Versão inicial gerada por `/reversa-requirements` (argumento: "NG-01 completo com PP-StructureV3" — escopo decidido pelo humano pbena) | reversa |
| 2026-10-01 | `/reversa-clarify` (sessão com o humano pbena): tabela serializada com `[TABELA]`; layout default em páginas sem texto nativo + flag; `section_name` literal; marcadores Cláusula/Artigo/Seção/Epígrafe — RNs 02/03/04, RFs 01/02/03, Gherkin e RNF de desempenho atualizados | reversa |
| 2026-10-01 | Acerto de redação (no `/reversa-plan`): aceitação do RF-03 e Gherkin da tabela passam a exigir **limites de corte inalterados** em vez de "contagem de chunks igual" (impreciso — a serialização entra como texto do chunk) | reversa |
