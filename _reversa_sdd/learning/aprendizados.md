# Aprendizados — o que fazer, o que não fazer, falhas e acertos

> Data: `2026-09-26` (ISO 8601) · Versão: **v1.0** (consolidada após debate multiagente: 3 críticos × 2 rodadas — arquitetura/qualidade, entrega/processo, valor/Reversa)
> Escopo: Fase 0 (contratos), feature `dev1-001-vertical-slice-e2e` (21 ações, 137 passed/4 skipped), `reversa-sync`, PR/GitHub CLI, benchmark de 3 repositórios externos.
> Escala: 🟢 CONFIRMADO (executado/verificado no código) · 🟡 INFERIDO (com ressalva) · 🔴 LACUNA (validação humana pendente)
> Uso: fonte única dos mandamentos. Os planos `plano-acao-dev1.md` (IDs `D1-*`) e `plano-acao-dev2.md` (IDs `D2-*`) citam os IDs daqui (`F-xx` = falha, `A-xx` = acerto). Itens de ambiente vão ao **Apêndice A**.

## 1. Método

Cada item registra **o que aconteceu**, a **causa raiz** e a **regra resultante**, com coluna de **evidência** apontando artefato do projeto (chat não conta como evidência — regra F-12). Onde a regra é inferida, confiança 🟡.

## 2. Falhas que mudam decisão (núcleo)

| ID | Falha | Causa raiz | Regra resultante | Evidência | Conf. |
|----|-------|-----------|------------------|-----------|-------|
| F-01 | `git commit` com heredoc bash no PowerShell falhou (parse) | Comando POSIX colado em Windows/PowerShell | Nunca heredoc bash no PowerShell; commit via string multilinha ou `-F arquivo` | sessão 2026-09-26 (operação — ver Apêndice A) | 🟢 |
| F-02 | E2E quebrou e a suspeita inicial foi "bug do código" | Pré-condição do teste incompleta (faltava extrair `franquia` do lado A) | Falha de teste: auditar pré-condições do teste ANTES de mexer no código | `_reversa_forward/dev1-001-vertical-slice-e2e/actions.md` §Notas de execução | 🟢 |
| F-03 | `PytestUnknownMarkWarning: integration` | Marker sem registro em `pyproject.toml` | Todo marker registrado; warning aponta configuração ausente | `pyproject.toml` (corrigido) | 🟢 |
| F-12 | Análise dos 3 repositórios externos ficou só no chat | Entrega sem artefato | Todo resultado de valor é gravado em `_reversa_sdd/`/`_reversa_forward/` na hora — chat não é repositório | `benchmark-repos-referencia.md` (reparo) | 🟢 |
| F-14 | Contrato `RetrievalQuery` promete 4 filtros; `retrieve_evidence` descarta `section_name`/`field_code` em silêncio e o consumidor (Dev 2) achava que filtrava | Parâmetro de contrato sem teste de propagação | Parâmetro de contrato nunca é ignorado em silêncio: ou implementado, ou removido com revisão dos dois; teste de contrato por parâmetro | `src/modules/document_processing/application/service.py` (linhas 150-158) — verificado em 2026-09-26 | 🟢 |
| F-15 | UI importava `policy_analysis.infrastructure`/`domain` direto (viola fachada) e o teste de arquitetura não varria `src/ui` | Regra arquitetural com teste que não cobre todo o alvo | Toda regra arquitetural tem teste que varre TODO alvo (`src/ui` incluído); regra sem cobertura é intenção | `src/ui/app.py` linhas 21-28 vs `tests/architecture/test_imports.py` | 🟢 |
| F-16 | Loop de revisão humana (Must do PRD §9: confirmar/corrige/registrar) ficou fora da UI do slice sem registro de decisão | Escopo do slice fechado sem re-leitura dos Musts do PRD | Ao fechar escopo de slice, listar Musts do PRD e declarar cada um: implementado OU adiado com registro | `_reversa_sdd/prd.md` §9 vs `src/ui/app.py` (fila só lista) | 🟢 |
| — | F-04..F-11 (tooling/sandbox) | ambiente | ver **Apêndice A** | Apêndice A | 🟢 |
| — | F-13 (anti-padrões de repos externos: pós-filtro vaza dado; import fantasma) | repositório externo | movido para `benchmark-repos-referencia.md` §4 (anti-padrões) | benchmark §4.1-4.2 | 🟢 |

## 3. Acertos (o que FAZER)

