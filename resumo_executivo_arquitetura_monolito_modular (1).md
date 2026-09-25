# Resumo Executivo — Arquitetura Monolítica Modular

## Plataforma Inteligente para Análise e Comparação de Apólices D&O

## 1. Resumo executivo

A separação entre dois desenvolvedores deve ser feita por **capacidades de negócio e fluxo de dados**, não por camadas técnicas. Portanto, não é recomendável separar simplesmente “um desenvolvedor fica com frontend e outro com backend”, pois ambos passariam a tocar continuamente nos mesmos contratos, modelos e fluxos.

A divisão recomendada é:

- **Desenvolvedor 1 — Núcleo documental e RAG:** ingestão, processamento de PDF, PaddleOCR, PP-StructureV3, segmentação, LlamaIndex, embeddings, Qdrant e recuperação de evidências.
- **Desenvolvedor 2 — Núcleo de análise e experiência:** extração estruturada com PydanticAI, validação, DuckDB, comparação entre apólices, Streamlit, relatórios e avaliação dos resultados.

Essa divisão é boa, mas não é perfeitamente independente. Existem quatro zonas inevitáveis de integração:

1. contratos de domínio;
2. metadados dos chunks;
3. evidências;
4. orquestração do workflow.

Essas zonas devem ser definidas antes do desenvolvimento e tratadas como **interfaces estáveis**, não como código compartilhado mutável.

A principal regra é:

> Um módulo pode chamar a interface pública de outro módulo, mas nunca importar suas classes internas, acessar suas tabelas diretamente ou modificar seus arquivos.

O projeto será um monólito modular: um único processo e uma única aplicação, mas com limites internos explícitos, contratos claros e propriedade definida dos dados.

## 2. Princípios arquiteturais

### 2.1 Separar por capacidades

Os módulos devem representar responsabilidades coesas do domínio, não somente tecnologias.

Boa separação:

```text
document_processing
policy_analysis
evaluation
```

Má separação:

```text
models
services
repositories
utils
```

A segunda abordagem tende a permitir que qualquer componente importe qualquer outro e rapidamente cria um monólito acoplado.

### 2.2 Isolar implementações

O módulo de análise não deve conhecer PaddleOCR, PyMuPDF, LlamaIndex ou Qdrant. Ele deve conhecer apenas a capacidade de consultar evidências.

O módulo documental não deve conhecer regras de comparação, telas Streamlit ou a interpretação de coberturas.

### 2.3 Contratos antes da implementação

Os contratos compartilhados devem ser definidos antes do desenvolvimento paralelo. Eles funcionam como um acordo entre os dois desenvolvedores e reduzem bloqueios entre branches.

### 2.4 Comparação determinística

O LLM pode extrair, validar e explicar, mas a comparação entre valores estruturados deve ser realizada por regras determinísticas. Não se deve comparar apólices inteiras apenas por similaridade vetorial ou pela interpretação livre do LLM.

### 2.5 Evidência obrigatória

Todo fato extraído deve apontar para uma evidência de origem:

- apólice;
- documento;
- página;
- trecho;
- seção ou cláusula;
- chunk;
- score de recuperação, quando aplicável.

## 3. Mapa de domínios

