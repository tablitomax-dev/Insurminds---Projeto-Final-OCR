"""Versionamento do contrato compartilhado (spec shared-kernel-contracts, RF-08).

Política semântica:
- PATCH (1.0.x): correção compatível, nenhum campo/tipo alterado.
- MINOR (1.x.0): campo opcional novo (compatível com consumidores antigos).
- MAJOR (x.0.0): qualquer quebra de campo, tipo ou literal — exige revisão
  dos DOIS desenvolvedores (Dev 1 + Dev 2) antes do merge.
"""

from typing import Final

#: v1.1.0 (MINOR): `ChunkMetadata.content_fingerprint` opcional (caixa postal
#: `contract-delta-chunkmetadata.md`, feature dev1-005-p1-proveniencia).
CONTRACTS_VERSION: Final[str] = "1.1.0"
