"""Casos de uso do Relatório D&O (metodologia de comparação de apólices).

Fluxo de `build_report`: identificação por documento → matriz preenchida em
map/reduce POR CATEGORIA (uma chamada do agente por categoria × apólice, nunca
uma chamada gigante) → guarda de rastreabilidade (célula sem referência documental
vira "Requer confirmação") → tabelas especiais → cenários com ressalva fixa →
ranking e sensibilidade → guarda §9 (sem vencedora sem dados) → conclusões e
checklist. `sections_source` aceita `get_evidences(policy_id)` ou
`get_markdown_sections(policy_id)` (duck-typing); sem agente configurado,
`ClassifiedError("LLM_UNAVAILABLE", ...)`.
"""

from __future__ import annotations

from ..domain.report import (
    CONCLUSION_KEYS,
    SCENARIO_RESSALVA,
    DocumentIdentification,
    RankingResult,
    Report,
    ReportCell,
    ReportRow,
    ReportTable,
    ReportTableRow,
    Scenario,
    build_checklist,
    compute_ranking,
    compute_sensitivity,
    guard_sem_vencedora,
    report_id_for,
)
from ..domain.report_catalog import (
    CATEGORIES,
    DEFAULT_WEIGHTS,
    FIELDS_BY_CODE,
    REPORT_FIELDS,
    SENSITIVITY_SCENARIOS,
    CoverageStatus,
)
from .errors import ClassifiedError

#: Origens válidas de uma célula (rastreabilidade §10).
VALID_ORIGENS = frozenset({"fato", "interpretacao", "inferencia", "nao_localizado", "requer_confirmacao"})


