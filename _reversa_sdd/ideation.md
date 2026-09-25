# Ideation, Insurminds - Desafio Final

> Selo 🟡 PLANEJADO em todos os itens, sujeito a validação.

## Brief original

Plataforma inteligente (monólito modular em Python) para ingestão, análise e comparação de apólices de seguro D&O, transformando PDFs em evidências recuperáveis e depois em fatos estruturados, comparações determinísticas e explicações rastreáveis.

Arquitetura de referência completa em `resumo_executivo_arquitetura_monolito_modular (1).md` na raiz do projeto (resumo executivo, 95% de confiança). Dois desenvolvedores:

- **Dev 1 (pbena)** — pipeline documental e RAG: ingestão, PDF/PyMuPDF, PaddleOCR, PP-StructureV3, chunking, LlamaIndex, embeddings Gemini, Qdrant (local Docker), retrieval e entrega de `EvidenceRef`.
- **Dev 2** — núcleo de análise e experiência: extração estruturada com Pydantic AI, validação, DuckDB, comparação determinística entre apólices, explicação, Streamlit.

Decisões já registradas nesta sessão: Python; Pydantic AI para orquestração de agentes; LLM Gemini (provedor único, inclusive embeddings); Qdrant local via Docker; princípios KISS/YAGNI/SDD; comparação determinística (LLM extrai/explica, jamais compara); zonas de integração (EvidenceRef, metadados de chunks, evidências, workflow, ModelGateway/observabilidade) documentadas com aviso antes de tocar; alteração de contrato exige revisão dos dois desenvolvedores.

## Problema

🟡 O problema é composto e atinge três frentes ao mesmo tempo (resposta do usuário: "todos"):
1. **Comparação manual sem rastreio** — apólices D&O são PDFs longos (limites, coberturas, exclusões, endossos); a comparação entre elas é manual, lenta e sem evidência anexada, com risco de passar despercebida uma exclusão ou um limite inferior. Quem sente: analistas/corretores; quando: cotação, renovação e placement.
2. **Renovações sem auditoria** — a equipe que renova apólices não consegue auditar o que mudou de uma versão para outra da mesma apólice.
3. **Multi-formatos sem padrão** — várias seguradoras, formatos de apólice distintos, nenhum padrão de estrutura para automatizar.

## Valor entregue

🟡 Ambos os ganhos, juntos: comparar apólices campo a campo (limites, exclusões, condições) **com evidência anexada a cada fato** e explicação rastreável — tudo o que o usuário antes fazia lendo PDFs inteiros manualmente — **e** auditar cada decisão: todo fato extraído aponta para página/trecho/cláusula, permitindo defender a análise perante cliente e seguradora.

## Alternativas existentes

🟡 Nenhuma alternativa conhecida pelo usuário (resposta: "Nenhuma conhecida"). O processo atual presume-se manual (leitura de PDF + planilhas), mas não foi identificada ferramenta ou processo formal em uso. Impacto: sem benchmark externo, as métricas precisam ser definidas internamente.

## Público-alvo (bruto)

🟡 Analista de seguros/corretora que compara limites, coberturas, exclusões e condições entre apólices D&O. Perfil bruto; detalhamento em personas (próxima fase).

## Métricas de sucesso

🟡 Daqui a 3 meses: **1 comparação ponta a ponta entre 2 apólices reais**, com os campos críticos do vertical slice (alvo: ~10 campos) extraídos com **100% de evidência anexada**, revisão humana funcionando e comparação determinística produzida — sem necessidade de ler os PDFs manualmente.

## Premissas a validar

🟡 1. **PDFs são extraíveis** — os PDFs de apólices (nativos ou escaneados) têm qualidade/estrutura suficiente para OCR + layout (PaddleOCR/PP-StructureV3) atingir confiança útil.
🟡 2. **Custo/latência viáveis** — o pipeline Gemini (LLM + embeddings) + PaddleOCR + Qdrant roda localmente (Docker) dentro de custo e latência aceitáveis para uso single-user.

## Notas

🟡 - Comparação entre valores é **determinística** (regras), jamais por similaridade vetorial ou interpretação livre do LLM (resumo §2.4).
- Toda evidência obrigatoriamente referencia apólice, documento, página, trecho/seção/cláusula, chunk e score de recuperação quando aplicável (resumo §2.5).
- Contratos entre Dev 1 e Dev 2 definidos **antes** do desenvolvimento: `EvidenceRef`, IDs, `RetrievalQuery/Result`, `ExtractedFact`, `ProcessingStatus`, `ChunkMetadata`.
- Estratégia de entrega: vertical slice mínimo antes das sofisticações (PP-Structure, tabelas, múltiplos agentes, fallback, scoring avançado) — resumo §13.
- Stack decidado: Python, Pydantic AI, Gemini (provedor único), Qdrant Docker, DuckDB, Streamlit.

---
Gerado por reversa-ideator em 2026-09-25T00:00:00-03:00
Fonte: newproject-brief.md
