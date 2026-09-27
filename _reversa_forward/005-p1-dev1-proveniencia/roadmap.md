# Roadmap: P1 do Desenvolvedor 1 — Proveniência do Chunk e Modo Offline

> Identificador: `005-p1-dev1-proveniencia`
> Data: `2026-09-26`
> Requirements: `_reversa_forward/005-p1-dev1-proveniencia/requirements.md`
> Confidência: 🟢 CONFIRMADO, 🟡 INFERIDO, 🔴 LACUNA

## 1. Resumo da abordagem

Dois deltas no núcleo documental já fechado (adendo 002): (a) proveniência — `content_fingerprint` (sha256 hex do texto do chunk) como campo **opcional** em `ChunkMetadata` e no payload do índice vetorial, com mudança precedida da **caixa postal** (`contract-delta-chunkmetadata.md`, aceite do Dev 2, bump `CONTRACTS_VERSION` 1.0.0 → 1.1.0, MINOR retrocompatível) e round-trip provado por teste; (b) modo offline — fixtures com 1 PDF digital pequeno + 1 PDF "escaneado" (imagem única, sem camada de texto) e teste de integração opt-in (`-m integration`) que roda o pipeline real com fake apenas do `Embedder`, declarando real vs fake. Sem flag de truncamento (RN-04) e sem mudança em `EvidenceRef`.

## 2. Princípios aplicados

`.reversa/principles.md` não existe neste projeto (verificação em 2026-09-26). Normas vigentes: `_reversa_sdd/learning/aprendizados.md#§5` e as regras absolutas do plano Dev 1:

| Norma | Como a feature se relaciona | Status |
|-------|------------------------------|--------|
| `aprendizados.md` §5.2 (caixa postal, 1 mudança por vez, bump de versão) | É o **mecanismo central** da feature (D-01) — proposta, aceite, bump, código | respeita |
| Plano Dev 1 §4.3 (sem segundo modelo de `Evidence`/`ChunkMetadata` ou payload "só pra eu usar") | Campo opcional é de consumo geral (integridade verificável), proposta formal e aceitada — não é payload privado | respeita |
| Plano Dev 1 §4.5 (nunca pós-filtro de segurança depois da busca) | Fingerprint não participa de filtro de busca — é dado de proveniência | respeita |
| A-10 (decisão registrada em `_reversa_forward/`) | Semântica do fingerprint e escolhas descartadas registradas nesta feature (RF-05) | respeita |
| `aprendizados.md` §5.3 (gate `T-1`) | Gate antes do PR; integração opt-in complementa, não substitui | respeita |

## 3. Decisões técnicas

| ID | Decisão | Justificativa | Alternativas descartadas | Confidência |
|----|---------|---------------|--------------------------|-------------|
| D-01 | Caixa postal primeiro: `contract-delta-chunkmetadata.md` na feature → aceite/negativa do Dev 2 em 1 dia útil (silêncio = escalada ao humano) → **só então** código | Convenção §5.2; zona compartilhada `ChunkMetadata` exige aceite antes do código | Implementar e avisar depois; reunião informal sem registro | 🟢 |
| D-02 | `content_fingerprint: str \| None = None` em `ChunkMetadata`; valor = sha256 (hex, 64 chars) do **texto do chunk**; bump `CONTRACTS_VERSION` `1.0.0` → `1.1.0` (MINOR: campo opcional retrocompatível) | Escopo `D1-P1-1`; campo opcional não quebra consumidores existentes | Campo obrigatório (break MAJOR); hash do PDF por documento (granularidade errada — queremos integridade por chunk) | 🟢 |
| D-03 | Função pura `compute_content_fingerprint(text)` no domínio do `document_processing`; o adapter de indexação apenas serializa/desserializa o campo no payload (`_payload_from_record`/`_record_from_payload`) | Determinismo (testável sem Qdrant); segue o padrão F-14 de propagação por parâmetro com teste | Calcular dentro do adapter (invisível ao teste puro); derivar do `chunk_id` (não prova integridade do texto) | 🟢 |
| D-04 | Fixtures commitadas em `tests/fixtures/`: 1 PDF digital pequeno + 1 PDF "escaneado" gerado do digital (página-imagem única, sem camada de texto), gerados por receita documentada no teste de integração | Artefatos estáveis e inspecionáveis; "pronto quando" do `D1-P1-2` | Gerar PDFs no próprio teste (variabilidade entre runs); fixture binária grande (limite: PDFs pequenos, < 100 KB cada) | 🟢 |
| D-05 | Modo offline = pipeline real + fake **apenas** do `Embedder`; índice vetorial local via Docker conta como offline; marker `integration` registrado no `pyproject.toml` | Definição corrigida pela crítica C2-05; F-03 (marker registrado) | Fake de mais portas (não testa o pipeline real); exigir Docker remoto | 🟢 |
| D-06 | Round-trip testado com índice fake/`QdrantClient` mockado: gravar com fingerprint → recuperar → conferir sha256; chunk legado sem o campo → `None` aceito | RF-02 tem dois lados (novo e retrocompatível); padrão de teste de payload já usado em `test_indexing.py` | Teste só de escrita (não prova leitura) | 🟢 |
| D-07 | Nenhuma flag de truncamento — o pipeline não trunca | RN-04 explícita no requirements (`D1-P1-1`) | Criar flag "por precaução" (YAGNI — nasce só com truncamento real) | 🟢 |

## 4. Premissas

Nenhuma premissa derivada de `[DÚVIDA]` — o requirements da 005 saiu com zero marcadores (o fallback da caixa postal já está definido: silêncio = escalada ao humano). Premissas de contexto:

