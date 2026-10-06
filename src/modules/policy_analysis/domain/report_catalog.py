"""Catálogo do Relatório D&O (metodologia de comparação de apólices).

Dado puro, sem lógica: é a ÚNICA fonte de vocabulário de status, categorias,
campos da matriz, critérios/pesos do ranking, cenários de sensibilidade e itens
do checklist final. Regras de vocabulário:

- `CoverageStatus` é o vocabulário FECHADO de status de contratação. O rótulo
  oficial para ausência é "Não localizado" — a expressão "não existe" é
  PROIBIDA em toda a cadeia (prompts, modelos, export).
- Toda célula com status diferente de `NAO_LOCALIZADO` exige referência
  documental (arquivo/página/seção) — guarda de rastreabilidade (§10).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class CoverageStatus(str, Enum):
    """Status de contratação de um campo num documento (vocabulário fechado)."""

    PREVISTO = "Previsto"
    EXCLUIDO = "Excluído"
    CONDICIONADO = "Condicionado"
    NAO_LOCALIZADO = "Não localizado"
    AMBIGUO = "Ambíguo"
    NAO_APLICAVEL = "Não aplicável"
    REQUER_CONFIRMACAO = "Requer confirmação"


class Importance(str, Enum):
    """Importância do campo na leitura comparativa da apólice."""

    CRITICA = "Crítica"
    ALTA = "Alta"
    MEDIA = "Média"
    COMPLEMENTAR = "Complementar"


@dataclass(frozen=True)
class ReportCategory:
    """Categoria da matriz principal do relatório (§5)."""

    code: str
    label: str


CATEGORIES: tuple[ReportCategory, ...] = (
    ReportCategory("estrutura_protecao", "Estrutura da proteção"),
    ReportCategory("gatilho_temporal", "Gatilho temporal"),
    ReportCategory("limites_exposicao", "Limites e exposição financeira"),
    ReportCategory("custos_defesa", "Custos de defesa e regulação"),
    ReportCategory("coberturas_extensoes", "Coberturas e extensões"),
    ReportCategory("exclusoes", "Exclusões"),
    ReportCategory("defesa_separabilidade", "Defesa, separabilidade e conflitos"),
    ReportCategory("procedimentos", "Procedimentos e obrigações"),
)


@dataclass(frozen=True)
class ReportField:
    """Campo da matriz principal do relatório."""

    code: str
    category: str
    label: str
    importance: Importance


REPORT_FIELDS: tuple[ReportField, ...] = (
    # §4.1 Estrutura da proteção
    ReportField(
        "protecao_direta_administrador_ab_side",
        "estrutura_protecao",
        "Proteção direta do administrador (A/B side)",
        Importance.CRITICA,
    ),
    ReportField("reembolso_empresa", "estrutura_protecao", "Reembolso da empresa (B side)", Importance.ALTA),
    ReportField(
        "protecao_sociedade_c_side",
        "estrutura_protecao",
        "Proteção da própria sociedade (C side)",
        Importance.ALTA,
    ),
    ReportField(
        "reclamacoes_empresa_entre_administradores",
        "estrutura_protecao",
        "Reclamação da empresa contra administrador e entre administradores",
        Importance.ALTA,
    ),
    ReportField(
        "reclamacoes_acionistas_entidades_externas",
        "estrutura_protecao",
        "Reclamações de acionistas e de entidades externas",
        Importance.ALTA,
    ),
    ReportField(
        "protecao_herdeiros_espolio_conjuge_representantes",
        "estrutura_protecao",
        "Proteção de herdeiros, espólio, cônjuge e representantes",
        Importance.MEDIA,
    ),
    ReportField(
        "administradores_atuais_anteriores_futuros",
        "estrutura_protecao",
        "Administradores atuais, anteriores e futuros",
        Importance.ALTA,
    ),
    ReportField(
        "empregados_procuradores_representantes",
        "estrutura_protecao",
        "Empregados, procuradores e representantes",
        Importance.MEDIA,
    ),
    ReportField(
        "subsidiarias_entidades_relacionadas",
        "estrutura_protecao",
        "Subsidiárias e entidades relacionadas",
        Importance.ALTA,
    ),
    # §4.2 Gatilho temporal
    ReportField(
        "base_ocorrencia_claims_made",
        "gatilho_temporal",
        "Base de ocorrência × base de reclamações (claims-made)",
        Importance.CRITICA,
    ),
    ReportField("retroatividade", "gatilho_temporal", "Retroatividade", Importance.CRITICA),
    ReportField("data_continuidade", "gatilho_temporal", "Data de continuidade", Importance.ALTA),
    ReportField(
        "atos_anteriores_circunstancias_conhecidas",
        "gatilho_temporal",
        "Atos anteriores e circunstâncias conhecidas",
        Importance.ALTA,
    ),
    ReportField(
        "prazos_complementares_contratacao",
        "gatilho_temporal",
        "Prazos complementar/suplementar/adicional e condições de contratação",
        Importance.ALTA,
    ),
    ReportField(
        "notificacao_quem_prazo_forma",
        "gatilho_temporal",
        "Notificação: quem, prazo, forma e efeito",
        Importance.CRITICA,
    ),
    ReportField(
        "transferencia_transformacao_troca_seguradora",
        "gatilho_temporal",
        "Transferência/transformação de apólice e troca de seguradora",
        Importance.MEDIA,
    ),
    ReportField(
        "cancelamento_nao_renovacao_run_off",
        "gatilho_temporal",
        "Cancelamento, não renovação e run-off",
        Importance.ALTA,
    ),
    ReportField(
        "fusao_aquisicao_mudanca_controle",
        "gatilho_temporal",
        "Fusão, aquisição e mudança de controle",
        Importance.ALTA,
    ),
    # §4.3 Limites e exposição financeira
    ReportField("lmg", "limites_exposicao", "Limite Máximo Garantido (LMG)", Importance.CRITICA),
    ReportField("lmi", "limites_exposicao", "Limite Máximo de Indenização (LMI)", Importance.CRITICA),
    ReportField("limite_agregado", "limites_exposicao", "Limite agregado", Importance.CRITICA),
    ReportField("sublimites", "limites_exposicao", "Sublimites", Importance.CRITICA),
    ReportField(
        "limites_compartilhados_independentes_adicionais",
        "limites_exposicao",
        "Limites compartilhados, independentes, adicionais e em excesso",
        Importance.ALTA,
    ),
    ReportField("reintegracao_limite", "limites_exposicao", "Reintegração do limite", Importance.ALTA),
    ReportField("custos_dentro_fora_limite", "limites_exposicao", "Custos dentro ou fora do limite", Importance.ALTA),
    ReportField("franquia", "limites_exposicao", "Franquia/deducível", Importance.CRITICA),
    ReportField(
        "participacao_obrigatoria",
        "limites_exposicao",
        "Participação obrigatória (mín/máx e responsabilidade)",
        Importance.ALTA,
    ),
    ReportField(
        "moeda_atualizacao_conversao_cambial",
        "limites_exposicao",
        "Moeda, atualização, conversão cambial e despesas de tradução",
        Importance.MEDIA,
    ),
    ReportField(
        "distribuicao_limite_encerramento_consumo",
        "limites_exposicao",
        "Distribuição do limite entre segurados e encerramento após consumo",
        Importance.ALTA,
    ),
    # §4.4 Custos de defesa e regulação
    ReportField("adiantamento_custos_defesa", "custos_defesa", "Adiantamento de custos de defesa", Importance.CRITICA),
    ReportField(
        "autorizacao_previa_despesas_emergenciais",
        "custos_defesa",
        "Autorização prévia e despesas emergenciais sem autorização",
        Importance.ALTA,
    ),
    ReportField(
        "escolha_advogado_rede_referenciada",
        "custos_defesa",
        "Livre escolha de advogado × rede referenciada",
        Importance.ALTA,
    ),
    ReportField(
        "custas_honorarios_periciais",
        "custos_defesa",
        "Custas, honorários advocatícios e periciais",
        Importance.ALTA,
    ),
    ReportField(
        "depositos_recursais_garantias_judiciais",
        "custos_defesa",
        "Depósitos recursais, seguro garantia judicial e fiança bancária",
        Importance.MEDIA,
    ),
    ReportField(
        "despesas_investigacao_previas",
        "custos_defesa",
        "Despesas de investigação e prévias à reclamação",
        Importance.ALTA,
    ),
    ReportField(
        "custos_especialistas_crise_publicidade",
        "custos_defesa",
        "Custos de especialistas e de crise/publicidade/proteção de imagem",
        Importance.MEDIA,
    ),
    ReportField(
        "alocacao_cobertos_nao_cobertos",
        "custos_defesa",
        "Alocação entre segurados cobertos e não cobertos",
        Importance.ALTA,
    ),
    ReportField(
        "acordo_consentimento_recusa",
        "custos_defesa",
        "Acordo judicial/extrajudicial, consentimento e recusa de acordo",
        Importance.ALTA,
    ),
    ReportField("devolucao_valores_adiantados", "custos_defesa", "Devolução de valores adiantados", Importance.MEDIA),
    ReportField(
        "dolo_fraude_culpa_grave_comprovados",
        "custos_defesa",
        "Dolo, fraude e culpa grave posteriormente comprovados",
        Importance.CRITICA,
    ),
    # §4.5 Coberturas e extensões
    ReportField(
        "investigacoes_internas_externas",
        "coberturas_extensoes",
        "Investigações internas e externas",
        Importance.ALTA,
    ),
    ReportField(
        "procedimentos_administrativos_reguladores_cvm",
        "coberturas_extensoes",
        "Procedimentos administrativos, órgãos reguladores, CVM e mercado de capitais",
        Importance.ALTA,
    ),
    ReportField(
        "custos_mitigacao_emergenciais",
        "coberturas_extensoes",
        "Custos de mitigação e emergenciais",
        Importance.MEDIA,
    ),
    ReportField(
        "bens_liberdade_extradicao_bloqueio",
        "coberturas_extensoes",
        "Bens, liberdade, extradição e bloqueio/penhora/indisponibilidade de bens",
        Importance.MEDIA,
    ),
    ReportField(
        "responsabilidade_tributaria_multas_penalidades",
        "coberturas_extensoes",
        "Responsabilidade tributária, multas e penalidades",
        Importance.ALTA,
    ),
    ReportField("tac_termo_compromisso", "coberturas_extensoes", "TAC/termo de compromisso", Importance.MEDIA),
    ReportField(
        "praticas_trabalhistas_danos_morais",
        "coberturas_extensoes",
        "Práticas trabalhistas e danos morais",
        Importance.ALTA,
    ),
    ReportField("dano_ambiental", "coberturas_extensoes", "Dano ambiental", Importance.MEDIA),
    ReportField(
        "responsabilidade_profissional_advogados_internos",
        "coberturas_extensoes",
        "Responsabilidade profissional e advogados internos",
        Importance.MEDIA,
    ),
    ReportField(
        "evento_cibernetico_ativos_digitais_ia",
        "coberturas_extensoes",
        "Evento cibernético, ativos digitais e inteligência artificial",
        Importance.ALTA,
    ),
    ReportField("entidades_externas", "coberturas_extensoes", "Entidades externas", Importance.MEDIA),
    ReportField(
        "previdencia_complementar_gestoras_ofertas_publicas",
        "coberturas_extensoes",
        "Previdência complementar, gestoras de fundos e ofertas públicas",
        Importance.MEDIA,
    ),
    ReportField(
        "programa_internacional_eua_canada",
        "coberturas_extensoes",
        "Programa internacional / EUA e Canadá / apólice internacional",
        Importance.ALTA,
    ),
    ReportField(
        "cosseguro_lideranca_subsidiarias_novas",
        "coberturas_extensoes",
        "Cosseguro, liderança e subsidiárias novas",
        Importance.COMPLEMENTAR,
    ),
    ReportField(
        "gerenciamento_crise_suporte_administrador",
        "coberturas_extensoes",
        "Gerenciamento de crise e suporte ao administrador (inabilitação e recolocação)",
        Importance.MEDIA,
    ),
    ReportField(
        "aposentados_demissoes_voluntarias",
        "coberturas_extensoes",
        "Aposentados e demissões voluntárias",
        Importance.COMPLEMENTAR,
    ),
    ReportField(
        "garantias_pessoais",
        "coberturas_extensoes",
        "Garantias pessoais (aval, fiança, garantia real)",
        Importance.MEDIA,
    ),
    ReportField(
        "limite_adicional_excesso",
        "coberturas_extensoes",
        "Limite adicional para certos administradores e cobertura em excesso",
        Importance.MEDIA,
    ),
    # §4.6 Exclusões
    ReportField("exclusao_dolo", "exclusoes", "Dolo", Importance.CRITICA),
    ReportField("exclusao_fraude", "exclusoes", "Fraude", Importance.CRITICA),
    ReportField("exclusao_culpa_grave", "exclusoes", "Culpa grave", Importance.CRITICA),
    ReportField(
        "exclusao_vantagem_indevida_atos_conscientes",
        "exclusoes",
        "Vantagem indevida/atos lesivos contra a administração pública ou privada e atos conscientes",
        Importance.ALTA,
    ),
    ReportField(
        "exclusao_reclamacoes_entre_segurados_sociedade",
        "exclusoes",
        "Reclamações entre segurados e da sociedade",
        Importance.ALTA,
    ),
    ReportField(
        "exclusao_acionista_majoritario_insolvencia",
        "exclusoes",
        "Acionista majoritário, insolvência, falência e recuperação judicial",
        Importance.ALTA,
    ),
    ReportField(
        "exclusao_preco_aquisicao_emprestimos",
        "exclusoes",
        "Preço inadequado de aquisição, empréstimos e financiamentos",
        Importance.MEDIA,
    ),
    ReportField("exclusao_anticorrenciais", "exclusoes", "Condutas anticoncorrenciais", Importance.ALTA),
    ReportField(
        "exclusao_nao_provisionamento_ativos_digitais_ia",
        "exclusoes",
        "Não provisionamento, ativos digitais e IA",
        Importance.MEDIA,
    ),
    ReportField(
        "exclusao_sancoes_embargos_territorios",
        "exclusoes",
        "Sanções, embargos e territórios restritos (Rússia/Bielorrússia/Venezuela)",
        Importance.ALTA,
    ),
    ReportField(
        "exclusao_doenca_transmissivel_danos_corporais",
        "exclusoes",
        "Doença transmissível, danos corporais e materiais",
        Importance.ALTA,
    ),
    ReportField(
        "exclusao_responsabilidade_profissional_poluicao",
        "exclusoes",
        "Responsabilidade profissional e poluição/dano ambiental",
        Importance.MEDIA,
    ),
    ReportField(
        "exclusao_reclamacoes_anteriores_fatos_conhecidos",
        "exclusoes",
        "Reclamações anteriores e fatos conhecidos",
        Importance.ALTA,
    ),
    ReportField(
        "exclusao_contratos_obrigacoes_assumidas",
        "exclusoes",
        "Contratos e obrigações assumidas",
        Importance.ALTA,
    ),
    ReportField("exclusao_questoes_trabalhistas", "exclusoes", "Questões trabalhistas", Importance.ALTA),
    ReportField(
        "exclusao_questoes_tributarias_criminais",
        "exclusoes",
        "Questões tributárias e criminais",
        Importance.ALTA,
    ),
    # §4.7 Defesa, separabilidade e conflitos
    ReportField(
        "divisibilidade_separacao_condutas",
        "defesa_separabilidade",
        "Divisibilidade/separação de declarações e separação de condutas",
        Importance.ALTA,
    ),
    ReportField(
        "imputacao_conhecimento_segurados_inocentes",
        "defesa_separabilidade",
        "Imputação de conhecimento e proteção de segurados inocentes",
        Importance.ALTA,
    ),
    ReportField(
        "conflitos_escolha_advogados",
        "defesa_separabilidade",
        "Conflitos administrador × sociedade/entre administradores e escolha/substituição de advogados",
        Importance.ALTA,
    ),
    ReportField(
        "prioridade_pagamento_alocacao_limite_insuficiente",
        "defesa_separabilidade",
        "Prioridade de pagamento, alocação e ordem de pagamento com limite insuficiente",
        Importance.ALTA,
    ),
    ReportField(
        "subrogacao_direito_regresso",
        "defesa_separabilidade",
        "Sub-rogação e direito de regresso",
        Importance.MEDIA,
    ),
    ReportField(
        "pagamento_direto_vs_reembolso",
        "defesa_separabilidade",
        "Pagamento direto ao administrador × reembolso à sociedade",
        Importance.ALTA,
    ),
    # §4.8 Procedimentos e obrigações
    ReportField("prazo_aviso_sinistro", "procedimentos", "Prazo de aviso de sinistro", Importance.CRITICA),
    ReportField(
        "prazo_notificacao_circunstancias",
        "procedimentos",
        "Prazo de notificação de circunstâncias",
        Importance.CRITICA,
    ),
    ReportField(
        "meio_comunicacao_documentos_exigidos",
        "procedimentos",
        "Meio de comunicação e documentos exigidos",
        Importance.MEDIA,
    ),
    ReportField("cooperacao_segurado", "procedimentos", "Cooperação do segurado", Importance.ALTA),
    ReportField("autorizacao_acordo_despesas", "procedimentos", "Autorização para acordo e despesas", Importance.ALTA),
    ReportField(
        "agravamento_risco_perda_direitos",
        "procedimentos",
        "Agravamento do risco e perda de direitos",
        Importance.ALTA,
    ),
    ReportField(
        "inadimplemento_premio_cancelamento_rescisao",
        "procedimentos",
        "Inadimplemento do prêmio, cancelamento e rescisão",
        Importance.ALTA,
    ),
    ReportField("prescricao_foro_arbitragem", "procedimentos", "Prescrição, foro e arbitragem", Importance.ALTA),
    ReportField(
        "confidencialidade_dados_sancoes_economicas",
        "procedimentos",
        "Confidencialidade, proteção de dados e sanções econômicas",
        Importance.MEDIA,
    ),
    ReportField("territorialidade_jurisdicao", "procedimentos", "Territorialidade e jurisdição", Importance.ALTA),
)

#: Índice de campo por `code` (conveniência de leitura; dado derivado estático).
FIELDS_BY_CODE: dict[str, ReportField] = {field.code: field for field in REPORT_FIELDS}

#: Critérios do ranking informativo (§8): código, rótulo, peso e justificativa.
@dataclass(frozen=True)
class RankingCriterion:
    """Critério do ranking informativo (§8), com peso e justificativa."""

    code: str
    label: str
    weight: float
    justificativa: str


RANKING_CRITERIA: tuple[RankingCriterion, ...] = (
    RankingCriterion(
        "protecao_individual",
        "Proteção individual",
        25.0,
        "A proteção direta do administrador (A/B side) é o núcleo da apólice D&O.",
    ),
    RankingCriterion(
        "custos_defesa",
        "Custos de defesa",
        15.0,
        "Custos de defesa podem consumir o limite e mudar a utilidade prática da cobertura.",
    ),
    RankingCriterion(
        "alcance_temporal",
        "Alcance temporal",
        15.0,
        "Claims-made, retroatividade e notificação definem se a reclamação é coberta.",
    ),
    RankingCriterion(
        "limites_exposicao",
        "Limites e exposição financeira",
        15.0,
        "LMG, LMI, limite agregado, sublimites e franquia dimensionam a exposição real.",
    ),
    RankingCriterion(
        "exclusoes_criticas",
        "Exclusões críticas",
        15.0,
        "Exclusões de dolo, fraude e culpa grave afetam o núcleo da proteção do administrador.",
    ),
    RankingCriterion(
        "cobertura_sociedade",
        "Cobertura da sociedade e reembolso",
        5.0,
        "Cobertura da sociedade (C side) e reembolso (B side) ampliam quem é protegido.",
    ),
    RankingCriterion(
        "extensoes",
        "Extensões",
        5.0,
        "Extensões agregam valor, mas nunca podem ser presumidas como contratadas.",
    ),
    RankingCriterion(
        "procedimentos",
        "Procedimentos e obrigações",
        5.0,
        "Prazos e obrigações operacionais determinam a preservação ou a perda de direitos.",
    ),
)

# NOTA DE RECONCILIAÇÃO: os pesos nominais indicados na metodologia
# (protecao_individual 25, custos_defesa 15, alcance_temporal 15,
# limites_exposicao 15, exclusoes_criticas 15, cobertura_sociedade 10,
# extensoes 5, procedimentos 5) somam 105, enquanto `compute_ranking` exige
# soma 100 (±0.01). Para fechar a escala, `cobertura_sociedade` fica 5 (a
# metodologia indica 10); os demais pesos seguem exatamente a metodologia.
DEFAULT_WEIGHTS: dict[str, float] = {criterion.code: criterion.weight for criterion in RANKING_CRITERIA}


@dataclass(frozen=True)
class SensitivityScenario:
    """Cenário de sensibilidade do ranking: nome e pesos alternativos (§8)."""

    name: str
    weights: dict[str, float]


SENSITIVITY_SCENARIOS: tuple[SensitivityScenario, ...] = (
    SensitivityScenario(
        "Proteção individual elevada",
        {
            "protecao_individual": 35.0,
            "custos_defesa": 15.0,
            "alcance_temporal": 15.0,
            "limites_exposicao": 15.0,
            "exclusoes_criticas": 15.0,
            "cobertura_sociedade": 5.0,
            "extensoes": 0.0,
            "procedimentos": 5.0,
        },
    ),
    SensitivityScenario(
        "Exclusões críticas",
        {
            "protecao_individual": 25.0,
            "custos_defesa": 15.0,
            "alcance_temporal": 15.0,
            "limites_exposicao": 15.0,
            "exclusoes_criticas": 25.0,
            "cobertura_sociedade": 5.0,
            "extensoes": 5.0,
            "procedimentos": 0.0,
        },
    ),
)

#: Itens da verificação final (§11), na ordem canônica do checklist.
CHECKLIST_ITEMS: tuple[str, ...] = (
    "documentos analisados integralmente",
    "condições particulares incluídas",
    "extensões não tratadas como automaticamente contratadas",
    "LMG, LMI, limite agregado e sublimites diferenciados",
    "custos de defesa avaliados separadamente",
    "claims made e notificações comparados",
    "exclusões com reembolso de defesa distinguidas de exclusões integrais",
    "cobertura do administrador e da sociedade não confundidas",
    "diferenças entre empresa aberta e fechada consideradas",
    "documentos ausentes explicitamente listados",
    "sem conclusão financeira sem dados financeiros",
    "nenhuma lacuna preenchida por suposição de prática de mercado",
    "módulo de ranking apresentado com critérios, pesos e pergunta sobre alterações",
    "análise agnóstica em relação a seguradoras e número de propostas",
)
