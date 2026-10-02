# Decisions: Documento complexo — estrutura, cláusulas e tabelas (NG-01)

> Identificador: `dev1-006-p2-documento-complexo`
> Data: `2026-10-01`
> Registro de decisões de implementação (A-10): semântica adotada, escolhas descartadas e porquê.

| ID | Decisão | Escolhas descartadas | Porquê |
|----|---------|----------------------|--------|
| E-01 | Atribuição de seção por peça de chunk: a peça herda a seção vigente no início dela; marcador no início da peça (após espaço em branco) já vale para a própria peça; marcadores internos valem para as peças seguintes | atribuição char-precisa por offset global | `chunk_text` faz strip/slice e os offsets globais se perdem; a regra por peça é determinística, testável e estável para o consumidor (Dev 2) |
| E-02 | Headings do layout **não** criam seção — só a família fechada Cláusula/Artigo/Seção/Epígrafe detectada no texto | headings como marcadores de seção | o clarify descartou a "heurística ampla"; heading literal solto criaria nomes fora da família combinada (RN-02). Heading da família (ex.: "CLÁUSULA 5ª...") é capturado pelo detector comum quando entra no texto |
| E-03 | `LayoutRegion`/`LayoutError`/`LayoutEngine` moram em `application/ports.py` | dataclass dentro do adapter de infraestrutura | o serviço/domínio não devem importar infraestrutura; segue o padrão dos erros de porta (`EmbeddingError`/`IndexingError`) — correção refletida no `data-delta.md` |
| E-04 | Tabela: adapter normaliza HTML do SDK para TSV; o domínio serializa como `célula | célula` com o marcador `[TABELA]` | serializar HTML direto no chunk; chunk dedicado por tabela | texto determinístico e legível para embedding/consumidor; chunk dedicado mudaria o corte (RN-06) |
| E-05 | `_layout_page_text` degrada com `except Exception` (não só `LayoutError`) | capturar apenas `LayoutError` | RN-05: motor de terceiros falha de formas imprevisíveis; a feature nunca derruba o processamento — a falha do motor não é erro do documento |
| E-06 | Normalização defensiva do SDK em três formatos (região normalizada, resumo `headings/texts/tables_html`, formato PP-StructureV3 `table_res_list`+`overall_ocr_res`) | travar um único formato de resposta | a resposta do PP-StructureV3 varia entre versões e o ambiente local não tem Paddle para validar; o opt-in `-m integration` valida contra o SDK real |
| E-07 | A sobreposição de chunks (`CHUNK_OVERLAP=100`) pode cortar uma tabela entre chunks — comportamento aceito | ajustar overlap em tabela; não sobrepor tabelas | o conteúdo continua recuperável (ambos os chunks carregam o pedaço); mudar o corte violaria a RN-06 |
