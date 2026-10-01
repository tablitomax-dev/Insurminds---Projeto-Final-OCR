# Plano de ação — Desenvolvedor 2 (Núcleo de análise e experiência)

> Data: `2026-09-26` · Versão **v1.0** (pós-debate multiagente 3 críticos × 2 rodadas)
> Dono: **Desenvolvedor 2** — extração estruturada, validação, revisão humana, DuckDB, comparação, explicação, Streamlit, avaliação.
> Base: `aprendizados.md` (IDs `F-xx`/`A-xx`/Apêndice A), `benchmark-repos-referencia.md`, `_reversa_sdd/sdd/policy-analysis.md` e `evaluation.md`, `_reversa_sdd/prd.md` (§9 Musts), `_reversa_forward/dev1-001-vertical-slice-e2e/`, `resumo_executivo_arquitetura_monolito_modular (1).md` (fora do corpus Reversa — §6.2/§7/§10).
> Regra-mãe: você transforma **evidências em fatos de negócio** — com validação, revisão humana, comparação determinística e explicação rastreável.
> Convenções de coordenação (IDs `D2-*`, caixa postal de contrato, gate `T-1`): ver `aprendizados.md` §5.

## 1. Seu terreno (e o que é cerca)

**Seu:** `src/modules/policy_analysis/**`, `src/ui/**`, testes de `tests/modules/policy_analysis/`, `tests/fakes/policy_analysis.py`, jornada de análise em `tests/e2e/`, tabelas DuckDB.

**Não é seu:** PaddleOCR/PyMuPDF/chunking/Qdrant, payload do índice vetorial, `src/modules/document_processing/**`, segundo modelo de `Evidence`.

## 2. Estado atual (verificado no código em 2026-09-26)

- Catálogo dos 10 `field_code` com semântica documentada; campo fora do catálogo rejeitado. 🟢
- `ExtractionService`: valida saída do LLM contra `ExtractedFact` (EC-05: FOUND exige evidência; `evidence_ids` ⊆ recebidos). Precisão: em erro, nada de **fato** é persistido — mas **evidências** são persistidas antes da chamada do LLM. 🟢
- `ComparisonService`: 10 linhas × 7 direções, determinístico; `ComparisonId`; export Markdown. Explicação exige citação dos dois lados. 🟢
- DuckDB com **5 tabelas** (`policies`, `documents`, `facts`, `comparisons`, `evidences`); upsert idempotente; sem tabela de controle de migração. 🟢
- ⚠️ **Fila de revisão só LISTA** (`get_review_queue`); não existe ciclo confirmar/corrige/registrar — Must do PRD §9 pendente (F-16).
- ⚠️ **UI viola a fachada (F-15):** `src/ui/app.py:21,28` importa `policy_analysis.infrastructure.document_retriever` e `policy_analysis.domain.catalog` direto; o teste de arquitetura não varre `src/ui`.
- ⚠️ **Vazamento em erro (A-13 ressalva):** `LlmOutputError` interpola o `ValidationError` do Pydantic (ecoa o texto do input) e a UI mostra `st.error` com a mensagem crua.
- `requires_human_review` é campo do contrato (`ExtractedFact`) — permanece. 🟢
- Módulo `evaluation` **não existe**, embora `evaluation.md` exija o esqueleto já no vertical slice. �

## 3. O que fazer e como fazer (ordem de execução)

### D2-P0-1 — Guardas pós-LLM: ancoragem de citação + temperature 0
- **O quê:** cada citação/excerpt do LLM deve existir de fato no texto do chunk citado (`EvidenceRef`); `temperature = 0.0` em extração e explicação; reusar a normalização pt-br já testada (A-14) antes de classificar confiança.
- **Como:** função pura de ancoragem em `application/` (quote é substring do texto recuperado?); ancorar em `value.raw_text`; com múltiplas evidências, toda citação é ancorada. Sem ancoragem → `LlmOutputError` → fila de revisão, nunca `FOUND`.
- **Pronto quando:** LLM fake que inventa citação é rejeitado; citação real aceita; E2E verde.
- **Origem:** A-07, benchmark §3.1/§3.9. **Ordem:** ancoragem ANTES do loop de revisão — revisor sem evidência ancorada vira adivinhação (decisão do debate).

### D2-P0-2 — Loop de revisão humana (Must do PRD §9) + fix mínimo da fachada na UI
- **O quê:** ações **Confirmar / Corrigir valor / Registrar divergência** por campo, gravando revisor, timestamp, valor original e valor corrigido, sempre ligados ao `EvidenceRef`; a decisão persiste e o fato revisado alimenta a comparação. Junto: a UI para de importar `infrastructure`/`domain` direto (F-15) — consome só as fachadas.
- **Como:** método de decisão via `PolicyAnalysisFacade` + persistência no repositório (tabela de revisão ou colunas na `facts`); UI com componente de revisão; `tests/architecture` estendido para varrer `src/ui`.
- **Pronto quando:** E2E prova o ciclo completo (fato NEEDS_REVIEW → corrigido → registrado → comparação usa o valor revisado); teste de arquitetura cobre `src/ui`.
- **Origem:** F-16 (Must do PRD §9 sem implementação), F-15.

