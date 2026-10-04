# Handoff de fechamento — bugs do `policy_analysis` (2026-10-04)

> **Autor:** sessão de fechamento de bugs (pbena + assistente) · **Destinatário:** Dev 2 (dono do
> quadrado `policy_analysis`) e Dev 1 (leitura de impacto)
> **Branch:** `main` (sem branch feature; correções fechadas em sessão única, push/PR pendentes
> do ambiente com `gh` autenticado)
> **Gate `T-1`:** verde no fechamento — `ruff` All checks passed · `mypy` Success (68 arquivos) ·
> `pytest` **349 passed, 4 skipped**.

## 1. Escopo

Fechamento das 2 correções em aberto identificadas na auditoria de 2026-10-04, mais 1 bug
descoberto no debate. Registro completo em `_reversa_bugs/policy-analysis/` (3 bugs, todos
`resolved · fixed · spec-correta`, com `DONE.md`):

| Bug | Defeito | Fix |
|-----|---------|-----|
| `BUG-20261004-YFN3` (P0) | `application/extraction.py` interpolava o `ValidationError` cru e ecoava texto de apólice em mensagem de erro/log (T-2a) | mensagem sanitizada (tipo + quantidade + `field_code`) + `from exc` → `from None` |
| `BUG-20261004-ODCS` (P1) | regra `enum_base_territorial` (D2-P0-3) nunca implementada; texto qualquer passava como `FOUND` | regra nova em `domain/rules.py` (enum fechado, igualdade exata pós-normalização) |
| `BUG-20261004-KD2H` (P2) | notas do D2-P0-2 declaravam `validate_fact` na correção humana, mas `review.py` não chamava | guarda no ramo `CORRIGIDO` (violação = `ContractValidationError` sanitizado, nada persistido) |

Processo: rota expressa do `/reversa-debugger` + debate multiagente (repair + spec, N=3 × R=2 +
juiz isolado) + `/reversa-debugger-fix` com prova vermelho → verde por bug. Veredito de spec
humano: `spec-correta` nos três (specs intactas, sem adendos).

## 2. Arquivos e trechos modificados (§5.6-b)

Código (quadrado do Dev 2):
- `src/modules/policy_analysis/application/extraction.py` — `_build_fact`, `except ValidationError`
  da linha do `ExtractedFact.model_validate`: mensagem vira tipo + `len(exc.errors())` +
  `field_code`; `raise ... from None`.
- `src/modules/policy_analysis/domain/rules.py` — novo `_rule_enum_base_territorial` +
  `_fold_text` + consts `_ENUM_FIELD_CODES`/`_TERRITORY_ENUM` (13 tokens); wiring em
  `validate_fact`; docstring atualizado com o mapeamento `base_territorial` (nome da spec) ×
  `extensao_territorial` (campo real).
- `src/modules/policy_analysis/application/review.py` — `ReviewService.record_decision`, ramo
  `CORRIGIDO`: `validate_fact` após `normalize_value`; violação → `ContractValidationError`
  sanitizado antes de `repo.record_review` (nada persistido). Novos imports
  (`shared_kernel.errors.ContractValidationError`, `..domain.rules.validate_fact`).

Testes:
- `tests/modules/policy_analysis/test_extraction_agent.py` — `test_erro_de_schema_nao_ecoa_texto_de_apolice`
  (anti-vazamento: str/repr/to_dict/to_processing_status/traceback + guarda `__cause__`).
- `tests/modules/policy_analysis/test_rules.py` — 4 testes do enum (aceita, rejeita, motivo
  sem o valor, não alcança `exclusoes_chave`) + 2 de integração (rebaixa FOUND / mantém FOUND válido).
- `tests/modules/policy_analysis/test_review_queue.py` — 3 testes da guarda (rejeição sem
  persistir, moeda inválida, `CONFIRMADO` sem regras).

