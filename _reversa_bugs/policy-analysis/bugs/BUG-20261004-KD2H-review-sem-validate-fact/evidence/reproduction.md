# Cápsula de reprodução (BUG-20261004-KD2H)

- Commit base: `1784ad9` (HEAD antes dos fixes de 2026-10-04; o estado de `review.py` não foi
  tocado por eles).
- Ambiente: Windows, Python 3.13.7 (C:\Python313), dependências vendoradas em `.tools/pylibs`.
- Comando: `$env:PYTHONPATH=".tools/pylibs;src"; python -B _reversa_bugs/policy-analysis/bugs/BUG-20261004-KD2H-review-sem-validate-fact/evidence/repro_kd2h.py`
- Execução de 2026-10-04 (ANTES do fix): exit code 0 com saída:

  `STATUS_FINAL: FOUND | RULE_VIOLATIONS: None`
  `DEFEITO CONFIRMADO: CORRIGIDO persistiu valor que viola regras (negativo + moeda desconhecida) sem ContractValidationError e sem guarda.`

  Experimento: extração rebaixa `limite_agregado` para `NEEDS_REVIEW` (EC-04) e a decisão
  humana `CORRIGIDO` grava `{"amount": "-100.00", "currency": "XYZ"}` — que viola
  `valor_positivo` (negativo) e `moeda_conhecida` (XYZ) — como `FOUND`, sem `ContractValidationError`
  e sem `rule_violations`.
- Script de reprodução preservado em `evidence/repro_kd2h.py` (reproduzível; espera guard ativa
  depois do fix).
- Corroboração estática: grep de `validate_fact` em
  `src/modules/policy_analysis/application/review.py` = zero ocorrências (ver
  `evidence/nota-actions-d2-p0-2.txt`).
- Classificação: deterministic (1/1).