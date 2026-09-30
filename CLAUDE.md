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

## Regra perpétua de colaboração Dev 1 × Dev 2 — protocolo de PRs mergeáveis + cascata de decisão de código

**Vigor permanente, a partir de 2026-09-30, definido por pbena.** Normativo para os dois desenvolvedores **e para os assistentes de IA de cada um**. Fonte oficial e única: [`_reversa_sdd/learning/protocolo-colaboracao-dev1-dev2.md`](./_reversa_sdd/learning/protocolo-colaboracao-dev1-dev2.md) (protocolo de PRs mergeáveis + item 2.1 cascata de decisão + seção 7 exemplo aplicado do PR #8). Complementa `aprendizados.md` §5 (caixa postal, gate `T-1`, regra §5.6) — não substitui. **Ler esse documento antes de qualquer PR/merge.**

### A) Propriedade de arquivos (quem altera o quê) — limite de escrita
- **Dev 1:** `src/modules/document_processing/**`, `tests/modules/document_processing/**`, `tests/integration/**`, `tests/fixtures/**`.
- **Dev 2:** `src/modules/policy_analysis/**`, `src/ui/**`, `src/modules/evaluation/**`, `src/composition_root/**`, `tests/modules/policy_analysis/**`, `tests/e2e/**`, `tests/ui/**`.
- **Contratos compartilhados (ambos, por caixa postal):** `src/shared_kernel/**`, `tests/contracts/**` — mudança em `contracts.py` sempre via caixa postal `contract-delta-*.md` + bump `CONTRACTS_VERSION`, nunca silenciosa.
- **Infra de projeto (ambos, avisando no PR):** `requirements.txt`, `pyproject.toml`, `CLAUDE.md`, `.reversa/**`, `_reversa_sdd/**`.
- Para alterar zona alheia: só dentro da própria feature, como **extensão aditiva**, e o PR traz o "Relatório de áreas compartilhadas" (regra §5.6) apontando o ponto exato.

### B) Extensão aditiva, nunca reescrita (item 2)
- **Um arquivo = um autor conceitual.** Ao evoluir código alheio: acrescente (método novo, parâmetro opcional, módulo novo); **não** reescreva o arquivo inteiro, **não** cole bloco novo no meio/fim do arquivo alheio.
- **Conflito de merge NUNCA se resolve aceitando os dois lados** (theirs+ours concatenados). Escolha **uma** base e costure as capacidades faltantes.
- Implementações incompatíveis: **não mesclar código** — escolher a base pela cascata (2.1) e reimplementar a outra capacidade por cima (como feito em 2026-09-29: arquitetura do Dev 2 prevaleceu, features 003/004 reimplementadas sobre ela).
- Novas capacidades entram pela **fachada pública** (`public_api.py`) do módulo dono — consumidores nunca importam internos de outro módulo.

### C) Cascata de decisão de código — item 2.1 (qual código prevalece)
Quando as mudanças forem incompatíveis, decidir **nesta ordem**:
1. **Mudança aditiva?** Coexiste — sem vencedor nem disputa.
2. **Zona de propriedade → prevalece o MELHOR código**, não automaticamente o do dono. "Melhor" = (a) atende **todos os objetivos planejados** da feature (RFs/RNs do `_reversa_forward/<feature>/requirements.md`) e (b) tem **passagem comprovada pelos gates de teste** (gate `T-1` verde; cenários cobertos). Código que não passa nos gates **não** prevalece.
3. Comparação por **análise estruturada com as skills do Reversa** (`code-review`, `understand-diff`, `understand-explain`, `codebase-design`, `diagnosing-bugs`), nos critérios: aderência aos objetivos, qualidade (simplicidade, sem duplicação, legibilidade), testes/cobertura, risco de regressão — avaliação **escrita** (o que cada lado resolve + evidências).
4. **Dúvida/ambiguidade → opções com trade-offs ao desenvolvedor.** A IA nunca decide sozinha: apresenta, aguarda a escolha e registra.
5. **Zonas compartilhadas/contratos → decide a spec/adendo** (`_reversa_sdd/sdd/`, adendos, `shared_kernel`).
6. **Anterioridade (o que já está no `main`) só como desempate final** entre equivalentes técnicos — nunca regra principal.
- **Princípio do vencedor: nunca eliminar capacidade.** O que a base descartada entregava deve ser (a) reimplementado sobre a base vencedora ou (b) registrado como **perda observada** para decisão futura.
- Toda decisão da cascata vira **registro** (adendo ou `decisões`), com critério + evidências — para não redecidir o mesmo ponto.

### D) Antes de subir o PR (obrigatório) e durante o merge
1. `git fetch origin` + rebase/merge do `main` atualizado na branch.
2. Gate `T-1` completo verde (ruff + mypy + pytest) — para mudança grande, 3 execuções.
3. Conferir no diff que **não há arquivo duplicado/empilhado** (se houve conflito local, releia o arquivo inteiro antes de commitar).
4. Nenhum arquivo de zona alheia sem "Relatório de áreas compartilhadas" no corpo do commit/PR.
5. Corpo do commit/PR no formato da regra §5.6.
6. Revisar o diff inteiro ao mesclar o PR do outro; se o `main` andou, pedir rebase + gate de novo. **Nunca mesclar PR vermelho no `main`.** Conflito na hora do merge = avisar o autor para resolver (item 2), não resolver manualmente.

### E) Checklist do assistente de IA (sempre)
- Respeitar a tabela de propriedade (A) como limite de escrita.
- Antes de editar arquivo, checar se não há trabalho concorrente do outro dev nele (`git status`, diff recente do `main`).
- Nunca "limpar" código alheio ao passar (mudança cosmética em zona alheia gera conflito sem valor).
- Código do outro dev conflitando com a feature atual → reportar ao humano **com alternativas**, nunca decidir sozinho.

**Lição do PR #8 (seção 7):** conflito nunca se resolve com "aceitar ambos os lados"; gate verde é pré-requisito do vencedor; a decisão (critério + evidência) fica registrada. Diagnóstico completo: [`_reversa_bugs/auditoria-merge-dev2-2026-09-29.md`](./_reversa_bugs/auditoria-merge-dev2-2026-09-29.md).
