# PRD: Insurminds - Desafio Final (Plataforma de Comparação de Apólices D&O)

> Selo 🟡 PLANEJADO. Documento gerado a partir de ideation + personas.

**Versão:** 1.0
**Data:** 2026-09-25T01:00:00-03:00
**Autor:** reversa-drafter
**Status:** rascunho

---

## 1. Problema

🟡 A comparação de apólices de seguro D&O é hoje **manual, lenta e sem rastreabilidade**. O problema é composto e atinge três frentes ao mesmo tempo: (1) comparação manual entre PDFs longos (limites, coberturas, exclusões, endossos) sem evidência anexada, com risco de uma exclusão ou limite inferior passar despercebido; (2) renovações nunca auditadas contra a versão anterior da apólice; (3) formatos de apólice distintos por seguradora, sem padrão de estrutura para automatizar. Quem processa as apólices não consegue defender a análise com evidência nem ganhar tempo — lê PDFs inteiros repetidamente a cada cotação ou renovação.

### Quem sente

🟡 Derivado de personas.md (referência completa em [`personas.md`](./personas.md)):

- **Analista de seguros/corretora** — na mesa de cotação/renovação, ao montar ou renovar um placement D&O com prazo curto e necessidade de resposta ao cliente: sente a comparação manual (dor imediata) e a falta de rastreabilidade para defender a recomendação (dor de defesa perante cliente e seguradora).
- A equipe que renova apólices, quando precisa auditar o que mudou de uma versão para outra e não tem como fazer isso com evidência.

---

## 2. Personas-alvo

🟡 Referência completa em [`personas.md`](./personas.md). Resumo:

- **Analista de cotação D&O**: 🟡 Analista de seguros de mesa de cotação/renovação de corretora; intermediário em seguros, não-técnico. Dor principal: comparação manual, lenta e sem rastreabilidade; renovações não auditadas; formatos distintos impedem padronização. Objetivo final (os 3 combinados): defender a recomendação com evidência verificável, fechar placements mais rápido e zerar o risco de omissão.

---

## 3. Métricas de sucesso

🟡 Métricas copiadas do ideation.md, com unidade e alvo explícitos. Sem benchmark externo (nenhuma alternativa conhecida), as métricas são definidas internamente.

| Métrica | Unidade | Alvo | Prazo |
|---|---|---|---|
| 🟡 Comparativeção ponta a ponta entre 2 apólices reais | nº de comparações E2E concluídas | 1 (mínimo), sem leitura manual dos PDFs | 3 meses |
| 🟡 Campos críticos extraídos por apólice (vertical slice) | nº de campos | ~10 campos (limites, exclusões, endossos, condições) | 3 meses |
| 🟡 Evidência anexada aos fatos extraídos | % de fatos com `EvidenceRef` completo | 100% | 3 meses |
| 🟡 Revisão humana dos fatos sinalizados | % dos fatos sinalizados revisados | 100% | 3 meses |
| 🟡 Determinismo da comparação | comparações com divergência definida por regras | 100% (LLM jamais compara valores) | contínuo |

---

## 4. Escopo (in)

🟡 Derivado do ideation.md + jornada da persona (7 passos) + vertical slice mínimo (resumo executivo §13):

- 🟡 Upload de PDFs de apólices (nativos ou escaneados) a comparar.
- 🟡 Pipeline documental mínimo: PyMuPDF + PaddleOCR básico, chunking, embeddings Gemini, índice Qdrant local (Docker), retrieval com entrega de evidências.
- 🟡 Status de processamento por apólice (OCR, indexação) visível, com falhas classificadas e reexecução.
- 🟡 Extração estruturada de ~10 campos críticos (limites, exclusões, endossos, condições) com Pydantic AI, validada por schemas Pydantic.
- 🟡 Consulta dos fatos extraídos por campo.
- 🟡 Sinalização de fatos para revisão humana, com confirmação/correção registrada.
- 🟡 Comparação determinística campo a campo entre 2 apólices (regras explícitas: maior/menor/igual/ausente) — LLM extrai e explica, jamais compara.
- 🟡 Explicação das diferenças com evidência anexada (`EvidenceRef`: apólice, documento, página, trecho/seção/cláusula, chunk, score quando aplicável).
- 🟡 Exportação do resumo da comparação para defesa da análise.
- 🟡 Interface simples (Streamlit) que cobre a jornada de 7 passos.
- 🟡 Contratos compartilhados definidos antes do desenvolvimento: `EvidenceRef`, IDs, `RetrievalQuery/Result`, `ExtractedFact`, `ProcessingStatus`, `ChunkMetadata` (shared_kernel), com acesso entre módulos apenas via `public_api.py`.

