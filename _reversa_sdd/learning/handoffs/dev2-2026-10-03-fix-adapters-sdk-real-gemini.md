# Handoff Dev 2 — Fix dos adapters Gemini contra os SDKs reais + modelo padrão gemini-3.8-flash

> **Destinatário:** assistente de IA do Dev 1 (pbena) — leitura antes de revisar/integrar.
> **Data:** 2026-10-03 · **Autor:** Dev 2
> **Branch:** `feature/dev2-policy-analysis-slice` (commit deste handoff, pushado)
> **Contexto:** primeira execução REAL do pipeline com `GEMINI_API_KEY` definida (teste real autorizado pelo humano). Os testes usam fakes e os de integração com chave estavam `skipped` — por isso três incompatibilidades com os SDKs reais nunca tinham sido exercitadas e apareceram agora.

---

## 1. Visão geral

Três correções necessárias para o teste real funcionar, nenhuma mudança de contrato:

1. **`GeminiEmbedder` chamava um método que não existe no `google-genai`** (quadrado do Dev 1 — detalhe no §3): `models.embed_contents` → `models.embed_content` com `EmbedContentConfig`.
2. **`PydanticAIClient` importava `GeminiModel`, que não existe mais no `pydantic-ai` 2.51.0**: renomeado para `GoogleModel` + `GoogleProvider`. Cadeia de fallback por versão mantida (o padrão já existente no adapter foi estendido).
3. **`gemini-2.0-flash` foi descontinuado pela Google** (API responde `404 NOT_FOUND … use models/gemini-3.8-flash`): defaults de modelo atualizados para `gemini-3.8-flash` em `PydanticAIClient`, `create_default_policy_analysis` e `build_facades`.

## 2. Commits incluídos

| Commit | O que contém |
|--------|--------------|
| (este) | `indexing.py` (fix `embed_content`), `test_indexing.py` (fake do SDK + assert da dimensão), `llm_agent.py` (`_build_gemini_model` + default), `public_api.py` (default), `root.py` (default), este handoff |

- **Gate T-1:** `ruff` All checks passed · `mypy` sem erros (69 arquivos) · `pytest` **348 passed, 1 skipped** — com `GEMINI_API_KEY` + `INTEGRATION_QDRANT_URL=:memory:` (o teste de embeddings reais roda de verdade; o skip restante é o caso 'escaneado' do PaddlePaddle no Windows/CPU, limitação conhecida — Linux/CI).

## 3. Toque no quadrado do Dev 1 — `document_processing` (pedido de revisão)

O fix em `src/modules/document_processing/infrastructure/indexing.py` é **mínimo e obrigatório**: o `GeminiEmbedder._request_embeddings` chamava `client.models.embed_contents(...)`, método **inexistente** no `google-genai` 2.25.0 (o correto é `embed_content`, que aceita o lote em `contents` e leva a dimensionalidade em `config=EmbedContentConfig(output_dimensionality=...)`). Com isso, **qualquer indexação real falhava** com `AttributeError` traduzido para `EmbeddingError` — o caminho só não pegava porque os testes usam um fake que espelhava o nome errado.

- A normalização de resposta (`_response_embeddings`/`_embedding_values`) **não mudou** — `EmbedContentResponse.embeddings[].values` já era coberta.
- `test_indexing.py` (fake `_FakeGenaiSdk`): método renomeado para `embed_content` e `_FakeEmbedContentConfig` acrescentado ao `types` do fake; um assert novo trava que a dimensão vai na config (contrato com a coleção do Qdrant). Os demais asserts (retry, lote de 100, métrica) seguem intactos.
- Se preferir replantar o fix de outra forma, é só avisar — mudança de 1 chamada.

## 4. Validação real feita hoje (evidências)

- **Embeddings reais:** `GeminiEmbedder(output_dimensionality=8).embed_texts([...])` → vetor de 8 dimensões retornado pelo `gemini-embedding-001` (chamada real confirmada).
- **LLM real (smoke):** `PydanticAIClient(model_name="gemini-3.8-flash").complete_json(...)` → `{'ok': True}`.
- **Qdrant:** standalone 1.19.1 em `localhost:6333` (sem auth) rodando; testes de integração usam `INTEGRATION_QDRANT_URL=":memory:"` (modo projetado — servidor compartilhado colide dimensão na coleção `policy_chunks`).

## 5. PENDENTE (não validar como fechado)

1. **E2E da extração com o LLM real não concluída:** a demo (`python -m modules.policy_analysis.demo`) chegou ao LLM, mas o primeiro retorno veio **fora do schema esperado** (`_parse_structured(raw, list)` — o dict sem a chave `facts` caiu no fallback) e, ao tentar diagnosticar o formato bruto, o provedor passou a responder `503 high demand` de forma persistente (6 tentativas). Smoke simples (`{'ok': true}`) passou; o caso com prompt de extração precisa ser refeito com calma. Possíveis causas: formato de saída do `gemini-3.8-flash` no `output_type=dict` do Pydantic AI, ou prompt que precisa de ajuste para o modelo novo. **Nada de código foi inventado para "consertar" às cegas.**
2. **Tabela de preços sem `gemini-3.8-flash`:** `USD_PER_1M_TOKENS` só tem `gemini-2.0-flash`; o custo do modelo novo sai `None` (regra D-04 — nenhum número inventado). Falta o preço oficial (entrada/saída por 1M de tokens) para atualizar a tabela + `PRICE_REFERENCE_DATE` (isso mexe em `test_metrics.py`, que fixa a data — avisar antes).
3. **`GEMINI_API_KEY` via variável de ambiente** (perfil do Windows, `setx`) — nunca em arquivo do git. O `.gitignore` ainda **não** ignora `.env` (o `onboarding.md` do projeto manda criar `.env` na raiz — risco de commit acidental). Sugestão: adicionar `.env` ao `.gitignore`.

## 6. Pendências Dev 2 conhecidas (sem mudança)

- **D2-P1-3 (apólices reais/anonimizadas):** dependência externa (sponsor/curso) — segue em aberto.
- **PR para o `main`:** a branch acumula commits (sync, UI, tela de consulta, este fix) sem PR — abrir quando o humano decidir.