| ID | Acerto | Por que funcionou | Repetir assim | Evidência | Conf. |
|----|--------|-------------------|---------------|-----------|-------|
| A-01 | Análise de granularidade explícita antes de codar (atômico p/ lógica pura; ação maior coesa p/ scaffolding/portas; UI por último) | Evitou churn de assinatura entre turnos; atomicidade real = "um turno sem feedback humano" | Registrar a análise **no `actions.md` da feature** (o `/reversa-to-do` já gera a seção — não criar documento à parte) | `actions.md` §Análise de granularidade | 🟢 |
| A-02 | Contratos `shared_kernel` v1.0.0 antes de qualquer módulo | Desenvolvimento paralelo sem bloqueio; zero mudança MAJOR **declarada** | Contrato primeiro, versionado, mudança com revisão dos dois. ⚠️ Ressalva: durante a execução houve ajustes (tabela `evidences` extra, `ChunkRecord.vector` opcional, PK `comparisons`) — o ritual de mudança de contrato precisa CABER mudanças mid-flight (caixa postal — ver §5) | `actions.md` §Notas de execução | 🟡 |
| A-03 | Portas `typing.Protocol` + fakes injetáveis | 137 testes sem Docker/chave/rede | Núcleo depende só de portas; toda externa tem fake | `tests/fakes/` | 🟢 |
| A-04 | TDD no núcleo determinístico | Limiares, chunking, comparação, catálogo nasceram testados | Lógica determinística: teste primeiro. LLM/adapters: integração opt-in depois | `tests/modules/` | 🟢 |
| A-05 | Dois agentes em paralelo para módulos independentes + integração por um só | Fronteiras de arquivo claras = zero conflito | Paralelizar só o que não compartilha arquivos; a costura é de um só | `progress.jsonl` (T001-T021) | 🟢 |
| A-06 | Testes de arquitetura automatizados | Regra verificada por teste, não por intenção | Toda regra arquitetural vira teste — cobrindo TODO alvo (lição F-15: `src/ui` ficou de fora) | `tests/architecture/test_imports.py` | 🟢 |
| A-07 | Validação de saída de LLM contra o contrato (EC-05; `evidence_ids` ⊆ recebidos; erro → nada de fato persistido) | Anti-alucinação na fronteira | Todo output de LLM passa por schema + ancoragem em evidência antes de persistir/apresentar | `policy_analysis/application/extraction.py` | 🟢 |
| A-08 | Comparação 100% determinística (7 direções); LLM jamais compara | Reproduzível e auditável | LLM extrai e explica; regra compara | `policy_analysis/domain/comparison.py` | 🟢 |
| A-09 | Idempotência por design (`uuid5` estável; delete+upsert) | Reprocessar não duplica — testado | Todo recurso reprocessável nasce idempotente com teste de reprocessamento | `infrastructure/indexing.py` | 🟢 |
| A-10 | Decisões de slice documentadas (`requirements.md#10`) + alternativas descartadas (`investigation.md#2`) | Cada default tem justificativa rastreável | Toda decisão registra: escolha, descartadas, porquê | `_reversa_forward/dev1-001-vertical-slice-e2e/requirements.md` §10 | 🟢 |
| A-11 | Integração real opt-in (marker `integration`, skip gracioso) | Suíte verde sem infra | Externa nunca bloqueia suíte; fake sempre presente | `tests/integration/` | 🟢 |
| A-12 | Convergência via adendo (`reversa-sync`) em vez de re-extração | Extração vigente + impacto mapeado, custo baixo | Forward converge por adendo; re-extração só para divergência estrutural | `_reversa_sdd/addenda/dev1-001-vertical-slice-e2e.md` | 🟢 |
| A-13 | Erros classificados por estágio (`EXTRACT:`/`OCR:`/`INDEXING:`) — classificação acertou | Diagnóstico rápido | Erro carrega prefixo de estágio. ⚠️ Ressalva: a regra "log sem texto de apólice" era **falsa** — `service._cause` retorna `str(exc)` cru e erros podem vazar texto (ver ação `T-2`); materializam-na a sanitização de exceções + teste anti-vazamento | `service.py:203-216` (verificado) | 🟡 |
| A-14 | Normalização tolerante pt-br (`1.000.000,00`, `dd/mm/aaaa`) testada | Comparação não quebra em formatação | Normalizar na borda de entrada; nunca comparar string crua | `domain/comparison.py` | 🟢 |
| A-15 | Adaptação às restrições do sandbox em vez de forçá-las | Desbloqueou o trabalho sem loop de retry | Restrição de ambiente = mudança de rota imediata + registro | Apêndice A | 🟡 |
| A-16 | (nova) Suíte verde com fakes **não** prova valor ao analista | 137 verdes, mas zero execução com PDF real validada — o risco nº1 do PRD (R1/R3) segue aberto | Todo slice declara explicitamente o que **não** foi validado e a premissa pendente | `prd.md` §8 R1/R3 vs suíte | 🟢 |

## 4. Mandamentos (síntese operacional)

