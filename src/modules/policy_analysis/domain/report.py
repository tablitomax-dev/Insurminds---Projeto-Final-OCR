"""Modelos e funções puras do Relatório D&O (metodologia de comparação).

Dataclasses frozen + funções determinísticas (sem LLM, sem I/O): `compute_ranking`
(fórmula exata Σ(nota × peso) / 10), `compute_sensitivity`, `guard_sem_vencedora`
(guarda do §9) e `build_checklist` (§11). Mesma entrada → mesma saída (RNF-01).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from .report_catalog import (
    CHECKLIST_ITEMS,
    CoverageStatus,
    ReportField,
    SensitivityScenario,
)

#: Ressalva fixa anexada a todo cenário hipotético (§7) — nunca afirmar que a
#: cobertura será necessariamente aceita pela seguradora.
SCENARIO_RESSALVA = "Cenário hipotético — sem afirmar que a cobertura será necessariamente aceita."

#: Chaves da seção de conclusões (§9).
CONCLUSION_KEYS: tuple[str, ...] = (
    "5_diferencas",
    "5_riscos",
    "vantagens",
    "desvantagens",
    "nao_comparaveis",
    "negociaveis",
    "perguntas_corretor",
    "documentos_adicionais",
)

_REPORT_NAMESPACE = uuid.UUID("6f9619ff-8b86-d011-b42d-00c04fc964ff")


def report_id_for(policy_ids: tuple[str, ...] | list[str]) -> str:
    """`ReportId` determinístico do conjunto de apólices (idempotência)."""
    key = "|".join(policy_ids)
    return str(uuid.uuid5(_REPORT_NAMESPACE, f"insurminds:report:{key}"))


@dataclass(frozen=True)
class DocumentIdentification:
    """Identificação de um documento analisado (§1), com o que está ausente."""

    policy_id: str
    seguradora: str | None
    produto: str | None
    processo_susep: str | None
    versao_data: str | None
    publico_alvo: str | None
    empresa_aberta_fechada: str | None
    secoes_natureza: tuple[str, ...]
    num_paginas: int | None
    coberturas_descritas: tuple[str, ...]
    limitacoes: tuple[str, ...]
    ausentes: tuple[str, ...] | str | None


@dataclass(frozen=True)
class ReportCell:
    """Célula da matriz: status + limites, condições, impactos e referência (§10).

    `origem` classifica a natureza da afirmação: "fato" | "interpretacao" |
    "inferencia" | "nao_localizado" | "requer_confirmacao".
    """

    status: CoverageStatus
    limite_franquia: str | None = None
    exclusoes_condicoes: str | None = None
    impacto_pratico: str | None = None
    impacto_financeiro: str | None = None
    referencia: str | None = None
    origem: str = "fato"


@dataclass(frozen=True)
class ReportRow:
    """Linha da matriz principal: um campo do catálogo × uma célula por apólice."""

    field: ReportField
    cells: dict[str, ReportCell]


@dataclass(frozen=True)
class ReportTableRow:
    """Linha de tabela especial: rótulo + valor textual por apólice."""

    label: str
    cells: dict[str, str | None]


@dataclass(frozen=True)
class ReportTable:
    """Tabela especial (§6): pessoas_protegidas, limites, matriz_temporal,
    exclusoes_criticas ou coberturas_sociedade."""

    code: str
    title: str
    rows: tuple[ReportTableRow, ...]


@dataclass(frozen=True)
class Scenario:
    """Cenário hipotético (§7) com a ressalva fixa de não aceitação."""

    name: str
    policy_findings: dict[str, str]
    ressalva: str = SCENARIO_RESSALVA


@dataclass(frozen=True)
class RankingScore:
    """Pontuação de uma apólice no ranking informativo (§8)."""

    policy_id: str
    nota_por_criterio: dict[str, float]
    contribuicao_por_criterio: dict[str, float]
    total: float


@dataclass(frozen=True)
class RankingResult:
    """Resultado do ranking (base ou cenário de sensibilidade)."""

    scores: tuple[RankingScore, ...]
    weights: dict[str, float]
    informative_only: bool = False
    motivo_sem_vencedora: str | None = None


@dataclass(frozen=True)
class Report:
    """Relatório D&O completo (§1, §5–§11)."""

    report_id: str
    policy_ids: tuple[str, ...]
    identifications: dict[str, DocumentIdentification]
    rows: tuple[ReportRow, ...]
    tables: tuple[ReportTable, ...]
    scenarios: tuple[Scenario, ...]
    ranking: RankingResult
    sensitivity: tuple[RankingResult, ...]
    conclusions: dict
    checklist: dict[str, bool]
    profile_mode: str


# --- funções puras ------------------------------------------------------------


def normalize_weights(weights: dict[str, float]) -> dict[str, float]:
    """Normaliza pesos relativos para a escala 100 (soma exata 100.0).

    Os cenários de sensibilidade são definidos por pesos relativos (a soma
    nominal é 105); a normalização mantém a fórmula e os totais comparáveis
    entre cenários.
    """
    total = sum(weights.values())
    if total <= 0:
        raise ValueError(f"pesos devem somar um valor positivo; soma informada: {total}")
    return {code: value * 100.0 / total for code, value in weights.items()}


def compute_ranking(
    notes: dict[str, dict[str, float]], weights: dict[str, float]
) -> tuple[RankingScore, ...]:
    """Ranking determinístico: `total = Σ(nota × peso) / 10` por apólice.

    - notas fora de [0, 10] → `ValueError`;
    - pesos devem somar 100 (±0.01), senão `ValueError`;
    - critério do peso sem nota correspondente → `ValueError`;
    - contribuição por critério = `nota × peso / 10`;
    - saída em ordem decrescente de total; empate preserva a ordem de entrada.
    """
    total_weight = sum(weights.values())
    if abs(total_weight - 100.0) > 0.01:
        raise ValueError(f"pesos devem somar 100 (±0.01); soma informada: {total_weight}")
    scores: list[RankingScore] = []
    for policy_id, per_criterion in notes.items():
        missing = [code for code in weights if code not in per_criterion]
        if missing:
            raise ValueError(f"critério sem nota para {policy_id}: {sorted(missing)}")
        notas: dict[str, float] = {}
        contribuicoes: dict[str, float] = {}
        total = 0.0
        for code, weight in weights.items():
            nota = per_criterion[code]
            if isinstance(nota, bool) or not isinstance(nota, (int, float)):
                raise ValueError(f"nota inválida para {policy_id}/{code}: {nota!r}")
            nota = float(nota)
            if nota < 0.0 or nota > 10.0:
                raise ValueError(f"nota fora de [0,10] para {policy_id}/{code}: {nota}")
            contribuicao = nota * weight / 10.0
            notas[code] = nota
            contribuicoes[code] = contribuicao
            total += contribuicao
        scores.append(
            RankingScore(
                policy_id=policy_id,
                nota_por_criterio=notas,
                contribuicao_por_criterio=contribuicoes,
                total=total,
            )
        )
    scores.sort(key=lambda score: -score.total)  # estável: empate preserva ordem de entrada
    return tuple(scores)


def compute_sensitivity(
    notes: dict[str, dict[str, float]], scenarios: tuple[SensitivityScenario, ...]
) -> tuple[RankingResult, ...]:
    """Ranking por cenário de sensibilidade, na ordem dos cenários informados.

    Os pesos relativos de cada cenário são normalizados para a escala 100 antes
    do cálculo (`normalize_weights`), mantendo a fórmula e os totais
    comparáveis entre cenários.
    """
    results: list[RankingResult] = []
    for scenario in scenarios:
        weights = normalize_weights(dict(scenario.weights))
        results.append(RankingResult(scores=compute_ranking(notes, weights), weights=weights))
    return tuple(results)


GUARD_REQUIRED_FACTS: tuple[str, ...] = (
    "preco",
    "lmg",
    "lmis",
    "franquias",
    "sublimites",
    "cobertura_efetivamente_contratada",
    "perfil_do_contratante",
)

_GUARD_LABELS: dict[str, str] = {
    "preco": "prêmio",
    "lmg": "LMG",
    "lmis": "LMIs",
    "franquias": "franquias",
    "sublimites": "sublimites",
    "cobertura_efetivamente_contratada": "cobertura efetivamente contratada",
    "perfil_do_contratante": "perfil do contratante",
}


def guard_sem_vencedora(
    facts_available: dict, profile_complete: bool
) -> tuple[bool, str | None]:
    """Guarda do §9: SEM vencedora geral sem a base de dados completa.

    Retorna `(True, motivo em pt-br)` quando falta qualquer um de: prêmio
    (`preco`), LMG, LMIs, franquias, sublimites, cobertura efetivamente
    contratada e perfil do contratante — `perfil_do_contratante` também exige
    `profile_complete=True`. Com tudo disponível, retorna `(False, None)`.
    """
    missing = [code for code in GUARD_REQUIRED_FACTS if not facts_available.get(code)]
    if not profile_complete and "perfil_do_contratante" not in missing:
        missing.append("perfil_do_contratante")
    if missing:
        rotulos = ", ".join(_GUARD_LABELS[code] for code in missing)
        return True, (
            "Sem vencedora geral: o ranking é informativo porque faltam dados de "
            f"{rotulos} (§9 — não há conclusão financeira sem dados financeiros)."
        )
    return False, None


# Itens do checklist (§11) preenchidos por dado externo (chave em `report_data`).
_EXTERNAL_CHECKS: dict[str, str] = {
    "documentos analisados integralmente": "documentos_analisados_integralmente",
    "condições particulares incluídas": "condicoes_particulares_incluidas",
    "documentos ausentes explicitamente listados": "documentos_ausentes_listados",
    "módulo de ranking apresentado com critérios, pesos e pergunta sobre alterações": (
        "ranking_apresentado_com_pergunta"
    ),
    "análise agnóstica em relação a seguradoras e número de propostas": "analise_agnostica",
}


def build_checklist(report_data: dict) -> dict[str, bool]:
    """Avalia os 14 itens da verificação final (§11) de forma mecânica.

    Itens determináveis são calculados sobre `rows`/`identifications`/`ranking`;
    itens que dependem de dado externo recebem o booleano de `report_data`
    (chaves: `documentos_analisados_integralmente`,
    `condicoes_particulares_incluidas`, `documentos_ausentes_listados`,
    `ranking_apresentado_com_pergunta`, `analise_agnostica`), com
    `dados_financeiros_disponiveis` entrando no item de conclusão financeira.
    """
    rows = list(report_data.get("rows") or [])
    rows_by_code = {row.field.code: row for row in rows}
    identifications = report_data.get("identifications") or {}
    ranking = report_data.get("ranking")
    checklist: dict[str, bool] = {}
    for item in CHECKLIST_ITEMS:
        if item in _EXTERNAL_CHECKS:
            checklist[item] = bool(report_data.get(_EXTERNAL_CHECKS[item], False))
            continue
        checklist[item] = _computed_check(item, rows, rows_by_code, identifications, ranking, report_data)
    return checklist


def _filled(row: ReportRow | None) -> bool:
    return row is not None and any(
        cell.status is not CoverageStatus.NAO_LOCALIZADO for cell in row.cells.values()
    )


def _computed_check(item, rows, rows_by_code, identifications, ranking, report_data) -> bool:
    if item == "extensões não tratadas como automaticamente contratadas":
        # Nenhuma extensão pode aparecer como "Previsto" sem referência documental.
        for row in rows:
            if row.field.category != "coberturas_extensoes":
                continue
            for cell in row.cells.values():
                if cell.status is CoverageStatus.PREVISTO and not cell.referencia:
                    return False
        return True
    if item == "LMG, LMI, limite agregado e sublimites diferenciados":
        return all(_filled(rows_by_code.get(code)) for code in ("lmg", "lmi", "limite_agregado", "sublimites"))
    if item == "custos de defesa avaliados separadamente":
        return any(_filled(row) for row in rows if row.field.category == "custos_defesa")
    if item == "claims made e notificações comparados":
        return all(
            _compared(rows_by_code.get(code))
            for code in ("base_ocorrencia_claims_made", "notificacao_quem_prazo_forma")
        )
    if item == "exclusões com reembolso de defesa distinguidas de exclusões integrais":
        for row in rows:
            if row.field.category != "exclusoes":
                continue
            if any(cell.exclusoes_condicoes for cell in row.cells.values()):
                return True
        return False
    if item == "cobertura do administrador e da sociedade não confundidas":
        return all(
            _filled(rows_by_code.get(code))
            for code in ("protecao_direta_administrador_ab_side", "protecao_sociedade_c_side")
        )
    if item == "diferenças entre empresa aberta e fechada consideradas":
        return bool(identifications) and all(
            ident.empresa_aberta_fechada for ident in identifications.values()
        )
    if item == "sem conclusão financeira sem dados financeiros":
        if report_data.get("dados_financeiros_disponiveis"):
            return True
        return bool(getattr(ranking, "informative_only", False))
    if item == "nenhuma lacuna preenchida por suposição de prática de mercado":
        # Lacuna (não localizada) só pode ter origem "nao_localizado", nunca suposição.
        for row in rows:
            for cell in row.cells.values():
                if cell.status is CoverageStatus.NAO_LOCALIZADO and cell.origem != "nao_localizado":
                    return False
        return True
    return False


def _compared(row: ReportRow | None) -> bool:
    """Campo preenchido em pelo menos 2 apólices (ou em todas, se houver menos de 2)."""
    if row is None or not row.cells:
        return False
    filled = sum(1 for cell in row.cells.values() if cell.status is not CoverageStatus.NAO_LOCALIZADO)
    return filled >= min(2, len(row.cells))
