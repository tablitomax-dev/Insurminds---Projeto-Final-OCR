"""Agentes LLM do Relatório D&O (padrão de `infrastructure/llm_agent.py`).

Prompts versionados (`*_PROMPT_VERSION` + `prompt_fingerprint` para diff
auditável), execução com retry/backoff (`_with_retries`), registro de uso com
kind novo `"report"` (`_record_usage`) e provedor real `PydanticAIClient` via
`complete_json`. `FixtureReportAgent` roda sem rede (testes e demo offline).

Regras obrigatórias em todos os prompts: exigir referência documental
(arquivo/página/seção) em toda célula; usar SOMENTE o vocabulário de status;
PROIBIDO "não existe" (usar "Não localizado"); nunca afirmar aceitação de
cobertura em cenários; dinheiro como número simples (ex.: 2000000.00).
"""

from __future__ import annotations

import time
from typing import Any, Protocol

from ..domain.report import CONCLUSION_KEYS
from ..domain.report_catalog import (
    RANKING_CRITERIA,
    REPORT_FIELDS,
    CoverageStatus,
    Importance,
    RankingCriterion,
    ReportCategory,
    ReportField,
)
from .llm_agent import (
    LLMClient,
    _parse_structured,
    _record_usage,
    _with_retries,
    prompt_fingerprint,
)

# D2-P2-2: prompts versionados — ao alterar um build_*_prompt, bumpar a versão
# correspondente (diff auditável + re-execução do golden set).
IDENTIFY_PROMPT_VERSION = "report-identify-v1"
FILL_PROMPT_VERSION = "report-fill-v1"
TABLES_PROMPT_VERSION = "report-tables-v1"
SCENARIOS_PROMPT_VERSION = "report-scenarios-v1"
SCORES_PROMPT_VERSION = "report-scores-v1"
CONCLUSIONS_PROMPT_VERSION = "report-conclusions-v1"

#: Novo tipo de chamada instrumentada em métricas de uso do LLM.
KIND_REPORT = "report"

#: Regras de vocabulário que todo prompt do relatório repete (§10).
_VOCABULARIO = [
    '"status" SOMENTE um destes rótulos: ' + ", ".join(status.value for status in CoverageStatus) + ".",
    'PROIBIDO escrever "não existe" — para ausência use "Não localizado".',
    '"referencia" (arquivo/página/seção) é OBRIGATÓRIA em toda célula com status',
    'diferente de "Não localizado"; sem lastro documental use status "Requer confirmação".',
    '"origem" é um de: fato, interpretacao, inferencia, nao_localizado, requer_confirmacao.',
    "Valores em dinheiro sempre como número simples (ex.: 2000000.00), sem símbolo de moeda.",
]


class ReportAgent(Protocol):
    """Porta do agente de relatório (duck-typing com `LLMReportAgent`/`FixtureReportAgent`)."""

    def identify(self, policy_id: str, sections: list[dict]) -> dict: ...

    def fill_category(
        self, category: ReportCategory, fields: tuple[ReportField, ...], sections: list[dict]
    ) -> dict: ...

    def fill_tables(self, policy_ids: list[str], sections_by_policy: dict) -> list: ...

    def build_scenarios(self, policy_ids: list[str], sections_by_policy: dict) -> list: ...

    def score_criteria(self, policy_ids: list[str], sections_by_policy: dict) -> dict: ...

    def build_conclusions(self, policy_ids: list[str], sections_by_policy: dict) -> dict: ...


# --- prompts versionados ------------------------------------------------------


def _render_sections(sections: list[dict] | None) -> list[str]:
    lines = []
    for section in sections or []:
        source = section.get("source") or "seção"
        text = str(section.get("text") or "").strip()
        lines.append(f"- [{source}] {text or '(sem texto)'}")
    return lines or ["(sem seções recuperadas)"]


def _render_documents(policy_ids, sections_by_policy) -> list[str]:
    lines: list[str] = []
    for policy_id in policy_ids:
        lines.append(f"## Documento {policy_id}")
        lines.extend(_render_sections(sections_by_policy.get(policy_id)))
        lines.append("")
    return lines


