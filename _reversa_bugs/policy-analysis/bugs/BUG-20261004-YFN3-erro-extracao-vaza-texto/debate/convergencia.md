# Convergência por rodada (auditoria) — BUG-20261004-YFN3

Épocas fixas (N=3, R=2), sem early stopping. Métrica: quão próximas ficaram as propostas.

## Rodada 0 (independentes)

- 3/3 propostas válidas (quórum 2 de 3 exigido).
- Convergência ALTA no núcleo: as três propõem mensagem com tipo + `field_code` + contagem,
  sem `str(exc)`, e escopo cirúrgico no `except ValidationError` de `extraction.py`.
- Divergência real: encadeamento (`from exc` x `from None`) e profundidade da bateria de
  asserção (só `str` x `str`/`repr`/`to_dict`/`to_processing_status`/`traceback`).

## Rodada 1

- 3/3 válidas. Convergência MUITO ALTA: as três passam a defender `from None` e bateria ampla.
- Divergência residual: asserção de mecanismo (`__cause__`/`__suppress_context__`) e a
  variante "levantar fora do bloco `except`" (agente-3) para zerar o `__context__` residual.
- Correções factuais incorporadas: `errors.py` L41 interpola `{exc}` (seguro só por herança
  da mensagem limpa); ecos residuais em `llm_agent.py` L267 e `document_processing_source.py`
  L30 ficam como follow-up próprio, fora do change set.

## Rodada 2

- 3/3 válidas. Convergência TOTAL na correção de duas linhas: mensagem minimalista
  (tipo + `field_code` + `len(exc.errors())`), `from exc` vira `from None`, escopo cirúrgico.
- Divergências fechadas: (a) guarda mecanística nomeada no teste
  (`__cause__ is None and __suppress_context__`) como política, com o traceback formatado
  como prova preta; (b) a variante de reestruturar o try fica arquivada como plano B
  documentado (decisão explícita sobre o residual de `__context__`); (c) promoção de
  relação com BUG-20261004-ODCS retirada do fechamento (ruído de processo).

## Estado ao fim

Propostas finais prontas para o juiz (anonimizadas em `debate/juiz/propostas-anonimas.md`).
Métrica de saúde: convergência alta desde a época 0; custo por contribuição aceita deve ser
bom, pois o debate refinou testes e fechou a aresta do encadeamento em vez de reformular o fix.