# Registro de correções de registro — execução da feature dev2-003 (2026-10-04)

> Documento próprio, decidido pelo usuário em 2026-10-04 (fora do change set dos fixes
> BUG-20261004-YFN3/ODCS/KD2H). Finalidade: corrigir A FALSIDADE DOS REGISTROS de execução,
> sem mudar norma. As fontes normativas permanecem como estão; o que se corrige são frases
> que declararam execução inexistente.

## 1. `_reversa_sdd/addenda/dev2-003-p0-analise-experiencia.md` §6.1

- Afirmação: "erros sanitizados; regras por campo (`vigencia_ordem`, `valor_positivo`,
  moedas, `enum_base_territorial`) rebaixam fato inválido para `NEEDS_REVIEW`".
- Correção factual (2026-10-04): na data da entrega, `enum_base_territorial` NÃO existia em
  `domain/rules.py` (implementada hoje nos fixes); e a sanitização tinha a brecha do
  `ValidationError` interpolado em `application/extraction.py` (corrigida hoje). Ambos os
  comportamentos passaram a existir em 2026-10-04, via bugs BUG-20261004-ODCS e
  BUG-20261004-YFN3.
- Observação: o adendo não é editado (imutável); esta é a anotação de correção correspondente.

## 2. `_reversa_forward/dev2-003-p0-analise-experiencia/actions.md`, seção D2-P0-3

- Afirmação: lista "Regras implementadas" incluindo `enum_base_territorial`.
- Correção factual (2026-10-04): a regra não foi implementada naquela execução; foi
  implementada hoje (BUG-20261004-ODCS, `domain/rules.py`).
- Correção de nomenclatura: a nota trata `base_territorial` como `field_code`; o campo real
  do catálogo é `extensao_territorial` ("base territorial" só aparece em texto de
  documento). Mapeamento registrado na docstring de `domain/rules.py`.

## 3. `_reversa_forward/dev2-003-p0-analise-experiencia/actions.md`, seção D2-P0-2

- Afirmação: "Correção humana passa pelas regras do campo (`validate_fact`) como guarda
  contra erro de digitação: violação → `ContractValidationError` sanitizado ... nada é
  persistido."
- Correção factual (2026-10-04): a guarda não existia no código (`review.py` só normalizava);
  foi implementada hoje (BUG-20261004-KD2H). A norma descrita na nota foi mantida como
  comportamento desejado (decisão humana de 2026-10-04).
- Complemento da mesma decisão: `confirm` segue sem regras (revisor é autoridade final),
  exatamente como a nota já dizia.

## Origem e rastreabilidade

Achados convergentes do debate multiagente do BUG-20261004-ODCS (rodadas 1 e 2), verificados
no código e decididos pelo usuário em 2026-10-04. Bugs relacionados:
`BUG-20261004-YFN3`, `BUG-20261004-ODCS`, `BUG-20261004-KD2H`
(`_reversa_bugs/policy-analysis/bugs/`).