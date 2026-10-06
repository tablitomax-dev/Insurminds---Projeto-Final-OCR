# Handoff — Pipeline markdown + Agentes + Relatório D&O (2026-10-05/06)

**Entrega:** feature/pipeline-markdown-relatorio-do → main (PR em aberto)
**Dias:** 2026-10-05 (UI/agentes) e 2026-10-06 (pipeline markdown, Relatório D&O, validação real)
**Gate T-1:** ruff ✓ · mypy ✓ · pytest 474 passed, 4 skipped

## 1. O que foi entregue

### A. Pipeline OCR pesado → markdown → banco → LLM (decisão humana 2026-10-05)
- `document_processing`: PP-StructureV3 devolve **markdown estruturado por página**
  (`analyze_page_markdown`, leitura defensiva `markdown_text`/`md_info`/`markdown`);
  `split_markdown_sections` (headings ATX); `extract_markdown_pages` com
  **cache de predição por página** (regiões e markdown compartilham UMA rodada
  do engine) e cache de OCR (preview não reprocessa).
- `policy_analysis`: `MarkdownSectionEvidenceSource` — cada **seção do markdown**
  vira `EvidenceRef` citável (RAG por seções, sobreposição léxica por campo,
  truncamento 4000 chars, ids `ev_md_{policy}:p{n}:s{i}` — nunca inventados).
- DuckDB: migração `2` — tabelas `document_markdown` (cache por fingerprint) e
  `extra_findings` (idempotência EC-06 delete+insert).

### B. Decisão híbrido de campos (2026-10-05)
- Catálogo fechado de 10 campos **preservado** (comparação determinística e
  contrato versionado intactos) + `LLMExtraFindingsAgent` registra achados
  fora do catálogo em `extra_findings`, exibidos À PARTE na UI.

### C. Relatório D&O (metodologia §1–§11, 2026-10-06)
- `domain/report_catalog.py`: vocabulário fechado (CoverageStatus com
  "Não localizado" — nunca "não existe"), ~80 campos em 8 categorias,
  pesos §8.1, cenários de sensibilidade §8.3, checklist §11 (14 itens).
- `domain/report.py`: matemática pura — `compute_ranking`
  (`Σ(nota×peso)/10`), `compute_sensitivity`, `guard_sem_vencedora` (§9:
  sem prêmio/LMG/LMIs/franquias/sublimites/perfil → sem vencedora geral),
  `build_checklist`.
- `application/report_service.py`: map/reduce POR CATEGORIA (nunca uma
  chamada gigante); guarda de rastreabilidade §10 (célula sem referência vira
  "Requer confirmação"); ressalva fixa nos cenários (§7).
- `infrastructure/report_agent.py`: prompts versionados
  (identify/fill/tables/scenarios/scores/conclusions `*-v1`) + fixture.
- `infrastructure/report_export.py`: Markdown standalone (matriz §5, 5
  tabelas §6, ranking+sensibilidade §8, conclusões §9, checklist §11).

### D. UI (2026-10-05/06)
- Rótulos de exibição pela seguradora real (LLM + fallback do usuário);
  "2. Extrair campos" só escrita oculta; "3. Comparação"; "Métricas";
  "4. Alguma divergência? Me indique por aqui:"; "5. Relatório D&O" com
  painel de pesos interativo (§8.2).
- Agente Inteligente (RAG com citações, controles de busca ocultos,
  barra "Digite sua dúvida" + ↑) e revisão por mensagem (LLM corrige,
  `decided_by = "Analista via Agente IA"`).
- Trava sanitizada T-2a removida por decisão humana (sem dados sensíveis).

### E. Infra/demo/validação real (2026-10-06)
- `run_ui_demo.py`: fachadas reais (`LLM_REAL=1` + MiMo via OpenRouter),
  `PADDLE_PDX_CACHE_HOME=.tools/paddlex-home`, layout engine conectado.
- `iniciar_app.bat`: launcher de dois cliques.
- `pyproject.toml`: stack completo instalável (`pip install -e ".[dev]"`).
- **Timeout de LLM (300s)** — `LLM_TIMEOUT` reexecutável; antes, conexão
  presa no provedor bloqueava o fluxo para sempre.
- `tests/apolices/validate_real.py`: bancada de validação real (3 rodadas
  de 2 arquivos; JSON de saída por rodada).

## 2. Achados da validação real (rodada 1: AXA + Allianz 2025)
- ✅ Seguradora: "AXA Seguros" (2025) e "Allianz Seguros" (2025) — leitura direta.
- ✅ Markdown: 104 e 75 páginas (~250k chars); extras: 12 e 17 achados.
- ⚠️ Extração do catálogo: 2/10 e 1/10 FOUND — os PDFs são Condições Gerais
  (valores como LMG/franquia moram na especificação); parte do NOT_FOUND é
  correta. Pendente de validação com apólice+especificação.
- ⚠️ Relatório D&O: 23 chamadas LLM sequenciais demoram 40–90 min no MiMo —
  otimização por lote é a próxima pendência de performance.

## 3. Zonas compartilhadas tocadas (atenção Dev 1/Dev 2)
- `policy_analysis/public_api.py`: +`report_agent`, +`store_markdown`,
  +`get_markdown_sections`, +`extract_extra_findings`, +`build_report`,
  +`export_report`; `_file_paths` (policy_id → caminho do PDF).
- `document_processing/public_api.py`: +`extract_markdown`.
- `duckdb_repository.py`: migração `2` (NUNCA editar a baseline `1`).
- `shared_kernel/contracts.py`: **INTOCADO** (contrato versionado).

## 4. Pendências conhecidas
1. Otimizar o Relatório D&O (agrupar categorias por chamada/paralelizar).
2. Rodadas 2 e 3 da validação real (PORTO; Allianz 2017 JPG → PDF).
3. Validar extração com apólice completa (com especificação/valores).
4. Commit/push/PR deste handoff (processo §5.6 concluído na entrega).
