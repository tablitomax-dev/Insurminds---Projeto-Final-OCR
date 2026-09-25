# Brief inicial, /reversa-new

> Selo 🟡 PLANEJADO. Documento de entrada do time Code New Project Agents.

**Data:** 2026-09-25T00:00:00-03:00
**Usuário:** pbena

## Ideia original

Plataforma inteligente (monólito modular em Python) para ingestão, análise e comparação de apólices de seguro D&O, transformando PDFs em evidências recuperáveis e depois em fatos estruturados, comparações determinísticas e explicações rastreáveis.

Arquitetura de referência completa em `resumo_executivo_arquitetura_monolito_modular (1).md` na raiz do projeto (resumo executivo, 95% de confiança). Dois desenvolvedores:

- **Dev 1 (pbena)** — pipeline documental e RAG: ingestão, PDF/PyMuPDF, PaddleOCR, PP-StructureV3, chunking, LlamaIndex, embeddings Gemini, Qdrant (local Docker), retrieval e entrega de `EvidenceRef`.
- **Dev 2** — núcleo de análise e experiência: extração estruturada com Pydantic AI, validação, DuckDB, comparação determinística entre apólices, explicação, Streamlit.

Decisões já registradas nesta sessão: Python; Pydantic AI para orquestração de agentes; LLM Gemini (provedor único, inclusive embeddings); Qdrant local via Docker; princípios KISS/YAGNI/SDD; comparação determinística (LLM extrai/explica, jamais compara); zonas de integração (EvidenceRef, metadados de chunks, evidências, workflow, ModelGateway/observabilidade) documentadas com aviso antes de tocar; alteração de contrato exige revisão dos dois desenvolvedores.

---

Gerado por /reversa-new em 2026-09-25T00:00:00-03:00
