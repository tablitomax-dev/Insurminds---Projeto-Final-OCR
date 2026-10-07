# Handoff — Failover de LLM, saúde do provedor e UI simplificada (2026-10-06)

## Entregas

1. **Cadeia de failover LLM**: `FallbackLLMClient` com cadeia de N provedores
   (glm-5.3-flash → deepseek-v4.1-flash → mimo-v2.6-pro; 2 falhas consecutivas
   por nível). Slot Gemini opcional (`GEMINI_API_KEY`, `LLM_GEMINI_MODEL`) em
   conta separada — único nível que sobrevive a limite estourado no OpenRouter.
2. **Fail-fast e causa raiz**: 401 → `LLM_AUTH_FAILED`, 403 →
   `LLM_QUOTA_EXCEEDED` (retriable=False, sem retry nem avanço de cadeia);
   400/404 pulam direto ao próximo nível; mensagens trazem
   `HTTP <status> — <mensagem da API>` (T-2a preservado: texto livre do
   provedor não vaza — só erro HTTP leva a mensagem).
3. **Health-check do provedor**: `FallbackLLMClient.health_check()` +
   `PolicyAnalysisFacade.llm_health()` + banner no boot da UI
   (verde/vermelho/amarelo com causa real; uma checagem por sessão).
4. **UI simplificada** (decisão do dono — projeto acadêmico): seção
   "5. Relatório D&O" oculta por completo (componente preservado); extração
   automática e idempotente sem botão; tabela/expanders de campos ocultos;
   aviso "Extração concluída — você já pode fazer suas perguntas na seção de
   consulta livre".
5. **Erros amigáveis**: `_CODE_HINTS` por código (incl. `LLM_QUOTA_EXCEEDED` e
   `LLM_AUTH_FAILED`) — dica + detalhe real + código (decisão 2026-10-05: sem
   trava de sanitização).

## Achados

- Causa raiz da falha em cadeia das chamadas LLM (2026-10-06): **HTTP 403
  "Key limit exceeded (total limit)"** — crédito da chave OpenRouter
  estourado, derrubando os 3 modelos (mesma conta). Recarregada pelo usuário;
  sonda direta confirmou HTTP 200 nos 3 modelos da cadeia.
- T-2a x diagnóstico: solução = causa raiz apenas em erro HTTP (diagnóstico
  estruturado do provedor); exceção de texto livre vira só o nome do tipo
  (testes `test_erro_do_llm_nao_vaza_texto_de_apolice` e
  `test_mensagem_final_do_with_retries_traz_a_causa_raiz` cobrem os dois lados).

## Zonas compartilhadas

- `infrastructure/llm_agent.py` (`_with_retries`/`_as_unavailable`): consumido
  por todos os agentes LLM — mudanças restritas à classificação de erro, sem
  efeito em prompts nem assinaturas.
- `public_api.py`: só acréscimos (`llm_health()`; ctor com `llm_client=None`
  opcional, retrocompatível).
- `src/ui/errors.py`: só o mapa de dicas por código.
- Contrato UI × backend: `llm_health() -> [{"provider","model","ok","detail"}]`.

## Pendências

1. **Batching/paralelo/cache do Relatório D&O estacionado** (seção oculta da
   UI): contrato `fill_batch` preparado em `report_agent.py`; implementar
   (2 lotes de 4 categorias + ThreadPoolExecutor + cache por fingerprint)
   quando o relatório voltar a ser exposto.
2. **Validação real de `tests/apolices` incompleta**: rodada 1 (AXA +
   Allianz 2025) concluída; rodadas 2 (PORTO + Allianz 2025) e 3 (Allianz 2017
   JPG + PORTO) pendentes — "ao menos uma vez cada"; análise de qualidade e
   correções após.
3. Validar extração com apólice completa (com especificação/valores — os PDFs
   atuais são Condições Gerais).
4. Pendências antigas: imagem de fundo; custo de cache/batch; renomear
   `test_texto_nao_recebe_regras_de_valor`; ecos de `str(exc)`.
