# Insurminds — Plataforma Inteligente para Análise e Comparação de Apólices D&O

Protótipo funcional (MVP) que extrai, organiza e compara informações de apólices de seguro
**D&O (Directors and Officers)** com OCR, LLMs e agentes inteligentes — do recebimento do PDF até a
apresentação das diferenças entre duas apólices, com **evidência documental** (página e trecho) em
cada informação extraída.

**Instituto de Inteligência Artificial Aplicada — I2A2** · Curso de Inteligência Artificial Aplicada —
Desafio Final · **Grupo AlgorithLabs** · Outubro/2026.

---

## Para a banca avaliadora: onde está a entrega do projeto

A entrega completa (relatório técnico, slides, vídeo de demonstração e apólices de teste) está na
pasta **[`Entrega do projeto/`](./Entrega%20do%20projeto/)**, na raiz deste repositório:

| Item | Arquivo | Descrição |
|---|---|---|
| Relatório técnico | `Relatorio_Tecnico_InsurMinds_Projeto_Final.pdf` | Documento completo: problema, arquitetura, agentes de IA, decisões, segurança, limitações e matriz de requisitos × evidência |
| Slides | `InsurMinds_Projeto_Final.pptx` | Apresentação do projeto |
| Vídeo de demonstração | `InsurMinds_Projeto_Final.mp4` | Demonstração do fluxo completo na interface (comprimido para viabilizar o versionamento no Git) |
| Apólices de teste | `APÓLICES/` | Apólices reais (versões de teste) de AXA, Allianz (2025 e 2017) e Porto, usadas na validação |

O código-fonte do protótipo é este próprio repositório (módulos em `src/`, testes em `tests/`,
execução via `iniciar_app.bat` — veja as instruções abaixo).

---

## Descrição do projeto

Apólices D&O são documentos longos, complexos e redigidos em linguagem jurídica. Comparar duas
apólices — típico em cotações, renovações e auditorias de *placement* — consome horas de especialistas
e costuma ser entregue **sem rastreabilidade**: a recomendação raramente aponta a página e o trecho
que a sustentam.

A plataforma resolve isso com um pipeline automático ponta a ponta:

1. **Recebimento** — upload de PDFs (digitais ou escaneados) com validação;
2. **Extração automática** — texto nativo (PyMuPDF) + OCR (PaddleOCR) convertidos em **markdown
   estruturado por seções** (PP-StructureV3);
3. **Organização** — cada seção vira evidência citável; os dados de negócio vão para um catálogo
   tipado de **10 campos críticos** + achados fora do catálogo;
4. **Armazenamento estruturado** — DuckDB (fatos, comparações, markdown) + índice vetorial Qdrant;
5. **Consulta** — perguntas livres em linguagem natural com citações (Agente Inteligente RAG);
6. **Comparação** — motor **100% determinístico** campo a campo (o LLM extrai e explica; **nunca**
   decide valores — elimina alucinação no resultado);
7. **Apresentação** — tabela de diferenças, explicações rastreáveis, fila de revisão humana e
   **Relatório D&O** com ranking parametrizável, cenários de sensibilidade e checklist de decisão.

Diferenciais: rastreabilidade total (todo fato aponta página/trecho), comparação determinística,
decisão apoiada pelo Relatório D&O e qualidade de engenharia (contratos versionados, erros
classificados com timeout, cadeia de fallback de LLMs, testes automatizados e validação com apólices
reais das seguradoras AXA, Allianz e Porto).

## Instruções de instalação

Pré-requisitos:

- **Python 3.12** (recomendado; mínimo 3.11) e `pip`;
- **Qdrant** local na porta 6333 (opcional para o modo demo): `docker run -p 6333:6333 qdrant/qdrant`;
- **Chave de API de LLM** (OpenRouter e/ou Gemini) para o modo real.

```bash
git clone <url-do-repositório> Insurminds---Projeto-Final-OCR
cd Insurminds---Projeto-Final-OCR
python -m venv .venv
.venv\Scripts\activate          # Linux/macOS: source .venv/bin/activate
pip install -e ".[dev]"         # stack completo do projeto (instalável)
```

Configuração de credenciais — **nunca no código** (as chaves moram em variáveis de ambiente):

```powershell
# Windows — persistente (uma única vez no terminal) e depois reabra o app:
setx OPENROUTER_API_KEY "sua-chave"
# Opcional (fallback em conta separada):
setx GEMINI_API_KEY "sua-chave"
```

## Instruções de execução

```bash
# Pelo launcher de dois cliques (Windows):
iniciar_app.bat

# Ou manualmente — interface completa (modo real):
python -m streamlit run run_ui_demo.py

# Modo demonstração offline (sem LLM/OCR — usa fixtures; ids POL-A e POL-B):
python -m streamlit run run_ui_demo.py    # sem LLM_REAL=1
```

No modo real, a cadeia de modelos de IA é configurada por variáveis de ambiente (padrões entre
parênteses): `LLM_MODEL` (`z-ai/glm-5.3-flash`, principal) → `LLM_FALLBACK_MODEL`
(`deepseek/deepseek-v4.1-flash`) → `LLM_FALLBACK_MODEL_2` (`xiaomi/mimo-v2.6-pro`), com avanço
automático após 2 falhas consecutivas de cada nível. Com `GEMINI_API_KEY` definida, um nível extra em
conta separada (`LLM_GEMINI_MODEL`, padrão `gemini-2.0-flash`) entra no fim da cadeia.

Fluxo do usuário: carregar as duas apólices → **Processar apólices** (a extração dos campos roda
automaticamente) → aviso *"Extração concluída — você já pode fazer suas perguntas"* → **consulta
livre** com o Agente Inteligente → comparação, revisão e exportação.

Gate de qualidade do código:

```bash
python -m pytest -q     # testes automatizados
ruff check .            # lint
mypy src                # tipos
```

## Tecnologias utilizadas

| Área | Tecnologia |
|---|---|
| Linguagem | Python 3.12 |
| Interface | Streamlit |
| Agentes de IA | Pydantic AI · LLMs via OpenRouter (glm-5.3, deepseek-v4.1, mimo-v2.6) e Google Gemini |
| OCR e layout | PaddleOCR · PP-StructureV3 (markdown estruturado) |
| PDF | PyMuPDF |
| Armazenamento | DuckDB (banco analítico em arquivo) · Qdrant (índice vetorial) |
| Qualidade | pytest · ruff · mypy |

## Identificação dos integrantes

**Grupo AlgorithLabs** — Instituto de Inteligência Artificial Aplicada (I2A2), Desafio Final,
Outubro de 2026:

- Giovani Amiti
- Pablo Benachio
- Eridalgo Ramos da Silva

## Licença

Distribuído sob licença **MIT** — veja o texto da licença abaixo.

```
MIT License

Copyright (c) 2026 Grupo AlgorithLabs — Insurminds

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```