| Domínio/módulo | Tipo | Responsabilidade principal | Dono sugerido |
|---|---|---|---|
| Ingestão de documentos | Negócio/técnico | Receber, identificar e registrar arquivos | Desenvolvedor 1 |
| Processamento documental | Técnico | Extrair texto de PDF/imagem | Desenvolvedor 1 |
| OCR e layout | Técnico especializado | PaddleOCR, PP-Structure, caixas e blocos | Desenvolvedor 1 |
| Indexação RAG | Técnico | Nodes, chunks, embeddings e Qdrant | Desenvolvedor 1 |
| Recuperação de evidências | Negócio/técnico | Buscar trechos por apólice e campo | Desenvolvedor 1 |
| Catálogo de apólices | Negócio | Identificação, versões, documentos e status | Desenvolvedor 2 |
| Extração estruturada | Negócio/IA | Transformar evidências em fatos tipados | Desenvolvedor 2 |
| Validação e revisão | Negócio/IA | Validar campos, confiança e revisão humana | Desenvolvedor 2 |
| Comparação | Negócio | Comparar limites, coberturas, exclusões e condições | Desenvolvedor 2 |
| Explicação | IA/apresentação | Explicar diferenças com base em evidências | Desenvolvedor 2 |
| Interface Streamlit | Apresentação | Upload, revisão, consulta e comparação | Desenvolvedor 2 |
| Persistência DuckDB | Infraestrutura de dados | Fatos, evidências, resultados e auditoria | Desenvolvedor 2 |
| Observabilidade | Transversal | Logs, métricas, traces e custo | Compartilhado |
| Configuração | Transversal | Variáveis, modelos e paths | Compartilhado |
| Testes de integração | Transversal | Validar a integração entre os módulos | Compartilhado |

## 4. Domínios sem sobreposição significativa

### 4.1 Responsabilidades do Desenvolvedor 1

- Leitura de PDF e imagem.
- Detecção de texto nativo.
- Renderização de páginas.
- PaddleOCR.
- PP-StructureV3.
- Extração de blocos e coordenadas.
- Normalização documental.
- Chunking.
- Embeddings Gemini.
- Indexação no Qdrant.
- Retrieval de chunks.

### 4.2 Responsabilidades do Desenvolvedor 2

- Schemas Pydantic de domínio.
- Catálogo de apólices.
- DuckDB.
- Extração de fatos estruturados.
- Validação de resultados.
- Motor de comparação.
- Tela de revisão.
- Tela comparativa.
- Relatórios.
- Avaliação dos resultados.

A divisão é viável porque o Desenvolvedor 1 produz **evidências documentais recuperáveis**, enquanto o Desenvolvedor 2 consome essas evidências e produz **fatos e comparações estruturados**.

## 5. Domínios com sobreposição

### 5.1 Evidência

O Desenvolvedor 1 conhece:

- página;
- bloco;
- posição;
- texto OCR;
- score de OCR;
- chunk;
- score de recuperação.

O Desenvolvedor 2 precisa:

- página;
- trecho;
- seção;
- cláusula;
- confiança;
- origem do campo extraído.

Se ambos criarem modelos próprios de evidência, haverá incompatibilidade.

**Decisão:** `EvidenceRef` deve ser um contrato compartilhado, definido em conjunto e alterado somente com revisão dos dois desenvolvedores.

### 5.2 Documento e apólice

Uma apólice pode possuir vários documentos: condições gerais, condições particulares, endossos e anexos. Portanto, não se deve usar um único identificador para tudo.

```text
policy_id   = entidade lógica da apólice
document_id = arquivo físico associado à apólice
page_id     = página do documento
chunk_id    = fragmento indexado
fact_id     = fato extraído
comparison_id = comparação entre apólices
```

### 5.3 Orquestração

O Desenvolvedor 1 sabe quando o documento foi indexado. O Desenvolvedor 2 sabe quando pode iniciar a extração estruturada.

Se ambos controlarem o pipeline, haverá lógica duplicada ou chamadas fora de ordem.

**Decisão:** criar uma camada de aplicação com workflow explícito. Os módulos não chamam diretamente implementações internas uns dos outros; o workflow coordena as fachadas públicas.

### 5.4 LLMs

Se cada desenvolvedor instanciar seu próprio cliente de modelo, haverá:

- configurações duplicadas;
- prompts espalhados;
- custos não rastreados;
- versões inconsistentes;
- dificuldade de fallback.

**Decisão:** criar um módulo comum de `ModelRuntime`, sem lógica de negócio.

### 5.5 Observabilidade

Todos os módulos devem registrar:

