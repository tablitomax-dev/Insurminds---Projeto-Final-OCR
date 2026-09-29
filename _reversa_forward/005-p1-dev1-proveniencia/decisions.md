# Registro de decisões: P1 do Desenvolvedor 1 — Proveniência do Chunk e Modo Offline

> Identificador: `005-p1-dev1-proveniencia`
> Data: `2026-09-27` (ISO 8601) · Convenção: **A-10** (decisão registrada na feature)
> Complementa as decisões `D-01`..`D-07` do `roadmap.md` — aqui ficam as decisões **de execução** (semântica adotada, escolhas descartadas, porquê).

## 1. Semântica adotada do `content_fingerprint`

- **Valor:** `sha256` do texto do chunk **como vai para o payload** (`ChunkRecord.text`), em UTF-8, hex 64 chars minúsculo.
- **`None`:** chunk indexado antes de v1.1.0 ou fonte sem texto estável — consumidores não podem exigir o campo.
- **Divergência** entre o resumo gravado e o do texto recuperado = **sinal de alerta** (drift/corrupção/merge manual), nunca exceção.
- **Fora de escopo:** filtro de busca, ranking e `EvidenceRef` (a caixa postal `contract-delta-chunkmetadata.md` fixa a fronteira).

## 2. Decisões de execução

| ID | Decisão | Escolhas descartadas | Porquê |
|----|---------|----------------------|--------|
| E-01 | O preenchimento do fingerprint acontece em `application/service.py`, no ato de montar o `ChunkRecord` (`compute_content_fingerprint(chunk)`) | calcular no adapter de indexação; `build_chunk_metadata(text=...)` | O roadmap (D-03) fixa o adapter como **serializador apenas**; mudar a assinatura de `build_chunk_metadata` traria o texto para um domínio que hoje só recebe metadados — 1 linha no orquestrador é o menor delta |
| E-02 | Fixtures de PDF geradas por **receita stdlib** (zlib), documentada no teste | gerar com PyMuPDF (premissa §4 do roadmap) | `fitz` não está disponível no ambiente; a tabela de riscos do roadmap já previa "receita alternativa com outra ferramenta de geração de PDF imagem" — o resultado é equivalente e reproduzível sem dependências |
| E-03 | Teste de validação das fixtures (`test_fixtures_pdf.py`) **sem** marker `integration` | marcá-lo como opt-in | Ele é stdlib puro (parse de objetos PDF + zlib) e roda sempre no gate `T-1` — provar a ausência de camada de texto todo dia vale mais que opt-in |
| E-04 | Guard de versão `test_packaging.py::test_contracts_version_is_semver` atualizado junto do bump para `1.1.0` | deixar o teste falando `1.0.0` | O teste trava a **versão vigente** do contrato; o bump MINOR (aceito na caixa postal) é exatamente o momento de acompanhá-lo |
| E-05 | Aceite da caixa postal registrado por **decisão humana** após escalada (silêncio do Dev 2 em 1 dia útil) | prosseguir sem registro; aguardar indefinidamente | Convenção §5.2: silêncio = escalada ao humano; o humano (pbena) autorizou seguir em 2026-09-27 — registro em `contract-delta-chunkmetadata.md` |
| E-06 | `metadata.content_fingerprint` atribuído depois de `build_chunk_metadata` (modelo pydantic mutável) | novo parâmetro na função do domínio | Menor delta possível; o modelo continua fechado (`extra="forbid"`) e o campo é do contrato v1.1.0 |

## 2.1 Decisões da validação pós-merge (2026-09-27, PR #5)

| ID | Decisão | Escolhas descartadas | Porquê |
|----|---------|----------------------|--------|
| E-07 | `QdrantVectorIndex` aceita `client` opcional injetado; o teste opt-in usa `QdrantClient(":memory:")` (modo embutido) quando `INTEGRATION_QDRANT_URL=:memory:` | exigir Docker/Qdrant servidor para toda validação | O cliente embutido é o MESMO `qdrant-client` real, só que sem servidor — índice local, ainda mais offline que o Docker; sem Docker no ambiente, era o único jeito de exercitar o índice real |
| E-08 | O caso do "escaneado" diagnostica a falha de OCR e pula **somente** na limitação conhecida do PaddlePaddle no Windows/CPU (`NotImplementedError` do executor PIR/oneDNN, `onednn_instruction.cc`); qualquer outra causa continua como falha real | deixar o teste vermelho; transformar toda falha de OCR em skip | O bug é de runtime do PaddlePaddle em Windows/CPU (sobrevive a `FLAGS_enable_pir_api=0`, `FLAGS_enable_pir_in_executor=0`, `FLAGS_use_mkldnn=0`) — mascarar falha real seria pior que um skip com razão explícita |
| E-09 | Extras de integração instaladas em `.tools/pylibs` (dentro do workspace) com cache do Paddle em `PADDLE_PDX_CACHE_HOME=.tools/paddlex-home` | instalar no site-packages do usuário | O sandbox bloqueia escrita fora do workspace; `.tools/` já é a casa das ferramentas do repo (ruff/mypy) |

**Resultado da validação** (`INTEGRATION_QDRANT_URL=:memory:`, sem Docker, sem rede de embeddings): `pytest -m integration` → **3 passed, 3 skipped** — o caso do PDF digital rodou o pipeline real ponta a ponta (PyMuPDF → chunking → fingerprint → Qdrant real embutido → busca → sha256 confere); o "escaneado" pula pela limitação do PaddlePaddle (E-08); os demais skips são os já conhecidos (duckdb/Gemini key).

## 3. Rastreabilidade

- Caixa postal (aceite registrado): `_reversa_forward/005-p1-dev1-proveniencia/contract-delta-chunkmetadata.md`
- Escopo e prioridades: `requirements.md` (RF-01..RF-05, RN-01..RN-04)
- Decisões de desenho `D-01`..`D-07`: `roadmap.md#3`
