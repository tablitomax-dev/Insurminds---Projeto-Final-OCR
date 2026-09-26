"""Configuração comum dos testes: garante `tests/` no sys.path para importar `fakes`."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