- `run_id`;
- `policy_id`;
- `document_id`;
- duração;
- modelo;
- tokens;
- custo;
- erros;
- status.

Observabilidade deve ser tratada como contrato transversal, não como propriedade de apenas um desenvolvedor.

## 6. Divisão de trabalho

## 6.1 Desenvolvedor 1 — Pipeline documental e RAG

### Responsabilidade

Construir a camada que transforma arquivos em evidências recuperáveis:

```text
Arquivo
  → páginas
  → texto/blocos
  → chunks
  → embeddings
  → Qdrant
  → evidências recuperadas
```

### Estrutura de módulos

```text
src/modules/document_processing/
├── domain/
│   ├── document_models.py
│   ├── page_models.py
│   └── ocr_models.py
├── application/
│   ├── process_document.py
│   ├── extract_pages.py
│   └── index_document.py
├── infrastructure/
│   ├── pdf/
│   │   ├── pymupdf_adapter.py
│   │   └── renderer.py
│   ├── ocr/
│   │   ├── paddleocr_adapter.py
│   │   └── pp_structure_adapter.py
│   └── rag/
│       ├── llamaindex_pipeline.py
│       ├── embedding_adapter.py
│       ├── qdrant_adapter.py
│       └── retriever.py
└── public_api.py
```

### Entregas

- Extrair texto nativo de PDFs.
- Detectar páginas que exigem OCR.
- Executar PaddleOCR.
- Executar PP-StructureV3 em documentos complexos.
- Persistir páginas e blocos.
- Gerar chunks com metadados.
- Gerar embeddings Gemini.
- Indexar no Qdrant.
- Recuperar chunks por pergunta e filtros.
- Fornecer evidências em formato público.
- Criar fixtures de documentos e chunks para testes.

### Fora da responsabilidade

- Comparar apólices.
- Criar telas finais de revisão.
- Definir regra de superioridade de cobertura.
- Persistir fatos extraídos como verdade de negócio.
- Escrever diretamente nas tabelas de comparação.
- Criar prompts de explicação comparativa.

## 6.2 Desenvolvedor 2 — Núcleo de análise e interface

### Responsabilidade

Transformar evidências em fatos de negócio, validar, comparar e apresentar:

```text
Evidências
  → fatos estruturados
  → validação
  → revisão humana
  → comparação
  → explicação
  → interface
```

### Estrutura de módulos

```text
src/modules/policy_analysis/
├── domain/
│   ├── policy_models.py
│   ├── fact_models.py
│   ├── comparison_models.py
│   └── business_rules.py
├── application/
│   ├── extract_policy_facts.py
│   ├── validate_facts.py
│   ├── compare_policies.py
│   └── explain_comparison.py
├── infrastructure/
│   ├── duckdb/
│   │   ├── connection.py
│   │   ├── repositories.py
│   │   └── migrations.py
│   └── llm/
│       ├── extraction_agent.py
│       ├── validation_agent.py
│       └── explanation_agent.py
├── presentation/
│   └── streamlit/
│       ├── upload_page.py
│       ├── review_page.py
│       ├── comparison_page.py
│       └── components.py
└── public_api.py
```

### Entregas

- Modelos Pydantic de apólice, fato, evidência e comparação.
- Tabelas DuckDB.
- Persistência de documentos e fatos.
- Agente de extração estruturada.
- Agente de validação.
- Revisão humana.
- Motor de comparação determinístico.
- Agente de explicação.
- Interface Streamlit.
- Exportação dos resultados.
- Fixtures de fatos e comparações para testes.

### Fora da responsabilidade

- Alterar o código interno do PaddleOCR.
- Alterar chunking interno sem coordenação.
- Escrever diretamente no Qdrant.
- Criar um segundo modelo de `Evidence`.
- Implementar parsing de PDF.
- Definir payloads arbitrariamente no vector store.

## 7. Estrutura do monólito modular

