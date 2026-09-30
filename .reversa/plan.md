# Plano do Projeto — Insurminds - Desafio Final

> Ajustado pelo Reversa em 2026-09-25: projeto **greenfield** (sem código legado),
> guiado por `resumo_executivo_arquitetura_monolito_modular (1).md`.
> Fluxo: `/reversa-new` (ideia → PRD → specs SDD) → `/reversa-forward` (specs → código).
> Marque cada tarefa com ✅ quando concluída.

---

## Papéis e ownership

- **Desenvolvedor 1 (pbena):** `src/modules/document_processing/**`, pipeline documental + RAG (PyMuPDF, PaddleOCR, PP-StructureV3, LlamaIndex, embeddings Gemini, Qdrant local Docker). Produce `EvidenceRef`.
- **Desenvolvedor 2:** `src/modules/policy_analysis/**`, `src/modules/evaluation/**`, Streamlit, DuckDB (extração estruturada, validação, comparação, explicação). Consome `EvidenceRef`, produz `ExtractedFact`.
- **Compartilhado (muda só com revisão dos dois):** `src/shared_kernel/contracts/**`, `src/composition_root/**`, `tests/contracts/**`, `docs/architecture/**`.

## Zonas de integração — AVISAR ANTES DE TOCAR

1. `shared_kernel/contracts` — `EvidenceRef`, IDs, `RetrievalQuery/Result`, `ExtractedFact`, `ProcessingStatus`, `ChunkMetadata`
2. Metadados de chunks (contrato versionado)
3. Evidências (produzidas pelo Dev 1, consumidas pelo Dev 2)
4. Orquestração do workflow (camada de aplicação, fachadas públicas)
5. `ModelGateway` + observabilidade (transversais)

Regra: nenhum módulo importa o interno do outro; acesso só via `public_api.py`. Alteração de contrato exige PR revisada pelos dois desenvolvedores.

## Pipeline /reversa-new

- [x] **Ideator** — brainstorm estruturado a partir do resumo executivo → `_reversa_sdd/ideation.md`
- [x] **Researcher** — personas e jornadas → `_reversa_sdd/personas.md`
- [x] **Drafter** — PRD com requisitos e escopo → `_reversa_sdd/prd.md` (9 seções preenchidas, 0 [INDEFINIDO]; cobertura: sigilo de cliente com envio a Gemini como decisão explícita; prazo alvo 3 meses + viés custo baixo)
- [x] **Spec-SDD (shared_kernel)** — contratos → `_reversa_sdd/sdd/shared-kernel-contracts.md` (score 100/100 ⭐; RF-01..RF-10; OQ-01..04 para o Dev 2 validar na PR)
- [x] **Spec-SDD (módulos)** — `document-processing.md`, `policy-analysis.md`, `evaluation.md` → `_reversa_sdd/sdd/` (todas 100/100 ⭐; handoff: tela mínima e workflow ficam para o ciclo forward — NG-05 da policy-analysis)
- [x] **Implementação dos contratos (Fase 0)**: `src/shared_kernel/` (`version`, `identifiers`, `contracts`, `errors`) + `tests/contracts/` (8 suítes, 67 testes passando em 1.27s) + 18 fixtures JSON (9 válidas / 9 inválidas) + `pyproject.toml` + `requirements.txt` — conforme spec 100/100; RF-01..RF-10 cobertos
- [x] Handoff → `/reversa-forward` (iniciado em 2026-09-26: feature `001-vertical-slice-e2e`)

## Implementação (/reversa-forward)

- [x] Vertical slice mínimo (resumo §13): PDF simples → OCR básico → chunks → Qdrant → retrieval → 1 campo extraído → 1 comparação → tela simples — feature `001-vertical-slice-e2e`, 21/21 ações em `_reversa_forward/001-vertical-slice-e2e/actions.md`, suíte 137 passed / 4 skipped
- [x] Quality gates (resumo §14): testes de contrato, PDF nativo/escaneado, documento duplicado, baixa confiança, falha de LLM (tabela fora do escopo — NG-01/PP-Structure fase posterior)
- [x] Núcleo do `policy_analysis` (Dev 2, implementação paralela) — feature `001-dev2-policy-analysis-slice`, 31/31 ações em `_reversa_forward/001-dev2-policy-analysis-slice/actions.md`, 120 testes passando (67 contratos da Fase 0 + 53 novos), branch `feature/dev2-policy-analysis-slice`; OQ-01..OQ-04 resolvidas (catálogo de 10 campos, regras híbridas de comparação, export PDF, agente multi-campo)
- [x] Ações P0 dos devs 1 e 2 (features `002-p0-dev1-documental-rag` e `003-p0-dev2-analise-experiencia`) — erros tipados, retrieval honrado, ancoragem, revisão humana e evaluation (PR #4); planejamento complementar do Dev 2 em `_reversa_sdd/learning/plano-acao-dev2.md`

## Decisões registradas nesta sessão

- Linguagem: **Python** · Orquestração de agentes: **Pydantic AI**
- LLM: **Gemini** (provedor único, incluindo embeddings)
- Qdrant: **local via Docker** (MVP; nenhum dado sensível sai da máquina)
- Escopo das specs desta fase: **shared_kernel + document_processing + policy_analysis + evaluation**
- Princípios: **monólito modular, KISS, YAGNI, SDD**; comparação entre valores é **determinística** (LLM extrai/explica, jamais compara)
- doc_level: **completo** · doc_language: Português · answer_mode: chat

## Fluxos não usados (registro)

- `/reversa` (extração): sem código legado; fica para o pós-implementação (fechar o ciclo 🟢).
- `/reversa-migrate`, `/reversa-docs`, Visor/Data Master/Design System: sem material de entrada por enquanto.
