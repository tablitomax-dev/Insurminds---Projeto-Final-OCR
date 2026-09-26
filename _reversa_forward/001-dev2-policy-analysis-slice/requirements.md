# Requirements: Vertical slice do policy_analysis — extração de fatos, comparação determinística e export

> Identificador: `001-dev2-policy-analysis-slice`
> Data: `2026-09-26`
> Pasta da extração reversa: `_reversa_sdd/`
> Confidência: 🟢 CONFIRMADO, 🟡 INFERIDO, 🔴 LACUNA / DÚVIDA

## 1. Resumo executivo

🟡 Esta feature entrega o núcleo de análise de apólices D&O (Directors & Officers — seguro de administradores) do Desenvolvedor 2: extrai os ~10 campos críticos de uma apólice em fatos estruturados ancorados em evidência, sinaliza o que precisa de revisão humana, compara duas apólices campo a campo por regras determinísticas, explica cada diferença com citação de evidência dos dois lados e exporta o resumo para a defesa da análise. Resolve o problema do PRD §1: comparação manual, sem rastro e sem auditoria de renovação.

## 2. Contexto a partir do legado

| Fonte | Trecho relevante | Confidência |
|-------|------------------|-------------|
| `_reversa_sdd/sdd/policy-analysis.md#6.1` | RF-01..RF-09 do componente: extração por campo, catálogo de `field_code`, fila de revisão, persistência, comparação determinística, explicação e export | 🟡 |
| `_reversa_sdd/sdd/policy-analysis.md#15` | Decision Log: comparação 100% por regras (LLM só extrai/explica); persistência com IDs compartilhados; revisão humana como fluxo de 1ª classe | 🟡 |
| `_reversa_sdd/sdd/policy-analysis.md#8` | Fachada pública `PolicyAnalysisFacade` (extract_field, get_facts, compare_policies, explain_difference, export_comparison) | 🟡 |
| `_reversa_sdd/sdd/policy-analysis.md#11` | Edge cases EC-01..EC-07 (LLM indisponível, evidências conflitantes, campo ausente, valor não normalizável, persistência indisponível, comparação repetida, `field_code` fora do catálogo) | 🟡 |
| `_reversa_sdd/sdd/shared-kernel-contracts.md#8` | Contratos de trânsito `EvidenceRef`, `ExtractionRequest`, `ExtractedFact`, `ProcessingStatus`, `ComparisonId` já implementados na Fase 0 | 🟢 |
| `_reversa_sdd/sdd/evaluation.md#4` | Non-Goals: avaliação de qualidade (LLM-as-judge, baterias) fica fora desta feature | 🟡 |
| `_reversa_sdd/prd.md#1` | Problema: comparação manual sem rastro verificável | 🟡 |
| `_reversa_sdd/prd.md#3` | Métrica: 1 comparação ponta a ponta com 100% de evidência anexada | 🟡 |
| `_reversa_sdd/prd.md#6` | Restrições: dados de apólice trafegam para o provedor de LLM por decisão explícita; comparação não pode depender de LLM | 🟡 |
| `_reversa_sdd/prd.md#2` | Persona: analista de cotação D&O | 🟡 |

## 3. Personas e cenários de uso

| Persona | Objetivo | Cenário-chave |
|---------|----------|---------------|
| 🟡 Analista de cotação D&O | Comparar duas apólices com rastro verificável, sem reler os PDFs inteiros | Analista extrai os fatos das duas apólices, revisa as sinalizações, dispara a comparação, lê a explicação com evidência e exporta o resumo para defender a análise |
| 🟡 Desenvolvedor 1 (pbena) | Integrar o fluxo documental à análise sem tocar no interno do módulo | Integração consome apenas as fachadas públicas de `document_processing` e `policy_analysis` |
| 🟡 Desenvolvedor 2 (dono da feature) | Validar o núcleo de análise antes da integração completa | Desenvolve com evidências de teste (mockadas) e depois troca pela evidência real do retrieval sem mudar o contrato |

## 4. Regras de negócio novas ou alteradas

1. **RN-01:** O LLM (modelo de linguagem) extrai e explica fatos; a comparação entre apólices é 100% determinística por regras (maior/menor/igual/ausente) e jamais usa LLM. 🟡
   - Origem no legado: `_reversa_sdd/sdd/policy-analysis.md#15` (Decision Log, 1ª decisão)
   - Tipo: nova
