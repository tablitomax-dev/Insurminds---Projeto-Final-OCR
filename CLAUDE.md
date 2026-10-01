# Reversa

> Framework de Engenharia Reversa instalado neste projeto.

## Como usar

Use o fluxo adequado no chat:

- `/reversa` — descobrir e documentar um sistema existente
- `/reversa-new` — criar PRD e specs para um projeto novo
- `/reversa-forward` — implementar ou evoluir código a partir das specs
- `/reversa-migrate` — planejar a migração de um sistema legado
- `/reversa-docs` — gerar o mini-site visual da documentação
- `/reversa-agents-help` — consultar o catálogo completo de agentes

## Comportamento ao ativar

Quando o usuário digitar `/reversa` ou a palavra `reversa` sozinha em uma mensagem:

1. Ative o skill `reversa` disponível em `.claude/skills/reversa/SKILL.md`
2. Se não encontrar em `.claude/skills/`, tente `.agents/skills/reversa/SKILL.md`
3. Leia o SKILL.md na íntegra e siga exatamente as instruções do Reversa

## Regra não-negociável

Por padrão, nunca apague, modifique ou sobrescreva arquivos pré-existentes do projeto legado:
o Reversa escreve apenas em `.reversa/`, `_reversa_sdd/`, `_reversa_docs/`, `_reversa_forward/`, `_reversa_bugs/` e `_reversa_refactor/`.
A única exceção é a política configurável abaixo, controlada exclusivamente pelo usuário.

Antes de criar, modificar ou apagar qualquer arquivo fora das pastas próprias do Reversa, leia `.reversa/reversa-config.json` e obedeça ao resultado:

- Arquivo ausente, JSON inválido ou campo com tipo errado: trate como `allowLegacyEdits: false` (falha segura, nenhuma escrita fora das pastas do Reversa).
- `allowLegacyEdits: false`: recuse a escrita, informando o caminho recusado, o estado atual da config e o que o usuário deve editar para liberar.
- `allowLegacyEdits: true` com `allowedPaths` não vazio: escreva apenas em caminhos que casem com algum glob da lista (globs relativos à raiz do projeto, com `/`, suportando `*` e `**`).
- `allowLegacyEdits: true` com `allowedPaths` vazio ou ausente: projeto liberado; avise uma vez por sessão que a liberação é irrestrita.

Nunca crie nem edite `.reversa/reversa-config.json` por iniciativa própria: pedido na conversa não é liberação implícita, alterações nesse arquivo são ato exclusivo do usuário.

## Regras perpétua (entregas e documentos)

O texto completo das regras perpétua — **registro detalhado em commits/PRs** (§5.6) e **gestão de documentos normativos** (§5.7) — vive em `_reversa_sdd/learning/aprendizados.md` §5, que é a **fonte canônica**. Este arquivo guarda só bootstrap e ponteiro: nunca duplique texto de regra aqui.

- **Cláusula de desempate:** havendo divergência do mesmo assunto entre este arquivo e `_reversa_sdd/learning/aprendizados.md`, **prevalece `aprendizados.md`**. O protocolo de colaboração Dev 1 × Dev 2 (PRs mergeáveis + cascata de decisão) vive em [`_reversa_sdd/learning/protocolo-colaboracao-dev1-dev2.md`](./_reversa_sdd/learning/protocolo-colaboracao-dev1-dev2.md).
- Resumo operacional (não normativo): todo commit, push e PR registra histórico detalhado — arquivos/trechos modificados, funcionalidades, passos anti-conflito de merge e relatório de zonas compartilhadas; cada entrega publica handoff em `_reversa_sdd/learning/handoffs/`.
