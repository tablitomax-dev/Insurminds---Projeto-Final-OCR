# Requirements: Vertical Slice E2E — PDF até comparação e tela

> Identificador: `dev1-001-vertical-slice-e2e`
> Data: `2026-09-26`
> Pasta da extração reversa: `_reversa_sdd/`
> Confidência: 🟢 CONFIRMADO, 🟡 INFERIDO, 🔴 LACUNA / DÚVIDA

## 1. Resumo executivo

Entrega o primeiro corte vertical completo da plataforma de comparação de apólices D&O: um PDF de apólice entra, vira evidências recuperáveis, depois fatos estruturados, uma comparação determinística entre 2 apólices e uma tela Streamlit mínima para o analista visualizar o resultado. Resolve o problema central do PRD (análise manual de apólices demorada e sujeita a erro) provando a jornada fim a fim com 1 campo extraído e 1 comparação, antes de escalar para o catálogo completo.

## 2. Contexto a partir do legado

| Fonte | Trecho relevante | Confidência |
|-------|------------------|-------------|
| `_reversa_sdd/prd.md#4. Escopo (in)` | Jornada de 7 passos: ingestão → OCR → chunking → retrieval → extração → comparação → explicação/tela | 🟢 |
| `_reversa_sdd/sdd/document-processing.md#6.1` | RF-01..RF-09 do módulo documental (validação, texto nativo, OCR, chunking, embeddings/Qdrant, status, retrieval, fachada, idempotência) | 🟢 |
| `_reversa_sdd/sdd/document-processing.md#6.2` | Fluxo principal do vertical slice (1 página → 1 documento fixture → índice real) | 🟡 |
| `_reversa_sdd/sdd/policy-analysis.md#6.1` | RF-01..RF-09 do módulo de análise (catálogo, extração por agente, revisão humana, DuckDB, comparação determinística, explicação, export, validação de saída LLM) | 🟢 |
| `_reversa_sdd/sdd/policy-analysis.md#8. Design e Interface` | Fachada pública `PolicyAnalysisFacade` (extract_field, get_facts, compare_policies, explain_difference, export_comparison) | 🟡 |
| `_reversa_sdd/sdd/shared-kernel-contracts.md#6.1` | Contratos versionados 1.0.0: EvidenceRef, ChunkMetadata, RetrievalQuery/Result, ExtractionRequest, ExtractedFact, ProcessingStatus (já implementados em `src/shared_kernel`) | 🟢 |
| `_reversa_sdd/sdd/evaluation.md#4. Non-Goals` | Avaliação automatizada (LLM-as-judge) é fase posterior — fora deste slice | 🟢 |
| `_reversa_sdd/prd.md#6. Restrições` | Sigilo de apólice; envio de conteúdo ao Gemini é decisão explícita registrada; prazo 3 meses com viés de custo baixo | 🟢 |

## 3. Personas e cenários de uso

| Persona | Objetivo | Cenário-chave |
|---------|----------|---------------|
| Analista de cotação D&O (`_reversa_sdd/personas.md#Persona 1`) | Comparar 2 apólices com segurança e agilidade | O analista carrega 2 PDFs, vê a comparação campo a campo com evidência de página/trecho e exporta o resumo para a defesa |

## 4. Regras de negócio novas ou alteradas

1. **RN-01:** Comparação é sempre determinística: o LLM extrai e explica, jamais compara. Numérico: maior/menor/igual; texto: igual/ausente; ausente: sinalizado como diferença por omissão. 🟢
   - Origem no legado: `_reversa_sdd/sdd/policy-analysis.md#6.1` RF-06; `_reversa_sdd/prd.md#5. Não-objetivos`
   - Tipo: nova
2. **RN-02:** Todo fato exige rastreabilidade: `ExtractedFact` com `status != "NOT_FOUND"` só existe com `evidence_ids` não vazios (EC-05 do contrato, validado por `model_validator`). 🟢
   - Origem no legado: `_reversa_sdd/sdd/shared-kernel-contracts.md#6.1`
   - Tipo: nova
3. **RN-03:** Identificadores compartilhados entre módulos: `document_id`/`chunk_id`/`policy_id` do Qdrant são os mesmos do DuckDB e dos contratos (0 divergências). 🟢
   - Origem no legado: `_reversa_sdd/sdd/document-processing.md#6.1` RF-05; `_reversa_sdd/sdd/policy-analysis.md#6.1` RF-05
   - Tipo: nova
4. **RN-04:** Idempotência: reprocessar o mesmo `document_id` substitui chunks e fatos sem duplicar no índice nem no banco. 🟢
   - Origem no legado: `_reversa_sdd/sdd/document-processing.md#6.1` RF-09
   - Tipo: nova
