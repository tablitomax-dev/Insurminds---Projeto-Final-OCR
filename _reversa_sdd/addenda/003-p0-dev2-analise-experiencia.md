# Adendo: P0 do Desenvolvedor 2 — Análise e Experiência

> Identificador: `003-p0-dev2-analise-experiencia`
> Data: `2026-09-26` (ISO 8601)
> Cenário: `greenfield`
> Gerado por `/reversa-sync` após a implementação das ações P0 (`T-2a`, `T-1`, `T-2b`, `D2-P0-1`..`D2-P0-4` — 6/6 concluídas)

## Vigência

Vigente desde 2026-09-26.

## Resumo da entrega

O núcleo de análise ganhou as guardas pós-LLM (ancoragem literal de citação + regras por campo) e o **loop de revisão humana do PRD §9** (Confirmar/Corrigir/Registrar, auditável), que era o Must mais crítico pendente. O módulo `evaluation` deixou de ser planejado e passou a existir com o golden set sintético (2 apólices × 10 campos = 20 casos) e a UI consome apenas fachadas públicas. Suíte do projeto após a entrega: 233 passed, 4 skipped (esta feature contribuiu com +60 testes); gate local `ruff + mypy + pytest` verde 3× consecutivas.

## Impacto por artefato da extração

| Artefato | Seção | Tipo de impacto | Delta |
|----------|-------|-----------------|-------|
| `_reversa_sdd/sdd/policy-analysis.md` | §6.1 Requisitos Funcionais | componente-novo | Guardas pós-LLM implementadas: citação precisa ser substring literal do chunk citado (**OQ-02 decidida: substring**), `temperature=0`, erros sanitizados; regras por campo (`vigencia_ordem`, `valor_positivo`, moedas, `enum_base_territorial`) rebaixam fato inválido para `NEEDS_REVIEW` |
| `_reversa_sdd/sdd/policy-analysis.md` | §6.1 (fila de revisão) / `prd.md` §9 | componente-novo | Fila de revisão deixou de só listar: loop humano **Confirmar / Corrigir valor / Registrar divergência** com revisor, timestamp e `EvidenceRef`; valor revisado alimenta a comparação |
| `_reversa_sdd/sdd/policy-analysis.md` | §9 Modelo de Dados | delta-de-dados | Nova tabela `reviews` no DuckDB (decisões humanas rastreáveis); `requires_human_review` permanece no contrato (nenhum delta MAJOR no `shared_kernel`) |
| `_reversa_sdd/sdd/evaluation.md` | §6.1 Requisitos Funcionais | componente-novo | O esqueleto do módulo (exigido no vertical slice) existe com fachada mínima + golden set sintético 2×10 = 20 casos e relatório por campo; **ressalva registrada: não valida R1/R3** (validação com apólices reais/anonimizadas = `D2-P1-3`) |
| `_reversa_sdd/prd.md` | §4 Escopo (in) | regra-alterada | Tela do analista com componente de revisão; UI passa a consumir só fachadas (regra de importação agora coberta por teste em `src/ui`); higiene de artefatos sensíveis (uploads temporários limpos; `exports/` com aviso de retenção) |
| `_reversa_sdd/sdd/shared-kernel-contracts.md` | §6.1 Requisitos Funcionais | componente-novo | Contrato v1.0.0 intacto; `ExtractedFact` ganha guarda adicional no consumo (ancoragem), sem mudança de formato |

## Regras sob vigilância

Nenhum watch item na tabela principal (cenário greenfield). Observações sem peso de regressão: `O001`..`O006` em `_reversa_forward/003-p0-dev2-analise-experiencia/regression-watch.md`.

## Fontes

- `_reversa_forward/003-p0-dev2-analise-experiencia/requirements.md`
- `_reversa_forward/003-p0-dev2-analise-experiencia/actions.md`
- `_reversa_forward/003-p0-dev2-analise-experiencia/progress.jsonl`
- `_reversa_forward/003-p0-dev2-analise-experiencia/legacy-impact.md`
- `_reversa_forward/003-p0-dev2-analise-experiencia/regression-watch.md`
