"""Uploads temporários da UI em diretório controlado do projeto (T-2b).

Antes o Streamlit gravava em `%TEMP%\\apolice_*` e nunca apagava. Agora o
upload vai para `.tmp/uploads/` (raiz do projeto) e é removido ao fim do
processamento — nada persiste depois do fluxo.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

#: Diretório controlado de uploads temporários (raiz do projeto).
UPLOAD_DIR = Path(".tmp") / "uploads"


def save_upload(
    name: str, data: bytes | bytearray | memoryview, base_dir: Path | None = None
) -> Path:
    """Grava o upload no diretório controlado, com nome de arquivo seguro."""
    directory = base_dir if base_dir is not None else UPLOAD_DIR
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / Path(name).name
    path.write_bytes(bytes(data))
    return path


def cleanup_uploads(paths: Iterable[Path], base_dir: Path | None = None) -> None:
    """Remove os arquivos enviados no fluxo e o diretório quando fica vazio."""
    for path in paths:
        try:
            Path(path).unlink()
        except FileNotFoundError:
            pass
    directory = base_dir if base_dir is not None else UPLOAD_DIR
    if directory.is_dir() and not any(directory.iterdir()):
        directory.rmdir()