### D2-P0-3 — Regras mínimas por campo do catálogo
- **O quê:** validações pós-extração por campo: `vigencia_inicio ≤ vigencia_fim`, valores numéricos > 0, moeda coerente, enums para `base_territorial`. Falha de regra → `NEEDS_REVIEW` (nunca `FOUND`).
- **Como:** regras puras em `domain/` (determinismo — A-08), testadas por regra; alimentam o loop do `D2-P0-2`.
- **Pronto quando:** cada regra tem teste próprio; fato que passa no LLM mas falha na regra cai na fila de revisão.
- **Origem:** A-08, A-14, benchmark §3.5; promovido de P1 por decisão do debate.

### D2-P0-4 — Esqueleto do módulo `evaluation` + golden set sintético (baseline)
- **O quê:** `src/modules/evaluation/` (pacote + fachada mínima — **exigido pela `evaluation.md` já no slice**; hoje inexistente) + golden set: **2 apólices sintéticas × 10 campos = 20 casos** com fatos esperados; execução produz relatório por campo (campo correto? evidência correta?).
- **Como:** casos em fixtures JSON; execução via fachada do `policy_analysis` (sem internals); relatório simples de acertos por campo. ⚠️ **Ressalva obrigatória no artefato:** golden set sintético mede regressão — **NÃO valida os riscos R1/R3 do PRD** (formatos distintos por seguradora); a validação real é `D2-P1-3`.
- **Pronto quando:** 1 execução produz o relatório dos 20 casos; ressalva R1/R3 escrita no próprio relatório.
- **Origem:** `evaluation.md` §1/§2/§13 (correção de citação da rodada 1), A-16; OQ-02 da spec (substring vs semelhança para texto livre) **decidido como substring** nesta rodada (ancoragem do `D2-P0-1`) — registrar a decisão.

### D2-P1-1 — `Issue`/`QualityReport` (aditivo, não substituto)
- **O quê:** `Issue(severity, field_code, reason, evidence_ref)` + `QualityReport` por documento/comparação. **`requires_human_review` permanece no contrato** — nada de remoção sem caixa postal MAJOR.
- **Pronto quando:** severidades cobertas por teste; UI agrupa fila por severidade.
- **Origem:** benchmark §3.2; forma "aditiva" decidida no debate (C1-06).

### D2-P1-2 — `UsageMetrics` local (custo/latência por run)
- **O quê:** tokens, custo estimado e latência por chamada de LLM (extração/explicação), no log estruturado e agregado por `run_id` — mitiga o risco R2 do PRD ("medir custo/latência desde o slice").
- **Como:** instrumentação **local no adapter** (`llm_extractors.py`). **Sem `ModelGateway` nesta rodada** (gatelo registrado: surgir 2º provedor ou 2º consumidor → extrair porta para `shared_kernel`); **fallback de modelo é NG do PRD** — fora do plano, listado como risco conhecido. Embeddings: fora desta conta (métrica opcional do Dev 1, `D1-P2-1`).
- **Pronto quando:** cada run de extração expõe tokens/latência/custo sem texto de apólice.
- **Origem:** PRD §8 R2; decisão do debate (Q3: métrica sim, gateway não).

### D2-P1-3 — Coleta de apólices reais/anonimizadas (premissa R1/R3)
- **O quê:** solicitar ao sponsor/curso ≥2 apólices reais ou anonimizadas de seguradoras distintas; rodar a jornada e medir acerto por campo nos 10 `field_code`. **Sem código de detecção de layout por seguradora** (fora desta rodada).
- **Como:** dependência externa explícita (não é tarefa de código); o resultado substitui/reforça o baseline sintético do `D2-P0-4`.
- **Pronto quando:** existe relatório de acerto por campo com dado real, OU a premissa segue registrada com o risco R1/R3 declarado e o slice **não** se declara validado em campo.
- **Origem:** PRD §3 (métrica 1) e §8 R1/R3; decisão do debate (validação real = critério de aceite com premissa).

### D2-P1-4 — UI estruturada + composition root
- **O quê:** `src/composition_root/` (resumo §7) montando as fachadas em um só lugar; `src/ui/app.py` em componentes (upload, estágios, revisão, comparação, export) consumindo **apenas** fachadas; nenhum SQL/Qdrant/prompt na UI.
- **Pronto quando:** teste de arquitetura garante `src/ui` sem imports de `infrastructure`/`domain` alheios; a jornada do `onboarding.md` funciona sem pular etapa.
- **Origem:** resumo §7/§10 Conflito 5; F-15.

