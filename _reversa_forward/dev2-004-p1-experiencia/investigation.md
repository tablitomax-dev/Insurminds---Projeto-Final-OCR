# Investigação: P1 do Desenvolvedor 2 — Experiência e Governança da Análise

> Identificador: `dev2-004-p1-experiencia`
> Data: `2026-09-26`

## 1. Pesquisa de fundo

- **Estado verificado no código (2026-09-26):** `src/ui/` tem 4 arquivos (`app.py`, `errors.py`, `uploads.py`); `policy_analysis` tem `domain/` (anchoring, catalog, comparison, review, rules), `application/` (comparison, extraction, ports, review), `infrastructure/` (document_retriever, duckdb_repository, llm_extractors) e `public_api.py` com `PolicyAnalysisFacade` + factories. O adapter de LLM (`llm_extractors.py`) concentra `PydanticAiFieldExtractor.extract` e `LlmExplanationGenerator.explain` — é o ponto único de chamada de LLM de negócio, portanto o ponto natural de instrumentação de métricas.
- **Sinais de qualidade já existentes:** `rules.py` grava `value["rule_violations"]` e rebaixa para `NEEDS_REVIEW`; `anchoring.py` + validação pós-LLM produzem `LlmOutputError` que vai para a fila; `reviews` registra decisões humanas. Todos são matéria-prima suficiente para `Issue` sem novo detector.
- **Padrão de fachada:** `public_api.py` já é a fronteira consumida pela UI (adendo 003); os novos métodos seguem o mesmo padrão.

## 2. Alternativas avaliadas

| Tema | Alternativa adotada | Descartadas | Por quê |
|------|---------------------|-------------|---------|
| Persistência de `Issue` | Derivar de `facts` + `reviews` a cada consulta | Tabela `issues` no DuckDB | `Issue` descreve estado atual; tabela histórica duplicaria `reviews` e exigiria migração — YAGNI nesta rodada |
| Coleta de métricas | Instrumentação local no adapter (`llm_extractors.py`) | `ModelGateway` em `shared_kernel`; middleware de prompt | Gatelo registrado em `D2-P1-2`: gateway só nasce com 2º provedor/consumidor |
| Persistência de métricas | Log estruturado por `run_id` + retenção em memória (último run) | Tabela DuckDB `usage_metrics`; arquivo JSON por run | Single-user; o log já cumpre auditoria; painel só precisa do último run — persistência completa é item futuro |
| Custo estimado | USD com tabela de preços versionada (data de referência) | BRL com câmbio; só tokens | Moeda nativa do provedor; câmbio adicionaria manutenção sem valor analítico |
| Superfície de métricas | Log + painel simples na UI (clarify) | Só log; export embutido | Decisão do usuário: analista controla custo sem abrir log |
| Montagem de dependências | Composition root único (`src/composition_root/`) | Factories espalhadas na UI; factory global implícita | F-15: montagem espalhada é como a violação de fachada nasceu |
| Fontes de `Issue` | Só sinais existentes (clarify) | + qualidade de OCR; + divergências de revisão como `Issue` | Escopo fechado no clarify; OCR é terreno do Dev 1 |

## 3. Fontes externas e padrões aplicáveis

- **Structured logging com `run_id`:** padrão consolidado de observabilidade (log em JSON, correlação por identificador de execução) — sem biblioteca nova; `logging` padrão do Python com payload serializado.
- **Composition root:** padrão de injeção de dependência "object composition root" (Mark Seemann) — um único módulo decide o grafo de dependências; o restante do código só recebe interfaces.
- **Severity scales:** escalas de 4 níveis (`CRÍTICO/ALTO/MÉDIO/BAIXO`) são o padrão de análise de risco adotado no próprio PRD (impacto/probabilidade) — coerência de vocabulário com o domínio do projeto.
- Referências internas: `_reversa_sdd/learning/plano-acao-dev2.md` (`D2-P1-1`, `D2-P1-2`, `D2-P1-4`), `_reversa_sdd/learning/benchmark-repos-referencia.md#§3.2` (Issue/relatório de qualidade), `_reversa_sdd/prd.md#§8 Riscos` (R2).

## 4. Padrões anti-reincidência (aprendizados)

- Toda regra arquitetural ganha teste que varre TODO o alvo (F-15) → `tests/architecture` cobre `src/ui` **e** `src/composition_root`.
- Nenhum output de métrica/erro sem teste anti-vazamento (A-13/T-2a) → teste com texto marcador de apólice.
- Escopo fechado com re-leitura dos Musts do PRD (F-16) → Musts §9 relidos antes do `to-do`; nenhum Must novo nasce desta feature.
