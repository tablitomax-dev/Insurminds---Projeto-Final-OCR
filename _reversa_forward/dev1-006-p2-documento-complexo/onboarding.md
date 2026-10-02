# Onboarding: Documento complexo — estrutura, cláusulas e tabelas (NG-01)

> Passo a passo para um humano testar a feature pela primeira vez. Comandos em PowerShell, na raiz do projeto.

## 1. Pré-requisitos

- Ambiente de desenvolvimento do repo (Python 3.13 + `.tools/` com ruff/mypy; duckdb em `.tools\pylibs`).
- **Não** é necessário ter Paddle instalado: os testes usam motor de layout **fake**; o motor real é opt-in (extras de integração em `.tools/pylibs`, padrão E-08 do dev1-005).

## 2. Provar que a detecção de seções funciona (offline, sem dependência)

1. Rode os testes de estrutura:
   `python -B -m pytest -q -p no:cacheprovider tests/modules/document_processing -k structure`
2. Espere testes verdes declarando: marcador vigente atravessa páginas; literal preservado; chunk sem seção → `section_name=None`.

## 3. Provar o fluxo completo com fakes

1. `python -B -m pytest -q -p no:cacheprovider tests/modules/document_processing`
2. Confirme os cenários Gherkin: `section_name` literal, tabela serializada com `[TABELA]`, `source_type="PP_STRUCTURE"` no caminho do motor, e degradação sem motor (RN-05).

## 4. Prova manual (opcional, com dados sintéticos)

1. Processe a fixture digital (`tests/fixtures/aplice_digital.pdf`) pela fachada e recupere evidências filtrando por `section_name` de uma cláusula conhecida.
2. Reprocesse o mesmo `document_id`: os `section_name` devem ser idênticos (idempotência RF-09).

## 5. Integração real opt-in (só se o Paddle estiver instalado)

1. `python -B -m pytest -q -p no:cacheprovider -m integration` — o mesmo padrão de skip do OCR: a limitação conhecida do PaddlePaddle em Windows/CPU pula com razão explícita; qualquer outra falha é real.
2. Com a flag `layout_mode="all"`, páginas nativas também passam pelo motor e carregam `source_type="PP_STRUCTURE"`.

## 6. O que é real e o que é fake

- **Real:** domínio (detecção de marcadores, serialização de tabela, chunking), serviço, payload Qdrant, contratos.
- **Fake:** motor de layout (regiões determinísticas) nos testes unitários; o motor real só no opt-in de integração.

## 7. Problemas comuns

- **`section_name` sempre `None`:** o marcador precisa estar no **início de linha** e pertencer à família Cláusula/Artigo/Seção/Epígrafe — literal não é inventado (RN-02).
- **Tabela vira texto corrido:** esperado quando o motor de layout não roda na página (default só em escaneadas) — use `layout_mode="all"` para forçar.
- **Paddle falha no Windows/CPU:** comportamento previsto (D-07) — o processamento degrada e conclui; não é bug da feature.
