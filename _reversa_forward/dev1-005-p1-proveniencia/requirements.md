# Requirements: P1 do Desenvolvedor 1 — Proveniência do Chunk e Modo Offline

> Identificador: `dev1-005-p1-proveniencia`
> Data: `2026-09-26`
> Pasta da extração reversa: `_reversa_sdd/`
> Confidência: 🟢 CONFIRMADO, 🟡 INFERIDO, 🔴 LACUNA / DÚVIDA
> Dono de execução: **Desenvolvedor 1** (itens `D1-P1-1`, `D1-P1-2` de `_reversa_sdd/learning/plano-acao-dev1.md#§3`)

## 1. Resumo executivo

A feature entrega proveniência rica no chunk indexado — `content_fingerprint` (resumo criptográfico sha256 do texto do chunk) como campo opcional no payload — e um modo de teste offline confiável: fixtures com um PDF digital pequeno e um PDF "escaneado" gerado do digital, processados pelo pipeline real com fakes apenas do `Embedder`. Resolve a ausência de lastro de integridade do chunk (benchmark de referência §2.4) e a impossibilidade atual de rodar integração sem internet.

## 2. Contexto a partir do legado

| Fonte | Trecho relevante | Confidência |
|-------|------------------|-------------|
| `_reversa_sdd/sdd/document-processing.md#§9 Modelo de Dados` | Payload do chunk indexado (metadados do chunk no índice vetorial) — é onde `content_fingerprint` entra como campo opcional | 🟢 |
| `_reversa_sdd/sdd/document-processing.md#§6.1 Requisitos Funcionais` | Pipeline PDF → chunking → embeddings → indexação; `chunk_text` nunca trunca (sem flag de truncamento — regra vigente) | 🟢 |
| `_reversa_sdd/sdd/shared-kernel-contracts.md#§6.1 Requisitos Funcionais` | Contrato v1.0.0; campo opcional novo é mudança **MINOR** retrocompatível, via caixa postal + bump de `CONTRACTS_VERSION` | 🟢 |
| `_reversa_sdd/learning/benchmark-repos-referencia.md#§2.4` | Aproveitamento: proveniência rica no chunk (fingerprint) rastreia integridade do texto indexado | 🟢 |
| `_reversa_sdd/learning/benchmark-repos-referencia.md#§2.6` | Aproveitamento: fixtures offline para testar o pipeline sem rede | 🟢 |
| `_reversa_sdd/learning/plano-acao-dev1.md#D1-P1-1` | Escopo: `content_fingerprint` opcional (sha256), sem flag de truncamento; mecanística da caixa postal primeiro | 🟢 |
| `_reversa_sdd/learning/plano-acao-dev1.md#D1-P1-2` | Escopo: fixtures 1 PDF digital + 1 "escaneado" gerado; offline = pipeline real com fakes de `Embedder` apenas; "pronto quando" real | 🟢 |
| `_reversa_sdd/learning/aprendizados.md#§5.2` | Caixa postal: `contract-delta-*.md` → aceite/negativa em 1 dia útil (silêncio = escalada ao humano) → uma mudança por vez → bump `CONTRACTS_VERSION` | 🟢 |
| `_reversa_sdd/addenda/dev1-002-p0-documental-rag.md#Impacto por artefato` | Estado pós-P0 vigente: lote ≤100, erros tipados e sanitizados, `RetrievalQuery` honrado por completo, isolamento provado | 🟢 |

## 3. Personas e cenários de uso

| Persona | Objetivo | Cenário-chave |
|---------|----------|---------------|
| Desenvolvedor do time (Dev 2 ou revisor) | Conferir que o texto indexado é o mesmo texto recuperado | Ao recuperar evidências, o desenvolvedor compara o `content_fingerprint` do chunk gravado com o do texto recuperado |
| Desenvolvedor do time | Rodar testes de integração sem internet | O desenvolvedor roda `pytest -m integration` numa máquina sem rede e o pipeline real processa as fixtures com o `Embedder` falso |
| Analista de cotação D&O (indireto) | Confiança na evidência citada | Fatos ancorados em chunks cuja integridade é verificável por fingerprint |

