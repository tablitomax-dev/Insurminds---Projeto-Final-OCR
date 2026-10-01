# Actions: P0 do Desenvolvedor 2 — Análise e Experiência

> Identificador: `dev2-003-p0-analise-experiencia`
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
| T-2a | Sanitizar erros do lado análise/UI: `LlmOutputError` nunca interpola `ValidationError` crua; `st.error` mostra tipo + estágio + IDs; teste anti-vazamento | - | `[//]` | `src/modules/policy_analysis/application/extraction.py`, `src/ui/app.py` | 🟢 | `[X]` (parte 1: lado análise; parte 2: `st.error`/UI) |
| T-1 | Gate local único documentado para os dois devs: `ruff` + `mypy` + `python -B -m pytest -q -p no:cacheprovider` (inclui `tests/architecture/` e E2E); marker `integration` segue registrado | - | `[//]` | `pyproject.toml`, documentação do ritual | 🟡 | `[X]` |
| T-2b | Higiene mínima de artefatos: `exports/` com caminho fixo + aviso de retenção na UI; uploads temporários em diretório controlado com limpeza ao fim (escrita do upload está em `src/ui/app.py` — seu terreno) | - | `[//]` | `src/ui/app.py`, `src/modules/policy_analysis/application/comparison.py` | 🟡 | `[X]` |

## Fase 2 — Guardas pós-LLM (P0)

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| D2-P0-1 | Ancoragem de citação (toda quote existe no texto do chunk citado; `value.raw_text`; múltiplas evidências = todas ancoradas) + `temperature=0` em extração/explicação; sem ancoragem → `LlmOutputError`, nunca `FOUND` | T-2a | - | `src/modules/policy_analysis/application/extraction.py`, `application/comparison.py`, `infrastructure/llm_extractors.py` | 🟢 | `[X]` |
| D2-P0-3 | Regras mínimas por campo em `domain/` (`vigencia_inicio ≤ vigencia_fim`, valores > 0, moeda coerente, enums de `base_territorial`); falha → `NEEDS_REVIEW` | D2-P0-1 | `[//]` | `src/modules/policy_analysis/domain/catalog.py`, `domain/`, `tests/modules/policy_analysis/` | 🟢 | `[X]` |

## Fase 3 — Revisão humana (P0 — Must do PRD §9)

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| D2-P0-2 | Loop **Confirmar / Corrigir valor / Registrar divergência** por campo (revisor, timestamp, valor original/corrigido, `EvidenceRef`) via `PolicyAnalysisFacade`, persistido; fato revisado alimenta a comparação. Fix mínimo da fachada: UI para de importar `infrastructure`/`domain` (F-15); `tests/architecture` passa a varrer `src/ui` | D2-P0-1, D2-P0-3 | - | `src/modules/policy_analysis/public_api.py`, `infrastructure/duckdb_repository.py`, `src/ui/app.py`, `tests/architecture/test_imports.py` | 🟢 | `[X]` |

## Fase 4 — Medição (P0)

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| D2-P0-4 | Esqueleto do módulo `evaluation` (pacote + fachada mínima — exigido pela spec no slice) + golden set sintético 2 apólices × 10 campos = 20 casos (fixtures JSON) com relatório por campo (campo correto? evidência correta?); OQ-02 = substring; ressalva R1/R3 escrita no relatório | D2-P0-1, D2-P0-3 | - | `src/modules/evaluation/`, `tests/` (fixtures) | 🟢 | `[X]` |

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

## Gate `T-1` (comando único — rodar antes de todo PR)

```powershell
ruff check . && mypy src && python -B -m pytest -q -p no:cacheprovider
```

- No PowerShell 5.1 (sem `&&`): `ruff check .; mypy src; python -B -m pytest -q -p no:cacheprovider`.
- Configuração pragmática em `pyproject.toml`: `[tool.ruff]` (E,F,I; line-length 120;
  `known-first-party = ["fakes", "modules", "shared_kernel"]`; per-file-ignores para
  `src/shared_kernel/**` congelado e `src/modules/document_processing/**` terreno do Dev 1)
  e `[tool.mypy]` (`ignore_missing_imports = true`, sem strict; override para
  `modules.document_processing.*` enquanto o Dev 1 não limpa as pendências de tipagem dele).
