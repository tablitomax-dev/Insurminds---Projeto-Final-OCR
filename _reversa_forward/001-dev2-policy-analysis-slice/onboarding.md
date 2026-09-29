# Onboarding: Vertical slice do policy_analysis

> Identificador: `001-dev2-policy-analysis-slice`
> Data: `2026-09-26`
> Para quem: humano que vai testar a feature pela primeira vez

## 1. Pré-requisitos

1. **Python 3.12+** instalado (verificar com `python --version`).
2. Git (para clonar/checkout da branch).
3. (Opcional) Chave de API do Gemini — só é necessária para rodar extração real; os testes não chamam LLM.

## 2. Preparação do ambiente

```powershell
cd Insurminds---Projeto-Final-OCR
git checkout feature/dev2-policy-analysis
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Se o `requirements.txt` ainda não listar as dependências do módulo (pydantic-ai, duckdb, fpdf2), instale com `pip install pydantic-ai duckdb fpdf2` — o plano prevê a atualização do `requirements.txt` na primeira ação de coding.

## 3. Configuração

1. Crie um `.env` na raiz (apenas para execução real, não para testes):

```text
GEMINI_API_KEY=<sua-chave>
```

2. Fixtures de evidência mockada já vêm em `tests/modules/policy_analysis/fixtures/` (apólices sintéticas — nenhum dado real).

## 4. Rodar os testes

```powershell
pytest tests/ -q
```

Esperado: suíte verde, incluindo os 67 testes de contrato da Fase 0 (`tests/contracts/`) e os novos testes do `policy_analysis`. Casos relevantes:
- determinismo da comparação (2 execuções → mesmo resultado);
- rejeição de `field_code` fora do catálogo;
- saída de LLM inválida nunca vira fato;
- fato FOUND sempre com `evidence_ids` reais.

## 5. Rodar o vertical slice de ponta a ponta (com evidências mockadas)

```powershell
$env:PYTHONPATH="src"
python -m modules.policy_analysis.demo
```

O script demonstração (entregue no coding) executa: extração dos 10 campos das 2 apólices fixture → comparação determinística → explicação por diferença → export do PDF.

1. Confira o terminal: `ComparisonId` e resultado por campo.
2. Abra o Markdown gerado em `exports/<ComparisonId>.md` — deve listar todos os 10 campos, inclusive ausentes, com evidência citada.

## 6. Testar com a fachada real do Dev 1 (quando disponível)

```powershell
$env:EVIDENCE_SOURCE="document_processing"
python -m src.modules.policy_analysis.demo
```

Apena a origem da evidência muda (RF-10); o restante do fluxo é idêntico.

## 7. Problemas comuns

| Sintoma | Causa provável | Ação |
|---------|----------------|------|
| `Python não foi encontrado` | Python não instalado (só o stub da Microsoft Store) | Instalar Python 3.12 e reabrir o terminal |
| Erro de import de `shared_kernel` | venv não ativado ou pytest fora da raiz | ativar venv e rodar na raiz do repo |
| `GEMINI_API_KEY ausente` | `.env` não criado | criar `.env` ou usar modo mock (`EVIDENCE_SOURCE=mock`, padrão) |
| Export não gera | pasta `exports/` inexistente | criada automaticamente pelo demo; checar permissão de escrita |