5. **RN-05:** Saída de LLM nunca entra sem validação contra o schema do contrato; inválida vira falha classificada reexecutável, nunca fato. 🟢
   - Origem no legado: `_reversa_sdd/sdd/policy-analysis.md#6.1` RF-09
   - Tipo: nova

## 5. Requisitos Funcionais

| ID | Requisito | Prioridade | Critério de aceite | Confidência |
|----|-----------|------------|--------------------|-------------|
| RF-01 | Processar 1 PDF de apólice: validar (existência, extensão, tamanho, cabeçalho), extrair texto nativo por página (PyMuPDF) e aplicar OCR (PaddleOCR) apenas às páginas sem texto suficiente. | Must | PDF válido percorre os estágios com `ProcessingStatus`; PDF corrompido/não-PDF recebe `FAILED("EXTRACT: ...")` sem indexar nada. | 🟢 |
| RF-02 | Dividir o texto por página em chunks sequenciais com `ChunkMetadata` versionada (chunk_id, document_id, policy_id, page, chunk_index, section_name). | Must | Todo chunk indexado tem metadados válidos pelo contrato 1.0.0; `metadata_version` presente. | 🟢 |
| RF-03 | Gerar embeddings (Gemini) e indexar chunks no Qdrant local com os mesmos IDs dos metadados, de forma idempotente por `document_id`. | Must | Reprocessar o mesmo documento mantém a mesma contagem de chunks (sem duplicação); payload no índice tem IDs iguais aos de `ChunkMetadata`. | 🟢 |
| RF-04 | Responder `RetrievalQuery` com `RetrievalResult` (até `top_k` evidências com score em [0,1] e `retrieval_run_id` único por consulta). | Must | `top_k` respeitado; evidências válidas pelo contrato; consulta sem resultados devolve `evidences=[]` (não é erro). | 🟢 |
| RF-05 | Manter catálogo com os 10 `field_code` do slice (semântica documentada) e extrair campos com agente Pydantic AI que produz `ExtractedFact` validado (extração demonstrada no slice com `limite_agregado`). | Must | Campo fora do catálogo é rejeitado; todo fato FOUND carrega `evidence_ids` das evidências recebidas; saída inválida nunca vira fato. | 🟢 |
| RF-06 | Persistir apólices, documentos e fatos em DuckDB com os identificadores do shared_kernel. | Must | Fato consultado no DuckDB tem os mesmos IDs dos chunks indexados (0 divergências). | 🟢 |
| RF-07 | Comparar 2 apólices campo a campo com regras determinísticas e emitir `ComparisonId` único + export em arquivo standalone (todos os campos do catálogo, incluindo ausentes). | Must | 2 fixtures idênticas = 100% "igual"; execuções repetidas reproduzem exatamente o mesmo resultado; export abre sem o sistema. | 🟢 |
| RF-08 | Gerar, para cada diferença, explicação em linguagem do analista citando `EvidenceRef` de ambas as apólices. | Must | Explicação sem evidência citada é rejeitada; citações resolvem para `evidence_ids` dos fatos. | 🟡 |
| RF-09 | Tela Streamlit mínima: carregar 2 PDFs, acompanhar o processamento (`ProcessingStatus`), ver comparação por campo com evidências, ver fila de revisão e exportar o resumo. | Must | Analista completa a jornada na tela sem usar CLI; sinalizações `AMBIGUOUS`/`NEEDS_REVIEW` aparecem com a evidência anexa. | 🟡 |
| RF-10 | Expor apenas fachadas públicas (`document_processing.public_api`, `policy_analysis.public_api`); dependências externas (PyMuPDF, PaddleOCR, Qdrant, Gemini, DuckDB, Streamlit, Pydantic AI) isoladas em `infrastructure/**` ou camada de UI. | Must | Teste de arquitetura: nenhum import de dependência externa em `domain/`/`application/`; cross-module apenas via fachada. | 🟢 |

## 6. Requisitos Não Funcionais

| Tipo | Requisito | Evidência ou justificativa | Confidência |
|------|-----------|----------------------------|-------------|
| Determinismo | Mesma entrada → mesma saída em 100% das execuções da comparação | `_reversa_sdd/sdd/policy-analysis.md#7` RNF-01 | 🟢 |
| Desempenho | Retrieval top-5 em até 3s; extração por campo em até 30s (single-user, local) | `_reversa_sdd/sdd/document-processing.md#7` RNF-01; `policy-analysis#7` RNF-04 | 🟡 |
| Observabilidade | Toda indexação/consulta/extração carrega `run_id`/`retrieval_run_id`; custo de embeddings registrado por run | `_reversa_sdd/sdd/document-processing.md#7` RNF-04 | 🟡 |
| Segurança/Privacidade | Conteúdo de apólice é confidencial: nada de texto integral de chunk em logs; envio ao Gemini registrado como decisão explícita | `_reversa_sdd/prd.md#6. Restrições` | 🟢 |
| Manutenibilidade | Núcleo (domain/application) testável sem dependências externas — adapters substituíveis por fakes nos testes | `_reversa_sdd/sdd/document-processing.md#7` RNF-06; `policy-analysis#7` RNF-05 | 🟢 |

