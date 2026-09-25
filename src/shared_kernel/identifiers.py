"""Identificadores compartilhados do domínio (resumo executivo §5.2 e §8.1).

Um identificador por granularidade: apólice (entidade lógica), documento
(arquivo físico), página, chunk (fragmento indexado), fato extraído,
comparação e execução de workflow. Não há geração centralizada: quem cria a
entidade é dono do ID (YAGNI). Alteração exige revisão dos dois devs (MAJOR).
"""

from typing import NewType

PolicyId = NewType("PolicyId", str)
DocumentId = NewType("DocumentId", str)
PageId = NewType("PageId", str)
ChunkId = NewType("ChunkId", str)
FactId = NewType("FactId", str)
ComparisonId = NewType("ComparisonId", str)
RunId = NewType("RunId", str)