- Execução neste sandbox: `pip install --user ruff mypy` é **bloqueado** (escrita fora do
  projeto); as ferramentas foram instaladas em `.tools/` (gitignored) e o gate roda como
  `.\.tools\bin\ruff.exe check .` + `python -B -m mypy src` com `PYTHONPATH=.tools`. Com as
  ferramentas no PATH do ambiente, vale o comando único acima.

## Checklist de encerramento (ritual — plano §5)

- [X] Granularidade desta feature registrada aqui (feito no cabeçalho).
- [X] Todo output de LLM tem teste de falha (saída inválida, citação inventada, campo fora do catálogo).
- [X] Gate `T-1` verde 3× consecutivas; Musts do PRD relidos ao fechar escopo (F-16).
- [X] Caixa postal usada para mudança de contrato (uma por vez); `requires_human_review` permanece. — nenhuma mudança de contrato nesta rodada (shared_kernel intocado).
- [X] Nenhum texto de apólice em erro/UI (`T-2a`).
- [ ] Estado remoto checado (`gh pr list --state all`) antes do PR. — pendente no momento do PR (encerramento local desta rodada).
- [ ] `regression-watch.md` atualizado e `/reversa-sync` executado ao concluir (plano B: adendo manual). — pendente no momento do PR.

## Notas de execução

> Execução de 2026-09-26 — parte 1 (guardas pós-LLM): `T-2a` (lado análise) + `D2-P0-1` + `D2-P0-3`.
> Gate: `python -B -m pytest -q -p no:cacheprovider` verde 3× consecutivas — **204 passed, 4 skipped** (baseline era 173/4; +31 testes).

### T-2a — sanitização de erro (lado análise)

- `LlmOutputError` deixou de interpolar o `ValidationError` do Pydantic (que ecoa o `input` e podia vazar texto de apólice). Formato da mensagem: prefixo de estágio (`EXTRACT:`/`EXPLAIN:`), tipo do erro, nomes dos campos problemáticos (nome, nunca valor) e IDs.
- IDs e nomes passam por filtro de padrão (`_safe_id`/`_FIELD_NAME_PATTERN`): token fora do padrão (ex.: `evidence_id` inventado com texto de apólice) é substituído por `<id omitido>`; chaves inventadas que vazam pelo `loc` do Pydantic caem em `(modelo)`.
- Sanitização estendida aos erros do adapter (`infrastructure/llm_extractors.py`): `str(exc)` → `type(exc).__name__` (regra "nunca interpolar exceção crua").
- Testes anti-vazamento: input com `"Limite agregado R$ 1.000.000"` em `value.raw_text`, em chave inventada e em `evidence_id` — nenhum caso ecoa o texto na mensagem.
- Alternativa descartada: manter `str(exc)`/`exc.errors()[...]["msg"]` (ambos podem conter o input); nada de UI aqui — `st.error` fica para a parte 2.

### D2-P0-1 — ancoragem de citação + temperature 0

- Função pura nova em `domain/anchoring.py`: `collect_excerpts` (trechos literais sob as chaves `raw_text`, `excerpt`, `quote`, `quoted_text`, `cited_text`, `trecho` de `value`/`normalized_value` — escalares não são citação), `unanchored_excerpts` (substring **literal** após trim de bordas — OQ-02 = substring, sem semelhança difusa) e `extract_quoted_segments` (trechos entre aspas de texto livre).
- Âncora = união dos textos (`EvidenceRef.quoted_text`) das evidências **citadas** no fato; com múltiplas evidências, TODAS as citações são ancoradas — uma citação inválida rejeita o output inteiro. `FOUND` sem nenhum trecho literal também é rejeitado ("sem ancoragem nunca vira FOUND").
- Sem ancoragem → `LlmOutputError` (nada é persistido); EC-05 segue intacto (evidência obrigatória fora de `NOT_FOUND`, `evidence_ids` ⊆ recebidos).
- Explicação (`explain_difference`): toda citação literal entre aspas do texto deve ser substring dos textos recuperados dos dois lados (união de `evidences_a` + `evidences_b`); a validação de IDs citados dos dois lados continua como estava. Mensagem de erro traz só quantidade, nunca o texto.
- `temperature = 0.0` (`LLM_TEMPERATURE` + `ModelSettings`) nos dois agentes Pydantic AI (extração e explicação); prompts reforçam cópia literal em `raw_text` e aspas só para trechos reais.
- Alternativas descartadas: retorno estruturado de quotes na porta `ExplanationGenerator` (mudaria a porta/fachada consumida pela UI da parte 2 — fica para um caixa-postal MINOR se necessário); ancoragem por semelhança (OQ-02 decidiu substring); ancoragem só em `FOUND` (qualquer excerpt, inclusive de `AMBIGUOUS`/`NEEDS_REVIEW`, é ancorado — revisor não recebe citação inventada).

