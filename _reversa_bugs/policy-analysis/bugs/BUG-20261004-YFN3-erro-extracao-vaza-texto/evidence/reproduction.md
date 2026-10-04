# Cápsula de reprodução (BUG-20261004-YFN3)

- Commit base: `1784ad9` (docs(fechamento): PRs #12 e #13 mesclados e validados no main).
- Ambiente: Windows, Python 3.13.7 (C:\Python313), pytest 8.4.2; dependências vendoradas em
  `.tools/pylibs` (PYTHONPATH=".tools/pylibs").
- Comando: `python -B -m pytest tests/modules/policy_analysis/test_extraction_agent.py tests/modules/policy_analysis/test_rules.py -q -p no:cacheprovider`
- Execução de 2026-10-04 (ANTES do fix): exit code 1, `7 failed, 43 passed`. O teste
  `test_erro_de_schema_nao_ecoa_texto_de_apolice` reproduz o defeito: a falha mostra o marcador
  `TEXTO-CONFIDENCIAL-APOLICE-XYZ` DENTRO da mensagem do `ClassifiedError`
  ("...: 1 validation error for ExtractedFact ... input='TEXTO-CONFIDENCIAL-APOLICE-XYZ' ...").
- Execução de 2026-10-04 (DEPOIS do fix): exit code 0, `50 passed` nos dois arquivos;
  suíte completa `346 passed, 4 skipped`; ruff e mypy limpos.
- Classificação: deterministic (1/1); o caminho `ValidationError` no `ExtractedFact.model_validate`
  sempre ecoa o input do Pydantic na mensagem enquanto `str(exc)` for interpolado.