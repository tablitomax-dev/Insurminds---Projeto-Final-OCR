# Protocolo de colaboração Dev 1 × Dev 2 — como programar para os PRs se mergirem

> Vigência: **Vigente desde 2026-09-29.** Definido por pbena após o incidente do PR #8
> (merge que empilhou dois códigos no mesmo arquivo). Normativo para os dois
> desenvolvedores **e para os assistentes de IA de cada um**. Complementa
> `aprendizados.md` §5 (não substitui: caixa postal, gate `T-1`, regra §5.6).

## Por que este protocolo existe

O PR #8 foi mergeado com os dois códigos **concatenados** nos mesmos arquivos
(duas `ExtractionService`, duas `PolicyAnalysisFacade`, sintaxe quebrada no
meio de uma expressão). Conflito de merge **nunca se resolve aceitando os dois
lados** — resolve-se escolhendo **uma** implementação e costurando o resto.

## 1. Propriedade de arquivos (quem altera o quê)

| Zona | Dono | Caminhos |
|------|------|----------|
| Processamento documental | **Dev 1** | `src/modules/document_processing/**`, `tests/modules/document_processing/**`, `tests/integration/**`, `tests/fixtures/**` |
| Análise de apólices | **Dev 2** | `src/modules/policy_analysis/**`, `src/ui/**`, `src/modules/evaluation/**`, `src/composition_root/**`, `tests/modules/policy_analysis/**`, `tests/e2e/**`, `tests/ui/**` |
| Contratos compartilhados | **ambos, por caixa postal** | `src/shared_kernel/**`, `tests/contracts/**` |
| Infra de projeto | **ambos, avisando no PR** | `requirements.txt`, `pyproject.toml`, `CLAUDE.md`, `.reversa/**`, `_reversa_sdd/**` |

- Para alterar arquivo de **zona alheia**: só dentro da própria feature, como
  **extensão aditiva** (item 2), e o PR precisa trazer o "Relatório de áreas
  compartilhadas" (regra §5.6) explicando o ponto exato.
- Mudança em `src/shared_kernel/contracts.py` **sempre** via caixa postal
  (`contract-delta-*.md`) + bump `CONTRACTS_VERSION` — nunca silenciosa.

## 2. Extensão aditiva, nunca reescrita

- **Um arquivo = um autor conceitual.** Ao evoluir código que não é seu:
  acrescente (novo método, parâmetro opcional, módulo novo); **não** reescreva
  o arquivo inteiro, **não** cole um bloco novo no meio/fim do arquivo alheio.
- Nunca resolva conflito com "aceitar ambos os lados" (theirs+ours
  concatenados). Escolha **uma** base e costure as capacidades faltantes.
- Se as duas implementações são incompatíveis, **não mescle código**: escolha
  uma arquitetura (por decisão registrada) e reimplemente a outra capacidade
  sobre ela — foi o que fizemos em 2026-09-29 (arquitetura do Dev 2 prevaleceu,
  features 003/004 reimplementadas por cima).
- Novas capacidades entram pela **fachada pública** (`public_api.py`) do módulo
  dono — consumidores nunca importam internos de outro módulo.

## 3. Antes de subir o PR (obrigatório, os dois)

1. `git fetch origin` e **rebase/merge do `main` atualizado** na sua branch.
2. Rodar o **gate `T-1` completo** (ruff + mypy + pytest) — só sobe verde.
3. Conferir que **não há arquivo duplicado/empilhado** no diff (se o merge local
   mostrou conflito, releia o arquivo inteiro antes de commitar).
4. Conferir que nenhum arquivo de zona alheia foi alterado sem o relatório de
   áreas compartilhadas no corpo do commit/PR.
5. Commit/PR com o histórico detalhado da **regra §5.6**.

## 4. Durante o review/merge

- Quem for mesclar o PR do outro: revisa o diff inteiro (não só o título); se o
  `main` andou desde a branch, pede ao autor para **rebase + gate de novo**.
- **Nunca** mesclar PR vermelho no `main` — o `main` é a base de trabalho dos dois.
- Conflito na hora do merge = aviso para o autor resolver (com o item 2), não
  resolução manual de quem está mesclando.

## 5. Checklist de PR (colar no corpo)

- [ ] Branch partiu do `main` atualizado
- [ ] Gate `T-1` verde (ruff · mypy · pytest) — 3 execuções para mudança grande
- [ ] Nenhum arquivo de zona alheia sem "Relatório de áreas compartilhadas"
- [ ] Contratos (`shared_kernel`) intocados — ou caixa postal + bump enviados
- [ ] Corpo do commit/PR no formato da regra §5.6 (histórico, arquivos/trechos,
      funcionalidades, passos anti-conflito, áreas compartilhadas)
- [ ] Mudança de superfície da fachada? Consumidores + testes atualizados na
      mesma feature
- [ ] `/reversa-sync` ao fim da feature (adendo em `_reversa_sdd/addenda/`)

## 6. Checklist do assistente de IA (cada assistente ao gerar código)

- Respeitar a tabela de propriedade (item 1) como limite de escrita.
- Antes de editar arquivo, verificar se não há trabalho concorrente do outro
  dev nele (`git status`, diff do `main` recente).
- Nunca "limpar" código alheio ao passar: mudanças cosméticas em zona alheia
  geram conflito sem valor — não faça.
- Ao encontrar código do outro dev conflitando com a feature atual: reportar ao
  humano **com alternativas**, não decidir sozinho (padrão já adotado).
