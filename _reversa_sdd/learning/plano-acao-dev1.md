# Plano de ação — Desenvolvedor 1 (Núcleo documental e RAG)

> Data: `2026-09-26` · Versão **v1.0** (pós-debate multiagente 3 críticos × 2 rodadas)
> Dono: **Desenvolvedor 1** — ingestão, PDF, OCR, chunking, embeddings, Qdrant, retrieval de evidências.
> Base: `aprendizados.md` (IDs `F-xx`/`A-xx`/Apêndice A), `benchmark-repos-referencia.md`, `_reversa_sdd/sdd/document-processing.md`, `_reversa_forward/001-vertical-slice-e2e/`, `resumo_executivo_arquitetura_monolito_modular (1).md` (arquivo na raiz, fora do corpus Reversa — §6.1/§7/§10).
> Regra-mãe: você transforma **arquivos em evidências recuperáveis**. Fato, comparação, explicação e tela são do Dev 2.
> Convenções de coordenação (IDs `D1-*`, caixa postal de contrato, gate `T-1`): ver `aprendizados.md` §5.

## 1. Seu terreno (e o que é cerca)

**Seu:** `src/modules/document_processing/**`, testes de `tests/modules/document_processing/`, `tests/fakes/document_processing.py`, parte documental de `tests/integration/`.

**Não é seu:** `src/modules/policy_analysis/**`, `src/ui/**`, tabelas DuckDB, prompts de extração/explicação, regra de comparação, segundo modelo de `Evidence`.

## 2. Estado atual (verificado no código em 2026-09-26)

- `process_document`: PDF → páginas → classificação (`NATIVE_TEXT`/`PADDLEOCR`; `REVIEW_REQUIRED` é **estágio de status** para páginas ilegíveis, não classe de página) → chunking 800/100 → embeddings → Qdrant `policy_chunks` → status por estágio. 🟢
- `retrieve_evidence`: `RetrievalQuery` → `RetrievalResult` com `run_id`. 🟢
- `policy_id`/`document_id` já são **metadata filter na consulta** (o anti-padrão do benchmark §4.1 não ocorre aqui). 🟢
- ⚠️ **Bug de contrato vivo (F-14):** `section_name`/`field_code` do `RetrievalQuery` são **descartados em silêncio** (`service.py` linhas 150-158) — o Dev 2 manda `field_code` achando que filtra.
- ⚠️ **Vazamento em erro (A-13 ressalva):** `_cause` retorna `str(exc)` cru (`service.py:216`) — mensagem de erro pode conter texto de apólice.
- Embeddings e upsert já são **em lote** (1 chamada por documento); `ensure_collection` já roda antes do upsert. O que falta: limite de textos por request e eliminação do loop do SDK legado (`google.generativeai`).
- Idempotência (`uuid5` estável; delete+upsert) testada; `chunk_text` **nunca trunca** (não existe flag de truncamento). 🟢
- Adapters com imports lazy; 137 testes verdes sem Docker/chave. 🟢

## 3. O que fazer e como fazer (ordem de execução)

### D1-P0-1 — Erros tipados por porta + retry só no Gemini
- **O quê:** exceções de domínio por porta (`EmbeddingError`, `IndexingError`, `OcrError`) em `application/ports.py`; retry com backoff **somente** no adapter Gemini (429/5xx): 3 tentativas, backoff exponencial 1s→2s, timeout 30s. **Retry no Qdrant: cortado** (Docker local; idempotência delete+upsert já cobre reprocessamento).
- **Como:** helper de retry local em `infrastructure/indexing.py`; adapter traduz erro externo para a exceção da porta; domínio/application seguem sem imports externos.
- **Pronto quando:** teste com fake que falha 2× e acerta na 3ª prova o backoff; erro externo vira exceção tipada da porta; teste de arquitetura verde.
- **Origem:** A-03, benchmark §2.2; parâmetros explícitos por crítica C3-09.

### D1-P0-2 — Honrar `RetrievalQuery` (bug de contrato F-14)
- **O quê:** decidir e implementar a semântica de `section_name`/`field_code` no `retrieve_evidence`: aplicar como filtros adicionais no mesmo metadata filter **ou** removê-los de `RetrievalQuery` via caixa postal com o Dev 2 (quem manda `field_code` hoje). Nunca descartar em silêncio.
- **Como:** implementação + **teste de contrato por parâmetro** (para cada campo de `RetrievalQuery`, o teste prova que ele chega à porta `VectorIndex.search` — spy/fake gravando a chamada); decisão registrada em `_reversa_forward/`.
- **Pronto quando:** teste falha se qualquer filtro voltar a ser descartado; Dev 2 notificado pela caixa postal se a semântica mudar.
- **Origem:** F-14 (verificado no código).

### D1-P0-3 — Auditoria + gap real de indexação (sem re-implementar o que já existe)
- **O quê:** fechar só os gaps: (a) teste de isolamento com 2 apólices intercaladas (nenhum chunk da B na consulta da A) + teste do adapter com `QdrantClient` mockado assertando `query_filter` em `query_points` (comprova filtro NA consulta — F-13/benchmark §4.1); (b) limite de textos por request de embeddings (ex.: 100) no lote; (c) eliminar o loop do SDK legado (`embed_content` por texto) mantendo só o caminho em lote; (d) health-check da coleção com falha classificada `ProcessingStatus.FAILED("INDEXING: ...")`.
- **Como:** o que já está verde **não é refeito** — apenas os gaps acima, cada um com seu teste.
- **Pronto quando:** cada gap (a)-(d) tem teste próprio que falha se o gap voltar.
- **Origem:** C1-02/C1-03 (auditoria da rodada 1 do debate): o texto anterior vendia como pendente o que já estava implementado.

