# Roadmap: Vertical slice do policy_analysis — extração de fatos, comparação determinística e export

> Identificador: `dev2-001-policy-analysis-slice`
> Data: `2026-09-26`
> Requirements: `_reversa_forward/dev2-001-policy-analysis-slice/requirements.md`
> Confidência: 🟢 CONFIRMADO, 🟡 INFERIDO, 🔴 LACUNA

## 1. Resumo da abordagem

🟡 Criar o módulo `src/modules/policy_analysis/` em camadas (domain, application, infrastructure, public_api), seguindo a arquitetura do resumo §7 e a fachada definida em `_reversa_sdd/sdd/policy-analysis.md#8`. O módulo consome apenas `shared_kernel.contracts` (Fase 0, já implementada) e a fachada `document_processing.public_api` do Dev 1, atrás de uma porta `EvidenceSource` que aceita evidências mockadas (RF-10) — desbloqueando o desenvolvimento em paralelo. A extração usa um agente multi-campo (1 chamada de LLM por apólice, decisão OQ-02) com saída estruturada validada por Pydantic. A comparação é uma função pura determinística em domain, sem LLM (RN-01), com comparadores por tipo de valor. Persistência em DuckDB com schema auto-criado e IDs do shared_kernel. Explicação por LLM com citação obrigatória de evidência dos dois lados e export final em Markdown standalone. Tudo coberto por pytest com fixtures sintéticas, na branch `feature/dev2-policy-analysis`.

## 2. Princípios aplicados

n/a — `.reversa/principles.md` não existe neste projeto (greenfield). As restrições duras são as do PRD §6 e do resumo executivo (determinismo da comparação, integração por fachada, IDs compartilhados), refletidas nas decisões abaixo.

## 3. Decisões técnicas

| ID | Decisão | Justificativa | Alternativas descartadas | Confidência |
|----|---------|----------------|--------------------------|-------------|
| D-01 | Módulo em camadas `domain` / `application` / `infrastructure` / `public_api` | Arquitetura do resumo §7; isolamento exigido pelo RNF-05 (`_reversa_sdd/sdd/policy-analysis.md#7`) | módulo monofásico; API exposta direto | 🟡 |
| D-02 | Porta `EvidenceSource` (protocolo) com 2 implementações: `MockEvidenceSource` (fixtures JSON) e `DocumentProcessingEvidenceSource` (fachada Dev 1) | RF-10: desenvolver sem o retrieval real; troca de origem sem mudança de contrato | mockar função de import; depender do Dev 1 no início | 🟡 |
| D-03 | Agente multi-campo (1 chamada de LLM por apólice) com saída estruturada validada por Pydantic | Decisão OQ-02 (sessão clarify 2026-09-26): menos chamadas, custo menor, contrato por campo preservado | 1 agente por campo; agente híbrido com re-extração | 🟢 |
| D-04 | Catálogo de campos como registry de dados (`field_code` → semântica, tipo de valor, regra de normalização) | RF-02: única fonte de `field_code`; rejeição na fronteira (RN-05) e reuso pelo comparador | constantes soltas; metadados espalhados nos prompts | 🟢 |
| D-05 | Comparador determinístico puro em domain, com comparadores por tipo (numérico, moeda, período, texto) usando `Decimal` para valores monetários | RN-01/RN-06 e tabela híbrida decidida (OQ-03): determinismo total, testável sem LLM | comparação por LLM; float puro (erro de arredondamento) | 🟢 |
| D-06 | Persistência em DuckDB com schema auto-criado (`CREATE TABLE IF NOT EXISTS`) na primeira execução | RF-05; spec §9 ("schema criado na primeira execução"); sem migração em greenfield | ORM relacional completo; arquivo JSON | 🟡 |
| D-07 | Explicação gerada por LLM com prompt que exige citação de `evidence_ids` dos dois lados; explicação sem citação resolvível é rejeitada e reexecutada | RF-07/RN-02: rastreabilidade da defesa | explicação livre sem validação; template fixo sem LLM | 🟡 |
| D-08 | Export em Markdown standalone (renderizador próprio em `infrastructure/markdown_export.py`) | Decisão OQ-04 **revisada em 2026-09-26** (alinhamento com o fluxo paralelo, `_reversa_forward/dev1-001-vertical-slice-e2e/`); arquivo que abre sem o sistema (RF-08) | PDF via fpdf2 (escolha inicial da sessão clarify, substituída); reportlab; weasyprint | 🟢 |
| D-09 | `ComparisonId` determinístico derivado do par ordenado de `policy_id` (hash estável) | Idempotência EC-06: mesma comparação → mesmo ID, sem duplicar registros | UUIDv4 por execução (quebraria idempotência) | 🟡 |
| D-10 | Falhas de LLM mapeadas para erro classificado reexecutável + sinalização de revisão; retry com backoff limitado (3 tentativas) | RF-09/EC-01 (`_reversa_sdd/sdd/policy-analysis.md#11`) | fallback de modelo (fora do escopo da spec); falha silenciosa | 🟡 |

## 4. Premissas

Nenhuma premissa derivada de `[DÚVIDA]` — as 4 aberturas (OQ-01..OQ-04) foram resolvidas na sessão de esclarecimentos de 2026-09-26 e incorporadas ao `requirements.md`.