### FAÇA
1. Contrato antes de código compartilhado; mudança via **caixa postal de decisão** (ver §5). (A-02)
2. Registre a granularidade das ações no `actions.md` da feature antes de codar. (A-01)
3. Núcleo puro + portas + fakes; teste determinístico primeiro. (A-03, A-04)
4. Valide toda saída de LLM contra contrato e evidência antes de persistir. (A-07)
5. Compare por regras; normalize entrada antes. (A-08, A-14)
6. Nasça idempotente e teste o reprocessamento. (A-09)
7. Toda regra arquitetural vira teste que varre TODO alvo, `src/ui` incluído. (A-06, F-15)
8. Parâmetro de contrato é implementado ou removido com revisão — nunca ignorado. (F-14)
9. Todo output de LLM leva ancoragem em evidência; erro nunca carrega texto de apólice. (A-07, A-13/F-14)
10. Grave análise/decisão em artefato; feche todo slice declarando Musts do PRD e o que não foi validado. (F-12, F-16, A-16)
11. Antes de agir no GitHub/ferramenta externa: confira o estado remoto/real. (Apêndice A)

### NÃO FAÇA
1. Não use heredoc bash/atalho POSIX no PowerShell. (F-01)
2. Não trate falha de teste como bug de código antes de auditar o teste. (F-02)
3. Não deixe marker/warning de configuração passar. (F-03)
4. Não planeje etapa com tooling não verificado. (Apêndice A)
5. Não insista em ferramenta bloqueada — mude a rota. (A-15)
6. Não faça pós-filtro de segurança depois do retrieval — filtre na consulta (anti-padrão confirmado no bot: vazava dado entre usuários). (benchmark §4.1)
7. Não deixe LLM comparar valores. (A-08)
8. Não persista saída de LLM não validada; não crie segundo modelo de `Evidence`. (A-07)
9. Não acesse módulo interno do outro dev — só fachada pública. (F-15)
10. Não entregue conhecimento só no chat. (F-12)

## 5. Convenções de coordenação (decididas no debate)

1. **IDs de ação prefixados pelo dono:** `D1-*` (Dev 1), `D2-*` (Dev 2), `T-*` (transversal). Numeração dentro de cada faixa de prioridade. **Pastas de feature em `_reversa_forward/`** seguem `<dev>-<NNN>-<slug>` (ex.: `dev1-005-p1-proveniencia`, `dev2-003-p0-analise-experiencia`) — prefixo do dono + número histórico preservado (convenção do humano, 2026-09-30; resolve a colisão `001-*` duplicada).
2. **Caixa postal de mudança de contrato:** proposta em `_reversa_forward/<feature>/contract-delta-*.md` → aceite/negativa do outro dev com prazo (1 dia útil; silêncio = escalada ao humano) → serialização: **uma mudança de contrato por vez**; quem propõe bumpa `CONTRACTS_VERSION` e atualiza consumidores.
3. **Gate local de qualidade (T-1):** comando único (`ruff` + `mypy` + `python -B -m pytest -q -p no:cacheprovider`) obrigatório antes de todo PR; dono do comando: Dev 2; execução: ambos. GitHub Actions = fora desta rodada.
4. **Marco de PR:** checar estado remoto (`gh pr list --state all`) antes de criar PR; feature concluída → `regression-watch.md` → `/reversa-sync` (plano B: adendo manual em markdown).
5. **Registro de decisões:** escolha/descartadas/porquê em `_reversa_forward/<feature>/` (A-10).
6. **Registro obrigatório em commits e PRs — REGRA PERPÉTUA** (decidida pelo humano em 2026-09-27): todo commit e todo PR preenchem obrigatoriamente os comentários (corpo da mensagem / descrição do PR) com:
   a. histórico detalhado de todas as alterações implementadas;
   b. lista exata de arquivos e trechos de código modificados;
   c. funcionalidades adicionadas ou corrigidas;
   d. passos sequenciais que outro desenvolvedor deve seguir para evitar conflitos de merge ao trabalhar nas mesmas seções de código;
   e. quando as alterações interferem em trechos de código compartilhados com outro desenvolvedor: relatório completo de todas as ações executadas nesses trechos compartilhados.
   Objetivo: evitar divergências de código, manter histórico versionado e acessível a todos, e garantir que o assistente de IA dos outros desenvolvedores interprete corretamente as modificações. Vale para todos os colaboradores e assistentes, sem exceção e sem data de término.
   **Fonte canônica desta regra é este arquivo (`aprendizados.md` §5)** — em caso de divergência com qualquer cópia (ex.: `CLAUDE.md`), este documento prevalece.