### D1-P1-1 — Proveniência rica no chunk (caixa postal primeiro)
- **O quê:** `content_fingerprint` (sha256 do texto do chunk) como campo **opcional** no payload do Qdrant (mudança MINOR). Sem "flag de truncamento" — o pipeline não trunca; se truncamento surgir (PP-Structure), aí nasce a flag.
- **Como:** ⚠️ zona compartilhada: proposta em `_reversa_forward/<feature>/contract-delta-chunkmetadata.md` → aceite do Dev 2 (prazo 1 dia útil, ver `aprendizados.md` §5.2) → bump de versão do contrato → implementação + teste de round-trip.
- **Pronto quando:** proposta aceita por escrito + teste de payload.
- **Origem:** benchmark §2.4; mecanística corrigida pela crítica C1-10.

### D1-P1-2 — Fixtures e modo offline (com "pronto quando" real)
- **O quê:** fixtures: 1 PDF digital pequeno + 1 "escaneado" gerado do digital (PDF imagem-única, sem camada de texto). Modo offline = **pipeline real com fakes de Embedder apenas** (Qdrant local via Docker conta como offline; rede de embeddings é a única externa).
- **Como:** fixtures em `tests/fixtures/`; teste de integração opt-in roda o pipeline real sobre elas.
- **Pronto quando:** `python -B -m pytest -q -p no:cacheprovider -m integration` roda sem internet usando o fake de `Embedder`; o teste declara explicitamente o que é real e o que é fake.
- **Origem:** benchmark §2.6, A-11; frase autocontraditória corrigida pela crítica C2-05.

### D1-P2-1 — Métrica de embedding (opcional)
- **O quê:** tokens/latência do adapter de embeddings no log estruturado (sem texto de apólice). Sem contrato compartilhado novo.
- **Origem:** resumo §5.5; opcional por decisão do debate (métrica principal de custo é `D2-P1-2`).

## 4. O que NUNCA fazer no seu quadrado

1. Comparar apólices ou tocar em `policy_analysis`/`src/ui`. (resumo §6.1)
2. Escrever no DuckDB ou criar fato de negócio — seu produto é evidência.
3. Segundo modelo de `Evidence`/`ChunkMetadata` ou payload "só pra eu usar". (resumo §5.2)
4. Dependência externa em `domain/`/`application/`. (A-06, F-15)
5. Pós-filtro de segurança depois da busca. (benchmark §4.1)
6. Mudar chunking/limiares sozinho — é contrato consumido pelo Dev 2 (caixa postal). (A-10)
7. Retry em ferramenta bloqueada pelo sandbox — mude a rota e registre. (A-15, Apêndice A)

## 5. Ritual de trabalho (checklist da feature)

1. Granularidade da feature registrada no `actions.md` (seção que o `/reversa-to-do` gera) — A-01.
2. Teste primeiro na lógica determinística; adapter depois — A-04.
3. Gate `T-1` antes de todo PR: `ruff` + `mypy` + `python -B -m pytest -q -p no:cacheprovider` (comando único, dono Dev 2, execução sua obrigatória).
4. Mudança de contrato = caixa postal (`aprendizados.md` §5.2), uma por vez.
5. Erro com prefixo de estágio (`EXTRACT:`/`OCR:`/`INDEXING:`); nunca texto de apólice em erro/log (`T-2a`).
6. Antes de PR: checar estado remoto (`gh pr list --state all`); feature concluída → `regression-watch.md` → `/reversa-sync` (plano B: adendo manual). Ambiente: consultar `aprendizados.md` Apêndice A.
7. Decisão de implementação registrada em `_reversa_forward/<feature>/` (escolha/descartadas/porquê) — A-10.

## 6. Zonas compartilhadas com o Dev 2

| Zona | Regra |
|------|-------|
| `shared_kernel/contracts` | Muda só via caixa postal + bump de versão (A-02, §5.2) |
| `ChunkMetadata`/payload do Qdrant | Campo novo: sua proposta, aceite do Dev 2 antes do código (D1-P1-1) |
| `EvidenceRef` | Você produz, ele consome; formato é contrato |
| Orquestração | Composition root único (dono do fix da UI: Dev 2, `D2-P1-4`) |
| Vocabulário de erros | `EXTRACT:`/`OCR:`/`INDEXING:` — mudança = aviso |

## Fora desta rodada (registro, não tarefa)

- PP-StructureV3/`section_name` real (NG-01) — registrar como ação da próxima feature de documento complexo.
- ModelGateway compartilhado (gatelo: surgir 2º provedor/consumidor).
- GitHub Actions (gatelo: remoto estável + 2º dev ativo) — hoje o gate é local (`T-1`).
- Prompt injection em PDF (risco ACEITO e registrado; revisar antes de expor a terceiros).
- Retenção/limpeza automática plena (mínimo em `T-2b`).

## Critério de parada da rodada

Todos os `D1-P0-*` + `D2-P0-*` concluídos e `T-1` verde em 3 execuções consecutivas = rodada encerrada; qualquer novidade vai para a próxima rodada.
