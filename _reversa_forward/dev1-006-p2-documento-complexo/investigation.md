# Investigation: Documento complexo — estrutura, cláusulas e tabelas (NG-01)

> Identificador: `dev1-006-p2-documento-complexo`
> Data: `2026-10-01`

## 1. Pesquisa de fundo

**O que o problema exige:** reconhecer a estrutura retórica de apólices D&O (cláusulas/artigos/seções) a partir do texto/estrutura do PDF, preservar tabelas de forma utilizável e analisar layout de páginas escaneadas — tudo sem mudar contrato e sem colocar texto de apólice em log (T-2a).

**Duas camadas, decopladas (decisão D-01/D-05 do roadmap):**
1. **Heurística pura de texto** (sempre ativa): marcadores de seção no início de linha — determinística, offline, testável sem dependência.
2. **Motor de layout** (PP-StructureV3, adapter lazy): regiões heading/table/text — principal valor em páginas escaneadas e na detecção de tabelas.

## 2. Alternativas avaliadas

| Alternativa | Prós | Contras | Decisão |
|-------------|------|---------|---------|
| PP-StructureV3 (PaddleOCR) como motor de layout | saída de regiões pronta (título/tabela/texto), HTML de tabela; já é a direção nominal do NG-01 e do PRD §5 | dependência pesada; risco PIR/oneDNN no Windows/CPU | **Adotado** (com degradação D-07 e validação opt-in) |
| Heurística pura de tabelas no texto (ASCII pipes/espaços) | zero dependência | frágil em tabelas reais de apólice (alinhamento variável) | Descartada como fonte primária; pode entrar como refinamento futuro |
| `pdfplumber`/`camelot`/`tabula` para tabelas | boas para PDFs digitais | dependências novas só para tabela; não ajudam página escaneada | Descartado nesta rodada |
| PyMuPDF `get_text("dict")` (blocos/fontes) para seções | já instalado; heurística de fonte/tamanho | semântica de seção por tamanho de fonte é frágil em apólices reais | Mantido como possível refinamento do marcador, não como fonte única |
| Detecção de seção via LLM | semântica rica | custo, latência, risco de invenção (RN-02 proíbe nome sem fonte) | Proibido por RN-02 |

## 3. Padrões aplicáveis do próprio repositório

- **Adapter lazy com erro tipado sanitizado:** `infrastructure/extractors.py` (PaddleOcrEngine) e `indexing.py` (GeminiEmbedder) — import na construção, `RuntimeError` claro sem dependência, erro externo vira exceção da porta com só o tipo do erro (T-2a).
- **Fake determinístico para o externo:** `tests/fakes/document_processing.py` (`FakeEmbedder` etc.) e `_FakeGenaiSdk` de `test_indexing.py` — o teste declara o que é real e o que é fake (RN-03 do dev1-005).
- **Domínio puro sem dependência externa:** `domain/processing.py` (RNF-06) — a heurística de seção segue o mesmo padrão.
- **Métrica/log estruturado só com números:** `_record_usage` do `llm_agent.py` e `_record_embedding_usage` do `indexing.py` (D1-P2-1) — o motor de layout não precisa de métrica nova nesta rodada; se preciso, seguir o mesmo formato.
- **Skip gracioso de dependência de integração:** padrão D-10 (`importorskip` + marcação `integration`), já usado para Paddle/Qdrant.

## 4. Fontes externas

- PaddleOCR PP-StructureV3 (pipeline de análise de layout com detecção de regiões e reconhecimento de tabelas): https://paddlepaddle.github.io/PaddleOCR/latest/paddleocr/tutorials/ppstructure/quick_start.html
- Contrato interno: `_reversa_sdd/sdd/shared-kernel-contracts.md#RF-06` (literal `PP_STRUCTURE` reservado desde a Fase 0).
- Restrição de ambiente conhecida: bug PIR/oneDNN do PaddlePaddle em Windows/CPU — registrado em `_reversa_forward/dev1-005-p1-proveniencia/decisions.md` (E-08), com política de skip diagnóstico.

## 5. Pontos de atenção para o coding

1. O literal do marcador deve ser capturado **como está no documento** (clarify: sem normalização) — cuidado com `.strip()` que remova formatação significativa.
2. O estado "marcador vigente" atravessa páginas — o loop de páginas do `service.py` precisa manter o estado, e chunks antes do primeiro marcador ficam `None`.
3. A serialização `[TABELA]` entra no **texto** que alimenta `chunk_text` — a sobreposição de 100 chars pode cortar uma tabela ao meio; aceitável (conteúdo continua recuperável por embedding), mas registrar em `decisions.md` no coding.
4. Teste anti-vazamento para `section_name` em log (RN-07) — espelhar `test_metrica_de_embedding_nunca_carrega_texto_de_aplice`.