| Premissa | Origem (`requirements.md` seção) | Risco se errada |
|----------|----------------------------------|-----------------|
| O Dev 2 responde a caixa postal em 1 dia útil (senão a decisão escala para o humano) | §10 Lacunas | Atraso da feature; código não avança sem aceite — sem retrabalho |
| `PyMuPDF` (dependência existente do pipeline) serve para gerar o PDF "escaneado" imagem-única na receita das fixtures | §5 RF-03 | Receita alternativa com outra ferramenta de geração de PDF imagem; escopo inalterado |
| Chunks existentes podem continuar sem fingerprint (re-indexação é opcional) | §6 Compatibilidade | Se um consumidor passar a exigir o campo, vira mudança MAJOR via caixa postal |

## 5. Delta arquitetural

| Componente | Arquivo de origem no legado | Tipo de mudança | Resumo |
|------------|------------------------------|-----------------|--------|
| `shared_kernel/contracts.py` (`ChunkMetadata`) | `_reversa_sdd/sdd/shared-kernel-contracts.md#§6.1 Requisitos Funcionais` | contrato-alterado | Campo opcional `content_fingerprint: str \| None` |
| `shared_kernel/version.py` | `_reversa_sdd/sdd/shared-kernel-contracts.md#§6.1` | contrato-alterado | `CONTRACTS_VERSION` `1.0.0` → `1.1.0` (MINOR) |
| `document_processing/domain/chunk_fingerprint.py` | `_reversa_sdd/sdd/document-processing.md#§9 Modelo de Dados` | componente-novo | Função pura sha256 do texto do chunk |
| `document_processing/infrastructure/indexing.py` | `_reversa_sdd/sdd/document-processing.md#§9 Modelo de Dados` | regra-alterada | Payload ganha `content_fingerprint` opcional no round-trip (`_payload_from_record`/`_record_from_payload`) |
| `tests/fixtures/` | `_reversa_sdd/sdd/document-processing.md#§6.1` | componente-novo | PDF digital pequeno + PDF "escaneado" imagem-única |
| `tests/integration/` | `_reversa_sdd/sdd/document-processing.md#§6.1` | componente-novo | Teste opt-in `-m integration` offline com fake de `Embedder`, declaração real vs fake |
| `contract-delta-chunkmetadata.md` (na feature) | `_reversa_sdd/learning/aprendizados.md#§5.2` | componente-novo | Caixa postal com aceite/negativa do Dev 2 registrado |

## 6. Delta no modelo de dados

- Resumo das mudanças: **um campo opcional** em `ChunkMetadata` + chave opcional `content_fingerprint` no payload do Qdrant; retrocompatível com chunks gravados sem o campo. Nenhuma mudança em `EvidenceRef` nem em tabelas DuckDB.
- Detalhe completo em: `_reversa_forward/005-p1-dev1-proveniencia/data-delta.md`

## 7. Delta de contratos externos

Nenhum contrato externo (HTTP/fila/gRPC/GraphQL) afetado — diretório `interfaces/` omitido. O contrato interno `shared_kernel` muda via caixa postal (`contract-delta-chunkmetadata.md`), que substitui o detalhamento em `interfaces/` conforme a convenção §5.2.

## 8. Plano de migração

1. Escrever `contract-delta-chunkmetadata.md` (proposta: campo, semântica, versão alvo 1.1.0) e aguardar aceite do Dev 2 (1 dia útil; silêncio = escalada ao humano).
2. Com aceite: bump `CONTRACTS_VERSION` para `1.1.0`, adicionar o campo opcional em `ChunkMetadata` (testes de contrato existentes continuam verdes — retrocompatibilidade provada).
3. Implementar `compute_content_fingerprint` + payload round-trip com testes.
4. Chunks já gravados **não** exigem migração: continuam válidos com `content_fingerprint = None`; repopular é opcional via reprocessamento idempotente (delete+upsert) do documento.
5. Fixtures + teste opt-in `integration`; gate `T-1` completo.

## 9. Riscos e mitigações

| Risco | Impacto | Probabilidade | Mitigação |
|-------|---------|---------------|-----------|
| Aceite do Dev 2 atrasar (caixa postal) | médio | baixa | Prazo de 1 dia útil com escalada ao humano (§5.2); o resto do plano da 005 (fixtures/offline) não depende do aceite e pode ir adiante |
| Consumidor futuro passar a exigir `content_fingerprint` | alto | baixa | Campo é opcional por decisão; exigência futura vira caixa postal MAJOR explícita |
| Fixtures binárias inflarem o repositório | baixo | média | Limite declarado (< 100 KB por PDF); PDFs gerados a partir de texto sintético curto |
| Teste `integration` opt-in não rodar no dia a dia e regredir em silêncio | médio | média | Registrar no `regression-watch.md`; rodar explicitamente antes do PR (item do ritual `D1`); marker registrado (F-03) |
| PDF "escaneado" acabar com camada de texto extraível (fixture falsa) | médio | baixa | O teste de integração **prova** a ausência de camada de texto antes de usar a fixture (cenário negativo do requirements) |

## 10. Critério de pronto

- [ ] Todas as ações do `actions.md` marcadas `[X]`
- [ ] Caixa postal `contract-delta-chunkmetadata.md` com aceite/negativa registrado **antes** do código de payload
- [ ] Gate `T-1` (`ruff` + `mypy` + `python -B -m pytest -q -p no:cacheprovider`) verde 3× consecutivas
- [ ] `python -B -m pytest -q -p no:cacheprovider -m integration` verde sem internet (fake de `Embedder` declarado)
- [ ] `regression-watch.md` gerado (com o teste opt-in sob vigilância)
- [ ] `/reversa-sync` executado ao final (adendo na extração)

## 11. Histórico de alterações

| Data | Alteração | Autor |
|------|-----------|-------|
| 2026-09-26 | Versão inicial gerada por `/reversa-plan` | reversa |