2. **RN-02:** Todo fato extraído com status FOUND deve ancorar-se exclusivamente em `evidence_ids` vindos das evidências recebidas; o sistema nunca aceita citação de evidência que não exista na requisição. 🟡
   - Origem no legado: `_reversa_sdd/sdd/policy-analysis.md#6.1` (RF-03)
   - Tipo: nova
3. **RN-03:** Fatos incertos (`AMBIGUOUS`/`NEEDS_REVIEW`) entram em fila de revisão humana com a evidência anexa; a decisão do analista é registrada e vira fato definitivo ou confirmação. 🟡
   - Origem no legado: `_reversa_sdd/sdd/policy-analysis.md#15` (3ª decisão) e `#6.1` (RF-04)
   - Tipo: nova
4. **RN-04:** Campo ausente em uma das apólices entra na comparação como "ausente" (diferença por omissão), nunca como erro. 🟡
   - Origem no legado: `_reversa_sdd/sdd/policy-analysis.md#11` (EC-03)
   - Tipo: nova
5. **RN-05:** `field_code` fora do catálogo fechado é rejeitado na fronteira do módulo; nada é extraído. 🟡
   - Origem no legado: `_reversa_sdd/sdd/policy-analysis.md#11` (EC-07) e `#6.1` (RF-02)
   - Tipo: nova
6. **RN-06:** A comparação do mesmo par de apólices é idempotente: mesma entrada produz o mesmo `ComparisonId` e o mesmo resultado, sem duplicar registros. 🟡
   - Origem no legado: `_reversa_sdd/sdd/policy-analysis.md#11` (EC-06) e `#7` (RNF-01)
   - Tipo: nova

## 5. Requisitos Funcionais

| ID | Requisito | Prioridade | Critério de Aceite | Confidência |
|----|-----------|------------|--------------------|-------------|
| RF-01 | O sistema deve obter evidências exclusivamente pela fachada pública do módulo documental (`retrieve_evidence`), sem importar internos do módulo documental. | Must | Verificação de arquitetura: zero imports de internos do módulo documental em `policy_analysis`; somente a fachada. | 🟡 |
| RF-02 | O sistema deve manter o catálogo fechado dos 10 `field_code` do vertical slice — `limite_agregado`, `limite_por_sinistro`, `franquia`, `vigencia`, `prazo_notificacao_sinistro`, `extensao_territorial`, `exclusoes_chave`, `limite_defesa_custos`, `retroatividade`, `indice_reajuste` — com semântica e normalização documentadas por campo. | Must | O catálogo é a única fonte de `field_code`; requisição com campo fora do catálogo é rejeitada (RN-05). | 🟢 |
| RF-03 | O sistema deve extrair os campos do catálogo com um agente multi-campo (uma chamada de LLM por apólice) que recebe evidências + versão de schema e devolve um fato estruturado validado por campo, com confiança e `evidence_ids` dos trechos usados. | Must | Toda saída passa na validação do contrato; nenhum `evidence_id` inexistente na requisição (RN-02). | 🟡 |
| RF-04 | O sistema deve sinalizar revisão humana para fatos `AMBIGUOUS`/`NEEDS_REVIEW` (ou `requires_human_review=true`), exibindo a evidência anexa e registrando a decisão do analista. | Must | Toda sinalização exibe evidência; decisão registrada gera fato novo ou confirmação (RN-03). | 🟡 |
| RF-05 | O sistema deve persistir apólices, documentos, fatos e comparações em banco analítico local com os mesmos identificadores do shared_kernel, usando `ProcessingStatus` para coordenar com o workflow. | Must | Fato consultado no banco tem os mesmos IDs dos chunks indexados (0 divergências). | 🟡 |
| RF-06 | O sistema deve comparar 2 apólices campo a campo por regras determinísticas por tipo de valor: numérico (maior/menor/igual); moeda (normalizada para BRL pela data da apólice); período (comparado por datas e duração); texto livre (igual/divergente após normalização, com explicação detalhando a divergência — semântica fica com o analista); ausente (sinalizado como diferença por omissão); retornando o resultado por campo. | Must | 2 fixtures idênticas = 100% "igual"; execuções repetidas do mesmo par produzem o mesmo resultado (RN-01, RN-06). | 🟢 |
| RF-07 | O sistema deve gerar, para cada diferença, uma explicação em linguagem de analista que cita a evidência (página/trecho) de ambas as apólices. | Must | Explicação sem evidência citada é rejeitada; citações resolvem para os `evidence_ids` dos fatos comparados. | 🟡 |
| RF-08 | O sistema deve emitir `ComparisonId` único por comparação e exportar o resumo (por campo: valores, direção da diferença, evidências, explicação) em documento PDF standalone que abre sem o sistema. | Must | O export contém todos os campos do catálogo, inclusive ausentes, e não depende do sistema para ser lido. | 🟢 |
| RF-09 | O sistema deve validar toda saída de LLM contra o schema do contrato antes de aceitar; saída inválida vira falha classificada (reexecutável) e sinalização de revisão, nunca fato. Indisponibilidade do provedor (timeout/erro temporário) segue retentativa com backoff e, persistindo, sinalização de revisão. | Must | Resposta fora do schema nunca é persistida como fato; falha registrada com causa classificada e reexecutável. | 🟡 |
| RF-10 | O sistema deve operar com evidências de teste (mockadas) e com evidências reais do retrieval, sem mudança de contrato, para permitir desenvolver antes da integração do módulo documental. | Must | Mesma extração roda com as duas fontes; apenas a origem da evidência muda. | 🟡 |

