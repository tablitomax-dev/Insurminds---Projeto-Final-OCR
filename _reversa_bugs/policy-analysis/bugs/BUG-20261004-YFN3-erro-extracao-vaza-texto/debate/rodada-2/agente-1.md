---
protocol_version: 1
debate_id: BUG-20261004-YFN3-r2
bug_id: BUG-20261004-YFN3
role: solver
solver_id: agente-1
engine: local
round: 2
status: ok
started_at: 2026-10-04
finished_at: 2026-10-04
---

## Estratégia de correção
Proposta final, síntese da rodada 1 (as três rotas convergiram; a disputa restante é de profundidade de teste e de limpeza da cadeia):
1. Mensagem do `ClassifiedError` em `src/modules/policy_analysis/application/extraction.py` L135-139: entra só o que T-2a permite, sai todo eco de valor. Fica: `code` `LLM_SCHEMA_INVALID`, `field_code`, `type(exc).__name__` e `len(exc.errors())`, ex.: `f"saída do LLM fora do contrato em {req.field_code}: {type(exc).__name__}, {len(exc.errors())} problema(s) de schema"`. Sai: `{exc}`, `str(exc)`, `repr(exc)`, `exc.errors()[...]["msg"|"ctx"|"input"|"url"]` e o dict completo (rota descartada em dev2-003). `retriable=True` intacto.
2. `raise ... from exc` vira `raise ... from None`: o `ValidationError` cru (que ecoa o input em `str`/`repr`/`errors()`) deixa de ser renderizado como causa em traceback/log (`__suppress_context__`); reversível em um token. Rejeito manter `from exc` para "diagnóstico" e rejeito a variante de levantar fora do bloco `except` (agente-3): zerar o `__context__` residual, alcançável só por introspecção, custa reestruturação do try/except que a rubrica de menor mudança não autoriza; fica como plano B documentado.
3. Escopo cirúrgico: somente este `except`. `errors.py`, `llm_agent.py`, `document_processing_source.py`, `ui/errors.py` e testes existentes intactos; mudança de duas linhas, `ClassifiedError`, `code`, `retriable` e o shape de `to_dict()` preservados.

## Causa raiz proposta
`f"...: {exc}"` interpola `str(ValidationError)` do Pydantic, que ecoa o `input` da validação (valor extraído da apólice); o `from exc` mantém esse erro cru vivo em `__cause__`, segunda via de vazamento em traceback/log. O `except` não aplica o padrão T-2a e descumpre a rota descartada em dev2-003: derrapagem de implementação, não de spec (RF-09 segue cumprida, nada vira fato). Correção da minha imprecisão da rodada 1: `to_processing_status` (`errors.py` L41) interpola `{exc}` e só fica seguro por herança da mensagem já sanitizada, não por seguir T-2a por conta própria.

## Teste
Reprodução/anti-vazamento novo em `tests/modules/policy_analysis/test_extraction_agent.py`, padrão `APOLICE_MARKER` de `test_metrics.py` (L27, L261-277): StubAgent devolve `confidence="TEXTO-CONFIDENCIAL-APOLICE-XYZ"` (viola `Field(ge=0, le=1)` de `shared_kernel/contracts.py` L140) e `model_validate` rejeita com o marcador como `input`. Com `pytest.raises(ClassifiedError)`:
- contrato: `code == "LLM_SCHEMA_INVALID"`, `retriable is True`, mensagem traz `field_code`, `ValidationError` e a contagem de problemas;
- black-box (prova de vazamento): marcador ausente de `str(exc)`, `repr(exc)`, `exc.to_dict()["message"]`, `to_processing_status("DOC-1", exc).message` e `"".join(traceback.format_exception(exc))` (superfície que hoje renderiza a causa);
- mecânica (único assert white-box, custo zero): `exc.__cause__ is None` e `exc.__suppress_context__ is True`, que documenta a decisão `from None` e trava regressão que reverta para `from exc` mantendo a mensagem limpa.
Vermelho antes do fix, verde depois. Regressão: `tests/modules/policy_analysis` (inclui `test_saida_fora_do_schema_nunca_vira_fato` e o `BadAgent` de `test_e2e_flow.py` L47), `tests/contracts/test_errors.py`, `tests/ui/test_error_sanitization.py` (asserta só `LLM_SCHEMA_INVALID` no texto, L57), `tests/e2e/test_governance_journey.py` (L114-115 monta a própria mensagem em fake), `tests/modules/document_processing`. Busca reconfirmada em 2026-10-04: nenhum teste asserta o texto exato da mensagem de `extraction.py`.

