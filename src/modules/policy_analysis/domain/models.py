"""Modelos de domínio do policy_analysis (T016).

`FieldComparison` e `ComparisonResult` são o resultado determinístico da
comparação (RN-01); `Explanation` é a explicação rastreável citando evidência
dos dois lados (RF-07); `ReviewItem` expõe o fato pendente de revisão humana
com a evidência anexa (RF-04).
"""

from __future__ import annotations

from dataclasses import dataclass

from shared_kernel.contracts import ExtractedFact


@dataclass(frozen=True)
class FieldComparison:
    """Resultado da comparação de um `field_code` entre duas apólices."""

    field_code: str
    resultado: str
    valor_a: dict | None
    valor_b: dict | None
    direcao: str
    evidencias_a: tuple[str, ...]
    evidencias_b: tuple[str, ...]
    explicacao: str | None = None


@dataclass(frozen=True)
class ComparisonResult:
    """Comparação campo a campo de um par de apólices (idempotente por ID)."""

    comparison_id: str
    policy_id_a: str
    policy_id_b: str
    campos: tuple[FieldComparison, ...]

    def campo(self, field_code: str) -> FieldComparison | None:
        for item in self.campos:
            if item.field_code == field_code:
                return item
        return None


@dataclass(frozen=True)
class Explanation:
    """Explicação de uma diferença, sempre com citação de evidência."""

    comparison_id: str
    field_code: str
    text: str
    evidence_ids: tuple[str, ...]


@dataclass(frozen=True)
class ReviewItem:
    """Fato sinalizado para revisão humana, com a evidência anexa."""

    fact: ExtractedFact
    revisao_status: str
    revisao_decisao: dict | None = None
    revisao_por: str | None = None
    revisao_em: str | None = None
