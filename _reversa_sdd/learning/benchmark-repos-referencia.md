# Benchmark — repositórios de referência analisados

> Data: `2026-09-26` (ISO 8601)
> Origem: análise de arquitetura de 3 repositórios públicos do mesmo autor (trilha Insurminds), clonados somente-leitura em `%TEMP%\repos-referencia\` (`desafio-4-csv`, `desafio-1-bot`, `desafio-5-meteo`).
> Escala: 🟢 CONFIRMADO (visto no código) · 🟡 INFERIDO (padrão deduzido) · 🔴 LACUNA (validar)
> Este registro atende a pendência F-12 de `aprendizados.md`: análise que antes existia só no chat.

## 1. Panorama

| Repo | Domínio | Stack | Afinidade com o nosso projeto |
|------|---------|-------|-------------------------------|
| `Desafio_5_Insurminds_Meteorologico` | Dados meteorológicos → alertas | Python, ports & adapters, pipelines de dados | 🟢 Alta — mesma forma de isolar dependências externas atrás de portas |
| `Desafio-4---CSV` | ETL de CSV → insights com IA | Python, Pydantic AI, DuckDB, Streamlit | 🟢 Média-alta — mesmo trio Pydantic AI + DuckDB + Streamlit do nosso Dev 2 |
| `Desafio-1---Bot-atendimento` | Bot de atendimento | Python, LangChain, vetores | 🟡 Baixa — outro framework (LangChain) e falhas reais de qualidade; serve como "o que evitar" |

## 2. O que aproveitar — Desenvolvedor 1 (documental/RAG/OCR)

| # | Ideia | Origem | Como aplicar no `document_processing` |
|---|-------|--------|--------------------------------------|
| 1 | Erros tipados por porta (ex.: `ExtractionError`, `IndexingError`) em vez de `Exception` crua | meteo 🟢 | Cada porta do `application/ports.py` declara suas exceções de domínio; adapter traduz erro externo para a porta |
| 2 | Adapter resiliente: retry com backoff + timeout para 429/5xx | meteo/csv 🟢 | Só em `infrastructure/` (GeminiEmbedder, QdrantVectorIndex, PaddleOcrEngine); nunca retry no domínio |
| 3 | Indexação de embeddings em lotes com controle de tamanho | csv 🟢 | `Embedder` aceita lote; `QdrantVectorIndex` upsert em batch com id estável (já temos `uuid5`) |
| 4 | Proveniência embutida no chunk (`content_fingerprint`, `pipeline_version`, flags de truncamento) | meteo 🟢 | Estender o payload do Qdrant (campo novo é delta de contrato — revisar com o Dev 2 antes) |
| 5 | Health-check da coleção antes de indexar (falha amigável cedo) | meteo 🟡 | Checar existência/`health` da coleção `policy_chunks` no início de `process_document` |
| 6 | Modo offline por fixtures (pipeline roda sem rede) | meteo 🟢 | Fixtures de PDF pequenos em `tests/`; já temos fakes — estender para demo offline |

## 3. O que aproveitar — Desenvolvedor 2 (análise/UI/DuckDB/avaliação)

| # | Ideia | Origem | Como aplicar no `policy_analysis` |
|---|-------|--------|----------------------------------|
| 1 | Guardas pós-LLM anti-alucinação (verificar que a citação existe no texto recuperado) | csv 🟢 | Em `application/extraction.py` e `explain_difference`: quote precisa ser substring do texto do chunk citado |
| 2 | `Issue`/`QualityReport` com severidades | csv 🟢 | Enriquecer a fila de revisão: `Issue(severity, field_code, reason, evidence_ref)` em vez de flag booleana |
| 3 | Camada DuckDB defensiva: leitura por views read-only + allowlist de colunas | csv 🟢 | Se a UI permitir consultas ad hoc, jamais SQL livre; repositório é o único que escreve |
| 4 | Fallback de modelo com métricas (uso/latência/custo) | csv 🟡 | `ModelGateway` compartilhado (Conflito 4 do resumo executivo) com `UsageMetrics` |
| 5 | Catálogo enriquecido com regras por campo (validação pós-extração: data coerente, valor > 0, unidade) | csv 🟢 | Estender `domain/catalog.py` (`FieldSpec`) com validações; fica no domínio, testado |
| 6 | Padrões de UI Streamlit (componentes, `session_state`, feedback de progresso) | csv 🟢 | Refatorar `src/ui/app.py` em componentes; UI só via fachada (Conflito 5) |
| 7 | Fallback de explicação: template determinístico quando o LLM falha | csv 🟡 | `ExplanationGenerator` com caminho de saída `MAIOR/MENOR/IGUAL` em texto fixo citando as evidências |
| 8 | Diretrizes/prompts externalizados em JSON versionado | csv 🟡 | Prompts de extração/explicação fora do código; versiona com o contrato |
| 9 | `temperature = 0.0` em tarefas estruturadas | csv 🟢 | Extração e explicação determinísticas o máximo possível |

## 4. O que NÃO fazer (anti-padrões observados)

| # | Anti-padrão | Onde vimos | Risco | Regra |
|---|------------|-----------|-------|-------|
| 1 | Filtro de isolamento (usuário/apólice) aplicado DEPOIS do `similarity_search` | bot 🟢 | Vazamento de dados entre usuários — resultados de outro domínio aparecem antes do filtro | Filtro SEMPRE como metadata filter na consulta (regra em `aprendizados.md` §4) |
| 2 | Código que usa `json.loads`/`datetime` sem import — só pego em execução | bot 🟢 | Runtime error no fluxo real | Lint + typecheck + testes de smoke no gate `T-1` (`aprendizados.md` §5.3) |
| 3 | Framework (LangChain) importado em todo lugar, inclusive no domínio | bot 🟢 | Domínio acoplado; impossível testar sem o framework; trocar peça = reescrever | Domínio/application sem imports externos — já é teste nosso (`tests/architecture`) |
| 4 | Prompt gigante inline + lógica de negócio dentro do prompt | bot/csv 🟡 | Impossível auditar/testar regra; mudança de prompt muda comportamento silenciosamente | Regra em código testado; prompt só formata |
| 5 | Sem versionamento de contrato de dados entre estágios do pipeline | bot 🟢 | Quebra silenciosa quando um lado muda formato | Contrato versionado (`metadata_version`, `schema_version`) — já temos |
| 6 | SQL/detalhe de persistência vazando para camada de apresentação | csv 🟡 | Acoplamento UI↔banco | UI só via fachada pública |

## 5. Veredito por repositório

- **meteo:** padrão arquitetural adotável quase inteiro (portas, resiliência, proveniência). É a nossa referência de forma, não de domínio.
- **csv:** fonte das melhores práticas de IA estruturada (guardas pós-LLM, quality report, fallback) — direto no backlog do Dev 2.
- **bot:** valor como anti-exemplo. Três ideias aproveitáveis (fixture-driven demo, cálculo de custo por chamada, fila de mensagens), mas os anti-padrões 1–3 são lições de segurança/qualidade que já viraram regra em `aprendizados.md`.
