# Investigation: Vertical slice do policy_analysis

> Identificador: `001-dev2-policy-analysis-slice`
> Data: `2026-09-26`
> Relacionado: `roadmap.md`, `requirements.md`

## 1. Perguntas de pesquisa

1. Qual estratégia de agente de extração equilibra precisão, custo e rastreabilidade? (resolvida — OQ-02)
2. Como garantir comparação determinística com valores de tipos diferentes (moeda, período, texto livre)? (resolvida — OQ-03)
3. Como produzir explicações de LLM rastreáveis (sempre citando evidência)?
4. Qual biblioteca de export PDF com menor atrito operacional?
5. Como persistir em DuckDB com IDs consistentes e idempotência?

## 2. Alternativas avaliadas

### 2.1 Estratégia de agente de extração

| Alternativa | Prós | Contras | Destino |
|-------------|------|---------|---------|
| 1 agente por campo (10 chamadas) | Prompts especializados; falha isolada por campo | 10× custo/latência; repetição de contexto | descartada |
| 1 agente multi-campo (1 chamada) | Custo mínimo; contexto compartilhado entre campos; consistência entre valores | Prompt maior; falha afeta todos os campos de uma vez | **escolhida (4b)** |
| Híbrida (multi-campo + re-extração individual) | Melhor dos dois mundos | 2 caminhos de código; mais casos de teste | descartada por complexidade no slice |

### 2.2 Regras de comparação por tipo

| Alternativa | Prós | Contras | Destino |
|-------------|------|---------|---------|
| Regra única (maior/menor/igual para tudo) | Simples | Inútil para texto/moeda com formatos distintos | descartada |
| Totalmente normalizada (moeda→BRL, período→duração, texto→semântica) | Máxima automação | Comparação semântica de texto exigiria LLM — proibido (RN-01) | descartada |
| Híbrida: normalização determinística onde é possível (numérico, moeda, período); texto livre igual/divergente + explicação detalhando | Determinismo preservado; análise útil para o analista | Texto livre não tem "maior/menor" | **escolhida (2c)** |

Detalhes: moeda usa `Decimal` (nunca `float`) e normalização por taxa injetável; período compara datas absolutas e duração; texto normaliza caixa/acentos/espaços.

### 2.3 Explicação rastreável com LLM

Padrão aplicável: **structured output + validação pós-resposta**. O prompt exige que cada afirmação da explicação cite `evidence_ids` das evidências recebidas; a saída é validada contra schema (todo `evidence_id` citado deve existir nos fatos comparados). Explicação inválida é rejeitada e reexecutada (máximo configurável), depois vira falha classificada. Referência: princípios de "grounded generation" (resposta ancorada em contexto fornecido).

### 2.4 Export PDF

| Biblioteca | Prós | Contras | Destino |
|------------|------|---------|---------|
| `fpdf2` | Leve, pura Python, API simples, sem dependências de sistema | Recursos gráficos limitados | **escolhida** |
| `reportlab` | Maduro, layout rico | Pesado; curva de aprendizado | descartada |
| `weasyprint` (HTML→PDF) | Layout CSS | Exige libs nativas (Pango/Cairo) — atrito no Windows | descartada |

### 2.5 Persistência DuckDB

Padrões: schema idempotente (`CREATE TABLE IF NOT EXISTS`) na primeira execução; JSON armazenado como `VARCHAR` + `json` functions do DuckDB para consulta; transação por unidade de trabalho (extração de uma apólice); idempotência de comparação por chave natural determinística (par ordenado de `policy_id` → hash estável como `ComparisonId`, D-09).

## 3. Fontes externas consultadas

- Pydantic AI — documentação oficial (structured output e tool/agent): https://ai.pydantic.dev/
- Pydantic v2 — validação e `model_validator`: https://docs.pydantic.dev/
- DuckDB — Python API e funções JSON: https://duckdb.org/docs/api/python/overview
- fpdf2 — documentação: https://py-pdf.github.io/fpdf2/
- Gemini API — limites e códigos de erro (429/timeout): https://ai.google.dev/gemini-api/docs

## 4. Padrões aplicáveis

- **Ports & Adapters** na porta `EvidenceSource` (D-02 do roadmap): domain define o protocolo, infrastructure implementa.
- **Value objects imutáveis** para `Money`, `Period`, `FieldCode` — eliminam classe de bugs de normalização.
- **Pure function core**: o comparador não tem I/O, não chama LLM, não lê banco — teste 100% determinístico.
- **Validação na fronteira**: `field_code` e saída de LLM validados antes de entrar no domínio (RF-02, RF-09).

## 5. Pendências de pesquisa

- 🔴 Taxa de câmbio para normalização de moeda: a porta `CurrencyNormalizer` será injetável e, no slice, fixtures informam a taxa; se apólices reais tiverem moeda estrangeira, decidir fonte de taxa (ex.: PTAX) em iteração futura.