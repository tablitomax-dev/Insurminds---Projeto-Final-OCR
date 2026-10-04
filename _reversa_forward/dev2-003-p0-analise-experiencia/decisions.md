# Registro de decisões: P0 do Desenvolvedor 2 — Análise e Experiência

> Identificador: `dev2-003-p0-analise-experiencia`
> Data: `2026-10-01` (ISO 8601) · Convenção: **A-10** (decisão registrada na feature)
> Complementa as decisões registradas no `actions.md` — aqui fica a decisão de design que o `plano-acao-dev2.md` (D2-P0-4) mandou registrar: **OQ-02 = substring**.

## 1. OQ-02 (evaluation.md) — critério de acerto/ancoragem de texto livre = **substring literal**

**Pergunta (spec):** critério de acerto de texto livre (exclusões): substring exato ou semelhança mínima definida por regra? — Dev 2 (propõe) + Dev 1.

**Decisão:** substring **literal** após trim de bordas. Sem limiar, sem semelhança difusa.

**Onde vale (dois usos, mesma régua):**

1. **Ancoragem de citação (D2-P0-1, `domain/anchoring.py`):** todo trecho citado pelo LLM (`raw_text`/`excerpt`/`quote`/... e aspas de texto livre) precisa aparecer literalmente no `EvidenceRef.quoted_text` das evidências citadas. Não ancora → `NEEDS_REVIEW` (nunca `FOUND`).
2. **Comparação/acerto de texto livre (`exclusoes_chave` etc.):** igualdade após normalização de forma (`normalize_text`: caixa, acentos, espaços — A-14), nunca "semelhança ≥ x%".

**Porquê:**

- **Determinismo (A-08/RNF-01):** mesma entrada → mesmo resultado, sem parâmetro de limiar arbitrário rodando solto no projeto.
- **Anti-alucinação (A-07):** "existe no texto?" é pergunta de igualdade — invenção do modelo só se denega por literalidade; semelhança alta ainda é invenção.
- **Fronteira proibida do PRD:** similaridade vetorial/embeddings para decidir comparação é regra absoluta proibida (A-08) — um critério por semelhança abriria a porta pela lateral.

**Escolhas descartadas:**

| Descartada | Porquê |
|---|---|
| Semelhança mínima (difusa/limiar %) | Não determinística por natureza de limiar; normalização extra ancoraria trecho que não existe literalmente |
| Similaridade vetorial/embeddings | Proibida pelo PRD para comparação; indisponível offline; escopo do Dev 1 (`D1-P2-1` mede métrica, não decide) |
| Ancoragem só em `FOUND` | Qualquer excerpt (inclusive de `AMBIGUOUS`/`NEEDS_REVIEW`) é ancorado — revisor não recebe citação inventada (já registrado no `actions.md`) |

**Status:** decisão de execução do Dev 2, implementada (testes `test_anchoring.py`); a OQ-02 da `evaluation.md` pede confirmação do **Dev 1** — este registro é a proposta formal na fronteira combinada (§5 do `aprendizados.md`; docs canônicos não são editados unilateralmente).

## 2. Decisões de execução complementares

| ID | Decisão | Escolhas descartadas | Porquê |
|----|---------|----------------------|--------|
| E-01 | `enum_base_territorial` (D2-P0-3): `extensao_territorial` ∈ vocabulário fechado (`KNOWN_TERRITORY_BASES` em `domain/rules.py`, forma normalizada — minúsculas/sem acento); fora do enum → `NEEDS_REVIEW` com motivo sanitizado | rejeitar o fato como erro; autocorrigir/enquadrar no enum mais próximo | Texto livre fora do vocabulário pode ser legítimo ("Mundo exceto EUA") — o humano decide na revisão; sinal, não erro (mesma intenção da `moeda_consistente`, §8.2) |
| E-02 | Vocabulário do enum = abrangências usuais D&O (brasil, eua/estados unidos, canadá, europa, américa latina/sul/norte, mundo/mundial/worldwide, internacional, exterior), já previsto no `actions.md` desta feature | enum de países completo; campo livre sem regra | O catálogo é fechado e comparável (A-08); países completos seriam enum infinito — o guarda existe justamente para o caso fora do esperado |
| E-03 | `datetime.now(UTC)` no lugar de `datetime.utcnow()` (`duckdb_repository.py`) | manter `utcnow()`; coluna `TIMESTAMPTZ` | `utcnow()` está deprecated (Python 3.12, nota §9 do handoff do Dev 1); DuckDB aceita datetime com timezone e guarda o valor UTC, sem delta de schema |
| E-04 | `collect_excerpts` não revira `raw_text` para aspas (dedup §8.1) | coletar aspas também de `raw_text` | Mesmo trecho era contado 2× e inflava o nº de citações não ancoradas (review do Dev 1, já aplicado) |

## 3. Rastreabilidade

- Escopo e prioridades: `_reversa_forward/dev2-003-p0-analise-experiencia/requirements.md` (RF-03 = regras por campo, inclui enum)
- Execução original: `actions.md` (D2-P0-1/D2-P0-3); regra `enum_base_territorial` prevista ali e restaurada em 2026-10-01 (perdida no realinhamento à base do PR #8)
- Plano: `_reversa_sdd/learning/plano-acao-dev2.md` (D2-P0-3 "enums para base_territorial"; D2-P0-4 "registrar a decisão" da OQ-02)
- Decisão de desenho da ancoragem (adaptada ao `value` estruturado): docstring de `src/modules/policy_analysis/domain/anchoring.py`