```text
src/
├── shared_kernel/
│   ├── identifiers.py
│   ├── errors.py
│   ├── contracts.py
│   ├── result.py
│   └── observability.py
│
├── modules/
│   ├── document_processing/
│   │   ├── domain/
│   │   ├── application/
│   │   ├── infrastructure/
│   │   └── public_api.py
│   │
│   ├── policy_analysis/
│   │   ├── domain/
│   │   ├── application/
│   │   ├── infrastructure/
│   │   └── public_api.py
│   │
│   └── evaluation/
│       ├── domain/
│       ├── application/
│       ├── infrastructure/
│       └── public_api.py
│
├── composition_root/
│   └── container.py
│
└── app.py
```

### Regra de importação

Permitido:

```text
document_processing.public_api
policy_analysis.public_api
shared_kernel.contracts
shared_kernel.identifiers
```

Proibido:

```text
policy_analysis importar:
document_processing.infrastructure.ocr.paddleocr_adapter

document_processing importar:
policy_analysis.infrastructure.duckdb.repositories

qualquer módulo importar:
outro_modulo.domain.internals
```

O acesso entre módulos ocorre somente pela API pública.

## 8. Contratos compartilhados

O pacote `shared_kernel/contracts` deve ser pequeno e estável.

### 8.1 Identificadores

```python
from typing import NewType

PolicyId = NewType("PolicyId", str)
DocumentId = NewType("DocumentId", str)
PageId = NewType("PageId", str)
ChunkId = NewType("ChunkId", str)
FactId = NewType("FactId", str)
ComparisonId = NewType("ComparisonId", str)
RunId = NewType("RunId", str)
```

### 8.2 Evidência

```python
from pydantic import BaseModel, Field
from typing import Literal

class EvidenceRef(BaseModel):
    evidence_id: str
    policy_id: str
    document_id: str
    page_number: int = Field(ge=1)
    chunk_id: str | None = None
    section_name: str | None = None
    clause_number: str | None = None
    quoted_text: str = Field(min_length=1)
    retrieval_score: float | None = Field(default=None, ge=0, le=1)
    ocr_confidence: float | None = Field(default=None, ge=0, le=1)
    source_type: Literal[
        "NATIVE_TEXT",
        "PADDLEOCR",
        "PP_STRUCTURE",
    ]
```

O contrato não deve exigir campos que um módulo ainda não consegue fornecer. Campos como `clause_number` podem ser opcionais quando não estiverem presentes no documento.

### 8.3 Recuperação

```python
class RetrievalQuery(BaseModel):
    query: str
    policy_id: str | None = None
    document_id: str | None = None
    section_name: str | None = None
    field_code: str | None = None
    top_k: int = Field(default=5, ge=1, le=20)

class RetrievalResult(BaseModel):
    query: RetrievalQuery
    evidences: list[EvidenceRef]
    retrieval_run_id: str
```

### 8.4 Extração

```python
class ExtractionRequest(BaseModel):
    policy_id: str
    field_code: str
    evidences: list[EvidenceRef]
    schema_version: str

class ExtractedFact(BaseModel):
    fact_id: str
    policy_id: str
    field_code: str
    status: Literal[
        "FOUND",
        "NOT_FOUND",
        "AMBIGUOUS",
        "NEEDS_REVIEW",
    ]
    value: dict | None
    normalized_value: dict | None
    confidence: float = Field(ge=0, le=1)
    evidence_ids: list[str]
    requires_human_review: bool
```

O Desenvolvedor 1 produz `EvidenceRef`. O Desenvolvedor 2 consome `EvidenceRef` e produz `ExtractedFact`.

### 8.5 Processamento

```python
class ProcessingStatus(BaseModel):
    document_id: str
    stage: Literal[
        "RECEIVED",
        "TEXT_EXTRACTED",
        "OCR_COMPLETED",
        "INDEXED",
        "FACTS_EXTRACTED",
        "REVIEW_REQUIRED",
        "COMPLETED",
        "FAILED",
    ]
    progress: float = Field(ge=0, le=1)
    message: str | None = None
```