7. **Gestão de documentos normativos (`CLAUDE.md` × `aprendizados.md`) — REGRA PERPÉTUA** (decidida pelo humano em 2026-09-30): os dois documentos existem por papéis diferentes e com **texto nunca duplicado**:
   a. `CLAUDE.md` = bootstrap de sessão (injetado em toda sessão de IA): ativação do Reversa, regras não-negociáveis de escrita, política `reversa-config.json` e **ponteiro curto** para o texto completo de cada regra;
   b. `_reversa_sdd/learning/aprendizados.md` = **fonte canônica do texto completo** das regras e convenções;
   c. se um assunto existir nos dois lugares, manter o texto completo **só aqui** e deixar no `CLAUDE.md` resumo/ponteiro;
   d. **cláusula de desempate:** havendo divergência do mesmo assunto entre `CLAUDE.md` e este arquivo, **prevalece este arquivo** (rede de segurança — o mecanismo principal é não duplicar texto).

## 6. Rastreabilidade: aprendizado → ação

| Aprendizado | Ação (dono) |
|-------------|-------------|
| F-14 (filtros descartados) | `D1-P0-2` (semântica + teste de contrato; Dev 2 consome via caixa postal) |
| F-15 (UI fora da fachada; teste incompleto) | `D2-P0-2` (fix mínimo na UI) + `T-1` (teste de arquitetura cobre `src/ui`) + `D2-P1-4` (composition root) |
| F-16 (Must de revisão humana fora do slice) | `D2-P0-2` (loop confirmar/corrige/registrar) |
| A-13 (vazamento via `str(exc)`) | `T-2a` (sanitização: `D1` `service._cause` + `D2` `LlmOutputError`/UI) |
| A-16 + PRD R1/R3 | `D2-P0-4` (golden set sintético) + `D2-P1-3` (coleta de apólices reais — premissa) |
| A-07 (guardas anti-alucinação) | `D2-P0-1` (ancoragem, temperature 0) |
| A-08, A-14 | `D2-P0-3` (regras por campo) |
| A-02 (mudança mid-flight) | Convenção §5.2 (caixa postal) |
| F-03, A-11 | `T-1` (gate local com markers registrados) |
| F-12, A-10 | Convenção §5.5 (registro em artefato) |

## Apêndice A — Operação em ambiente Windows/sandbox

> Incidentes de ambiente (não defeitos do projeto). Peso decisório: zero — registro operacional para evitar recaída. Rituais citam "consultar Apêndice A".

| ID | Incidente | Regra operacional |
|----|-----------|-------------------|
| F-04 | Skill `reversa-sync` ausente (instalação defasada v1.3.3) | Verificar tooling antes de planejar a etapa; manter atualizado (`npx reversa update`) |
| F-05 | `npx reversa update` travou em prompt interativo | Automatizar com modo não-interativo (`Write-Output "Y" \| ...`) |
| F-06 | winget bloqueado pelo sandbox (2 tentativas) | Restrição conhecida primeiro; plano B = instalação user-space (zip oficial) |
| F-07 | `Move-Item` entre árvores protegidas bloqueado | Extrair direto no destino (`Expand-Archive -DestinationPath`) |
| F-08 | `gh auth login --with-token` rejeitou token do GCM | `GH_TOKEN` com credencial de `git credential fill` |
| F-09 | `gh pr create` falhou — PR já mesclado no remoto | `gh pr list --state all` antes; estado local ≠ estado GitHub |
| F-10 | `--jq` com interpolação quebrou (aspas) | Valor literal primeiro; simplificar interpolação |
| F-11 | Layout do zip do gh inesperado (`bin\gh.exe` direto) | Inspecionar layout real antes de automatizar move |
| F-01 | Heredoc bash no PowerShell (também operacional) | Ver F-01 na tabela central |

## Histórico

| Data | Versão | O que mudou |
|------|--------|-------------|
| 2026-09-26 | v0 | Redação inicial (orquestrador) |
| 2026-09-26 | v1.0 | Debate multiagente (3 críticos × 2 rodadas): F-04..F-11 → Apêndice A; F-13 → benchmark §4; novas lições F-14/F-15/F-16/A-16; A-02 e A-13 com ressalvas 🟡; convenções de coordenação (§5); rastreabilidade com donos `D1-`/`D2-`/`T-` |
| 2026-09-27 | v1.1 | Convenção §5.6 (regra perpétua, decisão do humano pbena): registro obrigatório e detalhado em todo commit e PR — histórico de alterações, arquivos/trechos modificados, funcionalidades, passos anti-conflito de merge e relatório de áreas compartilhadas |
| 2026-09-30 | v1.2 | Convenção §5.7 (decisão do humano pbena): modelo "dois arquivos, sem duplicata" entre `CLAUDE.md` (bootstrap + ponteiro) e `aprendizados.md` (fonte canônica), com cláusula de desempate; §5.6 declarada fonte canônica deste arquivo |