class ReportService:
    """Caso de uso do Relatório D&O sobre a porta de seções e a porta do agente."""

    def __init__(self, sections_source, report_agent=None, repo=None):
        self._sections_source = sections_source
        self._report_agent = report_agent
        self._repo = repo

    def build_report(
        self,
        policy_ids: list[str],
        profile: dict | None = None,
        weights: dict[str, float] | None = None,
    ) -> Report:
        """Monta o relatório completo para o conjunto de apólices.

        `profile` (opcional) traz a entrada do analista: `facts_available` (dict
        com as chaves da guarda §9 — preco, lmg, lmis, franquias, sublimites,
        cobertura_efetivamente_contratada, perfil_do_contratante), `perfil_completo`
        (bool) e `checklist_inputs` (dict com as chaves externas do checklist §11).
        `weights` (opcional) substitui `DEFAULT_WEIGHTS` no ranking; os pesos
        devem somar 100 (±0.01).
        """
        if self._report_agent is None:
            raise ClassifiedError(
                "LLM_UNAVAILABLE", "agente de relatório não configurado", retriable=False
            )
        if not policy_ids:
            raise ValueError("build_report exige ao menos uma policy_id")

        sections_by_policy = {pid: self._load_sections(pid) for pid in policy_ids}
        identifications = {
            pid: _identification_from(pid, self._report_agent.identify(pid, sections_by_policy[pid]))
            for pid in policy_ids
        }

        rows = self._build_rows(policy_ids, sections_by_policy)
        tables = self._build_tables(policy_ids, sections_by_policy)
        scenarios = self._build_scenarios(policy_ids, sections_by_policy)

        notes = self._report_agent.score_criteria(policy_ids, sections_by_policy)
        effective_weights = dict(weights) if weights is not None else dict(DEFAULT_WEIGHTS)
        facts_available = dict((profile or {}).get("facts_available") or {})
        profile_complete = bool((profile or {}).get("perfil_completo"))
        informative, motivo = guard_sem_vencedora(facts_available, profile_complete)
        ranking = RankingResult(
            scores=compute_ranking(notes, effective_weights),
            weights=effective_weights,
            informative_only=informative,
            motivo_sem_vencedora=motivo,
        )
        sensitivity = compute_sensitivity(notes, SENSITIVITY_SCENARIOS)

        conclusions = self._build_conclusions(policy_ids, sections_by_policy)
        checklist_inputs = dict((profile or {}).get("checklist_inputs") or {})
        checklist_inputs.setdefault("dados_financeiros_disponiveis", bool(facts_available.get("preco")))
        # As chaves computadas sempre prevalecem sobre a entrada do analista.
        checklist_inputs.update(
            {"rows": rows, "identifications": identifications, "ranking": ranking}
        )
        checklist = build_checklist(checklist_inputs)

        report = Report(
            report_id=report_id_for(policy_ids),
            policy_ids=tuple(policy_ids),
            identifications=identifications,
            rows=tuple(rows),
            tables=tuple(tables),
            scenarios=tuple(scenarios),
            ranking=ranking,
            sensitivity=sensitivity,
            conclusions=conclusions,
            checklist=checklist,
            profile_mode="com_documentos_perfil" if profile else "comparacao_documental",
        )
        if self._repo is not None:
            upsert = getattr(self._repo, "upsert_report", None)
            if callable(upsert):
                upsert(report)
        return report

    # --- matriz principal (§5): map/reduce por categoria × apólice -------------

    def _build_rows(self, policy_ids, sections_by_policy) -> list[ReportRow]:
        cells_by_field: dict[str, dict[str, ReportCell]] = {code: {} for code in FIELDS_BY_CODE}
        for category in CATEGORIES:
            fields = tuple(field for field in REPORT_FIELDS if field.category == category.code)
            for pid in policy_ids:
                payload = self._report_agent.fill_category(category, fields, sections_by_policy[pid])
                seen = set()
                for raw in _iter_cell_payloads(payload):
                    code = str(raw.get("field_code") or "")
                    if code not in FIELDS_BY_CODE:
                        raise ClassifiedError(
                            "LLM_SCHEMA_INVALID",
                            f"célula para campo fora do catálogo: {code!r}",
                            retriable=True,
                        )
                    cells_by_field[code][pid] = _cell_from(raw)
                    seen.add(code)
                for code in (field.code for field in fields):
                    if code not in seen:
                        # Campo sem resposta do agente = não localizado (nunca erro, EC-03).
                        cells_by_field[code][pid] = ReportCell(
                            status=CoverageStatus.NAO_LOCALIZADO, origem="nao_localizado"
                        )
        return [
            ReportRow(field=field, cells=dict(cells_by_field[field.code]))
            for field in REPORT_FIELDS
        ]

    # --- tabelas especiais (§6) ------------------------------------------------

    def _build_tables(self, policy_ids, sections_by_policy) -> list[ReportTable]:
        raw_tables = self._report_agent.fill_tables(policy_ids, sections_by_policy) or []
        tables: list[ReportTable] = []
        for raw in raw_tables:
            rows = []
            for raw_row in raw.get("rows") or []:
                cells = raw_row.get("cells") or {}
                rows.append(
                    ReportTableRow(
                        label=str(raw_row.get("label") or ""),
                        cells={pid: _opt_str(cells.get(pid)) for pid in policy_ids},
                    )
                )
            tables.append(
                ReportTable(
                    code=str(raw.get("code") or ""),
                    title=str(raw.get("title") or ""),
                    rows=tuple(rows),
                )
            )
        return tables

    # --- cenários (§7) ---------------------------------------------------------

    def _build_scenarios(self, policy_ids, sections_by_policy) -> list[Scenario]:
        raw_scenarios = self._report_agent.build_scenarios(policy_ids, sections_by_policy) or []
        scenarios = []
        for raw in raw_scenarios:
            findings = raw.get("policy_findings") or {}
            scenarios.append(
                Scenario(
                    name=str(raw.get("name") or ""),
                    policy_findings={pid: str(findings.get(pid) or "") for pid in policy_ids},
                    ressalva=SCENARIO_RESSALVA,  # ressalva fixa, sempre anexada
                )
            )
        return scenarios

    # --- conclusões (§9) -------------------------------------------------------

    def _build_conclusions(self, policy_ids, sections_by_policy) -> dict:
        raw = self._report_agent.build_conclusions(policy_ids, sections_by_policy) or {}
        return {key: raw.get(key, []) for key in CONCLUSION_KEYS}

    # --- porta de seções (duck-typing) ----------------------------------------

    def _load_sections(self, policy_id: str) -> list[dict]:
        source = self._sections_source
        get_evidences = getattr(source, "get_evidences", None)
        if callable(get_evidences):
            return [_section_from_evidence(policy_id, ev) for ev in get_evidences(policy_id)]
        get_markdown = getattr(source, "get_markdown_sections", None)
        if callable(get_markdown):
            return [
                _section_from_markdown(policy_id, item, index)
                for index, item in enumerate(get_markdown(policy_id), start=1)
            ]
        raise ClassifiedError(
            "SECTIONS_UNAVAILABLE",
            "sections_source sem get_evidences nem get_markdown_sections",
            retriable=False,
        )


# --- normalização das entradas do agente -------------------------------------


