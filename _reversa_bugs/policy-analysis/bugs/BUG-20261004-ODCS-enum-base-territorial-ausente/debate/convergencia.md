# Convergência por rodada (auditoria) — BUG-20261004-ODCS

Épocas fixas (N=3, R=2), sem early stopping. Métrica: quão próximas ficaram as propostas.

## Rodada 0 (independentes)

- 3/3 propostas válidas (quórum 2 de 3 exigido).
- Convergência ALTA: as três propõem regra `enum_base_territorial` mirando o campo real
  `extensao_territorial`, enum fechado, rebaixamento FOUND → NEEDS_REVIEW com motivo
  sanitizado, e recomendam `spec-correta`.
- Divergências: camada da normalização (quem decide o aceite, `normalize_text` x valor pronto)
  e alcance do enum (aliases compostos, "Global").

## Rodada 1

- 3/3 válidas. Convergência MUITO ALTA nas 4 decisões centrais (nome, enum, rebaixamento,
  veredito).
- Achado novo convergente: segundo registro de execução falso no D2-P0-2 (as notas afirmam
  `validate_fact` na correção humana, mas `application/review.py` só normaliza).
- Divergência residual: destino da correção humana (guarda x "escape do revisor") e rótulo de
  "Global" (valor legítimo x sinônimo fora do enum).

## Rodada 2

- 3/3 válidas. Convergência TOTAL no comportamento: normalização defensiva via
  `normalize_text` antes da comparação, igualdade EXATA do token normalizado (nunca
  substring), dispatch por `field.code`, disparo só em FOUND com normalizado não nulo.
- Divergências fechadas: (a) "Global" e compostos legítimos ficam FORA do enum e rebaixam
  como sinal de revisão (ampliação de aliases só por adendo, nunca por substring); (b) a
  divergência do D2-P0-2 vira registro próprio, fora do change set deste fix; (c) correções
  de registro (frase do adendo §6.1, nota "Regras implementadas" do actions.md, mapeamento
  `base_territorial` x `extensao_territorial`) são documentais, não normativas.

## Estado ao fim

Propostas finais prontas para o juiz (anonimizadas em `debate/juiz/propostas-anonimas.md`).
Métrica de saúde: convergência alta desde a época 0; o debate refinou a semântica e descobriu
a segunda divergência código x spec em vez de reformular a leitura.