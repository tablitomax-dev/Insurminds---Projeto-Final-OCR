"""Tabela de preços do Gemini em USD, versionada no código (D2-P1-2, D-04).

Custo estimado = tokens de entrada/saída × preço por 1 milhão de tokens.
A data de referência é exposta no painel e no log: o valor é **estimativa**
(RN-03), não fatura do provedor. Modelo fora da tabela → custo `None`
(nada de número inventado).
"""

from __future__ import annotations

#: Data de referência da tabela de preços (visível no painel — decisão D-04).
PRICE_REFERENCE_DATE = "2026-09-26"

#: Preço em USD por 1 milhão de tokens: modelo -> (entrada, saída).
USD_PER_1M_TOKENS: dict[str, tuple[float, float]] = {
    "gemini-2.0-flash": (0.10, 0.40),
}


def compute_cost_usd(
    model_name: str, request_tokens: int, response_tokens: int
) -> float | None:
    """Custo estimado em USD; `None` quando o modelo não está na tabela."""
    prices = USD_PER_1M_TOKENS.get(model_name)
    if prices is None:
        return None
    input_price, output_price = prices
    cost = (request_tokens / 1_000_000) * input_price + (
        response_tokens / 1_000_000
    ) * output_price
    return round(cost, 6)
