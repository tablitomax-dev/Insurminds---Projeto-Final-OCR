# Handoff Dev 2 — Fechamento de pendências de execução (resumo para o assistente de IA do Dev 1)

> **Destinatário:** assistente de IA do Dev 1 (pbena) — leitura antes de revisar/integrar.
> **Data:** 2026-10-01 · **Autor:** Dev 2
> **Branch:** `feature/dev2-policy-analysis-slice` (commit `2336499` + este handoff, pushados)
> **Contexto:** pós-PR #11 (reconciliação FECHADA no §9 do handoff anterior) — o quadrado `policy_analysis` está unificado no `main`; esta entrega é o fechamento das pendências de execução do plano D2 que sobraram.

---

## 1. Visão geral

Três pendências menores do `plano-acao-dev2.md`, sem mudança de contrato e sem tocar o quadrado do Dev 1:

1. **Restauração da regra `enum_base_territorial`** (D2-P0-3) — a regra estava prevista no `actions.md` do `dev2-003` e citada nos adendos, mas **se perdeu** no realinhamento do código à base oficial do PR #8 (`ff12559`) e não foi reconstruída junto das guardas; hoje o D2-P0-3 fica 100%.
2. **Registro formal da OQ-02 (evaluation.md)** — substring literal vs semelhança: decisão tomada no D2-P0-1/D2-P0-4 e finalmente documentada em `_reversa_forward/dev2-003-p0-analise-experiencia/decisions.md`. **A OQ-02 da `evaluation.md` é "Dev 2 (propõe) + Dev 1" — pedimos a confirmação do Dev 1** (seção 3).
3. **Fix do `DeprecationWarning` de `datetime.utcnow()`** — nota menor registrada no §9 do seu handoff, agradecida e atendida.

## 2. Commit incluído

| Commit | O que contém |
|--------|--------------|
| `2336499` | `domain/rules.py` (enum + `KNOWN_TERRITORY_BASES`), `duckdb_repository.py` (`datetime.now(UTC)`), `tests/.../test_rules.py` (+4 testes), `decisions.md` (novo) |

- **Áreas compartilhadas:** nenhuma. `shared_kernel` intacto; nenhum arquivo de `document_processing`/testes do Dev 1 tocado.
- **Gate T-1:** `ruff` All checks passed · `mypy` sem erros · `pytest` **302 passed, 5 skipped** (baseline 298/5; +4).
- **PR:** ainda **não aberto** (o humano optou por adiar) — o commit está na branch do Dev 2; o PR para o `main` sai em entrega seguinte.

## 3. Proposta formal: OQ-02 (evaluation.md) = **substring literal** — aguarda confirmação do Dev 1

**Pergunta da spec:** "Criterio de acerto de texto livre (exclusões): substring exato ou semelhança mínima definida por regra?" (`evaluation.md`, tabela de OQs).

**Proposta do Dev 2 (implementada):** substring **literal** após trim de bordas, sem limiar, sem semelhança difusa. Mesma régua nos dois usos:

1. **Ancoragem de citação (D2-P0-1, `domain/anchoring.py`):** todo trecho citado pelo LLM precisa existir literalmente no `EvidenceRef.quoted_text` das evidências citadas; não ancora → `NEEDS_REVIEW` (nunca `FOUND`).
2. **Acerto de texto livre** (`exclusoes_chave` etc.): igualdade após normalização de forma (`normalize_text`), nunca "semelhança ≥ x%".

**Porquês:** determinismo (A-08/RNF-01 — limiar é parâmetro arbitrário solto); anti-alucinação (A-07 — "existe no texto?" é igualdade); fronteira proibida do PRD (similaridade vetorial/embeddings para decidir comparação é regra absoluta proibida — um critério por semelhança abriria a porta pela lateral).

**Descartadas:** semelhança difusa/limiar; similaridade vetorial/embeddings; ancoragem só em `FOUND` (qualquer excerpt é ancorado).

**Status:** proposta do Dev 2, implementada e testada (`test_anchoring.py`). Se o Dev 1 concordar, a OQ-02 da `evaluation.md` pode ser fechada na spec por quem detém o documento (não editamos `sdd/` unilateralmente — §5 do `aprendizados.md`). Registro completo em `_reversa_forward/dev2-003-p0-analise-experiencia/decisions.md`.

## 4. `enum_base_territorial` restaurado (D2-P0-3 completo)

- **Regra:** `extensao_territorial` ∈ vocabulário fechado (`KNOWN_TERRITORY_BASES`, formas normalizadas) — brasil, eua/estados unidos, canada, europa, america latina/sul/norte, mundo/mundial/worldwide, internacional, exterior (vocabulário **literal** do `actions.md` do `dev2-003`, nenhuma decisão nova).
- **Fora do enum → `NEEDS_REVIEW`** com motivo sanitizado (só regra/campo, nunca o valor — T-2a). É **sinal, não erro**: texto livre fora do vocabulário pode ser legítimo ("Mundo exceto EUA") e o analista decide na revisão (mesma intenção da `moeda_consistente`, §8.2).
- Golden set da `evaluation` continua válido: os valores esperados ("Mundo", "Estados Unidos") estão no vocabulário.

## 5. `datetime.utcnow()` → `datetime.now(UTC)`

`duckdb_repository.py` (inserts de `policies.created_at` e `comparisons.created_at`). DuckDB aceita datetime com timezone e grava o valor UTC — **sem delta de schema**. Não achamos outros `utcnow()` no repo; se sobrarem no quadrado do Dev 1, fica a sugestão do mesmo padrão.

## 6. Pendências Dev 2 que restam (para conhecimento)

- **D2-P1-3 (apólices reais/anonimizadas):** dependência externa (sponsor/curso, pós-fechamento do projeto — §6 do seu handoff). Sem isso, o slice segue **não validado em campo** (R1/R3).
- Fora do horizonte (registro, não tarefa): persistência de métricas em tabela DuckDB; tabela histórica de `Issue`.