# Legacy-Impact: P0 do Desenvolvedor 2 — Análise e Experiência

> Identificador: `dev2-003-p0-analise-experiencia`
> Data: `2026-09-26`
> Feature greenfield (âncora: prd.md + specs SDD); "legado" aqui = código entregue pelas features `001`/`002`.
> Política de edição: `allowLegacyEdits: true`, `allowedPaths = ["src/**", "tests/**", "pyproject.toml", "requirements.txt", ".gitignore"]` — escritas restritas a esses globs.

## Modificadas

| Arquivo afetado | Componente (spec) | Tipo | Severidade | Justificativa |
|-----------------|-------------------|------|------------|---------------|
| `src/modules/policy_analysis/application/extraction.py` | `policy-analysis` (`_reversa_sdd/sdd/policy-analysis.md#6.1`) | regra-alterada | MEDIUM | `LlmOutputError` sanitizado (tipo + nome de campo + IDs, nunca valores/texto); validação passa a exigir ancoragem literal de citação |
| `src/modules/policy_analysis/application/comparison.py` | `policy-analysis` (RF-06..RF-08) | regra-alterada | MEDIUM | valor revisado pelo humano substitui o cru na comparação; citações da explicação ancoradas nos textos dos dois lados |
| `src/modules/policy_analysis/infrastructure/llm_extractors.py` | `policy-analysis` | regra-alterada | LOW | `temperature = 0.0` em extração e explicação; sanitização de erro do SDK |
| `src/modules/policy_analysis/infrastructure/duckdb_repository.py` | `policy-analysis` (`#9` modelo de dados) | delta-de-dados | LOW | nova tabela `reviews` (revisor, timestamp, valor original/corrigido, `EvidenceRef`); `FactRepository` ganha `save_review`/`list_reviews` |
| `src/modules/policy_analysis/public_api.py` | `policy-analysis` | regra-alterada | MEDIUM | fachada expõe revisão humana (`confirm_fact`/`correct_fact`/`register_divergence`) e o que a UI precisa (`list_fields`, `create_document_processing_retriever`) — UI sem acesso a internals (F-15) |
| `src/ui/app.py` | `prd.md#4` (tela do analista) | regra-alterada | MEDIUM | componente de revisão humana (Confirmar/Corrigir/Registrar); sem imports de `infrastructure`/`domain` alheios; erro sanitizado |
| `tests/architecture/test_imports.py` | suíte de verificação | regra-alterada | LOW | passe a varrer `src/ui` e `src/modules/evaluation` (regra de fachada coberta por teste em todo alvo) |
| `pyproject.toml`, `.gitignore` | infraestrutura do projeto | regra-nova | LOW | gate `T-1` (`[tool.ruff]`, `[tool.mypy]`); ignore de `.tools/`, `.tmp/`, `exports/` |

## Arquivos criados (todo o impacto é `componente-novo`)

| Arquivo afetado | Componente (spec) | Tipo | Severidade | Justificativa |
|-----------------|-------------------|------|------------|---------------|
| `src/modules/policy_analysis/domain/anchoring.py` | `policy-analysis` | componente-novo | MEDIUM | guarda anti-alucinação: excerpt precisa ser substring literal do chunk citado (OQ-02 = substring) |
| `src/modules/policy_analysis/domain/rules.py` | `policy-analysis` | componente-novo | MEDIUM | regras por campo (`vigencia_ordem`, `valor_positivo`, moedas, `enum_base_territorial`): falha → `NEEDS_REVIEW` |
| `src/modules/policy_analysis/domain/review.py`, `application/review.py` | `policy-analysis` (RF fila de revisão; `prd.md#9`) | componente-novo | MEDIUM | loop de revisão humana: Confirmar / Corrigir / Registrar divergência, auditável e rastreável ao `EvidenceRef` |
| `src/modules/evaluation/**` | `evaluation` (`_reversa_sdd/sdd/evaluation.md`) | componente-novo | MEDIUM | esqueleto exigido pela spec + golden set sintético 2×10 = 20 casos com relatório por campo e ressalva R1/R3 |
| `src/ui/errors.py`, `src/ui/uploads.py` | `prd.md#4` | componente-novo | LOW | sanitização de erro da UI; uploads em `.tmp/uploads/` com limpeza ao fim do fluxo |
| `tests/modules/policy_analysis/test_anchoring.py`, `test_rules.py`, `test_review.py`, `tests/modules/evaluation/`, `tests/e2e/test_review_cycle.py`, `tests/ui/` | suíte de verificação | componente-novo | LOW | +29 testes (suíte total: 233 passed, 4 skipped) |

## Diff conceitual por componente

- **policy_analysis:** ganhou guardas pós-LLM (ancoragem literal + regras por campo) e o loop de revisão humana do PRD §9; valor revisado alimenta a comparação; erros nunca carregam texto de apólice.
- **evaluation:** deixou de ser "planejado" e existe como módulo com fachada mínima + baseline de medição (golden set sintético — não valida R1/R3; validação real = `D2-P1-3`).
- **UI:** consome apenas fachadas públicas; componente de revisão; higiene de artefatos (exports fixo com aviso de retenção; temp limpo).
- **shared_kernel:** contrato v1.0.0 intacto (`requires_human_review` permanece; `ExtractedFact` ganha guarda adicional de ancoragem no consumo, sem mudança de formato).

## Preservadas

Comparação 100% determinística (LLM jamais compara), catálogo dos 10 `field_code`, EC-05 (FOUND exige evidência), export Markdown, vocabulário de erros por estágio.

## Modificadas (regras removidas)

Nenhuma regra removida.