| Premissa | Origem (`requirements.md` seção) | Risco se errada |
|----------|----------------------------------|-----------------|
| n/a | — | — |

## 5. Delta arquitetural

| Componente | Arquivo de origem no legado | Tipo de mudança | Resumo |
|------------|------------------------------|-----------------|--------|
| `src/modules/policy_analysis/domain/` | `_reversa_sdd/sdd/policy-analysis.md#8` | componente-novo | Entidades de fato/comparação, catálogo de campos, comparadores determinísticos puros |
| `src/modules/policy_analysis/application/` | `_reversa_sdd/sdd/policy-analysis.md#8` | componente-novo | Casos de uso: extract_field, get_facts, compare_policies, explain_difference, export_comparison |
| `src/modules/policy_analysis/infrastructure/` | `_reversa_sdd/sdd/policy-analysis.md#8` | componente-novo | Adaptadores: DuckDB, agente Pydantic AI/Gemini, EvidenceSource (mock + fachada Dev 1), export PDF |
| `src/modules/policy_analysis/public_api.py` | `_reversa_sdd/sdd/policy-analysis.md#8` | contrato-novo | `PolicyAnalysisFacade` — única entrada do módulo |
| `src/shared_kernel/` | `_reversa_sdd/sdd/shared-kernel-contracts.md#8` | nenhuma | Somente consumo (`EvidenceRef`, `ExtractionRequest`, `ExtractedFact`, `ProcessingStatus`, `ComparisonId`) — sem alteração (Fase 0 intocada) |
| `src/modules/document_processing/public_api` | `_reversa_sdd/sdd/document-processing.md#8` | nenhuma | Consumo da fachada `retrieve_evidence` do Dev 1 (apenas quando disponível) |
| `tests/modules/policy_analysis/` | — | componente-novo | Testes unitários/de contrato do módulo com fixtures sintéticas |

Fora desta feature (intocáveis): `src/modules/evaluation/**` (spec `_reversa_sdd/sdd/evaluation.md`), camada de aplicação/Streamlit (resumo §7), `_reversa_sdd/`.

## 6. Delta no modelo de dados

- Resumo das mudanças: banco DuckDB novo (arquivo local), 4 tabelas (`policies`, `documents`, `facts`, `comparisons`) criadas idempotentemente na primeira execução; IDs coincidentes com os do shared_kernel/Qdrant; colunas JSON para `value`, `normalized_value` e `evidence_ids`; rastro de revisão humana embutido em `facts`.
- Detalhe completo em: `_reversa_forward/dev2-001-policy-analysis-slice/data-delta.md`

## 7. Delta de contratos externos

| Contrato | Tipo | Arquivo de detalhe |
|----------|------|--------------------|
| Provedor de LLM (Gemini, via Pydantic AI) | HTTP | `_reversa_forward/dev2-001-policy-analysis-slice/interfaces/llm-provider.md` |

## 8. Plano de migração

n/a — projeto greenfield: o banco é criado do zero na primeira execução (`CREATE TABLE IF NOT EXISTS`), sem dados existentes para migrar. Rollback = apagar o arquivo do DuckDB; fixtures sintéticas recriam qualquer estado de teste.

## 9. Riscos e mitigações

| Risco | Impacto | Probabilidade | Mitigação |
|-------|---------|---------------|-----------|
| Python 3.12 ainda não instalado na máquina (apenas instalador baixado) | alto | alto | Concluir a instalação + venv + `pip install` antes de codar (ação já prevista no plano mestre); sem isso nenhum teste roda |
| Fachada `document_processing` do Dev 1 indisponível no início | alto | alto | `MockEvidenceSource` (RF-10/D-02) isola a dependência; integração real é passo final |
| Chave de API do Gemini ausente/indisponível | médio | médio | Configuração via `.env`; testes de unidade não chamam LLM (agente mockado); falha classificada e reexecutável (D-10) |
| Perda de determinismo por arredondamento em moeda/período | médio | baixo | `Decimal` em moeda, datas absolutas em período, testes de determinismo (2 execuções idênticas) |
| Custo/latência do LLM fora do alvo (30s/campo) | baixo | médio | Agente multi-campo (1 chamada por apólice), `run_id` com tokens/custo (RNF-03) |
| Nomes/tipos do shared_kernel divergirem do código real da Fase 0 | médio | baixo | Conferir `src/shared_kernel/contracts.py` antes de implementar; testes de contrato existentes (67) devem continuar verdes |

## 10. Critério de pronto

- [ ] Todas as ações do `actions.md` marcadas `[X]`
- [ ] Os 7 cenários Gherkin do `requirements.md` cobertos por testes automatizados
- [ ] Testes de determinismo: comparação repetida do mesmo par = mesmo `ComparisonId` e mesmo resultado
- [ ] Suíte `tests/contracts/` (67 testes da Fase 0) continua verde — zero regressão
- [ ] Export Markdown gerado abre standalone e contém todos os 10 campos do catálogo, inclusive ausentes
- [ ] `cross-check.md` (se executado) sem CRITICAL nem HIGH
- [ ] `regression-watch.md` gerado

## 11. Histórico de alterações

| Data | Alteração | Autor |
|------|-----------|-------|
| 2026-09-26 | Versão inicial gerada por `/reversa-plan` | reversa |