def build_identify_prompt(policy_id: str, sections: list[dict]) -> str:
    """Prompt de identificação do documento (§1): dados de capa e ausentes."""
    lines = [
        "Você monta a identificação de um documento de apólice de seguro D&O para o Relatório D&O.",
        "Use SOMENTE o conteúdo das seções fornecidas; o que não aparecer deve ser null — nunca invente.",
        'PROIBIDO escrever "não existe" — para ausência use "Não localizado" ou null.',
        "Responda SOMENTE com JSON com as chaves:",
        "policy_id, seguradora, produto, processo_susep, versao_data, publico_alvo,",
        'empresa_aberta_fechada ("aberta"|"fechada"|"ambas"|null), secoes_natureza (lista),',
        "num_paginas (inteiro|null), coberturas_descritas (lista), limitacoes (lista), ausentes (lista).",
        "Em \"ausentes\" liste explicitamente os documentos/condições mencionados como ausentes.",
        "",
        f"## Documento {policy_id}",
        *_render_sections(sections),
    ]
    return "\n".join(lines)


def build_fill_prompt(
    category: ReportCategory, fields: tuple[ReportField, ...], sections: list[dict]
) -> str:
    """Prompt de preenchimento da matriz: uma categoria por chamada (map/reduce)."""
    lines = [
        f"Você preenche a matriz de comparação do Relatório D&O — categoria: {category.label} ({category.code}).",
        "Para CADA campo da lista devolva UMA célula. Responda SOMENTE com JSON {\"cells\": [...]}.",
        'Cada célula: {"field_code", "status", "limite_franquia", "exclusoes_condicoes",',
        '"impacto_pratico", "impacto_financeiro", "referencia", "origem"}.',
        *_VOCABULARIO,
        "Nunca afirme que a cobertura será aceita pela seguradora; descreva o que o documento prevê.",
        "",
        "## Campos da categoria",
    ]
    for field in fields:
        lines.append(f"- {field.code}: {field.label} (importância: {field.importance.value})")
    lines.append("")
    lines.append("## Seções do documento")
    lines.extend(_render_sections(sections))
    return "\n".join(lines)


def build_tables_prompt(policy_ids: list[str], sections_by_policy: dict) -> str:
    """Prompt das 5 tabelas especiais (§6)."""
    lines = [
        "Você monta as tabelas especiais do Relatório D&O a partir das seções fornecidas.",
        'Responda SOMENTE com JSON {"tables": [{"code", "title", "rows": [{"label", "cells": {...}}]}]}.',
        "Exatamente 5 tabelas, uma por code:",
        "- pessoas_protegidas — Pessoas protegidas (quem é coberto)",
        "- limites — Limites, sublimites e franquias",
        "- matriz_temporal — Matriz temporal (claims-made, retroatividade, notificação)",
        "- exclusoes_criticas — Exclusões críticas",
        "- coberturas_sociedade — Cobertura da sociedade e reembolso",
        'Em "cells", uma entrada por documento ({policy_id: texto|null}).',
        *_VOCABULARIO,
        "",
        *_render_documents(policy_ids, sections_by_policy),
    ]
    return "\n".join(lines)


def build_scenarios_prompt(policy_ids: list[str], sections_by_policy: dict) -> str:
    """Prompt dos cenários hipotéticos (§7) — sem afirmar aceitação."""
    lines = [
        "Você descreve cenários hipotéticos de sinistro para o Relatório D&O.",
        'Responda SOMENTE com JSON {"scenarios": [{"name", "policy_findings": {policy_id: texto}}]}.',
        "Gere 3 cenários realistas; para cada um, diga o que cada documento responderia.",
        "NUNCA afirme que a cobertura será aceita pela seguradora — trate tudo como cenário",
        "hipotético, sujeito a análise do sinistro, interpretação contratual e aceitação.",
        *_VOCABULARIO,
        "",
        *_render_documents(policy_ids, sections_by_policy),
    ]
    return "\n".join(lines)


def build_scores_prompt(
    criteria: tuple[RankingCriterion, ...], policy_ids: list[str], sections_by_policy: dict
) -> str:
    """Prompt das notas por critério do ranking informativo (§8)."""
    lines = [
        "Você pontua apólices D&O nos critérios do ranking informativo do Relatório D&O.",
        'Responda SOMENTE com JSON {"notes": {policy_id: {criterio: nota}}}.',
        "Notas de 0 a 10 (número simples, ex.: 7.5); pondere apenas o que os documentos sustentam.",
        "Critérios:",
    ]
    for criterion in criteria:
        lines.append(f"- {criterion.code}: {criterion.label} (peso {criterion.weight}) — {criterion.justificativa}")
    lines.append("")
    lines.extend(_render_documents(policy_ids, sections_by_policy))
    return "\n".join(lines)


