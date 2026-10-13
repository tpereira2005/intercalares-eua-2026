import json
from pathlib import Path

from contratos import exportar


def test_esquema_contem_todos_os_modelos_registados() -> None:
    esquema = exportar.gerar_esquema()
    assert set(esquema["$defs"]) >= {"Fonte", "Metadados"}


def test_ficheiro_gerado_esta_atualizado() -> None:
    """Falha se alguém alterou um contrato sem correr ``pnpm contratos:gerar``."""
    esperado = json.dumps(exportar.gerar_esquema(), ensure_ascii=False, indent=2, sort_keys=True)
    assert exportar.DESTINO.read_text(encoding="utf-8") == esperado + "\n"


def test_exportacao_e_deterministica(tmp_path: Path) -> None:
    primeiro, segundo = tmp_path / "a.json", tmp_path / "b.json"
    exportar.main(primeiro)
    exportar.main(segundo)
    assert primeiro.read_bytes() == segundo.read_bytes()