## Impacto sobre a spec
Nenhuma mudança de spec: cumpre o já normatizado (plano-acao-dev2 T-2a; policy-analysis §12 "nenhum texto integral em logs" e §6.1 RF-09; dev2-003 §6.1; rota descartada em `actions.md`). Contrato público estável; `resolution_kind`: fix de código, sem addenda. Concordo com agente-3: promover `related-to` BUG-20261004-ODCS no fechamento é ruído de processo, fica para decisão separada se auditoria futura confirmar o vínculo.

## Riscos e efeitos colaterais
- Diagnóstico mais sintético (perde a constraint exata): compensado por tipo + campo + contagem, exigido pela rubrica; reprodução local via teste determinístico com marcador.
- `from None` reduz contexto em depuração local. Residual consciente: `__context__` segue apontando para o `ValidationError` cru em introspecção, sem superfície de renderização no repo (zero `logger.exception`, zero uso de `__context__`, único `__cause__` em `tests/integration/test_pipeline_offline.py` L92, alheio a esta exceção).
- Consumidores: `to_processing_status` herda a mensagem limpa, UI ecoa só `.code`, nenhum teste asserta o texto exato.
- Ecos residuais fora do caminho do bug (`llm_agent.py` L267 e `document_processing_source.py` L30 interpolam `str(exc)` em mensagens de infra): follow-up próprio, fora do change_set, para preservar a menor mudança coerente.

## Evidências
- `extraction.py` L135-139 (`{exc}` + `from exc`) e `evidence/extracao-py-l135-140.txt`; `evidence/rota-descartada-dev2-003.txt`.
- `errors.py` L41 (interpola `{exc}`) e `src/ui/errors.py` (ecoa só `.code`): superfícies de consumo.
- Padrão T-2a: `_cause` (`document_processing/application/service.py` L285, "NUNCA `str(exc)`") e `_with_retries` (`policy_analysis/infrastructure/llm_agent.py`, só tipo + contagem).
- `shared_kernel/contracts.py` L140 (`confidence: float = Field(ge=0, le=1)`), `test_metrics.py` L27/L261-277 (padrão anti-vazamento) e greps de 2026-10-04 em `src` e `tests`.

## Confiança
alta. Vetores (mensagem e cadeia), consumidores, padrão canônico e plano de teste reconfirmados no código desta rodada; correção de duas linhas com teste anti-vazamento específico, convergente com agente-2 e agente-3.

## Crítica às demais propostas
- agente-2: correta nas duas vias (mensagem tipo + campo + contagem e `from None`) e certeira ao apontar que `errors.py` é ponto único de fuga por herança da mensagem (minha imprecisão da rodada 1, corrigida acima). Fraquezas: recusar qualquer assert de mecanismo deixa a decisão `from None` sem guarda de regressão (adotei o par `__cause__`/`__suppress_context__` como white-box único e explícito, com o traceback formatado como prova black-box principal); promover BUG-20261004-ODCS no fechamento é ruído de processo fora do escopo do fix.
- agente-3: a mais completa em superfícies de asserção (str/repr/to_dict/to_processing_status/traceback) e correta na varredura dos ecos residuais; aceito as correções que apontou em minhas rodadas anteriores (contradição `ui/errors.py` seguro vs `errors.py` que interpola; `llm_agent.py`/`document_processing_source.py` não são "seguras", interpolam `str(exc)`). Fraquezas: a variante de levantar fora do bloco `except` para zerar `__context__` excede a menor mudança coerente para ganho não observável, e ela própria admite que a renderização fica segura com `from None`; mantê-la só como plano B.
- Fechamento: as três propostas concordam no fix de duas linhas. A versão final acima fica com a mensagem minimalista de agente-2/agente-3, o `from None` com decisão explícita sobre `__context__` (agente-3), a bateria de assertivas de agente-3 enriquecida com `__suppress_context__` e a disciplina de escopo comum.
