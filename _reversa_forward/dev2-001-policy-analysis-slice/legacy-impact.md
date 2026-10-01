# Legacy Impact: Vertical slice do policy_analysis

> Identificador: `dev2-001-policy-analysis-slice`
> Data: `2026-09-26`
> Feature greenfield, sem legado pré-existente. Âncora: `prd.md` + specs SDD (`_reversa_sdd/sdd/`).
> Política de edição no momento da execução: `allowLegacyEdits: true`, `allowedPaths: ["src/**", "tests/**", "pyproject.toml", "requirements.txt", ".gitignore"]`

## Tabela de arquivos tocados

| Arquivo afetado | Componente | Tipo | Severidade | Justificativa |
|-----------------|------------|------|------------|---------------|
| `src/modules/__init__.py` | `_reversa_sdd/sdd/policy-analysis.md#8` | componente-novo | LOW | scaffolding do pacote de módulos |
| `src/modules/policy_analysis/__init__.py` | `_reversa_sdd/sdd/policy-analysis.md#8` | componente-novo | LOW | scaffolding do módulo |
| `src/modules/policy_analysis/domain/__init__.py` | `_reversa_sdd/sdd/policy-analysis.md#8` | componente-novo | LOW | camada de domínio |
| `src/modules/policy_analysis/domain/value_types.py` | `_reversa_sdd/sdd/policy-analysis.md#15` (D-05) | componente-novo | MEDIUM | value objects Money/Period + normalização determinística (OQ-03) |
| `src/modules/policy_analysis/domain/field_catalog.py` | `_reversa_sdd/sdd/policy-analysis.md#6.1` (RF-02) | componente-novo | MEDIUM | catálogo fechado dos 10 `field_code` (OQ-01) |
| `src/modules/policy_analysis/domain/models.py` | `_reversa_sdd/sdd/policy-analysis.md#8` | componente-novo | LOW | modelos FieldComparison/ComparisonResult/Explanation/ReviewItem |
| `src/modules/policy_analysis/domain/comparison.py` | `_reversa_sdd/sdd/policy-analysis.md#6.1` (RF-06) | componente-novo | HIGH | comparação determinística campo a campo (RN-01, núcleo da feature) |
| `src/modules/policy_analysis/application/__init__.py` | `_reversa_sdd/sdd/policy-analysis.md#8` | componente-novo | LOW | camada de aplicação |
| `src/modules/policy_analysis/application/errors.py` | `_reversa_sdd/sdd/policy-analysis.md#11` (EC-01/EC-05) | componente-novo | MEDIUM | erros classificados + mapeamento `ProcessingStatus(FAILED)` |
| `src/modules/policy_analysis/application/extraction.py` | `_reversa_sdd/sdd/policy-analysis.md#6.1` (RF-03, RF-09) | componente-novo | HIGH | extração validada (RN-02), normalização, NOT_FOUND (EC-03), NEEDS_REVIEW (EC-04) |
| `src/modules/policy_analysis/application/review.py` | `_reversa_sdd/sdd/policy-analysis.md#6.1` (RF-04) | componente-novo | MEDIUM | fila de revisão humana (RN-03) |
| `src/modules/policy_analysis/application/comparison_service.py` | `_reversa_sdd/sdd/policy-analysis.md#6.1` (RF-06) | componente-novo | HIGH | `ComparisonId` determinístico e idempotência (RN-06, EC-06) |
| `src/modules/policy_analysis/application/explanation.py` | `_reversa_sdd/sdd/policy-analysis.md#6.1` (RF-07) | componente-novo | MEDIUM | explicação com citação obrigatória dos dois lados (RN-02) |
| `src/modules/policy_analysis/application/export.py` | `_reversa_sdd/sdd/policy-analysis.md#6.1` (RF-08) | componente-novo | MEDIUM | export standalone (OQ-04: PDF) |
| `src/modules/policy_analysis/infrastructure/__init__.py` | `_reversa_sdd/sdd/policy-analysis.md#8` | componente-novo | LOW | camada de infraestrutura |
| `src/modules/policy_analysis/infrastructure/evidence_source.py` | `_reversa_sdd/sdd/policy-analysis.md#6.1` (RF-01, RF-10) | componente-novo | MEDIUM | porta `EvidenceSource` + mock (desbloqueia Dev 2 antes do Dev 1) |
| `src/modules/policy_analysis/infrastructure/document_processing_source.py` | `_reversa_sdd/sdd/document-processing.md#8` | componente-novo | MEDIUM | único ponto de contato com `document_processing.public_api` (RF-01) |
| `src/modules/policy_analysis/infrastructure/duckdb_repository.py` | `_reversa_sdd/sdd/policy-analysis.md#9` | componente-novo | HIGH | schema DuckDB auto-criado + upsert idempotente (RF-05) |
| `src/modules/policy_analysis/infrastructure/llm_agent.py` | `_reversa_sdd/sdd/policy-analysis.md#6.1` (RF-03, RF-07) | componente-novo | HIGH | agente multi-campo (OQ-02), retry/backoff (EC-01), uso RNF-03 |
| `src/modules/policy_analysis/infrastructure/pdf_export.py` | `_reversa_sdd/sdd/policy-analysis.md#6.1` (RF-08) | componente-novo | LOW | renderização do PDF standalone |
| `src/modules/policy_analysis/public_api.py` | `_reversa_sdd/sdd/policy-analysis.md#8` | componente-novo | HIGH | `PolicyAnalysisFacade` — fronteira pública do módulo |
| `src/modules/policy_analysis/demo.py` | `_reversa_sdd/sdd/policy-analysis.md#6.2` | componente-novo | LOW | demo do fluxo feliz ponta a ponta |
| `tests/modules/policy_analysis/**` (12 arquivos) | `_reversa_sdd/sdd/policy-analysis.md#6.1` | componente-novo | MEDIUM | cobertura dos RF-01..RF-10 + cenários Gherkin (fixtures sintéticas) |
| `requirements.txt` | `_reversa_sdd/sdd/policy-analysis.md#10` | regra-nova | MEDIUM | dependências do módulo (pydantic-ai, duckdb, fpdf2) |

## Diff conceitual por componente

- **policy_analysis (spec `policy-analysis.md`):** componentes `domain`/`application`/`infrastructure`/`public_api` criados do zero, entregando RF-01..RF-10 do vertical slice. Toda a comparação é determinística (RN-01); toda saída de LLM é validada antes de virar fato (RF-09); revisão humana é fluxo de 1ª classe (RF-04).
- **shared_kernel (spec `shared-kernel-contracts.md`):** NÃO modificado — apenas consumido (`EvidenceRef`, `ExtractionRequest`, `ExtractedFact`, `ProcessingStatus`).
- **document_processing (spec `document-processing.md`):** NÃO modificado — consumido exclusivamente via `public_api` quando disponível; `MockEvidenceSource` cobre o desenvolvimento paralelo (RF-10).
- **evaluation (spec `evaluation.md`):** intocado — fora do escopo desta feature (NG-03).

## Preservadas

n/a — feature greenfield, nenhuma regra 🟢 pré-existente para preservar (não houve extração de legado).

## Modificadas

n/a — feature greenfield, nenhuma regra 🟢 foi alterada ou removida.

## Histórico de alterações

| Data | Alteração | Autor |
|------|-----------|-------|
| 2026-09-26 | Versão inicial gerada por `/reversa-coding` | reversa |