## 9. Integração entre os módulos

### 9.1 Integração por fachada

Cada módulo deve expor uma fachada pública.

```python
class DocumentProcessingFacade:
    def process_document(
        self,
        document_id: str,
        file_path: str,
    ) -> ProcessingStatus:
        ...

    def retrieve_evidence(
        self,
        query: RetrievalQuery,
    ) -> RetrievalResult:
        ...
```

O módulo de análise não acessa Qdrant, LlamaIndex ou PaddleOCR diretamente.

```python
class PolicyAnalysisFacade:
    def extract_facts(
        self,
        request: ExtractionRequest,
    ) -> ExtractedFact:
        ...

    def compare(
        self,
        policy_a_id: str,
        policy_b_id: str,
    ) -> ComparisonResult:
        ...
```

### 9.2 Integração por workflow

O workflow conhece a ordem completa:

```python
class AnalyzePolicyWorkflow:
    def __init__(
        self,
        document_processing: DocumentProcessingFacade,
        policy_analysis: PolicyAnalysisFacade,
    ):
        self.document_processing = document_processing
        self.policy_analysis = policy_analysis

    def run(self, document_id: str, file_path: str):
        status = self.document_processing.process_document(
            document_id=document_id,
            file_path=file_path,
        )

        if status.stage != "INDEXED":
            raise ProcessingNotReadyError(status.message)

        return self.policy_analysis.extract_from_document(
            document_id=document_id,
        )
```

### 9.3 Integração por eventos internos

Para o MVP single-user, não se recomenda Kafka, Redis ou outro broker. Eventos podem ser representados por classes Python ou por uma tabela simples no DuckDB.

```python
class DocumentIndexed:
    document_id: str
    policy_id: str
    chunk_count: int
    index_name: str
    run_id: str
```

Fluxo:

```text
DocumentUploaded
    → DocumentProcessed
    → DocumentIndexed
    → FactsExtractionRequested
    → FactsExtracted
    → ReviewRequired ou AnalysisReady
```

### 9.4 Integração por banco

Cada módulo deve ser dono de suas tabelas.

| Tabela | Dono |
|---|---|
| `document` | Desenvolvedor 1, com leitura pelo Desenvolvedor 2 |
| `document_page` | Desenvolvedor 1 |
| `document_block` | Desenvolvedor 1 |
| `rag_chunk` | Desenvolvedor 1 |
| `policy` | Desenvolvedor 2 |
| `extracted_fact` | Desenvolvedor 2 |
| `evidence` | Desenvolvedor 2, recebendo referências do Desenvolvedor 1 |
| `comparison` | Desenvolvedor 2 |
| `workflow_run` | Compartilhada por contrato |
| `audit_event` | Adapter compartilhado |

O Desenvolvedor 2 não deve executar SQL diretamente contra tabelas internas do Desenvolvedor 1. Deve consumir um repository ou uma porta.

```python
class DocumentQueryPort(Protocol):
    def get_document(self, document_id: str) -> DocumentSummary:
        ...

    def get_pages(self, document_id: str) -> list[PageSummary]:
        ...
```

## 10. Conflitos prováveis e mitigação

### Conflito 1: ambos alteram `policy_models.py`

Solução:

- Modelos compartilhados ficam em `shared_kernel/contracts`.
- Alterações exigem revisão dos dois desenvolvedores.
- Modelos internos ficam dentro do módulo dono.
- Não usar o mesmo modelo Pydantic para persistência, OCR, Qdrant, LLM, Streamlit e domínio.

### Conflito 2: nomes de metadados divergentes

Exemplo de inconsistência:

```text
section
section_name
clause
clause_number
```

Solução: definir um contrato versionado de metadados:

