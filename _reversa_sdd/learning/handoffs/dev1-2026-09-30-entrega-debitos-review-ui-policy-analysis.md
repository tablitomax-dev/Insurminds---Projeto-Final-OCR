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
