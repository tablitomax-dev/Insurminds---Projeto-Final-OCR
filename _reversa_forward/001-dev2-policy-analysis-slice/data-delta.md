# Data Delta: Vertical slice do policy_analysis

> Identificador: `001-dev2-policy-analysis-slice`
> Data: `2026-09-26`
> Base de referência: `_reversa_sdd/sdd/policy-analysis.md#9` (modelo de dados) + `_reversa_sdd/sdd/shared-kernel-contracts.md#8` (contratos)

## 1. Visão geral

Diff conceitual sobre o modelo proposto na spec: o banco DuckDB deste módulo é **novo** (greenfield), com 4 tabelas. Não há tabelas existentes para alterar nem dados para migrar. Todos os identificadores são os do `shared_kernel` (`PolicyId`, `DocumentId`, `FactId`, `ComparisonId`, `RunId`), garantindo a consistência banco↔índice exigida pelo resumo §14.

## 2. Novas tabelas

### 2.1 `policies`

| Campo | Tipo | Regra |
|-------|------|-------|
| `policy_id` | VARCHAR (PK) | `PolicyId` do shared_kernel |
| `seguradora` | VARCHAR | nome da seguradora |
| `vigencia_inicio` | DATE | início da vigência |
| `vigencia_fim` | DATE | fim da vigência |
| `fonte_documentos` | VARCHAR | origem dos PDFs (caminho ou referência) |
| `created_at` | TIMESTAMP | registro da criação |

### 2.2 `documents`

| Campo | Tipo | Regra |
|-------|------|-------|
| `document_id` | VARCHAR (PK) | `DocumentId` do shared_kernel (mesmo ID dos chunks Qdrant) |
| `policy_id` | VARCHAR (FK → policies) | apólice dona do documento |
| `nome_fonte` | VARCHAR | nome do arquivo/origem |

### 2.3 `facts`

| Campo | Tipo | Regra |
|-------|------|-------|
| `fact_id` | VARCHAR (PK) | `FactId` do shared_kernel |
| `policy_id` | VARCHAR (FK → policies) | apólice do fato |
| `field_code` | VARCHAR | deve estar no catálogo (RF-02); FK lógica ao registry |
| `status` | VARCHAR | `FOUND \| NOT_FOUND \| AMBIGUOUS \| NEEDS_REVIEW` (literals do contrato) |
| `value` | VARCHAR (JSON) | valor bruto extraído |
| `normalized_value` | VARCHAR (JSON) | valor normalizado (moeda BRL, período, texto normalizado) |
| `confidence` | DOUBLE | [0,1] |
| `evidence_ids` | VARCHAR (JSON array) | referências a evidências/chunks; `[]` só em `NOT_FOUND` (EC-05 dos contratos) |
| `requires_human_review` | BOOLEAN | sinalização de revisão (RN-03) |
| `revisao_status` | VARCHAR | `PENDENTE \| CONFIRMADO \| CORRIGIDO` |
| `revisao_decisao` | VARCHAR (JSON) | decisão registrada do analista (fato novo ou confirmação) |
| `revisao_por` / `revisao_em` | VARCHAR / TIMESTAMP | quem/quando decidiu (auditoria mínima) |
| `run_id` | VARCHAR | `RunId` da execução (observabilidade RNF-03) |
| `schema_version` | VARCHAR | versão do contrato usado na extração |

### 2.4 `comparisons`

| Campo | Tipo | Regra |
|-------|------|-------|
| `comparison_id` | VARCHAR (PK) | `ComparisonId` **determinístico**: hash estável do par ordenado (`policy_id_a`, `policy_id_b`) — idempotência EC-06 (D-09) |
| `policy_id_a` / `policy_id_b` | VARCHAR (FK → policies) | par comparado, sempre em ordem canônica |
| `field_code` | VARCHAR | campo do catálogo comparado |
| `resultado` | VARCHAR | `MAIOR \| MENOR \| IGUAL \| DIVERGENTE \| AUSENTE_A \| AUSENTE_B \| AUSENTES_AMBOS` (por tipo, tabela OQ-03) |
| `valor_a` / `valor_b` | VARCHAR (JSON) | `normalized_value` de cada lado (null se ausente) |
| `direcao` | VARCHAR | lado com valor mais alto/relevante quando houver |
| `evidencias` | VARCHAR (JSON) | `evidence_ids` dos dois lados |
| `explicacao` | VARCHAR | texto citando evidências dos dois lados (RF-07) |
| `created_at` | TIMESTAMP | primeira gravação; reexecução do mesmo par não duplica (EC-06) |

## 3. Campos alterados ou removidos

Nenhum — banco novo, sem versão anterior.

## 4. Migrações de dados

n/a. Schema criado na primeira execução com `CREATE TABLE IF NOT EXISTS` (idempotente). Reexecução do mesmo par de apólices reutiliza o `comparison_id` e atualiza o registro (sem duplicar). Rollback = remover o arquivo do DuckDB.

## 5. Consistência de IDs (banco ↔ índice)

- `documents.document_id` = `document_id` dos `ChunkMetadata` do Dev 1.
- `facts.evidence_ids` = `evidence_id` das `EvidenceRef` retornadas por `retrieve_evidence`.
- Nenhuma tabela inventa ID próprio para entidades compartilhadas — apenas `fact_id`/`comparison_id` são gerados aqui (e `comparison_id` de forma determinística).