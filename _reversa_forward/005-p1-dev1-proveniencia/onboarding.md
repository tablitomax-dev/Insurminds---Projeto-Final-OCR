# Onboarding: P1 do Desenvolvedor 1 — Proveniência do Chunk e Modo Offline

> Identificador: `005-p1-dev1-proveniencia`
> Data: `2026-09-26`
> Para: humano testando a feature pela primeira vez (Windows/PowerShell — ver `aprendizados.md` Apêndice A)

## Pré-requisitos

1. Mesmo ambiente das features 001–003 (Python + dependências do projeto).
2. Docker local **só** para o teste de integração opt-in (índice vetorial local conta como offline).
3. Nenhuma chave de API e nenhuma internet para os testes: o `Embedder` é falso no modo offline.

## Passo a passo

1. **Confira a caixa postal primeiro** (pré-condição da feature):
   `_reversa_forward/005-p1-dev1-proveniencia/contract-delta-chunkmetadata.md` deve existir com aceite/negativa do Dev 2 **datado e assinado**. Sem aceite, o código de payload não deve estar integrado.
2. **Gate de qualidade:**
   ```powershell
   python -m ruff check .
   python -m mypy src
   python -B -m pytest -q -p no:cacheprovider
   ```
3. **Testes unitários da feature** (round-trip e fingerprint):
   ```powershell
   python -B -m pytest -q -p no:cacheprovider tests/modules/document_processing -k "fingerprint or payload or round"
   ```
4. **Teste de integração offline (opt-in):** com o Docker local no ar e **sem internet** (modo avião é o teste honesto):
   ```powershell
   python -B -m pytest -q -p no:cacheprovider -m integration
   ```
   O teste declara no próprio código o que é real (pipeline, chunking, indexação local) e o que é fake (`Embedder`).
5. **Confira as fixtures:** `tests/fixtures/` tem o PDF digital pequeno e o "escaneado". Prove que o "escaneado" não tem camada de texto (o próprio teste faz isso antes de usá-lo).
6. **Prova manual de proveniência (opcional):** processe um PDF pelo pipeline, recupere um chunk e compare `content_fingerprint` gravado com `sha256` do texto recuperado — devem coincidir; altere o texto e veja o hash divergir.

## O que é real e o que é fake neste teste

- Real: extração de texto, chunking, montagem de payload, indexação e recuperação (índice local), cálculo do fingerprint.
- Fake: `Embedder` (vetores determinísticos de teste) — a rede de embeddings é a única externa do pipeline.

## Problemas comuns

- **`-m integration` coleta 0 testes:** confirme que o marker `integration` está registrado no `pyproject.toml` (aprendizado F-03) e que os testes opt-in estão em `tests/integration/`.
- **Fingerprint `None` em chunk que você acabou de indexar:** o chunk foi gravado sem o campo (v1.0.0) — reprocessar o documento (upsert idempotente) popula o fingerprint.
- **Docker fora do ar:** o teste de integração falha cedo com mensagem do índice — suba o índice local e reexecute; nada de rede externa é necessária.
