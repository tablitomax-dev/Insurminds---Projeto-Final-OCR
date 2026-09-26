# Actions: P0 do Desenvolvedor 2 — Análise e Experiência

> Identificador: `003-p0-dev2-analise-experiencia`
> Data: `2026-09-26` (ISO 8601)
> Fonte: `_reversa_sdd/learning/plano-acao-dev2.md` v1.0 (método detalhado) · Aceitação: `requirements.md` desta feature
> Convenções: IDs `D2-*`/`T-*` (aprendizados §5.1); granularidade decidida por ação (A-01); caixa postal para contrato (§5.2); gate `T-1` antes de todo PR.

## Resumo

| Métrica | Valor |
|---------|-------|
| Ações desta rodada | 6 (`D2-P0-1`..`D2-P0-4` + `T-1`, `T-2`) |
| Ordem de execução | `T-2a`/`T-1` → `D2-P0-1` → `D2-P0-3` → `D2-P0-2` → `D2-P0-4` |
| Backlog (não executar agora) | `D2-P1-1`..`D2-P1-4`, `D2-P2-1`..`D2-P2-3` |

## Análise de granularidade (A-01)

- `D2-P0-1` e `D2-P0-3` são atômicas (lógica pura + testes).
- `D2-P0-2` é ação maior coesa: fachada + persistência da decisão + UI + teste de arquitetura nascem juntos (é o Must do PRD; meia implementação não fecha o ciclo).
- `D2-P0-4` junta esqueleto + golden set porque o relatório é o próprio contrato do módulo.
- `T-1`/`T-2` são transversais; aqui ficam as partes do Dev 2 (a parte documental de `T-2a` é do Dev 1, feature `002`).

## Fase 1 — Higiene e gate (P0 transversal)

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| T-2a | Sanitizar erros do lado análise/UI: `LlmOutputError` nunca interpola `ValidationError` crua; `st.error` mostra tipo + estágio + IDs; teste anti-vazamento | - | `[//]` | `src/modules/policy_analysis/application/extraction.py`, `src/ui/app.py` | 🟢 | `[ ]` |
| T-1 | Gate local único documentado para os dois devs: `ruff` + `mypy` + `python -B -m pytest -q -p no:cacheprovider` (inclui `tests/architecture/` e E2E); marker `integration` segue registrado | - | `[//]` | `pyproject.toml`, documentação do ritual | 🟡 | `[ ]` |
| T-2b | Higiene mínima de artefatos: `exports/` com caminho fixo + aviso de retenção na UI; uploads temporários em diretório controlado com limpeza ao fim (escrita do upload está em `src/ui/app.py` — seu terreno) | - | `[//]` | `src/ui/app.py`, `src/modules/policy_analysis/application/comparison.py` | 🟡 | `[ ]` |

## Fase 2 — Guardas pós-LLM (P0)

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| D2-P0-1 | Ancoragem de citação (toda quote existe no texto do chunk citado; `value.raw_text`; múltiplas evidências = todas ancoradas) + `temperature=0` em extração/explicação; sem ancoragem → `LlmOutputError`, nunca `FOUND` | T-2a | - | `src/modules/policy_analysis/application/extraction.py`, `application/comparison.py`, `infrastructure/llm_extractors.py` | 🟢 | `[ ]` |
| D2-P0-3 | Regras mínimas por campo em `domain/` (`vigencia_inicio ≤ vigencia_fim`, valores > 0, moeda coerente, enums de `base_territorial`); falha → `NEEDS_REVIEW` | D2-P0-1 | `[//]` | `src/modules/policy_analysis/domain/catalog.py`, `domain/`, `tests/modules/policy_analysis/` | 🟢 | `[ ]` |

## Fase 3 — Revisão humana (P0 — Must do PRD §9)

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| D2-P0-2 | Loop **Confirmar / Corrigir valor / Registrar divergência** por campo (revisor, timestamp, valor original/corrigido, `EvidenceRef`) via `PolicyAnalysisFacade`, persistido; fato revisado alimenta a comparação. Fix mínimo da fachada: UI para de importar `infrastructure`/`domain` (F-15); `tests/architecture` passa a varrer `src/ui` | D2-P0-1, D2-P0-3 | - | `src/modules/policy_analysis/public_api.py`, `infrastructure/duckdb_repository.py`, `src/ui/app.py`, `tests/architecture/test_imports.py` | 🟢 | `[ ]` |

## Fase 4 — Medição (P0)

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| D2-P0-4 | Esqueleto do módulo `evaluation` (pacote + fachada mínima — exigido pela spec no slice) + golden set sintético 2 apólices × 10 campos = 20 casos (fixtures JSON) com relatório por campo (campo correto? evidência correta?); OQ-02 = substring; ressalva R1/R3 escrita no relatório | D2-P0-1, D2-P0-3 | - | `src/modules/evaluation/`, `tests/` (fixtures) | 🟢 | `[ ]` |

## Backlog da rodada (não executar agora — ver plano de ação)

| ID | Descrição | Quando |
|----|-----------|--------|
| D2-P1-1 | `Issue`/`QualityReport` aditivos a `requires_human_review` (que permanece no contrato) | P1 |
| D2-P1-2 | `UsageMetrics` local no adapter Gemini (tokens/latência/custo por run) — sem ModelGateway | P1 |
| D2-P1-3 | Coleta de apólices reais/anonimizadas (premissa R1/R3; dependência externa) | P1 |
| D2-P1-4 | UI estruturada + composition root (`src/composition_root/`) | P1 |
| D2-P2-1 | Fallback de explicação (template determinístico) | P2 |
| D2-P2-2 | Prompts versionados (hash/versão auditável) | P2 |
| D2-P2-3 | DuckDB defensivo (baseline `001` + migrações mínimas) | P2 |

## Checklist de encerramento (ritual — plano §5)

- [ ] Granularidade desta feature registrada aqui (feito no cabeçalho).
- [ ] Todo output de LLM tem teste de falha (saída inválida, citação inventada, campo fora do catálogo).
- [ ] Gate `T-1` verde 3× consecutivas; Musts do PRD relidos ao fechar escopo (F-16).
- [ ] Caixa postal usada para mudança de contrato (uma por vez); `requires_human_review` permanece.
- [ ] Nenhum texto de apólice em erro/UI (`T-2a`).
- [ ] Estado remoto checado (`gh pr list --state all`) antes do PR.
- [ ] `regression-watch.md` atualizado e `/reversa-sync` executado ao concluir (plano B: adendo manual).

## Histórico de alterações

| Data | Alteração | Autor |
|------|-----------|-------|
| 2026-09-26 | Versão inicial — ações P0 do Dev 2 derivadas de `plano-acao-dev2.md` v1.0 (pós-debate multiagente) | reversa |
