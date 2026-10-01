"""Proveniência do chunk: resumo criptográfico do texto indexado (D1-P1-1).

`content_fingerprint` (contrato v1.1.0) guarda o sha256 do **texto do chunk**
para comparar o texto gravado com o texto recuperado — divergência é sinal de
alerta (chunk reescrito, corrompido ou merge manual), nunca exceção.

O resumo é one-way (não permite reconstruir o texto) e **não substitui**
anonimização de dados sensíveis (RNF de segurança da feature 005).
"""

import hashlib

#: Algoritmo do resumo de conteúdo: sha256 em hex, 64 chars, minúsculo.
FINGERPRINT_ALGORITHM = "sha256"


def compute_content_fingerprint(text: str) -> str:
    """Resumo sha256 (hex, 64 chars) do texto do chunk — pura e determinística.

    Mesmo texto ⇒ mesmo resumo em qualquer execução; textos distintos ⇒
    resumos distintos. A semântica adotada está registrada na feature
    `dev1-005-p1-proveniencia` (caixa postal `contract-delta-chunkmetadata.md`).
    """
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
