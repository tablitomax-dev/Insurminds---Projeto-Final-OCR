# Regression Watch: Documento complexo — estrutura, cláusulas e tabelas (NG-01)

> Identificador: `dev1-006-p2-documento-complexo`
> Data: `2026-10-01`

## Watch principal

Nenhum item — cenário greenfield (âncora `prd.md` + specs SDD, sem `domain.md` com regras 🟢 extraídas de legado). Os itens abaixo ganham peso de regressão quando uma futura re-extração (`/reversa`) sobre o código novo confirmar as regras como 🟢.

| ID | Origem (arquivo, seção) | Regra esperada após mudança | Tipo de verificação | Sinal de violação |
|----|-------------------------|-----------------------------|---------------------|-------------------|

## Observações (sem peso de regressão)

| ID | Origem (arquivo, seção) | Regra esperada após mudança | Tipo de verificação | Sinal de violação |
|----|-------------------------|-----------------------------|---------------------|-------------------|
| W001 | `_reversa_forward/dev1-006-p2-documento-complexo/requirements.md` RF-01 | `section_name` preenchido com o literal do marcador vigente (Cláusula/Artigo/Seção/Epígrafe); `None` antes do primeiro marcador | presença | chunk de cláusula rotulada com `section_name` nulo ou normalizado (não literal) |
| W002 | `requirements.md` RF-02 | Página analisada pelo motor de layout carrega `source_type="PP_STRUCTURE"` | presença | página analisada com outro `source_type` |
| W003 | `requirements.md` RF-03 | Tabela serializada no texto do chunk com marcador `[TABELA]` e colunas `a \| b \| c` | presença | tabela no layout sem o marcador no chunk |
| W004 | `requirements.md` RF-05/RN-05 | Ausência/falha do motor de layout degrada para texto extraído; nunca `FAILED` por causa do motor | presença | `ProcessingStatus(FAILED)` causado pelo motor de layout |
| W005 | `requirements.md` RN-07 (T-2a) | Logs/métricas do fluxo novo sem literal de seção, texto de tabela ou trecho de apólice | presença | literal de seção/tabela em mensagem de log |
| W006 | `_reversa_sdd/sdd/document-processing.md#15` | Decisão "PaddleOCR básico; PP-Structure fora" foi REVERTIDA (escopo completo, decisão do humano 2026-10-01) — futura re-extração deve registrar PP-StructureV3 como disponível | redação | spec/decisão afirmando que PP-Structure está fora do escopo sem citar a reversão |

## Histórico de re-extrações

## Arquivadas