## 4. Regras de negócio novas ou alteradas

1. **RN-01:** `content_fingerprint` = sha256 do texto do chunk, campo **opcional** no payload do chunk indexado. Mudança **MINOR** e retrocompatível: chunks gravados sem o campo continuam válidos. 🟢
   - Origem no legado: `_reversa_sdd/learning/plano-acao-dev1.md#D1-P1-1`; `_reversa_sdd/learning/benchmark-repos-referencia.md#§2.4`
   - Tipo: nova
2. **RN-02:** A mudança de contrato só acontece via caixa postal: proposta em `_reversa_forward/dev1-005-p1-proveniencia/contract-delta-chunkmetadata.md` → aceite do Dev 2 em 1 dia útil (silêncio = escalada ao humano) → **uma mudança de contrato por vez** → quem propõe bumpa `CONTRACTS_VERSION` e atualiza consumidores. **Nenhuma linha de código do payload muda antes do aceite por escrito.** 🟢
   - Origem no legado: `_reversa_sdd/learning/aprendizados.md#§5.2`; `_reversa_sdd/learning/plano-acao-dev1.md#§6 Zonas compartilhadas`
   - Tipo: nova (convenção aplicada a esta feature)
3. **RN-03:** Modo offline de teste = **pipeline real com fakes apenas do `Embedder`**; o índice vetorial local via Docker conta como offline; a rede de embeddings é a única externa. O teste declara explicitamente o que é real e o que é fake. 🟢
   - Origem no legado: `_reversa_sdd/learning/plano-acao-dev1.md#D1-P1-2` (correção C2-05 do debate)
   - Tipo: nova
4. **RN-04:** Não nasce "flag de truncamento": o pipeline não trunca texto (`chunk_text` nunca trunca). A flag só surge se truncamento real aparecer no futuro (ex.: PP-Structure). 🟢
   - Origem no legado: `_reversa_sdd/learning/plano-acao-dev1.md#D1-P1-1`
   - Tipo: nova (regra de não-criação)

## 5. Requisitos Funcionais

| ID | Requisito | Prioridade | Critério de aceite | Confidência |
|----|-----------|------------|--------------------|-------------|
| RF-01 | A mudança de payload é precedida de proposta de contrato com aceite por escrito do Dev 2 | Must | `contract-delta-chunkmetadata.md` existe na feature com aceite/negativa datada; sem aceite, o payload não muda (uma mudança de contrato por vez; `CONTRACTS_VERSION` bumpado por quem propõe) | 🟢 |
| RF-02 | O chunk indexado carrega `content_fingerprint` (sha256 do texto do chunk) como campo opcional | Must | Teste de round-trip: gravar chunk com fingerprint → recuperar → fingerprint confere com sha256 do texto; chunk sem o campo continua válido (retrocompatibilidade testada) | 🟢 |
| RF-03 | Existem fixtures de teste: 1 PDF digital pequeno + 1 PDF "escaneado" gerado do digital (imagem única, sem camada de texto) | Must | Os dois arquivos existem em `tests/fixtures/`; o "escaneado" de fato não tem camada de texto extraível | 🟢 |
| RF-04 | O teste de integração opt-in roda o pipeline real offline sobre as fixtures, com fake de `Embedder` declarado | Must | `python -B -m pytest -q -p no:cacheprovider -m integration` roda sem internet; o teste declara no próprio código o que é real e o que é fake | 🟢 |
| RF-05 | As decisões de implementação (escolha/descartadas/porquê) ficam registradas na feature | Should | `_reversa_forward/dev1-005-p1-proveniencia/` contém o registro da semântica adotada (convenção A-10) | 🟢 |

## 6. Requisitos Não Funcionais