### D2-P0-3 — regras mínimas por campo

- Novo `domain/rules.py` (puro e determinístico — A-08), com `RuleViolation(rule, field_code, reason)` e `validate_fact(spec, fact, others)`. Regras implementadas:
  - `valor_positivo` — campos `numeric` (limites e franquia): escalar > 0;
  - `moeda_conhecida` — campos monetários: `currency` declarada ∈ {BRL, USD, EUR, GBP, JPY, CAD, CHF, AUD} (ISO 4217 usual em D&O);
  - `moeda_consistente` — campos monetários da mesma apólice com a mesma moeda (regra cruzada via `others`);
  - `enum_base_territorial` — `base_territorial` ∈ enum fechado (brasil, eua/estados unidos, canadá, europa, américa latina, américa do sul, américa do norte, mundo/mundial/worldwide, internacional, exterior);
  - `vigencia_ordem` — `vigencia_inicio <= vigencia_fim` (regra cruzada; dispara quando o par está completo e ambos os lados são datas legíveis — a ordem é avaliada sobre o escalar ISO).
- Falha → fato rebaixado para `NEEDS_REVIEW` + `requires_human_review=True` + motivo registrado em `value["rule_violations"]` (o contrato v1.0.0 não tem campo de motivo; `Issue` é aditivo e fica para `D2-P1-1`). Motivos citam só regra/campo — nunca o valor (T-2a).
- Limites assumidos: `NOT_FOUND` não recebe regras; data ilegível não dispara `vigencia_ordem` (só a ordem entra aqui); a semântica de comparação não foi alterada (fato `NEEDS_REVIEW` ainda participa da comparação — decisão do loop de revisão, parte 2).

### Ajustes em fakes/E2E (guarda nunca desligada)

- Fatos FOUND que passam pelo `ExtractionService` nos testes passaram a citar trechos reais dos chunks fake (`"Trecho da apólice"` = `quoted_text` do `make_evidence`) em `value.raw_text`.
- E2E: o fato AMBIGUOUS de `prazo_notificacao` citava `"prazo nao claro na apólice"` (inventado); o fake passou a citar o trecho literal do chunk (`"Prazo de notificação: 30 dias."`). Nenhuma guarda foi relaxada.

> Execução de 2026-09-26 — parte 2 (revisão humana, avaliação, gate e higiene): `D2-P0-2` + `D2-P0-4` + `T-1` + `T-2b` + `T-2a` (UI).
> Gate: `ruff check .` + `mypy src` + `python -B -m pytest -q -p no:cacheprovider` verde 3× consecutivas — **233 passed, 4 skipped** (baseline da parte 1 era 204/4; +29 testes).

### D2-P0-2 — loop de revisão humana + fix da fachada na UI

