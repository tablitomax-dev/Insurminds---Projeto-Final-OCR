# Onboarding: P1 do Desenvolvedor 2 — Experiência e Governança da Análise

> Identificador: `004-p1-dev2-experiencia`
> Data: `2026-09-26`
> Para: humano testando a feature pela primeira vez (Windows/PowerShell — ver `aprendizados.md` Apêndice A)

## Pré-requisitos

1. Projeto com dependências instaladas (mesmo ambiente das features 001–003).
2. Chave da API Gemini configurada no ambiente (para extração real) — para testar sem rede, os testes usam `ScriptedLlmExtractor`.
3. Nenhum serviço externo novo: esta feature não toca Docker/Qdrant além do que já existia.

## Passo a passo

1. **Gate de qualidade primeiro** (deve sair verde antes de qualquer teste manual):
   ```powershell
   python -m ruff check .
   python -m mypy src
   python -B -m pytest -q -p no:cacheprovider
   ```
2. **Rode os testes novos da feature** (nomes prováveis — conferir no `actions.md`):
   ```powershell
   python -B -m pytest -q -p no:cacheprovider tests/modules/policy_analysis -k "quality or metrics"
   python -B -m pytest -q -p no:cacheprovider tests/architecture
   python -B -m pytest -q -p no:cacheprovider tests/ui
   ```
3. **Suba a UI** e execute a jornada completa (upload → estágios → revisão → comparação → export):
   ```powershell
   python -m streamlit run src/ui/app.py
   ```
4. **Confira a fila de revisão agrupada por severidade:** com um fato que viola regra (ex.: `vigencia_fim` anterior a `vigencia_inicio`), o grupo `CRÍTICO`/`ALTO` aparece primeiro; cada item mostra `field_code`, motivo e evidência.
5. **Confira o painel de métricas:** após a extração, o cartão mostra tokens, custo estimado (USD, com data de referência da tabela) e latência do último run; o mesmo agregado aparece no log estruturado por `run_id`.
6. **Confira o `QualityReport`:** a fachada devolve o relatório por documento e por comparação (via `PolicyAnalysisFacade.list_issues` / `get_quality_report`).
7. **Prove o anti-vazamento:** use um PDF com texto marcador e verifique que métricas, logs e erros não contêm o texto da apólice (teste automatizado `RF-04` cobre isso; o passo manual é redundância).

## O que é real e o que é fake neste teste

- Real: pipeline de análise, regras por campo, ancoragem, DuckDB, UI.
- Fake: LLM (nos testes) e a tabela de preços (estimativa, não fatura do provedor).

## Problemas comuns

- **Painel vazio após reiniciar o servidor:** as métricas são por processo (decisão D-03); o log estruturado mantém o histórico por `run_id`.
- **Teste de arquitetura falhando ao importar a UI:** confirme que `src/ui` e `src/composition_root` não importam `infrastructure`/`domain` alheios — é o ponto da feature.
