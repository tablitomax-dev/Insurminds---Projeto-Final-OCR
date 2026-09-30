"""EC-01/EC-04: carga e validação do conjunto de referência (RF-01)."""

import json

import pytest

from modules.evaluation.public_api import GOLDEN_SET_PATH, load_reference_set
from shared_kernel.errors import ContractValidationError


def test_golden_set_carregado_tem_2_apolices_x_10_campos():
    reference = load_reference_set(GOLDEN_SET_PATH)

    assert reference.reference_version == "golden-v1-sintetico"
    assert reference.oq_02 == "substring (ancoragem literal)"
    assert len(reference.cases) == 2
    total = sum(len(case.expected_facts) for case in reference.cases)
    assert total == 20
    for case in reference.cases:
        codes = [fact.field_code for fact in case.expected_facts]
        assert len(codes) == 10
        assert len(set(codes)) == 10
        assert all(fact.evidence_quote for fact in case.expected_facts)


def test_referencia_com_campo_repetido_eh_rejeitada(tmp_path):
    data = json.loads(GOLDEN_SET_PATH.read_text(encoding="utf-8"))
    data["cases"][0]["expected_facts"].append(dict(data["cases"][0]["expected_facts"][0]))
    path = tmp_path / "golden_ruim.json"
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(ContractValidationError):
        load_reference_set(path)  # EC-04: uniqueness por field_code


def test_referencia_found_sem_valor_eh_rejeitada(tmp_path):
    data = json.loads(GOLDEN_SET_PATH.read_text(encoding="utf-8"))
    data["cases"][0]["expected_facts"][0].pop("expected_value")
    path = tmp_path / "golden_sem_valor.json"
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(ContractValidationError) as excinfo:
        load_reference_set(path)  # EC-01: referência fora do contrato

    message = str(excinfo.value)
    assert "REFERENCE" in message
    assert "R$" not in message  # T-2a: payload nunca ecoa na mensagem
