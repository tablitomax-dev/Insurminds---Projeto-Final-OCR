# Cápsula de reprodução (BUG-20261004-ODCS)

- Commit base: `1784ad9` (docs(fechamento): PRs #12 e #13 mesclados e validados no main).
- Ambiente: Windows, Python 3.13.7 (C:\Python313), pytest 8.4.2; dependências vendoradas em
  `.tools/pylibs` (PYTHONPATH=".tools/pylibs").
- Comando: `python -B -m pytest tests/modules/policy_analysis/test_extraction_agent.py tests/modules/policy_analysis/test_rules.py -q -p no:cacheprovider`
- Execução de 2026-10-04 (ANTES do fix): exit code 1, `7 failed, 43 passed`. Do defeito:
  `test_enum_base_territorial_rejeita_fora_do_enum` (4 casos: "Atlântico Norte", "Global",
  "mundial exceto brasil", "Estados Unidos e Canadá" retornam `[]` de violações),
  `test_enum_base_territorial_motivo_nunca_traz_o_valor` (IndexError: sem violação) e
  `test_enum_rebaixa_found_para_needs_review_no_servico` (fato sai `FOUND` em vez de
  `NEEDS_REVIEW`).
- Execução de 2026-10-04 (DEPOIS do fix): exit code 0, `50 passed` nos dois arquivos;
  suíte completa `346 passed, 4 skipped`; ruff e mypy limpos.
- Classificação: deterministic (1/1); sem `enum_base_territorial` em `validate_fact`, qualquer
  texto em `extensao_territorial` mantém `FOUND`.