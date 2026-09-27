# Actions: P1 do Desenvolvedor 1 — Proveniência do Chunk e Modo Offline

> Identificador: `005-p1-dev1-proveniencia`
> Data: `2026-09-26` (ISO 8601)
> Fonte: `roadmap.md` + `data-delta.md` desta feature · Método: `_reversa_sdd/learning/plano-acao-dev1.md` v1.0 (`D1-P1-1`, `D1-P1-2`)
> Convenções: IDs `D1-*`/`T-*` (aprendizados §5.1); ação atômica = um turno de agente (A-01); caixa postal **antes do código de payload** (§5.2); gate `T-1` antes de todo PR.

## Resumo

| Métrica | Valor |
|---------|-------|
| Total de ações | 6 |
| Paralelizáveis (`[//]`) | 3 (`D1-P1-1a`, `D1-P1-1b`, `D1-P1-2a`) |
| Maior cadeia de dependência | 4 (`D1-P1-1a` → `D1-P1-1c` → `D1-P1-1d` → `D1-P1-1e`) |
| Fora desta feature (backlog) | `D1-P2-1` (métrica de embedding), PP-Structure/`section_name` real (NG-01) |

## Análise de granularidade (A-01)

- `D1-P1-1a` (caixa postal) e `D1-P1-1b` (função pura) são atômicos e independentes: a regra de "nada de código antes do aceite" vale para o **payload e o contrato** (`D1-P1-1c`/`D1-P1-1d`) — a função pura de hash não altera contrato nem payload.
- `D1-P1-1c` junta campo + bump de versão: mudar o contrato e não bumpar é exatamente a falha que a convenção §5.2 quer evitar.
- `D1-P1-1d` é o round-trip inteiro (escrever + ler de volta) — um teste de só escrita não prova leitura (F-14: propagação de contrato se prova ponta a ponta).
- `D1-P1-2a`/`D1-P1-2b` separados: fixture é artefato; o teste opt-in que a consome declara real vs fake (C2-05).

## Fase 1 — Preparação (caixa postal + fixtures)

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| D1-P1-1a | Caixa postal: escrever `contract-delta-chunkmetadata.md` (proposta: campo opcional `content_fingerprint` = sha256 hex do texto do chunk; semântica para consumidores; versão alvo `1.1.0`) e registrar aceite/negativa do Dev 2 (1 dia útil; silêncio = escalada ao humano). **Pré-condição para `D1-P1-1c`/`D1-P1-1d`** | - | `[//]` | `_reversa_forward/005-p1-dev1-proveniencia/contract-delta-chunkmetadata.md` | 🟢 | `[X]` |
| D1-P1-2a | Fixtures em `tests/fixtures/`: 1 PDF digital pequeno + 1 PDF "escaneado" gerado do digital (página-imagem única, sem camada de texto; receita documentada no teste; < 100 KB cada) + teste que prova a ausência de camada de texto no "escaneado" | - | `[//]` | `tests/fixtures/`, `tests/integration/` | 🟢 | `[X]` |

## Fase 2 — Testes (função pura primeiro, A-04)

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| D1-P1-1b | Função pura `compute_content_fingerprint(text)` (sha256 hex, 64 chars) em `domain/chunk_fingerprint.py` + testes (determinismo; textos distintos geram hashes distintos; estável entre execuções) | - | `[//]` | `src/modules/document_processing/domain/chunk_fingerprint.py`, `tests/modules/document_processing/test_fingerprint.py` | 🟢 | `[X]` |

## Fase 3 — Núcleo (contrato + payload)

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| D1-P1-1c | Contrato: campo opcional `content_fingerprint: str \| None = None` em `ChunkMetadata` + bump `CONTRACTS_VERSION` `1.0.0` → `1.1.0` (MINOR); testes de contrato existentes continuam verdes (retrocompatibilidade provada) | D1-P1-1a | - | `src/shared_kernel/contracts.py`, `src/shared_kernel/version.py`, `tests/contracts/` | 🟢 | `[X]` |
| D1-P1-1d | Payload round-trip em `indexing.py` (`_payload_from_record`/`_record_from_payload`): gravar com fingerprint → recuperar → sha256 confere; chunk sem o campo → `None` aceito (testes com `QdrantClient` mockado, padrão de `test_indexing.py`) | D1-P1-1b, D1-P1-1c | - | `src/modules/document_processing/infrastructure/indexing.py`, `tests/modules/document_processing/test_indexing.py` | 🟢 | `[X]` |