---

## 5. Não-objetivos (out)

🟡 Derivado do resumo executivo §13 (fase posterior) e §14 (simplicidade) + decisões da sessão:

- 🟡 PP-StructureV3 (análise de layout avançada) — fase posterior ao vertical slice.
- 🟡 Processamento de tabelas — fase posterior.
- 🟡 Múltiplos agentes de LLM (orquestração complexa) — fase posterior; MVP usa agentes Pydantic AI simples.
- 🟡 Fallback de modelos (provedor único: Gemini) — fase posterior.
- 🟡 Scoring avançado de recuperação — fase posterior; MVP usa score de retrieval básico.
- 🟡 Explicação sofisticada/relatórios elaborados — fase posterior; MVP exporta resumo essencial.
- 🟡 Avaliação completa do pipeline (baterias de avaliação, LLM-as-judge) — fase posterior.
- 🟡 Microsserviços, brokers externos, qualquer arquitetura distribuída — excluído por princípio (monólito modular).
- 🟡 Compação de valores por LLM ou similaridade vetorial — excluído por decisão: comparação é determinística.
- 🟡 Multi-usuário, autenticação/autorização — fora do MVP (single-user).

---

## 6. Restrições

🟡 Técnicas registradas nesta sessão e nas decisões do brief; prazo/compliance/orçamento das perguntas de cobertura (respondidas).

| Tipo | Descrição |
|---|---|
| 🟡 Técnica | Python; monólito modular; Pydantic AI (orquestração de agentes); LLM Gemini como provedor único (LLM + embeddings); Qdrant local via Docker; DuckDB; Streamlit; LlamaIndex; PyMuPDF; PaddleOCR. Princípios KISS/YAGNI/SDD. Acesso entre módulos apenas por `public_api.py`; mudança de contrato compartilhado exige revisão dos dois desenvolvedores; zonas de integração (EvidenceRef, metadados de chunks, evidências, workflow, ModelGateway/observabilidade) exigem aviso antes de tocar. |
| 🟡 Prazo | Alvo: 1 comparação E2E entre 2 apólices reais em 3 meses (métrica de sucesso). Sem deadline formal adicional; o escopo é guiado pelo vertical slice mínimo antes das sofisticações. |
| 🟡 Compliance | Apólices são dados confidenciais de cliente. O envio de trechos de apólice a serviço externo (API Gemini) é uma **decisão explícita registrada**, tomada consciente de que o texto sai do ambiente local — alinhada ao princípio "dados sensíveis não são enviados a serviços externos sem decisão explícita" (resumo §14). Sem requisito LGPD formal adicionado ao PRD (decisão de cobertura, resposta do usuário). |
| 🟡 Orçamento | Sem cap formal. Viés de custo baixo: pipeline pesado (OCR, embeddings, vetor) roda localmente via Docker; API Gemini paga por uso, single-user. |

---

## 7. Dependências externas

🟡 Serviços, APIs e infraestrutura externos:

- 🟡 **API Google Gemini** — serviço externo para LLM (extração, explicação, revisão) e embeddings. Decisão explícita e registrada (ver Compliance em §6).
- 🟡 **Docker** — infraestrutura local obrigatória para rodar Qdrant.
- 🟡 **Bibliotecas open source** (PyMuPDF, PaddleOCR, LlamaIndex, Pydantic AI, Streamlit, DuckDB) — sem serviço gerenciado externo.
- 🟡 Nenhuma API externa de dados de mercado ou fonte de apólices; os PDFs são fornecidos pelo usuário da plataforma.