### D2-P2-1 — Fallback de explicação (template determinístico)
- **O quê:** quando o LLM de explicação falhar, saída fixa (MAIOR/MENOR/IGUAL/…) citando as evidências — a UI nunca quebra por falta de explicação.
- **Origem:** benchmark §3.7.

### D2-P2-2 — Prompts versionados
- **O quê:** prompts de extração/explicação com versão/hash auditável (mudança de prompt vira diff inspecionável e roda o golden set do `D2-P0-4`).
- **Origem:** benchmark §3.8; escopo reduzido por crítica C1 (sem camada de config).

### D2-P2-3 — DuckDB defensivo (baseline + migrações)
- **O quê:** baseline `001` do schema atual (5 tabelas) + mecanismo mínimo de migração versionada. Views read-only/allowlist: **cortadas** (a UI não executa SQL — YAGNI; a escrita exclusiva pelo repositório já existe).
- **Origem:** resumo §9.4; item reduzido por decisão unânime do debate.

## 4. O que NUNCA fazer no seu quadrado

1. Escrever no Qdrant, executar OCR, alterar chunking ou tocar `document_processing`. (resumo §6.2)
2. Segundo modelo de `Evidence` — o contrato do `shared_kernel` é o único. (resumo §5.2)
3. Comparar por LLM/similaridade vetorial — LLM jamais decide "quem cobre mais". (A-08 — regra absoluta do PRD)
4. Persistir/apresentar saída de LLM sem validação + ancoragem. (A-07)
5. SQL livre na UI; regra de negócio escondida no prompt. (Conflito 5; benchmark §4.4)
6. Assumir OCR correto — respeitar `ocr_confidence`/`REVIEW_REQUIRED`. (resumo §10 Conflito 3)
7. Mudar contrato do `shared_kernel` sozinho (caixa postal — `aprendizados.md` §5.2).
8. Interpolar exceção crua em erro/UI (texto de apólice vaza — `T-2a`).

## 5. Ritual de trabalho (checklist da feature)

1. Granularidade registrada no `actions.md` da feature — A-01; teste primeiro na lógica determinística — A-04.
2. Gate `T-1` (seu comando, execução obrigatória): `ruff` + `mypy` + `python -B -m pytest -q -p no:cacheprovider` antes de todo PR.
3. Todo output de LLM tem teste de falha (saída inválida, citação inventada, campo fora do catálogo).
4. Erro amigável com estágio (`EXTRACT:`/…) — nunca stack nem texto de apólice (`T-2a`).
5. Mudança de contrato = caixa postal, uma por vez; Musts do PRD relidos ao fechar escopo (F-16).
6. Antes de PR: checar estado remoto (`gh pr list --state all`); feature → `regression-watch.md` → `/reversa-sync` (plano B: adendo manual). Ambiente: `aprendizados.md` Apêndice A.
7. Mudança no lado documental = proposta ao Dev 1; não implemente por conta própria.

## 6. Zonas compartilhadas com o Dev 1

| Zona | Regra |
|------|-------|
| `shared_kernel/contracts` | Caixa postal + bump de versão (A-02, §5.2); `requires_human_review` permanece |
| `ChunkMetadata`/payload do Qdrant | Você consome; mudança é proposta do Dev 1 com seu aceite (ex.: `D1-P1-1`) |
| `EvidenceRef` | Contrato, não conveniência |
| ModelGateway | Fora desta rodada (gatelo registrado em `D2-P1-2`) |
| Orquestração | Composition root único (`D2-P1-4`); UI só via fachadas |

## Fora desta rodada (registro, não tarefa)

- **Fallback de modelo** (NG explícito do PRD §5) — risco conhecido registrado, não tarefa.
- LLM-as-judge e baterias de avaliação em CI (NG-01/NG-02 do `evaluation.md`).
- Detecção de layout por seguradora (mitigação futura de R1/R3 além de `D2-P1-3`).
- GitHub Actions; retenção automática plena do DuckDB/exports (mínimo em `T-2b`); prompt injection (risco aceito, `D1` plano).

## Transversal (sua manutenção)

- **T-1 (dono seu):** gate local único — `ruff` + `mypy` + `python -B -m pytest -q -p no:cacheprovider` (inclui `tests/architecture/` — que deve passar a varrer `src/ui` — e o E2E), documentado para os dois; pronto quando: comando único documentado e verde.
- **T-2 (higiene de dados sensíveis, fatiado):** (a) **P0** sanitização de exceções — Dev 1 corrige `service._cause`; você corrige `LlmOutputError`/`st.error` (nunca `ValidationError` crua; tipo + estágio + IDs); teste anti-vazamento. (b) **P1** mínimo: `exports/` com caminho fixo + aviso de retenção na UI; uploads temporários em diretório controlado com limpeza (parte do Dev 1). (c) **fora:** prompt injection (risco aceito registrado).

## Critério de parada da rodada

Todos os `D1-P0-*` + `D2-P0-*` concluídos e `T-1` verde em 3 execuções consecutivas = rodada encerrada; qualquer novidade vai para a próxima rodada.
