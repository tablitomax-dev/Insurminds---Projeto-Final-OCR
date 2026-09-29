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

## Regra perpétua de entregas (commits, PRs e pushes) — Dev 2

**Vigor permanente, a partir de 2026-09-29, definida pelo usuário.** Todo commit, push ou Pull Request do Dev 2 DEVE incluir, nos campos de comentário (corpo do commit / descrição do PR / arquivo de handoff), um histórico detalhado contendo obrigatoriamente:

1. **Lista exata de arquivos e trechos de código modificados** — arquivo + função/seção alterada, por commit.
2. **Funcionalidades adicionadas ou corrigidas** — o quê mudou no comportamento.
3. **Passos sequenciais que outro desenvolvedor deve seguir para evitar conflitos de merge** ao trabalhar nas mesmas seções do código (ordem de integração, o que não sobrescrever).
4. **Relatório completo de ações executadas em trechos compartilhados** — sempre que a alteração tocar código/zonas em que outro desenvolvedor também trabalha (ex.: `src/shared_kernel/`, specs em `_reversa_sdd/sdd/`, `.reversa/`, `requirements.txt`).

Além disso, cada entrega do Dev 2 publica um **resumo para leitura do assistente de IA do Dev 1** em `_reversa_sdd/learning/handoffs/` (um arquivo por entrega, formato do arquivo `dev2-2026-09-29-entrega-policy-analysis-slice.md`).

Objetivo: evitar divergências de código, manter histórico versionado e acessível a todos, e garantir que os assistentes de IA dos outros desenvolvedores interpretem corretamente as modificações, minimizando erros de integração.