## Fase 4 — Integração

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| D1-P1-2b | Teste opt-in em `tests/integration/` com marker `integration` registrado (F-03): pipeline real sobre as duas fixtures, fake **apenas** do `Embedder`, declaração explícita real vs fake no próprio teste; `python -B -m pytest -q -p no:cacheprovider -m integration` roda **sem internet** | D1-P1-2a, D1-P1-1d | - | `tests/integration/`, `pyproject.toml` (marker) | 🟢 | `[X]` |

## Fase 5 — Polimento

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| D1-P1-1e | Registro de decisões (A-10: semântica do fingerprint, escolhas descartadas, porquê) + `regression-watch.md` com o teste opt-in sob vigilância | D1-P1-1d, D1-P1-2b | - | `_reversa_forward/005-p1-dev1-proveniencia/` | 🟢 | `[X]` |

## Checklist de encerramento (ritual — plano Dev 1 §5)

- [X] Granularidade registrada nesta tabela (feito no cabeçalho).
- [X] Caixa postal com aceite/negativa registrado **antes** do código de payload/contrato (§5.2); uma mudança de contrato por vez.
- [X] Teste primeiro na lógica determinística (A-04).
- [X] Gate `T-1` verde (`ruff` + `mypy` + `python -B -m pytest -q -p no:cacheprovider`) — 3× consecutivas (280 passed, 6 skipped).
- [X] Integração opt-in verde sem internet; nenhuma flag de truncamento criada (RN-04).
- [X] Estado remoto checado antes do PR (`gh` indisponível no ambiente; verificado via `git`/MCP GitHub).
- [X] `regression-watch.md` atualizado e `/reversa-sync` executado ao concluir (plano B: adendo manual).

## Notas de execução

- **Aceite da caixa postal (E-05):** o Dev 2 não respondeu em 1 dia útil; a escalada ao humano (§5.2) foi resolvida por **pbena** em 2026-09-27 ("continue a 005 até acabar"). Registro em `contract-delta-chunkmetadata.md` — nada de código de payload/contrato antes disso.
- **Premissa ajustada (E-02):** `fitz` (PyMuPDF) não está disponível no ambiente — as fixtures foram geradas por **receita stdlib** (zlib), documentada em `test_fixtures_pdf.py`; a tabela de riscos do roadmap já previa a receita alternativa. Sanity check com `pypdf`: digital com texto extraível, "escaneado" com `extract_text() == ""`.
- **Preenchimento do fingerprint (E-01):** em `application/service.py`, ao montar o `ChunkRecord` — o adapter segue serializando apenas (roadmap D-03).
- **Guard de versão (E-04):** `tests/contracts/test_packaging.py` acompanhado para `1.1.0` (o teste trava a versão vigente do contrato).
- **Contaminação de `sys.modules` detectada pelo teste de arquitetura:** o teste opt-in importa os adapters de forma **lazy** (padrão de `test_adapters_reais.py`) — corrigido na própria ação.
- **Integração opt-in:** `pytest -m integration` roda sem internet (6 skipped neste ambiente pelas extras locais ausentes — padrão D-10); para exercitar de fato, instalar as extras de `requirements.txt` e definir `INTEGRATION_QDRANT_URL` para o Qdrant local. Teste sob vigilância em `regression-watch.md` (O004).
- **Gate `T-1` (3× consecutivas):** `ruff` All checks passed · `mypy` Success (60 arquivos) · `pytest` **280 passed, 6 skipped** (+9 sobre o baseline pós-004: 271 passed, 4 skipped).

## Histórico de alterações

| Data | Alteração | Autor |
|------|-----------|-------|
| 2026-09-26 | Versão inicial gerada por `/reversa-to-do` | reversa |
| 2026-09-27 | 6/6 ações concluídas por `/reversa-coding`; checklist de encerramento fechado; gate `T-1` verde 3× | reversa |