```python
class ChunkMetadata(BaseModel):
    policy_id: str
    document_id: str
    page_number: int
    section_name: str | None
    clause_number: str | None
    document_type: str | None
    source_type: str
    content_hash: str
    pipeline_version: str
```

### Conflito 3: assumir OCR perfeito

O contrato deve expor incerteza:

```text
ocr_confidence
text_quality
source_type
requires_human_review
```

O Desenvolvedor 2 não deve assumir que um trecho é correto apenas porque veio do OCR.

### Conflito 4: ambos chamam LLM

Usar dois níveis de abstração:

```text
shared:
    ModelGateway
    UsageMetrics
    RetryPolicy

module-specific:
    ExtractionAgent
    ExplanationAgent
```

Exemplo:

```python
class ModelGateway(Protocol):
    async def generate_structured(
        self,
        *,
        model: str,
        prompt: str,
        output_type: type[BaseModel],
    ) -> BaseModel:
        ...
```

O gateway é compartilhado; prompts, schemas de saída e regras de negócio pertencem ao módulo que utiliza o LLM.

### Conflito 5: Streamlit acessa diretamente os módulos internos

A interface deve chamar somente uma fachada de aplicação:

```python
class ApplicationFacade:
    def upload_and_process(self, file) -> ProcessingStatus: ...
    def review_facts(self, policy_id) -> list[ExtractedFact]: ...
    def compare_policies(self, a, b) -> ComparisonResult: ...
    def ask_question(self, request) -> GroundedAnswer: ...
```

A interface não deve:

- abrir conexão com Qdrant;
- executar SQL diretamente;
- instanciar agentes;
- conhecer prompts;
- executar OCR;
- importar PaddleOCR.

## 11. Plano de desenvolvimento

### Fase 0 — Contratos

Responsabilidade compartilhada.

Entregáveis:

- IDs;
- `EvidenceRef`;
- `RetrievalQuery`;
- `RetrievalResult`;
- `ExtractedFact`;
- `ProcessingStatus`;
- estados do workflow;
- convenções de erro;
- fixtures JSON;
- versionamento.

Nenhum desenvolvedor deve iniciar implementação substancial antes dessa fase.

### Fase 1 — Desenvolvimento paralelo com mocks

Desenvolvedor 1:

- OCR;
- processamento de páginas;
- chunks;
- Qdrant;
- retrieval.

Desenvolvedor 2:

- DuckDB;
- schemas de fatos;
- agentes de extração;
- comparação;
- telas com dados falsos.

### Fase 2 — Primeiro contrato real

Integrar somente:

```text
Retrieval real do Desenvolvedor 1
        ↓
EvidenceRef
        ↓
Extração real do Desenvolvedor 2
        ↓
ExtractedFact
```

Não integrar comparação, relatório e observabilidade todos de uma vez.

### Fase 3 — Workflow ponta a ponta

```text
upload
  → OCR
  → indexação Qdrant
  → retrieval
  → extração
  → DuckDB
  → revisão
  → comparação
  → explicação
  → Streamlit
```

### Fase 4 — Quality gates

- Teste de contrato.
- Teste com PDF nativo.
- Teste com PDF escaneado.
- Teste com tabela.
- Teste de documento duplicado.
- Teste de baixa confiança.
- Teste de falha do LLM.
- Teste de recuperação sem evidência.
- Teste de comparação com campo ausente.

## 12. Governança do trabalho

### 12.1 Branches

```text
main
develop
feature/dev1-document-processing
feature/dev1-rag
feature/dev2-policy-analysis
feature/dev2-streamlit
integration/end-to-end
```

O branch de integração deve ser criado cedo, mas não deve virar o local de desenvolvimento cotidiano.

### 12.2 Regras de pull request

Toda PR deve responder:

- Qual módulo foi alterado?
- Qual contrato foi alterado?
- Houve mudança de schema?
- Houve mudança de prompt?
- Houve mudança de persistência?
- Quais testes foram executados?
- O custo de LLM mudou?
- Existe impacto no outro módulo?