- Novos `domain/review.py` (puro: `ReviewDecision`, `apply_review`) e `application/review.py` (`HumanReviewService`); a porta `FactRepository` ganhou `save_review`/`list_reviews`, com tabela `reviews` no DuckDB (auditoria: revisor, timestamp, valor original/corrigido, evidências) e memória no fake.
- Ações **Confirmar / Corrigir valor / Registrar divergência** via fachada (`confirm_fact`/`correct_fact`/`register_divergence`, mais `list_review_decisions` para rastreabilidade). Toda decisão fica ligada a um `EvidenceRef` **persistido** (evidence_id sem lastro é rejeitado); `correct` exige evidência sempre — inclusive sobre `NOT_FOUND`.
- **Semântica do valor revisado na comparação (decisão registrada):** o valor efetivo é o **valor revisado** — `confirm` aceita o cru como está (vira `FOUND`), `correct` substitui o cru pelo corrigido (normalizado recalculado, `fact_id` estável, original preservado na decisão). **Antes de qualquer decisão humana, `NEEDS_REVIEW`/`AMBIGUOUS` continua comparando o valor cru** (decisão registrada: mudar exigiria campo de revisão no contrato v1.0.0 — fora da caixa postal desta rodada). `divergence` **não altera o fato** (segue na fila, pendente de correção) e fica registrado para auditoria.
- Correção humana passa pelas regras do campo (`validate_fact`) como guarda contra erro de digitação: violação → `ContractValidationError` sanitizado (só regra/campo, nunca o valor) e nada é persistido. `confirm` **não** recebe regras — o revisor é a autoridade final sobre o valor documentado (é para isso que a fila existe).
- **Fix F-15:** `src/ui/app.py` deixou de importar `policy_analysis.infrastructure.*` e `policy_analysis.domain.*`; a fachada expõe `list_fields()`, `normalize_field_value()`, `get_evidence()` e `create_document_processing_retriever(document_processing)` (monta o retriever internamente) e reexporta `LlmOutputError`. `tests/architecture/test_imports.py` passou a varrer `src/ui` (só `modules.<mod>.public_api`) e a cobrir `evaluation`.
- UI: seção 4 com a fila `AMBIGUOUS`/`NEEDS_REVIEW`, os três botões por fato (Confirmar/Corrigir/Registrar) e tabela das decisões registradas. E2E `tests/e2e/test_review_cycle.py` prova o ciclo completo: `NEEDS_REVIEW` → corrigido → registrado (revisor/timestamp/originais/EvidenceRef) → comparação usa o valor revisado (o mesmo teste documenta o "antes" — valor cru ainda comparado).
- Alternativas descartadas: colunas de revisão na tabela `facts` (tabela separada preserva o valor original e a auditoria); tipo novo `ReviewOutcome` (usada tupla `(fato, decisão)`); `divergence` como "campo não comparável" via `NOT_FOUND` (mentiria a semântica do contrato — a leitura da spec §11 "registra ausência da comparação" fica para o `Issue` aditivo `D2-P1-1`); exigir ancoragem literal na correção humana (o revisor corrige exatamente o que o OCR errou — o lastro é o `EvidenceRef`).

### D2-P0-4 — esqueleto do `evaluation` + golden set sintético

- Pacote novo `src/modules/evaluation/` no padrão dos demais: `domain/models.py` (Pydantic versionado: `ReferenceCase`/`ExpectedFact`/`EvaluationEntry`/`EvaluationReport`), `domain/matching.py` (regras de acerto puras), `application/ports.py` (`PolicyAnalysisPort` — recorte da fachada), `application/runner.py` (`EvaluationService`) e `public_api.py` (`EvaluationFacade.run_evaluation(reference_set) -> report`, `create_evaluation`, `load_reference_set`, `GOLDEN_SET_PATH`). Só a fachada do `policy_analysis` é consumida (teste de arquitetura cobre).
- Golden set em `src/modules/evaluation/fixtures/golden_set.json`: **2 apólices sintéticas (BRL e USD) × 10 field_code = 20 casos**, cada caso com texto sintético em chunks, valor esperado e citação esperada por campo. A suíte executa a extração pela fachada com `ScriptedLlmExtractor` injetado (fakes determinísticos em `tests/fakes/policy_analysis.py`) — sem custo de LLM real.
- Relatório por campo responde **campo correto?** (igualdade exata de escalar numérico; **substring literal** em texto/data — OQ-02 = **substring (ancoragem literal)**, registrado no JSON da referência e no relatório) e **evidência correta?** (citação esperada ancorada nos textos das evidências citadas). Divergência sempre traz esperado × extraído; extração sinalizada vira `inconclusivo` (EC-03) e falha externa vira `nao_avaliado` (EC-02), nunca erro de extração.
- `run_id` determinístico (sha256 da referência — mesma entrada, mesmo relatório em entradas/totais; `generated_at` é só carimbo de auditoria). O relatório é gravado em `exports/evaluation/evaluation_<run_id>.json` e carrega a ressalva obrigatória: "golden set sintético mede regressão; NÃO valida R1/R3 do PRD (formatos por seguradora) — validação com apólices reais/anonimizadas pendente (D2-P1-3)".
- Alternativas descartadas: materializar o esperado como "apólice de referência" e usar `compare_policies` (misturaria avaliação com persistência de fatos e mudaria a semântica de `direction`); LLM-as-judge (NG-01); duplicar a regra de substring (a normalização é reusada via fachada `normalize_field_value` — só o critério de acerto mora no `evaluation`).
- Fora: baterias em CI (NG-02), dado real (D2-P1-3), avaliação de OCR (OQ-03).