def build_conclusions_prompt(policy_ids: list[str], sections_by_policy: dict) -> str:
    """Prompt das conclusões (§9): diferenças, riscos, negociação e pendências."""
    lines = [
        "Você escreve as conclusões do Relatório D&O a partir dos documentos analisados.",
        "Responda SOMENTE com JSON com as chaves:",
        '"5_diferencas" (lista das 5 diferenças mais relevantes), "5_riscos" (lista dos 5 riscos),',
        '"vantagens" e "desvantagens" (objeto por documento), "nao_comparaveis" (lista de itens',
        'não comparáveis entre os documentos), "negociaveis" (lista de itens negociáveis),',
        '"perguntas_corretor" (lista de perguntas para o corretor), "documentos_adicionais"',
        "(lista de documentos a solicitar).",
        "Não conclua nada sobre preço/prêmio sem dado financeiro nos documentos.",
        'PROIBIDO escrever "não existe" — para ausência use "Não localizado".',
        "",
        *_render_documents(policy_ids, sections_by_policy),
    ]
    return "\n".join(lines)


# --- agente real ---------------------------------------------------------------


class LLMReportAgent:
    """Agente do Relatório D&O sobre um `LLMClient` (ex.: `PydanticAIClient`)."""

    def __init__(
        self,
        client: LLMClient,
        retries: int = 3,
        backoff: float = 1.0,
        usage_collector=None,
    ):
        self._client = client
        self._retries = retries
        self._backoff = backoff
        self._usage_collector = usage_collector
        self.usage: list[dict] = []

    def identify(self, policy_id: str, sections: list[dict]) -> dict:
        return self._run(
            build_identify_prompt(policy_id, sections),
            "identify",
            IDENTIFY_PROMPT_VERSION,
            dict,
        )

    def fill_category(
        self, category: ReportCategory, fields: tuple[ReportField, ...], sections: list[dict]
    ) -> dict:
        return self._run(
            build_fill_prompt(category, fields, sections),
            f"fill:{category.code}",
            FILL_PROMPT_VERSION,
            dict,
        )

    def fill_tables(self, policy_ids: list[str], sections_by_policy: dict) -> list:
        raw = self._run(
            build_tables_prompt(policy_ids, sections_by_policy),
            "tables",
            TABLES_PROMPT_VERSION,
            dict,
        )
        return _list_from(raw, "tables")

    def build_scenarios(self, policy_ids: list[str], sections_by_policy: dict) -> list:
        raw = self._run(
            build_scenarios_prompt(policy_ids, sections_by_policy),
            "scenarios",
            SCENARIOS_PROMPT_VERSION,
            dict,
        )
        return _list_from(raw, "scenarios")

    def score_criteria(self, policy_ids: list[str], sections_by_policy: dict) -> dict:
        raw = self._run(
            build_scores_prompt(RANKING_CRITERIA, policy_ids, sections_by_policy),
            "scores",
            SCORES_PROMPT_VERSION,
            dict,
        )
        notes = raw.get("notes", raw)
        return notes if isinstance(notes, dict) else {}

    def build_conclusions(self, policy_ids: list[str], sections_by_policy: dict) -> dict:
        return self._run(
            build_conclusions_prompt(policy_ids, sections_by_policy),
            "conclusions",
            CONCLUSIONS_PROMPT_VERSION,
            dict,
        )

    def _run(self, prompt: str, operation: str, version: str, expected: type) -> Any:
        started = time.monotonic()
        raw = _with_retries(
            lambda: self._client.complete_json(prompt), self._retries, self._backoff
        )
        _record_usage(self._usage_collector, self._client, f"report:{operation}", KIND_REPORT, started)
        self.usage.append(
            {
                "operation": operation,
                "prompt_chars": len(prompt),
                "prompt_version": version,
                "prompt_hash": prompt_fingerprint(prompt),
            }
        )
        return _parse_structured(raw, expected)


def _list_from(raw: Any, key: str) -> list:
    if isinstance(raw, dict):
        raw = raw.get(key, [])
    return raw if isinstance(raw, list) else []