| Tipo | Requisito | Evidência ou justificativa | Confidência |
|------|-----------|----------------------------|-------------|
| Compatibilidade | Campo opcional, mudança MINOR, retrocompatível com chunks já gravados | `_reversa_sdd/sdd/shared-kernel-contracts.md#§6.1`; convenção §5.2 | 🟢 |
| Segurança | O fingerprint é resumo criptográfico one-way (sha256): não permite reconstruir o texto do chunk e **não substitui** anonimização de dados sensíveis | Natureza do sha256; higiene `T-2` | 🟡 |
| Reprodutibilidade | Suíte de integração roda sem internet (rede de embeddings é a única externa, substituída por fake) | `D1-P1-2`; aprendizado A-11 | 🟢 |
| Desempenho | O cálculo do fingerprint por chunk não adiciona latência perceptível no processamento | sha256 é operação local barata; pipeline em lote já existente (adendo 002) | 🟡 |

## 7. Critérios de Aceitação

```gherkin
Cenário: Fingerprint round-trip no chunk indexado
  Dado um PDF digital pequeno processado pelo pipeline real
  Quando o chunk é indexado com content_fingerprint
  E o chunk é recuperado do índice
  Então o content_fingerprint recuperado confere com o sha256 do texto do chunk

Cenário: Retrocompatibilidade com chunk legado
  Dado um chunk gravado sem content_fingerprint
  Quando ele é recuperado e consumido
  Então ele continua válido e nenhum consumidor quebra

Cenário: Integração offline com fake declarado
  Dado uma máquina sem acesso à internet
  Quando roda-se pytest -m integration com as fixtures (PDF digital e "escaneado")
  Então o pipeline real processa os dois PDFs usando o fake do Embedder
  E o teste declara explicitamente o que é real e o que é fake

Cenário negativo: mudança de contrato sem aceite não avança
  Dado uma proposta de mudança do payload sem aceite do Dev 2
  Quando se tenta alterar o payload do chunk
  Então a mudança não é integrada antes do aceite por escrito na caixa postal

Cenário negativo: PDF "escaneado" sem camada de texto
  Dado o PDF "escaneado" gerado do digital (imagem única)
  Quando se tenta extrair texto nativo dele
  Então não há camada de texto extraível e o pipeline o trata pelo caminho de OCR
```

## 8. Prioridade MoSCoW

| Item | MoSCoW | Justificativa |
|------|--------|---------------|
| RF-01 (caixa postal primeiro) | Must | Convenção absoluta de zona compartilhada (§5.2); sem aceite não há mudança de contrato |
| RF-02 (`content_fingerprint`) | Must | Entrega principal da proveniência (`D1-P1-1`); integridade verificável do chunk |
| RF-03 (fixtures) | Must | Pré-condição do RF-04; sem fixture não há modo offline |
| RF-04 (integração offline) | Must | "Pronto quando" real exigido pela crítica C2-05 do debate |
| RF-05 (registro de decisões) | Should | Convenção A-10; rastreabilidade, não bloqueia valor |
| RNF de compatibilidade | Must | Contrato compartilhado: retrocompatibilidade é condição de aceite da mudança MINOR |

## 9. Esclarecimentos

> Nenhuma sessão de dúvidas registrada ainda. Rode `/reversa-clarify` quando houver `[DÚVIDA]` pendente.

## 10. Lacunas

- 🟡 Aceite do Dev 2 na caixa postal (`contract-delta-chunkmetadata.md`) é dependência de processo com prazo de 1 dia útil; silêncio = escalada ao humano (`_reversa_sdd/learning/aprendizados.md#§5.2`) — sem nova decisão pendente.
- 🟡 Seção real por chunk (`section_name` com PP-Structure) segue fora do escopo (NG-01 registrado no plano Dev 1); `content_fingerprint` não a substitui.

## 11. Histórico de alterações

| Data | Alteração | Autor |
|------|-----------|-------|
| 2026-09-26 | Versão inicial gerada por `/reversa-requirements` | reversa |