def _opt_str(value) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _parse_status(raw) -> CoverageStatus:
    """Aceita rótulo ("Previsto") ou nome do enum ("PREVISTO"); fora do
    vocabulário → `REQUER_CONFIRMACAO` (nunca status inventado)."""
    if isinstance(raw, CoverageStatus):
        return raw
    text = str(raw or "").strip()
    for status in CoverageStatus:
        if text == status.value or text.upper() == status.name:
            return status
    return CoverageStatus.REQUER_CONFIRMACAO


def _parse_origem(raw, status: CoverageStatus) -> str:
    text = str(raw or "").strip().lower()
    if text in VALID_ORIGENS:
        return text
    return "nao_localizado" if status is CoverageStatus.NAO_LOCALIZADO else "fato"


def _cell_from(raw: dict) -> ReportCell:
    """Monta a célula aplicando a guarda de rastreabilidade (§10): status
    diferente de "Não localizado" sem `referencia` vira "Requer confirmação"."""
    status = _parse_status(raw.get("status"))
    origem = _parse_origem(raw.get("origem"), status)
    referencia = _opt_str(raw.get("referencia"))
    if status is not CoverageStatus.NAO_LOCALIZADO and not referencia:
        status = CoverageStatus.REQUER_CONFIRMACAO
        origem = "requer_confirmacao"
    return ReportCell(
        status=status,
        limite_franquia=_opt_str(raw.get("limite_franquia")),
        exclusoes_condicoes=_opt_str(raw.get("exclusoes_condicoes")),
        impacto_pratico=_opt_str(raw.get("impacto_pratico")),
        impacto_financeiro=_opt_str(raw.get("impacto_financeiro")),
        referencia=referencia,
        origem=origem,
    )


def _iter_cell_payloads(payload):
    """Aceita {"cells": [...]}, {"cells": {code: {...}}} ou {code: {...}}."""
    if not payload:
        return []
    cells = payload.get("cells", payload) if isinstance(payload, dict) else payload
    if isinstance(cells, dict):
        return [dict(cell, field_code=code) for code, cell in cells.items()]
    return [cell for cell in cells if isinstance(cell, dict)]


def _identification_from(policy_id: str, raw: dict) -> DocumentIdentification:
    raw = raw or {}
    empresa = _opt_str(raw.get("empresa_aberta_fechada"))
    if empresa not in ("aberta", "fechada", "ambas"):
        empresa = None
    paginas = raw.get("num_paginas")
    ausentes = raw.get("ausentes")
    if isinstance(ausentes, (list, tuple)):
        ausentes = tuple(str(item) for item in ausentes)
    elif not isinstance(ausentes, str):
        ausentes = None
    return DocumentIdentification(
        policy_id=policy_id,
        seguradora=_opt_str(raw.get("seguradora")),
        produto=_opt_str(raw.get("produto")),
        processo_susep=_opt_str(raw.get("processo_susep")),
        versao_data=_opt_str(raw.get("versao_data")),
        publico_alvo=_opt_str(raw.get("publico_alvo")),
        empresa_aberta_fechada=empresa,
        secoes_natureza=tuple(str(item) for item in raw.get("secoes_natureza") or ()),
        num_paginas=int(paginas) if isinstance(paginas, int) else None,
        coberturas_descritas=tuple(str(item) for item in raw.get("coberturas_descritas") or ()),
        limitacoes=tuple(str(item) for item in raw.get("limitacoes") or ()),
        ausentes=ausentes,
    )


def _section_from_evidence(policy_id: str, evidence) -> dict:
    """`EvidenceRef` (ou objeto compatível) → seção de prompt com referência."""
    document_id = getattr(evidence, "document_id", "?")
    page = getattr(evidence, "page_number", "?")
    section_name = getattr(evidence, "section_name", None)
    source = f"doc {document_id} · pág. {page}" + (f" · seção {section_name}" if section_name else "")
    return {
        "policy_id": policy_id,
        "source": source,
        "text": str(getattr(evidence, "quoted_text", "") or ""),
        "evidence_id": getattr(evidence, "evidence_id", None),
    }


def _section_from_markdown(policy_id: str, item, index: int) -> dict:
    """Seção markdown (dict ou texto) → seção de prompt com referência."""
    if isinstance(item, dict):
        title = (
            item.get("title")
            or item.get("heading")
            or item.get("section_name")
            or f"seção {index}"
        )
        page = item.get("page_number")
        source = f"{title}" + (f" · pág. {page}" if page is not None else "")
        text = item.get("text") or item.get("content") or ""
        return {"policy_id": policy_id, "source": source, "text": str(text)}
    return {"policy_id": policy_id, "source": f"seção {index}", "text": str(item or "")}