## 6. Requisitos Não Funcionais

| Tipo | Requisito | Evidência ou justificativa | Confidência |
|------|-----------|----------------------------|-------------|
| Determinismo | Mesma entrada de comparação → mesma saída, em 100% das execuções; sem aleatoriedade no caminho de comparação | `_reversa_sdd/sdd/policy-analysis.md#7` (RNF-01) | 🟡 |
| Rastreabilidade | Cada fato aponta para evidências; cada comparação carrega `ComparisonId` e fato por campo | `_reversa_sdd/sdd/policy-analysis.md#7` (RNF-02) | 🟡 |
| Observabilidade | Tokens/custo por execução registrados via `run_id` (mínimo desta versão) | `_reversa_sdd/sdd/policy-analysis.md#7` (RNF-03) | 🟡 |
| Desempenho | Extração de até 30s por campo em cenário single-user | `_reversa_sdd/sdd/policy-analysis.md#7` (RNF-04) | 🟡 |
| Isolamento | Camadas de domínio/aplicação não citam banco, OCR, fila ou interface gráfica; integração só por fachada pública | `_reversa_sdd/sdd/policy-analysis.md#7` (RNF-05) | 🟡 |
| Privacidade | Nenhum texto integral de apólice em logs; export traz apenas citações mínimas para a defesa | `_reversa_sdd/sdd/policy-analysis.md#12` | 🟡 |

## 7. Critérios de Aceitação

```gherkin
Cenário: Extração e comparação com export da defesa
  Dado duas apólices com evidências de teste disponíveis (RF-10)
  Quando o analista extrai os campos do catálogo das duas apólices
  Então cada campo vira um fato validado ancorado em evidence_ids reais (RF-03, RN-02)
  E quando o analista dispara a comparação do par
  Então o sistema devolve o resultado determinístico por campo com ComparisonId (RF-06, RN-06)
  E a explicação de cada diferença cita evidência das duas apólices (RF-07)
  E o export standalone lista todos os campos do catálogo, inclusive ausentes (RF-08)

Cenário: Revisão humana de fato ambíguo
  Dado um campo cujos trechos sustentam valores distintos
  Quando o agente extrai esse campo
  Então o fato fica AMBIGUOUS com requires_human_review e evidência anexa (RF-04, RN-03)
  E a comparação daquele campo aguarda a decisão do analista

Cenário: Campo fora do catálogo é rejeitado
  Dado o catálogo fechado de field_code (RF-02)
  Quando o sistema recebe uma requisição de extração com field_code desconhecido
  Então a requisição é rejeitada na fronteira e nada é extraído (RN-05)

Cenário: Campo ausente não vira erro
  Dado uma apólice sem o campo "franquia" nos documentos
  Quando o agente extrai esse campo
  Então o fato fica NOT_FOUND sem evidência (RN-04)
  E a comparação marca o campo como "ausente" (diferença por omissão), nunca como erro

Cenário: Saída de LLM fora do schema não vira fato
  Dado uma resposta do provedor de LLM que não valida no contrato
  Quando o sistema processa a resposta
  Então a resposta é registrada como falha classificada e reexecutável (RF-09)
  E nenhum fato é persistido a partir dela

Cenário: Fatos persistidos com os mesmos identificadores do índice
  Dado fatos extraídos já persistidos no banco analítico local
  Quando o sistema consulta esses fatos
  Então os identificadores coincidem com os dos chunks indexados, sem divergência (RF-05)

Cenário: Extração consome apenas a fachada pública do módulo documental
  Dado a verificação de arquitetura do módulo de análise
  Quando ela inspeciona as importações do módulo de análise
  Então não existe import de internos do módulo documental, apenas da fachada pública (RF-01)
```

