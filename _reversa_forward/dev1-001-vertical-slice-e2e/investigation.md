# Investigation: Vertical Slice E2E

> Identificador: `dev1-001-vertical-slice-e2e`
> Data: `2026-09-26`

## 1. Pesquisa de fundo

O stack já está decidido no resumo executivo (Python 3.11+, Pydantic v2, Pydantic AI, Gemini como provedor único, Qdrant Docker, DuckDB, Streamlit, LlamaIndex, PyMuPDF, PaddleOCR). Esta investigação cobre só as decisões de implementação do slice.

## 2. Alternativas avaliadas

| Tema | Alternativa escolhida | Descartadas | Por quê |
|------|----------------------|-------------|---------|
| Injeção de dependência | `typing.Protocol` em `application/ports.py` | ABCs; framework de DI | KISS — Protocol resolve duck-typing nos testes sem framework (PRD §6 viés custo baixo) |
| Texto nativo | PyMuPDF (`fitz`) por página | pdfplumber; extração por LLM | já no stack (resumo §3); sem custo de LLM |
| OCR | PaddleOCR básico por página só quando texto ausente | OCR sempre; PP-StructureV3 | decisão da spec (`document-processing#15`); PP-Structure é NG-01 |
| Chunking | fixo 800 chars / overlap 100 por página | por seção; semântico (LlamaIndex) | OQ-02: determinístico e simples; semântico muda o contrato consumido pelo Dev 2 |
| Embeddings | Gemini embeddings via porta `Embedder` | open-source local | provedor único decidido (PRD R2); porta mantém substituível |
| Vetor | Qdrant client direto na porta `VectorIndex` | LlamaIndex como orquestrador | LlamaIndex é "oportunidade" na spec (`document-processing#10`); no slice o client direto é menos camada; migração futura só em `infrastructure/` |
| Persistência | DuckDB com upsert por chave | SQLite; JSONL | stack decidido; consultas analíticas futuras |
| Extração LLM | Pydantic AI com output type `ExtractedFact` | chamada HTTP manual ao Gemini | validação de schema embutida (RF-09), menos código |
| Comparação | regras puras (numérico/texto/ausente) | LLM comparando | regra absoluta do PRD: LLM jamais compara |
| UI | Streamlit mínimo em `src/ui/app.py` | CLI; FastAPI+front | persona é analista; Streamlit no stack; fase posterior refina |

## 3. Padrões aplicáveis

- **Ports & Adapters (hexagonal):** núcleo puro, adapters em `infrastructure/` — coerente com RNF-06 das specs.
- **Fachada pública única por módulo:** `public_api.py` é a única superfície cross-module (RF-08 dp / RF-01 pa).
- **Fail-safe de contrato:** `ExtractedFact` do shared_kernel já valida EC-05 (FOUND exige evidência) — reuso puro, sem duplicar regra.
- **Test-first por camada:** domínio determinístico testado antes dos adapters (Núcleo antes de Integração).

## 4. Fontes externas consultadas

Sem pesquisa web necessária — stack e contratos já decididos em `_reversa_sdd/`. Referências do projeto:

- `_reversa_sdd/prd.md` (escopo, restrições, riscos)
- `_reversa_sdd/sdd/document-processing.md` e `policy-analysis.md` (RFs, ECs, OQs, Decision Log)
- `_reversa_sdd/sdd/shared-kernel-contracts.md` + `src/shared_kernel/` (contratos v1.0.0 implementados)

## 5. Riscos técnicos a validar no código

1. PaddleOCR/PyMuPDF podem não instalar neste ambiente → adapters ficam prontos, testes `integration` com skip gracioso.
2. Chave Gemini ausente → idem (portas com fake determinístico).
3. Idempotência do Qdrant depende de delete por filtro — testar explicitamente (RF-09/RN-04).
