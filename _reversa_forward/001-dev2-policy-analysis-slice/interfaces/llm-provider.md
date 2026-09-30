# Interface: Provedor de LLM (Gemini via Pydantic AI)

> Identificador: `001-dev2-policy-analysis-slice`
> Data: `2026-09-26`
> Contrato externo afetado: chamadas HTTP ao provedor de LLM (extração e explicação)
> Detalhe do roadmap: `_reversa_forward/001-dev2-policy-analysis-slice/roadmap.md#7`

## 1. Visão

O módulo `policy_analysis` fala com o provedor de LLM (Gemini) exclusivamente pela camada `infrastructure`, via agente Pydantic AI com saída estruturada. Duas operações usam o provedor:

1. **Extração** (agente multi-campo): evidências de uma apólice → 10 `ExtractedFact`.
2. **Explicação**: par de fatos divergentes → texto citando `evidence_ids` dos dois lados.

## 2. Request

| Campo | Descrição |
|-------|-----------|
| `model` | modelo Gemini configurado (ex.: `gemini-2.x-flash`) |
| `prompt` | instruções + evidências (`EvidenceRef.quoted_text` + metadados de página/trecho) + `schema_version` |
| `response_schema` | schema Pydantic derivado de `ExtractedFact[]` (extração) ou `Explanation` (explicação) |
| `run_id` | identificador da execução (não vai ao provedor; rastreia custo/tokens localmente) |

Limites: `top_k` de evidências por campo vem do retrieval (5 por padrão); texto integral de apólice nunca é enviado — só trechos citados (PRD §6).

## 3. Response

| Campo | Descrição |
|-------|-----------|
| saída estruturada | JSON validado contra o schema do contrato ANTES de qualquer persistência (RF-09) |
| uso de tokens | registrado por `run_id` (RNF-03) |

Regras de aceitação da resposta:
- todo `evidence_id` citado deve existir nas evidências recebidas (RN-02);
- `status=FOUND` exige `evidence_ids` não vazio (EC-05 dos contratos);
- explicação sem citação de evidência dos dois lados é rejeitada (RF-07).

## 4. Erros

| Erro | Código típico | Comportamento do módulo |
|------|---------------|-------------------------|
| Timeout | — | retry com backoff (até 3 tentativas); depois falha classificada + sinalização de revisão (EC-01) |
| Rate limit | 429 | retry com backoff; depois falha classificada reexecutável |
| Indisponibilidade | 5xx | retry com backoff; depois falha classificada reexecutável |
| Saída fora do schema | — | rejeitada; nova tentativa com o mesmo prompt; persistindo → `NEEDS_REVIEW` + falha classificada (RF-09) |

Nenhuma falha do provedor é silenciosa: sempre vira erro classificado (reexecutável) ou sinalização de revisão — nunca fato.

## 5. Idempotência

As chamadas de LLM **não são idempotentes** por natureza (texto gerado pode variar). A idempotência é garantida no domínio: o resultado da comparação é função pura dos fatos, e `comparison_id` é determinístico (D-09 do roadmap). A extração é reexecutável: nova `run_id`, fatos atualizados, sem duplicação (upsert por `fact_id`/campo).

## 6. Timeouts e limites

| Parâmetro | Valor | Origem |
|-----------|-------|--------|
| Timeout por chamada | 60s | margem sobre o alvo de 30s/campo (RNF-04) |
| Retentativas | 3, com backoff exponencial | EC-01 da spec |
| Máx. de reexecuções da explicação inválida | 2, depois `NEEDS_REVIEW` | RF-07/RF-09 |

## 7. Segurança e privacidade

- Apenas trechos citados (`quoted_text`) são enviados ao provedor — decisão explícita registrada no PRD §6.
- Nenhum texto integral de apólice em logs; `run_id` + contagem de tokens apenas.
- Chave de API via `.env`, nunca versionada.