## 8. Prioridade MoSCoW

| Item | MoSCoW | Justificativa |
|------|--------|---------------|
| RF-01 (evidência só via fachada) | Must | Fronteira de arquitetura entre os dois desenvolvedores; quebra integração se violada |
| RF-02 (catálogo de campos) | Must | Sem catálogo não há extração nem comparação; é a base do vertical slice |
| RF-03 (extração validada por campo) | Must | Núcleo da feature; alimenta tudo o resto |
| RF-04 (revisão humana) | Must | Persona exige "zerar omissões"; incerteza é fluxo de 1ª classe (PRD §2) |
| RF-05 (persistência com IDs compartilhados) | Must | Consistência banco↔índice é critério de aceite do resumo §14 |
| RF-06 (comparação determinística) | Must | Entregável central da análise de apólices |
| RF-07 (explicação com evidência) | Must | Métrica do PRD §3: 100% de evidência anexada |
| RF-08 (export standalone) | Must | Defesa da análise é o objetivo final da jornada da persona |
| RF-09 (validação de saída de LLM) | Must | Garante que fato nunca nasce de resposta inválida |
| RF-10 (evidências mockadas) | Must | Desbloqueia o Dev 2 em paralelo ao Dev 1 (plano mestre §papéis) |
| RNF de determinismo e rastreabilidade | Must | Restrições duras do projeto (PRD §6) |
| RNF de observabilidade (custo por run) | Should | Desejável para controle de custo, não bloqueia o slice |
| RNF de desempenho (30s/campo) | Should | Premissa single-user; não é requisito duro do slice |

## 9. Esclarecimentos

### Sessão 2026-09-26

- **Q:** [OQ-01] Quais campos entram no catálogo fechado dos ~10 `field_code` do vertical slice?
  **R:** Catálogo completo de 10 campos: limite agregado, limite por sinistro, franquia/deducível, vigência (início/fim), prazo de notificação de sinistro, extensão territorial, exclusões-chave, limite de defesa de custos, retroatividade (claims-made), índice de reajuste/correção.
- **Q:** [OQ-03] Qual tabela inicial de regras de comparação por tipo de valor?
  **R:** Híbrida: numérico, moeda e período seguem regra determinística normalizada (moeda para BRL pela data da apólice; período por datas e duração); texto livre compara igual/divergente após normalização e, havendo divergência, a explicação detalha — a semântica fica com o analista.
- **Q:** [OQ-04] Qual formato do export da defesa da análise?
  **R:** Documento PDF standalone.
- **Q:** [OQ-02] Qual estratégia de prompts dos agentes de extração?
  **R:** Agente multi-campo: uma única chamada de LLM por apólice extrai todos os campos do catálogo.

## 10. Lacunas

Nenhuma lacuna pendente. As aberturas OQ-01 (catálogo de campos), OQ-02 (estratégia de agente), OQ-03 (regras de comparação) e OQ-04 (formato do export) foram resolvidas na sessão de esclarecimentos de 2026-09-26.

## 11. Histórico de alterações

| Data | Alteração | Autor |
|------|-----------|-------|
| 2026-09-26 | Versão inicial gerada por `/reversa-requirements` | reversa |
| 2026-09-26 | Sessão `/reversa-clarify`: OQ-01..OQ-04 resolvidas (catálogo de 10 campos, regras híbridas de comparação, export em PDF, agente multi-campo) | reversa |