### 12.3 Ownership

```text
Desenvolvedor 1:
src/modules/document_processing/**
data/qdrant/**
tests/document_processing/**

Desenvolvedor 2:
src/modules/policy_analysis/**
src/interfaces/streamlit/**
data/insurance.duckdb schema logic
tests/policy_analysis/**

Ambos:
src/shared_kernel/contracts/**
src/composition_root/**
tests/contracts/**
docs/architecture/**
```

A pasta `shared_kernel` deve ser pequena. Se começar a conter serviços, regras de negócio, helpers gerais e modelos de todos os módulos, tornou-se um novo ponto de acoplamento.

## 13. Crítica final da divisão

A divisão é boa, mas existe um risco real: o Desenvolvedor 1 pode ficar responsável por uma infraestrutura sofisticada demais, enquanto o Desenvolvedor 2 concentra todo o valor de negócio.

O pipeline PaddleOCR + PP-StructureV3 + LlamaIndex + Gemini Embeddings + Qdrant possui bastante trabalho técnico. Para evitar bloqueios, deve ser construído primeiro um vertical slice mínimo:

```text
PDF simples
  → PyMuPDF/PaddleOCR básico
  → chunks
  → Qdrant
  → retrieval
  → um campo extraído
  → uma comparação
  → tela simples
```

Somente depois devem ser adicionados:

- PP-Structure;
- tabelas;
- múltiplos agentes;
- fallback de modelos;
- scoring avançado;
- explicação sofisticada;
- avaliação completa.

Também não é realista tentar criar dois módulos completamente independentes. Eles inevitavelmente compartilham:

- identidade de documentos;
- evidência;
- estados do workflow;
- configuração;
- observabilidade;
- contratos de LLM.

O objetivo é que cada desenvolvedor trabalhe sem tocar no **código interno** do outro, e não que jamais exista dependência entre os módulos.

## 14. Quality gates arquiteturais

Antes de aceitar uma integração, verificar:

### Segurança

- Arquivos são validados antes do processamento.
- Nenhuma credencial está no repositório.
- O texto de apólice é tratado como dado não confiável.
- O LLM não recebe permissões de escrita arbitrárias.
- Dados sensíveis não são enviados a serviços externos sem decisão explícita.

### Contratos

- Outputs são validados por Pydantic.
- IDs são consistentes entre DuckDB e Qdrant.
- Evidências possuem página e trecho.
- Mudanças de contrato têm versão.

### Rastreabilidade

- Fatos apontam para evidências.
- Chunks apontam para documento e página.
- Execuções possuem `run_id`.
- Prompts e schemas têm versão.

### Operabilidade

- Erros são classificados.
- Processamento é reexecutável.
- Falhas parciais podem ser identificadas.
- Há logs suficientes para investigar uma comparação.

### Simplicidade

- Nenhum broker externo.
- Nenhum microsserviço.
- Nenhum framework duplicado para a mesma responsabilidade.
- Nenhuma abstração sem caso de uso demonstrável.

## 15. Confiança

**Confiança: 95%.**

A divisão recomendada reduz o acoplamento e alinha cada desenvolvedor a uma capacidade coerente:

```text
Desenvolvedor 1 = documento → evidência recuperável
Desenvolvedor 2 = evidência → análise → comparação → interface
```

Os itens que precisam ser definidos antes do código são:

- schema definitivo de `EvidenceRef`;
- distinção entre `policy_id`, `document_id`, `page_id` e `chunk_id`;
- ownership das tabelas DuckDB;
- fachada pública de cada módulo;
- versão inicial do workflow;
- campos críticos do primeiro vertical slice.

Sem esses contratos, a arquitetura poderá parecer modular nos diretórios, mas continuará acoplada por modelos, SQL, prompts e decisões implícitas.
