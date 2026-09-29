# Regression Watch: P1 do Desenvolvedor 1 — Proveniência do Chunk e Modo Offline

> Identificador: `005-p1-dev1-proveniencia`
> Data: `2026-09-27` (ISO 8601)
> Cenário **greenfield** (âncora: `prd.md` + specs SDD): não há regras 🟢 extraídas para vigiar — o watch principal fica vazio e os RFs implementados ficam em "Observações", sem peso de regressão. Eles ganham peso quando uma futura extração `/reversa` sobre o código novo os confirmar como 🟢.

## Watch principal

| ID | Origem (arquivo, seção) | Regra esperada após mudança | Tipo de verificação | Sinal de violação |
|----|-------------------------|-----------------------------|---------------------|-------------------|
| — | — | — | — | — |

## Observações (sem peso de regressão)

| ID | Origem | Expectativa observada |
|----|--------|-----------------------|
| O001 | `requirements.md` RF-02 | `ChunkMetadata.content_fingerprint` opcional (v1.1.0); round-trip prova que o resumo recuperado confere com o sha256 do texto recuperado e que o payload legado sem a chave volta `None` |
| O002 | `requirements.md` RF-01/RN-02 | Mudança de contrato só após aceite por escrito na caixa postal; `CONTRACTS_VERSION` bumpado por quem propõe (guard em `test_packaging.py`) |
| O003 | `requirements.md` RF-03 | Fixtures `< 100 KB` em `tests/fixtures/`; o "escaneado" é imagem única **sem** camada de texto (provado por `test_fixtures_pdf.py`, stdlib puro, roda sempre) |
| O004 | `requirements.md` RF-04/RN-03 | **Sob vigilância especial:** `tests/integration/test_pipeline_offline.py` (marker `integration`) — opt-in, não roda no dia a dia e pode regredir em silêncio; rodar explicitamente antes de todo PR (`pytest -m integration` com `INTEGRATION_QDRANT_URL=:memory:` ou Qdrant local). Validado em 2026-09-27: **3 passed, 3 skipped** — digital ponta a ponta verde; "escaneado" pula pela limitação do PaddlePaddle Windows/CPU (decisão E-08), rodar em Linux/CI |
| O005 | `requirements.md` RN-04 | Nenhuma flag de truncamento nasce nesta feature — `chunk_text` segue sem truncar |

## Histórico de re-extrações

_(vazio — será preenchido quando uma re-extração `/reversa` rodar sobre o código novo)_

## Arquivadas

_(vazio)_
