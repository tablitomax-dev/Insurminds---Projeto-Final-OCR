"""T-2b: uploads temporários em diretório controlado, sem resíduo após o fluxo."""

from pathlib import Path

from ui.uploads import UPLOAD_DIR, cleanup_uploads, save_upload


def test_diretorio_de_upload_e_controlado_pelo_projeto():
    assert UPLOAD_DIR == Path(".tmp") / "uploads"


def test_upload_vai_para_diretorio_controlado_com_nome_seguro(tmp_path):
    saved = save_upload("../../apolice_sigilosa.pdf", b"%PDF-1.4", base_dir=tmp_path)

    assert saved == tmp_path / "apolice_sigilosa.pdf"
    assert saved.read_bytes() == b"%PDF-1.4"
    assert saved.parent == tmp_path  # sem traversal fora do diretório


def test_cleanup_remove_arquivos_e_diretorio(tmp_path):
    saved = [save_upload(f"apolice_{name}.pdf", b"%PDF", base_dir=tmp_path) for name in ("a", "b")]

    cleanup_uploads(saved, base_dir=tmp_path)

    assert not any(path.exists() for path in saved)
    assert not tmp_path.exists()  # nada persiste depois do fluxo
