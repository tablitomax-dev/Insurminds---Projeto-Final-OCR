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

## 3. Rastreabilidade

- Caixa postal (aceite registrado): `_reversa_forward/005-p1-dev1-proveniencia/contract-delta-chunkmetadata.md`
- Escopo e prioridades: `requirements.md` (RF-01..RF-05, RN-01..RN-04)
- Decisões de desenho `D-01`..`D-07`: `roadmap.md#3`
