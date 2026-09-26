# Regression-Watch: P0 do Desenvolvedor 2 — Análise e Experiência

> Identificador: `003-p0-dev2-analise-experiencia`
> Data: `2026-09-26`
> Feature greenfield: sem regras 🟢 extraídas de legado para vigiar. O watch principal
> fica vazio; as regras implementadas ganham peso quando uma futura re-extração `/reversa`
> sobre o código novo as confirmar como 🟢.

## Watch principal

| ID | Origem (arquivo, seção) | Regra esperada após mudança | Tipo de verificação | Sinal de violação |
|----|-------------------------|-----------------------------|---------------------|-------------------|
| — | — | — | — | — |

## Observações (sem peso de regressão)

IDs estáveis para acompanhamento das regras implementadas nesta feature:

| ID | Origem | Regra implementada nesta feature |
|----|--------|----------------------------------|
| O001 | `actions.md` D2-P0-1 | Ancoragem literal de citação (OQ-02 = substring): excerpt sem substring no chunk citado nunca vira `FOUND`; `temperature=0` |
| O002 | `actions.md` D2-P0-3 | Regras por campo: falha vira `NEEDS_REVIEW` + `requires_human_review` + `rule_violations` (nunca `FOUND`) |
| O003 | `actions.md` D2-P0-2 | Loop de revisão humana (Must PRD §9): Confirmar/Corrigir/Registrar com revisor, timestamp e `EvidenceRef`; valor revisado alimenta a comparação |
| O004 | `actions.md` D2-P0-4 | `evaluation` existe com golden set sintético 2×10; relatório carrega a ressalva R1/R3 (não valida formato por seguradora) |
| O005 | `actions.md` D2-P0-2 | UI consome só fachadas públicas; `tests/architecture` varre `src/ui` e `evaluation` |
| O006 | `actions.md` T-1/T-2 | Gate local `ruff + mypy + pytest` documentado; erros/UI sem texto de apólice; uploads em `.tmp/uploads/` com limpeza; `exports/` com aviso de retenção |

## Histórico de re-extrações

| Data | Extração | Veredito |
|------|----------|----------|
| — | — | — |

## Arquivadas

| ID | Motivo | Data |
|----|--------|------|
| — | — | — |