## 7. Critérios de Aceitação

```gherkin
Cenário: Jornada completa com 2 apólices
  Dado 2 PDFs de apólice D&O (1 digital, 1 com página escaneada)
  Quando o analista carrega os 2 arquivos na tela e dispara o processamento
  Então ambas as apólices chegam ao estágio INDEXED com status publicado por estágio
  E o campo limite_agregado é extraído como ExtractedFact com evidência de página/trecho
  E a comparação campo a campo é emitida com ComparisonId e explicação citando evidências
  E o resumo é exportado em arquivo standalone com todos os campos do catálogo

Cenário: PDF corrompido
  Dado um arquivo que não é PDF válido
  Quando o analista tenta processá-lo
  Então o sistema publica ProcessingStatus(FAILED, "EXTRACT: arquivo invalido")
  E nenhum chunk é indexado

Cenário: Campo ausente na apólice
  Dado uma apólice sem cláusula de franquia
  Quando o sistema extrai o campo franquia
  Então o resultado é ExtractedFact(status="NOT_FOUND") sem evidence_ids
  E a comparação sinaliza diferença por omissão para esse campo

Cenário: Reexecução idempotente
  Dado um documento já indexado
  Quando o mesmo document_id é processado novamente
  Então a contagem de chunks do índice permanece igual à da primeira execução

Cenário: Saída de LLM fora do schema
  Dado um agente de extração que devolve JSON inválido
  Quando o sistema valida a saída
  Então a resposta é rejeitada como falha classificada reexecutável
  E nenhum fato é persistido
```

## 8. Prioridade MoSCoW

| Item | MoSCoW | Justificativa |
|------|--------|---------------|
| RF-01..RF-07, RF-10 | Must | Sem eles não existe jornada fim a fim nem rastreabilidade — são o slice |
| RF-08 | Must | Explicação com evidência é o diferencial do produto (PRD §1) |
| RF-09 | Must | O analista só valida o valor com a tela; sem ela o slice não prova a jornada |
| RNF de determinismo | Must | Premissa central de negócio (LLM jamais compara) |
| RNF de desempenho | Should | Metas de latência são de produto; no slice basta medir |
| Avaliação automatizada (evaluation) | Won't neste slice | Explicitamente fase posterior (`evaluation.md#4`) |

## 9. Esclarecimentos

> Nenhuma sessão de dúvidas registrada ainda. As open questions OQ-01..OQ-04 de `document-processing.md#14` e OQ-01..OQ-04 de `policy-analysis.md#14` são dono Dev 1/Dev 2 e foram resolvidas com defaults de slice na seção 10 (Decisões do slice), registradas para validação conjunta na PR.

## 10. Lacunas e Decisões do slice

Decisões propostas pelo Dev 1 para as open questions marcadas "antes do vertical slice" (🟡 INFERIDO — defaults simples e substituíveis, validação conjunta com Dev 2 na PR):

1. **OQ-01 (limiares):** página com ≥ 40 caracteres não-brancos = texto nativo suficiente (`NATIVE_TEXT`); caso contrário OCR (`PADDLEOCR`). Página com `ocr_confidence` média < 0.5 é ilegível e entra em `REVIEW_REQUIRED` (EC-05) sem bloquear o documento. Limiares configuráveis no módulo.
2. **OQ-02 (chunking):** chunking fixo por página: ~800 caracteres com overlap de 100, ordem sequencial (`chunk_index`); detecção por seção fica para fase posterior.
3. **OQ-03 (section_name):** `section_name = null` no slice (campo opcional do contrato); heurística de marcadores é fase posterior.
4. **OQ-04 (coleção Qdrant):** coleção única `policy_chunks` com filtro por `policy_id`/`document_id` (mais simples de recriar; evita N coleções).
5. **OQ policy-analysis (catálogo):** 10 field_code do slice: `limite_agregado`, `limite_por_sinistro`, `franquia`, `vigencia_inicio`, `vigencia_fim`, `base_territorial`, `retroatividade`, `prazo_notificacao`, `exclusoes_chave`, `nome_segurado`. Extração demonstrada com `limite_agregado`; comparação cobre o catálogo inteiro.
6. **OQ policy-analysis (export):** export em Markdown standalone (`<ComparisonId>.md`) com valores, direção da diferença, evidências e explicação por campo.

Sem `[DÚVIDA]` pendentes: todos os pontos acima têm default executável; divergências de Dev 2 são ajustadas na PR (não bloqueiam o slice).

## 11. Histórico de alterações

| Data | Alteração | Autor |
|------|-----------|-------|
| 2026-09-26 | Versão inicial gerada por `/reversa-requirements` | reversa |