Registro (Reversa):
- `_reversa_bugs/` — bootstrap (`README.md`, `taxonomy.yaml`) + `policy-analysis/` inteiro
  (3 bugs com evidence/, debate/, fix/, DONE.md; views em `generated/`).
- `_reversa_forward/dev2-003-p0-analise-experiencia/registro-correcoes-20261004.md` — documento
  próprio com as correções de registro (adendo §6.1, "Regras implementadas", D2-P0-2, nomes).
- `_reversa_sdd/traceability/bugs.md` — espelho BUG ↔ SPEC.

## 3. Funcionalidades (§5.6-c)

1. Erros de validação de saída de LLM nunca mais ecoam texto de apólice (T-2a fechada no caminho
   do `ClassifiedError`).
2. `extensao_territorial` fora do enum fechado rebaixa `FOUND` → `NEEDS_REVIEW` com
   `rule_violations` sanitizado; valores dos fixtures/golden set (Mundial, Brasil, Canadá,
   Estados Unidos...) continuam aceitos.
3. Correção humana (`CORRIGIDO`) agora tem guarda de digitação: valor que viola regra é
   rejeitado sem persistir; `CONFIRMADO` permanece autoridade (sem regras).

## 4. Anti-conflito de merge (§5.6-d)

Quem for trabalhar nas mesmas seções, nesta ordem:
1. Rebase antes de codar (`git fetch` + `git rebase main`); os 3 fixes tocaram só
   `src/modules/policy_analysis/{application,domain}` e `tests/modules/policy_analysis/`.
2. `application/extraction.py`: conflito provável apenas no `except ValidationError` de
   `_build_fact` (~L135). Preserve a mensagem sanitizada e o `from None`.
3. `domain/rules.py`: regras novas entram como função `_rule_*` + entrada em `validate_fact`;
   mantenha `_ENUM_FIELD_CODES` como dispatch (nunca por `FieldType.TEXT`, pegaria
   `exclusoes_chave`).
4. `application/review.py`: a guarda fica entre `normalize_value` e `repo.record_review` no ramo
   `CORRIGIDO`; não mova para `CONFIRMADO`.
5. Testes: os nomes novos são contrato do fix (`test_erro_de_schema_nao_ecoa_texto_de_apolice`,
   `test_enum_*`, `test_corrigido_com_*`, `test_confirm_nao_recebe_regras`).
6. Gate `T-1` antes de qualquer PR: `$env:PYTHONPATH=".tools;.tools/pylibs"` +
   `python -B -m pytest -q -p no:cacheprovider` + `.tools/bin/ruff.exe check .` +
   `python -B -m mypy src` (ambiente Windows/sandbox — Apêndice A).

## 5. Zonas compartilhadas (§5.6-e)

- **`shared_kernel/contracts`: INTACTO.** Nenhum campo, versão ou contrato mudou
  (`CONTRACTS_VERSION` não mexeu). O único uso novo é leitura de
  `shared_kernel.errors.ContractValidationError` em `review.py` (erro de contrato existente).
- **Payload do Qdrant / `ChunkMetadata` / `EvidenceRef`:** sem toque (quadrado do Dev 1).
- **DuckDB:** sem mudança de schema (guarda é pré-persistência).
- **Vocabulário de erros:** mensagens seguem T-2a (tipo/estágio/IDs + quantidade); o motivo de
  regra continua só com regra/campo.
- **UI:** sem toque (a UI já sanitizava mensagens; agora o erro já nasce limpo).

## 6. Fechamento

- 3 bugs travados com `DONE.md`; views e espelho regenerados; registro de correções documentais
  publicado. Itens de manutenção futura registrados nos bugs (renomear
  `test_texto_nao_recebe_regras_de_valor`, aliases compostos do enum, ecos residuais de
  `str(exc)` em `llm_agent.py`/`document_processing_source.py`).
- Pendente de ambiente: `push`/PR para o remoto (`gh` sem `GH_TOKEN` nesta máquina); quando
  publicar, o corpo do PR copia as seções 2–5 deste handoff (regra perpétua §5.6).