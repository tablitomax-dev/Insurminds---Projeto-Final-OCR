# Onboarding: Vertical Slice E2E

> Identificador: `001-vertical-slice-e2e`
> Data: `2026-09-26`
> Para quem: humano que vai testar a feature pela primeira vez.

## 1. Pré-requisitos

- Python 3.11+ instalado
- `pip install -r requirements.txt` (núcleo: pydantic, pytest)
- Opcional (para a jornada real, não necessária para os testes):
  - Docker (Qdrant): `docker run -p 6333:6333 qdrant/qdrant`
  - `pip install pymupdf paddleocr paddlepaddle duckdb streamlit pydantic-ai google-genai qdrant-client`
  - Chave de API Gemini em `GEMINI_API_KEY`

## 2. Rodar os testes (primeira coisa a fazer)

```bash
python -B -m pytest -q -p no:cacheprovider
```

- Testes de núcleo e da jornada E2E (com fakes) rodam sem Docker nem chave de API.
- Testes marcados `integration` são pulados automaticamente quando a dependência falta.

## 3. Rodar a tela (jornada real)

```bash
python -B -m streamlit run src/ui/app.py
```

1. Carregue 2 PDFs de apólice D&O (um digital e um com página escaneada, se possível).
2. Clique em processar e acompanhe os estágios (`RECEIVED → TEXT_EXTRACTED → OCR_COMPLETED → INDEXED`).
3. Selecione o campo `limite_agregado` e extraia; veja o fato com a evidência de página/trecho.
4. Rode a comparação entre as 2 apólices; confira a explicação por diferença.
5. Exporte o resumo (gera `exports/<ComparisonId>.md`) e abra em qualquer editor.
6. Fila de revisão: campos `AMBIGUOUS`/`NEEDS_REVIEW` aparecem com a evidência anexa.

## 4. Comportamentos esperados

- PDF corrompido/não-PDF → status `FAILED("EXTRACT: ...")` e nada indexado.
- Reprocessar o mesmo PDF não duplica chunks (idempotência).
- Campo ausente → `NOT_FOUND` e, na comparação, diferença por omissão.
- Nenhum conteúdo de apólice aparece nos logs além de IDs e estágios.

## 5. Solução de problemas

| Sintoma | Causa provável | Ação |
|---------|----------------|------|
| `FAILED(INDEXING: ...)` | Qdrant fora do ar ou sem `GEMINI_API_KEY` | subir Docker/definir chave; reprocessar (idempotente) |
| Página inteira em `REVIEW_REQUIRED` | OCR abaixo do limiar 0.5 | esperado para página ilegível; revisar o PDF de origem |
| Testes `integration` skipped | dependência ausente | instalar extras da seção 1 |