# --- agente fixture (offline) --------------------------------------------------


_BASE_NOTES: dict[str, float] = {
    "protecao_individual": 8.0,
    "custos_defesa": 7.0,
    "alcance_temporal": 7.0,
    "limites_exposicao": 7.5,
    "exclusoes_criticas": 6.5,
    "cobertura_sociedade": 7.0,
    "extensoes": 6.0,
    "procedimentos": 7.0,
}


class FixtureReportAgent:
    """Agente de relatório determinístico para testes e demo offline (sem rede)."""

    def __init__(
        self,
        identifications: dict | None = None,
        cells: dict | None = None,
        tables: list | None = None,
        scenarios: list | None = None,
        notes: dict | None = None,
        conclusions: dict | None = None,
    ):
        self._identifications = identifications or {}
        self._cells = cells or {}
        self._tables = tables
        self._scenarios = scenarios
        self._notes = notes
        self._conclusions = conclusions
        self._field_index = {field.code: index for index, field in enumerate(REPORT_FIELDS)}
        self.calls = 0

    def identify(self, policy_id: str, sections: list[dict]) -> dict:
        self.calls += 1
        if policy_id in self._identifications:
            return dict(self._identifications[policy_id])
        suffix = len(policy_id)  # determinístico por apólice
        return {
            "policy_id": policy_id,
            "seguradora": f"Seguradora {policy_id}",
            "produto": "Responsabilidade Civil de Administradores (D&O)",
            "processo_susep": f"{10000 + suffix}/2025",
            "versao_data": "01/2025",
            "publico_alvo": "administradores, conselheiros e oficiais",
            "empresa_aberta_fechada": "ambas",
            "secoes_natureza": ["condições gerais", "condições particulares"],
            "num_paginas": 40 + suffix,
            "coberturas_descritas": ["proteção direta do administrador (A/B side)", "reembolso à empresa (B side)"],
            "limitacoes": ["sublimites por reclamação"],
            "ausentes": ["endosso de run-off"],
        }

    def fill_category(
        self, category: ReportCategory, fields: tuple[ReportField, ...], sections: list[dict]
    ) -> dict:
        self.calls += 1
        policy_id = _policy_hint(sections)
        cells = []
        for field in fields:
            cell = self._default_cell(policy_id, field)
            cell.update(self._cells.get(policy_id, {}).get(field.code, {}))
            cells.append(dict(cell, field_code=field.code))
        return {"cells": cells}

    def fill_tables(self, policy_ids: list[str], sections_by_policy: dict) -> list:
        self.calls += 1
        if self._tables is not None:
            return list(self._tables)
        return [
            {
                "code": "pessoas_protegidas",
                "title": "Pessoas protegidas",
                "rows": [
                    {"label": label, "cells": {pid: f"{label} — previsto em {pid}" for pid in policy_ids}}
                    for label in (
                        "Administradores atuais, anteriores e futuros",
                        "Empregados, procuradores e representantes",
                        "Herdeiros, espólio, cônjuge e representantes",
                        "Subsidiárias e entidades relacionadas",
                    )
                ],
            },
            {
                "code": "limites",
                "title": "Limites, sublimites e franquias",
                "rows": [
                    {"label": label, "cells": {pid: value for pid in policy_ids}}
                    for label, value in (
                        ("LMG", "2000000.00"),
                        ("LMI", "1500000.00"),
                        ("Limite agregado", "4000000.00"),
                        ("Sublimites", "500000.00"),
                        ("Franquia", "100000.00"),
                    )
                ],
            },
            {
                "code": "matriz_temporal",
                "title": "Matriz temporal",
                "rows": [
                    {"label": label, "cells": {pid: f"{label} — registrado em {pid}" for pid in policy_ids}}
                    for label in (
                        "Base de reclamações (claims-made)",
                        "Retroatividade",
                        "Prazo de notificação",
                        "Run-off",
                    )
                ],
            },
            {
                "code": "exclusoes_criticas",
                "title": "Exclusões críticas",
                "rows": [
                    {"label": label, "cells": {pid: f"{label} — excluído em {pid}" for pid in policy_ids}}
                    for label in ("Dolo", "Fraude", "Culpa grave", "Sanções e embargos")
                ],
            },
            {
                "code": "coberturas_sociedade",
                "title": "Cobertura da sociedade e reembolso",
                "rows": [
                    {"label": label, "cells": {pid: f"{label} — previsto em {pid}" for pid in policy_ids}}
                    for label in (
                        "Proteção da sociedade (C side)",
                        "Reembolso à empresa (B side)",
                        "Pagamento direto ao administrador",
                    )
                ],
            },
        ]

    def build_scenarios(self, policy_ids: list[str], sections_by_policy: dict) -> list:
        self.calls += 1
        if self._scenarios is not None:
            return list(self._scenarios)
        return [
            {
                "name": "Investigação conduzida por órgão regulador",
                "policy_findings": {
                    pid: (
                        f"Em {pid}, a resposta depende da extensão de procedimentos administrativos "
                        "e do adiantamento de custos."
                    )
                    for pid in policy_ids
                },
            },
            {
                "name": "Reclamação de acionista após venda da companhia",
                "policy_findings": {
                    pid: (
                        f"Em {pid}, a resposta depende da base claims-made, da retroatividade "
                        "e das exclusões de reclamações entre segurados."
                    )
                    for pid in policy_ids
                },
            },
        ]

    def score_criteria(self, policy_ids: list[str], sections_by_policy: dict) -> dict:
        self.calls += 1
        if self._notes is not None:
            return {pid: dict(self._notes.get(pid, {})) for pid in policy_ids}
        return {
            pid: {
                code: round(value - 0.25 * index, 2)  # determinístico por posição
                for code, value in _BASE_NOTES.items()
            }
            for index, pid in enumerate(policy_ids)
        }

    def build_conclusions(self, policy_ids: list[str], sections_by_policy: dict) -> dict:
        self.calls += 1
        if self._conclusions is not None:
            data = dict(self._conclusions)
        else:
            docs = ", ".join(policy_ids)
            data = {
                "5_diferencas": [
                    f"Diferença {index} entre os documentos analisados ({docs})." for index in range(1, 6)
                ],
                "5_riscos": [
                    f"Risco {index} identificado a partir dos documentos analisados ({docs})." for index in range(1, 6)
                ],
                "vantagens": {pid: f"Pontos fortes observados em {pid}." for pid in policy_ids},
                "desvantagens": {pid: f"Pontos de atenção observados em {pid}." for pid in policy_ids},
                "nao_comparaveis": ["Condições particulares ausentes em parte dos documentos."],
                "negociaveis": ["Sublimites e franquias podem ser negociados com a seguradora."],
                "perguntas_corretor": ["Há endossos de run-off disponíveis para contratação?"],
                "documentos_adicionais": ["Condições particulares completas e endossos."],
            }
        return {key: data.get(key, []) for key in CONCLUSION_KEYS}

    def _default_cell(self, policy_id: str, field: ReportField) -> dict:
        index = self._field_index[field.code]
        if field.importance is Importance.COMPLEMENTAR:
            return {"status": CoverageStatus.NAO_LOCALIZADO.value, "origem": "nao_localizado"}
        cell = {
            "status": CoverageStatus.PREVISTO.value,
            "origem": "fato",
            "limite_franquia": None,
            "exclusoes_condicoes": None,
            "impacto_pratico": f"Tratamento de {field.label} observado em {policy_id}.",
            "impacto_financeiro": f"Exposição de {field.label} considerada no ranking informativo.",
            "referencia": f"{policy_id}.pdf · pág. {10 + index % 30} · seção {field.category}",
        }
        if field.category == "limites_exposicao":
            cell["limite_franquia"] = f"{2000000.0 + (index % 5) * 500000:.2f}"
        if field.category == "exclusoes":
            cell["exclusoes_condicoes"] = (
                "Com reembolso de custos de defesa quando a exclusão não for integral."
            )
        return cell


def _policy_hint(sections: list[dict]) -> str:
    """Extrai o `policy_id` do cabeçalho de seções do fixture (determinístico).

    O `FixtureReportAgent` recebe as seções já rotuladas pelo serviço
    (`[doc POL-A · pág. ...]`); sem rótulo, usa o literal "POL?".
    """
    for section in sections or []:
        source = str(section.get("source") or "")
        marker = section.get("policy_id")
        if marker:
            return str(marker)
        if source.startswith("doc "):
            return source.split("·")[0].replace("doc ", "").strip()
    return "POL?"
