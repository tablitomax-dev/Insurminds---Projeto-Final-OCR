# Handoff — Entrega do projeto + README para a banca (2026-10-06)

## Entregas

1. Pasta `Entrega do projeto/` na raiz: relatório técnico (PDF), slides (PPTX),
   vídeo de demonstração (MP4 comprimido de 106 MB → 17,3 MB via ffmpeg
   libx264 CRF 18 + AAC 128k — dentro do limite rígido de 100 MB do GitHub,
   qualidade de tela preservada) e `APÓLICES/` (AXA, Allianz 2025, Allianz 2017
   JPG, Porto).
2. `README.md` na raiz para a banca avaliadora: onde está a entrega (com
   inventário), descrição do projeto (7 etapas do pipeline), instruções de
   instalação, instruções de execução (cadeia de LLMs glm → deepseek → mimo +
   Gemini opcional; modo demo offline), tecnologias utilizadas, integrantes do
   Grupo AlgorithLabs (I2A2 — Desafio Final, Outubro/2026) e licença MIT com
   texto integral.
3. `.reversa/reversa-config.json`: `allowedPaths` com `"Entrega do projeto/**"`
   e `"README.md"` (edição do usuário — ato exclusivo dele; registro por
   transparência).

## Zonas compartilhadas

- Nenhuma em código — só documentação/entrega. O `README.md` descreve
  comportamento entregue no PR #17 (cadeia de LLMs, banner de saúde, UI
  simplificada), então a ordem de merge dos PRs é indiferente para o código.

## Pendências

- Se o PR #17 estiver aberto ao mesclar este, a linha de `allowedPaths` pode
  pedir união trivial (ambos só acrescentam globs — concatenar as listas).
- Continuidade do roadmap: validação real (rodadas 2 e 3 de `tests/apolices`) e
  batching do Relatório D&O — ver
  `2026-10-06-fallback-llm-saude-provedor-ui.md`.
