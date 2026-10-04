# Relatório de Aderência — Escopo do Projeto Final × Sistema Insurminds

**Data:** 2026-10-03 (atualizado em 2026-10-03 após a entrega da tela de consulta)
**Escopo auditado:** enunciado do Projeto Final (solução de IA para extrair, organizar e comparar informações de apólices de seguro D&O)
**Código verificado:** `Insurminds---Projeto-Final-OCR/`
**Validação executada:** suíte de testes completa — **344 passed, 5 skipped** (4,7s)

---

## 1. As 7 etapas (preferenciais)

| # | Etapa | Status | Evidência no código |
|---|-------|--------|---------------------|
| 1 | Recebimento dos documentos | **Atende** | Upload de 2 apólices na UI (`src/ui/components/upload.py`) + validação (assinatura `%PDF-`, 50MB) em `src/modules/document_processing/application/service.py` |
| 2 | Extração automática do conteúdo | **Atende** | Texto nativo (PyMuPDF) + OCR de páginas escaneadas (PaddleOCR) + layout PP-Structure (`src/modules/document_processing/infrastructure/extractors.py`, `layout.py`) |
| 3 | Organização das informações | **Atende** | Chunking + seções + metadados com proveniência (sha256) no pipeline; campos em catálogo tipado com normalização (`src/modules/policy_analysis/domain/field_catalog.py`, `value_types.py`) |
| 4 | Armazenamento estruturado | **Atende** | DuckDB (tabelas `policies`, `documents`, `facts`, `comparisons` + migrações em `src/modules/policy_analysis/infrastructure/duckdb_repository.py`) + índice vetorial Qdrant |
| 5 | Consulta das informações | **Atende** | Tela "3. Consulta livre às apólices" (`src/ui/components/query.py`) com busca semântica em linguagem natural sobre as evidências indexadas, filtros de apólice (A/B/ambas) e quantidade de resultados; API `retrieve_evidence`, `get_facts`, `get_evidences` e histórico de revisão |
| 6 | Comparação entre apólices | **Atende** | Comparação **determinística** A × B campo a campo com resultado/direção (`src/modules/policy_analysis/domain/comparison.py`) |
| 7 | Apresentação dos resultados | **Atende** | Tela Streamlit (tabela formatada ao analista + explicação por campo) + export Markdown em `exports/<ComparisonId>.md` |

## 2. Requisitos mínimos

| Requisito | Status | Evidência |
|-----------|--------|-----------|
| Ler PDF ou imagem | **Atende (com ressalva)** | PDF digital e **PDF escaneado (imagem)** via OCR ✓. Arquivo de imagem avulso (PNG/JPG) **não** é aceito — o validador exige extensão `.pdf` e o uploader só aceita `type=["pdf"]` |
| Extrair automaticamente informações relevantes | **Atende** | Pipeline inteiro automático + extração de 10 campos-chave por agente LLM com guardas de qualidade (`src/modules/policy_analysis/infrastructure/llm_agent.py`) |
| Estruturar os dados extraídos | **Atende** | `ExtractedFact` tipado (Pydantic) com status, confiança, evidências e valor normalizado |
| Comparar pelo menos 2 apólices | **Atende** | Fluxo A × B (fixo em 2 — atende o mínimo, não compara 3+) |
| Apresentar as principais diferenças | **Atende** | Tabela campo × resultado (IGUAL/MENOR/MAIOR/DIVERGENTE), direção, valores formatados e explicação rastreável |
| Usar IA generativa no processamento | **Atende** | **Gemini 2.0 Flash** via Pydantic AI (extração + explicação) + embeddings Gemini (`src/composition_root/root.py`) |
| Interface de demonstração | **Atende** | Streamlit (`src/ui/app.py`) + modo demo offline (`run_ui_demo.py`) |

## 3. Objetivos transversais

- **Tecnologias do curso integradas:** OCR (PaddleOCR) ✓ · LLMs (Gemini) ✓ · agentes inteligentes (Pydantic AI) ✓ · bancos de dados (DuckDB + Qdrant) ✓ · automação (pipeline ponta a ponta) ✓ · interface de consulta (Streamlit) ✓
- **Arquitetura consistente e documentada:** monólito modular com contratos versionados, specs SDD (`_reversa_sdd/prd.md` + 4 specs em `sdd/` + 8 adendos de decisão), regras de import testadas (`tests/architecture/test_imports.py`) e resumo executivo de arquitetura na raiz ✓
- **Base técnica:** 336 testes (contratos, domínio, integração com PDFs reais de fixture — inclusive um escaneado —, E2E e UI), módulo de avaliação com golden set e relatórios de qualidade ✓

## 4. Gaps e pontos de atenção (ordem de prioridade)

1. **Imagem avulsa não aceita** — se o avaliador interpretar "PDF **ou** imagem" como exigir upload de PNG/JPG, falta relaxar o validador + o `file_uploader`. Hoje o OCR só é acionado dentro de PDF escaneado.
2. **Sem README.md na raiz** — a documentação é rica em `_reversa_sdd/`, mas para entrega acadêmica um README (como rodar, arquitetura, resultados) costuma ser esperado.
3. **A demonstração "real" depende de ambiente:** `GEMINI_API_KEY`, Qdrant em `localhost:6333` e libs (pymupdf, paddleocr, pp-structure). Sem isso, só a demo offline (fixtures) roda — prever isso na apresentação.

### Gaps já fechados

- ~~**Sem tela de consulta livre**~~ — **fechado em 2026-10-03**: tela "3. Consulta livre às apólices" (`src/ui/components/query.py`) com busca semântica livre, filtros de apólice e tabela amigável de evidências (etapa 5 agora **Atende**).

---

## Veredicto

Todos os **requisitos mínimos** são atendidos (o item "PDF ou imagem" com a ressalva acima) e as **7 etapas preferenciais estão cobertas**, incluindo a consulta das informações (API + tela livre).

Restam 3 ajustes finos, sendo os nº 1 e 2 os mais visíveis para um avaliador — nenhum deles impede a entrega.