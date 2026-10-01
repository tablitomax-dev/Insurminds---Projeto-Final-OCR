# Handoff Dev 1 → Dev 2 — débitos de revisão/UI no quadrado `policy_analysis` (2026-09-30)

> **Autor:** Dev 1 (pbena + assistente) · **Destinatário:** Dev 2 (leitura do assistente de IA)
> **Branch:** `fix/pendencias-metodo-debitos-review` (base: `main` = PR #9 mesclado)
> **Autorização do humano:** "Nós, com handoff §5.6" — Dev 1 atuou no quadrado do Dev 2 por decisão explícita, para fechar débitos observados na auditoria do merge (PR #8).
> **Gate `T-1`:** verde 3× consecutivas — `ruff` All checks passed · `mypy` Success (64 arquivos) · `pytest` **263 passed, 4 skipped**.

## 1. Escopo: o quê mudou no seu quadrado

Dois débitos do relatório `_reversa_bugs/auditoria-merge-dev2-2026-09-29.md` (§5, itens 2 e 3), implementados sobre **sua arquitetura** (fachada única, `ReviewService`, `value_types`) — nada foi reescrito, tudo é extensão aditiva.

### Débito A — histórico de decisões de revisão na UI

- `src/modules/policy_analysis/application/review.py` — **novo método** `ReviewService.list_decisions(policy_id)`.
  - Semântica descoberta no seu modelo: fatos que não precisavam de revisão nascem `revisao_status="CONFIRMADO"` sem revisor (`upsert_fact` linha do `status_revisao`). Portanto o filtro de "decisão humana" é **`revisao_por is not None`**, não o status.
- `src/modules/policy_analysis/public_api.py` — **novo método** `PolicyAnalysisFacade.list_review_decisions(policy_id)`.
- `src/ui/components/review.py` — nova seção "Histórico de decisões" (expander) renderizada sempre, mesmo com fila vazia (`_render_history`).

### Débito B — valor corrigido sem `{"text": ...}`

- `src/modules/policy_analysis/domain/value_types.py` — **nova função pura** `raw_value_from_text(field, text, *, original=None)`: monta o `value` bruto pelo `FieldType` do campo a partir do texto digitado.
  - `MONEY` preserva `currency` do valor anterior (default BRL); `NUMBER` preserva `unit`; `PERIOD` exige 2 datas no texto (`DD/MM/YYYY a DD/MM/YYYY`, ISO ou `DD-MM-YYYY`) e levanta `NormalizationError` com 1 data; `TEXT`/`DATE` diretos.
- `src/modules/policy_analysis/application/review.py` — `record_decision` agora aceita `value: dict | str | None`; `str` é coerido via `raw_value_from_text` (com `original=item.fact.value`) antes de normalizar. **Assinatura retrocompatível** (dict continua válido).
- `src/ui/components/review.py` — envia `corrected` (texto puro) no lugar de `{"text": corrected}` — nenhuma regra de tipo na UI.

## 2. Testes (novos, verdes)

- `tests/modules/policy_analysis/test_value_types.py` — `test_raw_value_from_text_monta_value_por_tipo_do_campo`, `test_raw_value_from_text_periodo_exige_duas_datas_e_texto_vazio_falha`.
- `tests/modules/policy_analysis/test_review_queue.py` — `test_corrigido_com_texto_digitado_coercao_por_tipo_do_campo` (MONEY + PERIOD), `test_corrigido_com_texto_invalido_para_o_tipo_e_rejeitado`, `test_historico_so_lista_decisoes_humanas`.

## 3. Funcionalidades adicionadas

1. O analista vê o histórico de revisões já decididas (quem, quando, decisão, valor).
2. A correção por texto funciona para **qualquer** campo do catálogo (antes: só `TEXT` não quebrava; MONEY/NUMBER/DATE/PERIOD levantavam `NormalizationError` sanitizado).

## 4. Passos para evitar conflito de merge (ordem de integração)

1. Se você tiver trabalho em andamento em `application/review.py`, `public_api.py`, `domain/value_types.py` ou `ui/components/review.py`, **faça rebase sobre estes commits** — os diffs são aditivos (métodos novos + 2 linhas alteradas em `record_decision`); não sobrescreva `list_decisions`/`raw_value_from_text`.
2. Não altere a semântica de `upsert_fact` (`CONFIRMADO` sem revisor) sem atualizar `list_decisions` — o filtro depende dela.
3. Se mudar a assinatura de `record_decision`, mantenha `value: dict | str | None` (a UI envia `str`).
4. Fora destes pontos, o quadrado é seu: qualquer refatoração que preserve a fachada (`list_review_queue`, `list_review_decisions`, `record_review_decision`) não conflita.

## 5. Relatório de áreas compartilhadas tocadas

| Zona | Ação |
|------|------|
| `src/shared_kernel/version.py` | **Só comentário** atualizado (referência da feature renomeada `005-p1-dev1-proveniencia` → `dev1-005-p1-proveniencia`). Nenhum contrato/versão alterado — `CONTRACTS_VERSION` segue `1.1.0`. |
| `_reversa_sdd/**`, `_reversa_forward/**`, `_reversa_bugs/**` | Renome de features para `<dev>-<NNN>-<slug>` (convenção do humano; colisão `001-*` resolvida) + varredura de referências (55 `.md`); `progress.jsonl` preservado como log histórico. Detalhes: `_reversa_bugs/auditoria-merge-dev2-2026-09-29.md` §5 "Resolução". |
| `_reversa_sdd/sdd/policy-analysis.md` OQ-04 | Marcada resolvida apontando o adendo canônico `_reversa_sdd/addenda/decisao-export-markdown.md`. |
| `_reversa_sdd/learning/aprendizados.md` §5 | Novas convenções §5.6 (fonte canônica) e §5.7 (dois arquivos, sem duplicata — `CLAUDE.md` × `aprendizados.md`). |
| `requirements.txt` | **Não tocou.** |

## 6. Decisões do humano registradas nesta entrega

- Mundo anterior (guardas `domain/rules.py`/`domain/anchoring.py`) **morre** — não volta.
- Backlog daqui em frente: **só itens do Dev 1** (`D1-P2-1`, `NG-01`); `D2-P2-1..3` seguem como seus.
- Validação em campo (`D2-P1-3`, apólices reais) fica para depois do fechamento do projeto.

---

## 7. ATUALIZAÇÃO (2026-09-30, pós-merge do PR #10) — mapa de colisão com `feature/dev2-policy-analysis-slice` (`5f94063`, `d7a0121`)

O trabalho paralelo do Dev 2 (commits `5f94063` guardas+P2 e `d7a0121` DIVERGENTE+histórico) **não está no `main`** (`d333b1a`) e sobrepõe o PR #10 recém-mesclado. Ao rebasear sobre o `main`, os conflitos serão:

| Arquivo | `main` (PR #10, nosso) | Branch Dev 2 | Reconciliação recomendada (princípio do vencedor: nunca perder capacidade) |
|---|---|---|---|
| `application/review.py` | `list_decisions` (filtro `revisao_por is not None`) + `record_decision` aceita `dict \| str` (coerção `raw_value_from_text`) | `list_decisions` (filtro `revisao_decisao is not None`) + 3ª ação `DIVERGENTE` (não resolve o fato) | **Ficar com os dois:** filtro do Dev 2 (`revisao_decisao`) + coerção por tipo + `DIVERGENTE`. Assinatura final: `value: dict \| str \| None`. |
| `public_api.py` | `list_review_decisions` + `record_review_decision(value: dict \| str \| None)` | `list_review_decisions` (idêntico em espírito) | Um único `list_review_decisions`; assinatura com `str` (a UI envia texto). |
| `ui/components/review.py` | 2 botões + `_render_history` + envia **texto puro** | 3 botões (Confirmar/Corrigir/Divergência) + `_render_decisions_history` + ainda envia `{"text": corrected}` | **Ficar com os dois:** 3 botões do Dev 2 + histórico (um único) + envio de texto puro do PR #10 (sem isto o bug `NormalizationError` volta). |
| `domain/value_types.py` | `raw_value_from_text` (só no `main`) | não toca | Manter do `main`; `record_decision` do Dev 2 deve chamá-lo. |
| `tests/.../test_review_queue.py` | +3 testes (coerção, período inválido, histórico) | +3 testes (DIVERGENTE, histórico, 3 ações) | **Manter os 6.** |
| `domain/rules.py` / `domain/anchoring.py` | ausentes (decisão "mundo anterior morre") | **novos** (implementações novas, `5f94063`, com testes) | ⚠️ **Decisão do humano pendente** — ver §8. |

**Regra de ouro para o rebase:** nenhum dos dois lados sobrescreve o outro; `record_decision` final = coerção por tipo (`raw_value_from_text`) **+** 3 ações (CONFIRMADO/CORRIGIDO/DIVERGENTE).

## 8. Guardas pós-LLM (`5f94063`) — VEREDITO do humano (2026-09-30): **ACEITAS como código do mundo novo**

Análise profunda (cascata 2.1) concluiu: `domain/rules.py`/`domain/anchoring.py` são **implementações novas** (não o código morto do mundo anterior) — puras, determinísticas, T-2a (motivos sem valor), 26 testes, rebaixam `FOUND → NEEDS_REVIEW` sem nunca promover, e alimentam `value["rule_violations"]` — que destrava o ramo `ALTO` da governança de qualidade (004). "Tudo do mundo anterior morre" segue valendo para o código antigo; estes são o `D2-P0-1`/`D2-P0-3` do plano do Dev 2.

**Observações de review (não bloqueiam o merge — corrigir quando conveniente):**
1. `domain/anchoring.py` `collect_excerpts`: `raw_text` entra duas vezes (chave de citação + varredura de aspas) — infla o contador de citações não ancoradas (a decisão não muda). Deduplicar a lista de chaves.
2. `domain/rules.py` `moeda_consistente`: moedas mistas na mesma apólice (rara, mas legal) rebaixam todos os monetários — comportamento aceito como sinal para humano; vale comentário de docstring registrando a intenção.