---

## 8. Riscos

🟡 Derivado de: (a) premissas a validar do ideation.md, (b) jornada da persona, (c) restrições e da crítica da divisão (resumo §13).

| Risco | Impacto | Probabilidade | Mitigação proposta |
|---|---|---|---|
| 🟡 PDFs reais não extraíveis (OCR com confiança insuficiente) | Alto | Média | Validar a premissa cedo com PDFs reais das seguradoras; sinalização para revisão humana; falhas classificadas e reexecutáveis. |
| 🟡 Custo/latência de Gemini + OCR inviáveis para uso single-user | Médio | Média | Medir custo/latência desde o vertical slice; cache de embeddings; pipeline local (Docker) para o processamento pesado. |
| 🟡 Formatos distintos por seguradora impedirem extração genérica dos ~10 campos | Alto | Alta | Campo a campo com schema Pydantic versionado; revisão humana nos casos duvidosos; escopo reduzido a ~10 campos críticos no MVP. |
| 🟡 LLM inventar valores inexistentes na apólice (alucinação) | Alto | Média | Compação determinística por regras; LLM só extrai/explica; todo fato exige `EvidenceRef` apontando página/trecho/chunk verificável. |
| 🟡 Desbalanço entre Dev 1 (infra sofisticada) e Dev 2 (valor de negócio) | Médio | Média | Vertical slice mínimo E2E primeiro (PDF → OCR → chunks → Qdrant → retrieval → 1 campo → 1 comparação → tela), sofisticações depois. |
| 🟡 Quebra de contratos compartilhados entre módulos (zonas de integração) | Alto | Média | Contratos definidos antes do desenvolvimento; mudança de contrato exige revisão dos dois devs; aviso antes de tocar zona de integração; qualidade de gates do resumo §14 (outputs validados por Pydantic, IDs consistentes DuckDB↔Qdrant, evidências com página e trecho, versão de contratos/prompts). |

---

## 9. Critérios de aceite (alto nível)

🟡 Um critério por passo da jornada da persona principal (Analista de cotação D&O), formato Dado/Quando/Então:

- 🟡 **Dado** 2 PDFs de apólices D&O de formatos distintos, **Quando** o analista faz upload, **Então** os documentos entram no pipeline e o status de processamento por apólice fica visível, com falhas classificadas.
- 🟡 **Dado** o processamento concluído (OCR + indexação + extração), **Quando** o analista consulta os ~10 campos críticos, **Então** cada fato exibido tem `EvidenceRef` completo (apólice, documento, página, trecho/seção/cláusula, chunk, score quando aplicável).
- 🟡 **Dado** fatos sinalizados para revisão humana, **Quando** o analista revisa, **Então** ele confirma ou corrige o fato e o resultado da revisão fica registrado.
- 🟡 **Dado** 2 apólices processadas, **Quando** o analista dispara a comparação, **Então** o resultado é determinístico campo a campo (valores comparados por regras, nunca pelo LLM), incluindo ausências.
- 🟡 **Dado** uma diferença na comparação, **Quando** o analista pede a explicação, **Então** vê uma explicação gerada com evidência anexada (página/trecho de cada apólice).
- 🟡 **Dado** a comparação concluída, **Quando** o analista exporta, **Então** obtém um resumo exportado capaz de defender a análise perante cliente e seguradora, sem precisar reler os PDFs manualmente.

---

## Pendências de cobertura

🟡 Nenhuma seção ficou `[INDEFINIDO]`: as 9 seções foram cobertas por ideation.md, personas.md, resumo executivo e pelas 2 perguntas de cobertura (compliance: sigilo + decisão explícita; prazo/orçamento: 3 meses + viés custo baixo).

🟡 Observação (não é pendência de cobertura, é premissa a validar em campo): "PDFs são extraíveis" e "custo/latência viáveis" seguem como riscos R1 e R2, a confirmar com PDFs reais na primeira execução do vertical slice.

---

Gerado por reversa-drafter em 2026-09-25T01:00:00-03:00
Fontes: ideation.md, personas.md
