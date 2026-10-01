# Requirements: P0 do Desenvolvedor 2 — Análise e Experiência

> Identificador: `dev2-003-p0-analise-experiencia`
> Data: `2026-09-26` (ISO 8601)
> Dono: **Desenvolvedor 2** (evidências → fatos, revisão humana, comparação, UI, avaliação)
> Fonte normativa: `_reversa_sdd/learning/plano-acao-dev2.md` v1.0 (detalhe do "como"), `_reversa_sdd/learning/aprendizados.md` v1.0 (regras F-xx/A-xx, convenções §5)
> Este documento fixa o **escopo e a aceitação**; o plano de ação fixa o **método**. Em conflito, vale o plano de ação para o "como" e este para o "o quê/quando está pronto".

## 1. Objetivo

Fechar os gaps do `policy_analysis`/UI verificados no código em 2026-09-26: guardas pós-LLM sem ancoragem de citação, **loop de revisão humana ausente (Must do PRD §9 — F-16)**, UI violando a fachada (F-15), vazamento de texto em erros (A-13 ressalva), regras por campo inexistentes e módulo `evaluation` ausente apesar da spec exigir o esqueleto no slice.

## 2. Escopo

**Nesta feature:** `D2-P0-1`..`D2-P0-4` + transversais `T-1` (gate local, dono seu) e `T-2` (partes da UI/erros) — detalhes em `actions.md`.
**Fora:** itens `D2-P1-*`/`D2-P2-*` (backlog), ModelGateway, fallback de modelo (NG do PRD), LLM-as-judge.

## 3. Requisitos de aceitação (pronto quando)

| ID | Requisito | Aceitação | Conf. |
|----|-----------|-----------|-------|
| RF-01 | Ancoragem de citação + `temperature=0`: toda citação do LLM existe no texto do chunk citado; sem ancoragem nunca vira `FOUND` | LLM fake que inventa citação é rejeitado (`LlmOutputError`); citação real aceita; E2E verde | 🟢 |
| RF-02 | Loop de revisão humana (Must PRD §9): **Confirmar / Corrigir valor / Registrar divergência** por campo, com revisor, timestamp, valor original/corrigido e `EvidenceRef`; fato revisado alimenta a comparação. Junto: UI consome só fachadas (F-15) | E2E prova o ciclo completo (NEEDS_REVIEW → corrigido → registrado → comparação usa o valor revisado); teste de arquitetura varre `src/ui` | 🟢 |
| RF-03 | Regras mínimas por campo (`vigencia_inicio ≤ vigencia_fim`, valores > 0, moeda, enums): falha vira `NEEDS_REVIEW`, nunca `FOUND` | Cada regra com teste próprio; fato inválido cai na fila de revisão | 🟢 |
| RF-04 | Esqueleto do módulo `evaluation` (exigido pela spec no slice) + golden set sintético 2 apólices × 10 campos = 20 casos, com relatório por campo; OQ-02 decidido como **substring** | 1 execução produz o relatório dos 20 casos, com a ressalva escrita: "não valida R1/R3 — validar com apólices reais (`D2-P1-3`)" | 🟢 |
| RF-05 | `T-1`: gate local único (`ruff` + `mypy` + `python -B -m pytest -q -p no:cacheprovider`) documentado para os dois devs | Comando único documentado e verde 3× consecutivas | 🟡 |
| RF-06 | `T-2`: nenhum erro/UI carrega texto de apólice (`LlmOutputError`/`st.error` nunca com `ValidationError` crua); `exports/` com caminho fixo + aviso de retenção | Teste anti-vazamento no lado Dev 2; UI mostra erro tipado (tipo + estágio + IDs) | 🟢 |

## 4. Premissas e dependências

- **Ancoragem antes do loop de revisão** (ordem obrigatória — revisor sem evidência ancorada vira adivinhação).
- Mudança em contrato compartilhado (ex.: `requires_human_review` permanece; `Issue` é aditivo) só via **caixa postal** (`aprendizados.md` §5.2).
- Golden set sintético **não** valida os riscos R1/R3 do PRD (formatos por seguradora); a validação real é `D2-P1-3` (coleta de apólices reais/anonimizadas — dependência externa).
- Fix mínimo da fachada na UI entra em `D2-P0-2`; a refatoração completa (composition root) é `D2-P1-4`.
- Ambiente Windows/PowerShell: consultar `aprendizados.md` Apêndice A antes de comandos de ferramenta externa.

## 5. Fora de escopo (registro)

Fallback de modelo (NG do PRD §5 — risco conhecido registrado); ModelGateway (gatelo: 2º provedor/consumidor); LLM-as-judge e baterias em CI (NG-01/NG-02 do `evaluation.md`); detecção de layout por seguradora; retenção automática plena do DuckDB; prompt injection (risco aceito).

## 6. Fontes

- `_reversa_sdd/learning/plano-acao-dev2.md` (§2 estado atual verificado; §3 método; §5 ritual; transversais T-1/T-2)
- `_reversa_sdd/learning/aprendizados.md` (F-14/F-15/F-16, A-07/A-08/A-13/A-16, §5 convenções)
- `_reversa_sdd/learning/benchmark-repos-referencia.md` §3 (guardas pós-LLM, quality report, padrões)
- `_reversa_sdd/sdd/policy-analysis.md`, `_reversa_sdd/sdd/evaluation.md`, `_reversa_sdd/prd.md` §9 (Musts) e §8 (R1/R3)