### T-1 — gate local de qualidade

- Comando único documentado na seção "Gate `T-1`" acima; `pyproject.toml` com `[tool.ruff]` (E,F,I, line-length 120) e `[tool.mypy]` (`ignore_missing_imports`, sem strict) pragmáticos. Correções triviais apenas: import não usado (`ExtractedFact` em `application/comparison.py`), ordem de imports (auto-fix) e 3 linhas >120 — **nenhuma refatoração em massa**.
- Resultado: gate **verde 3× consecutivas** (`ruff: All checks passed!` · `mypy: no issues found in 45 source files` · `pytest: 233 passed, 4 skipped`).
- Execução condicionada: `pip install --user ruff mypy` é **bloqueado pelo sandbox** (escrita fora do projeto); as ferramentas rodaram a partir de `.tools/` (gitignored). Os `per-file-ignores`/override para `src/modules/document_processing/**` cobrem pendências do terreno do Dev 1 (ordem de imports em `indexing.py` e tipagens de `service.py`/`indexing.py`) e devem sair quando ele corrigir.

### T-2b — higiene de artefatos + `st.error`

- `exports/` é caminho fixo e documentado (`EXPORT_DIR` na UI + aviso de retenção ao lado do botão de exportar: o arquivo fica no disco até exclusão manual — dado confidencial). `.gitignore` ganhou `.tmp/`, `exports/` e `.tools/`.
- Uploads temporários saíram de `%TEMP%\apolice_*` para `.tmp/uploads/` (diretório controlado do projeto, nome de arquivo seguro contra traversal) com `cleanup_uploads` ao fim do processamento — `tests/ui/test_uploads.py` prova que nada persiste depois do fluxo.
- `st.error` sanitizado por `src/ui/errors.py::sanitize_error_message(estágio, erro)`: tipo + estágio + detalhe só para exceções do projeto (mensagem já construída/filtrada); `ValidationError`/exceção crua vira apenas o tipo — teste anti-vazamento em `tests/ui/test_error_sanitization.py` com texto de apólice no input. Complementa a `T-2a` (nenhum caminho da UI ecoa `str(exc)` de exceção não confiável).

### Fora desta execução (registro)

- Backlog `D2-P1-*`/`D2-P2-*` (Issue/QualityReport, UsageMetrics, apólices reais, composition root, fallback de explicação, prompts versionados, DuckDB defensivo).
- Remoção dos desvios de lint/typing do `document_processing` (per-file-ignores do ruff e override do mypy) — manutenção do Dev 1.
- Estado remoto (`gh pr list --state all`), `regression-watch.md` e `/reversa-sync` ficam para o momento do PR (ritual §5).

## Histórico de alterações

| Data | Alteração | Autor |
|------|-----------|-------|
| 2026-09-26 | Versão inicial — ações P0 do Dev 2 derivadas de `plano-acao-dev2.md` v1.0 (pós-debate multiagente) | reversa |
| 2026-09-26 | Parte 1 executada: `T-2a` (lado análise), `D2-P0-1` e `D2-P0-3` concluídos (guardas pós-LLM); notas de execução adicionadas | dev2 |
| 2026-09-26 | Parte 2 executada: `T-2a` (`st.error`/UI), `T-2b` e `T-1` concluídos (higiene e gate local documentado) | dev2 |
| 2026-09-26 | Parte 3 executada: `D2-P0-2` (loop de revisão humana via fachada) e `D2-P0-4` (módulo `evaluation` + golden set) concluídos | dev2 |
