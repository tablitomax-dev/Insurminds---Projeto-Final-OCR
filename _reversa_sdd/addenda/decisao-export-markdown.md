# Adendo de decisão: formato do export = **Markdown** (todos os fluxos)

> Tipo: decisão de produto (não é feature)
> Data: `2026-09-27` (ISO 8601)
> Decidido por: **pbena** (humano) — "vamos definir tudo para markdown"
> Responde: `_reversa_sdd/sdd/policy-analysis.md` **OQ-04** ("Formato do export (Markdown? PDF? XLSX?)")

## Vigência

Vigente desde 2026-09-27.

## Resumo da decisão

O export do resumo da comparação é **Markdown**, em todos os fluxos do projeto. A divergência entre fluxos (Markdown vs PDF) está **fechada em favor de Markdown**: qualquer decisão de PDF/HTML/XLSX de fluxo paralelo fica **superada** por este adendo. A reconciliação na etapa de código sai alinhada por esta referência única.

## Impacto por artefato da extração

| Artefato | Seção | Tipo de impacto | Delta |
|----------|-------|-----------------|-------|
| `_reversa_sdd/sdd/policy-analysis.md` | OQ-04 | questão-respondida | Formato do export = **Markdown** (fica como resposta da OQ; a coluna de "questão em aberto" mantém o registro histórico) |
| `_reversa_sdd/prd.md` | §Critérios (resumo exportado) | regra-alterada | "Resumo exportado capaz de defender a análise" = **Markdown** (formato não estava especificado) |
| `_reversa_sdd/learning/plano-acao-dev2.md` | `D2-P0` (ComparisonService) | sem-mudança | Já diz "export Markdown" 🟢 — consistente com a decisão |
| `_reversa_forward/001-vertical-slice-e2e/roadmap.md` | D-09 | sem-mudança | Já implementado como Markdown standalone (`exports/<ComparisonId>.md`); a ressalva "formato precisa virar PDF/HTML depois" é **superada** — não sai de Markdown |

## Consequência prática

- **Nenhuma mudança de código:** `export_comparison` e `src/ui/components/export.py` já exportam Markdown (`exports/<ComparisonId>.md`) — implementação e decisão agora coincidem.
- Fluxos paralelos que decidiram **PDF** devem convergir para **Markdown** na reconciliação de código.

## Fontes

- Decisão do usuário (pbena), 2026-09-27
- `_reversa_sdd/sdd/policy-analysis.md` (OQ-04)
- `_reversa_forward/001-vertical-slice-e2e/roadmap.md` (D-09)
- `_reversa_sdd/learning/plano-acao-dev2.md` (export Markdown 🟢)