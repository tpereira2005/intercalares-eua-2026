"""Exporta os contratos registados para ``schemas/json/contratos.schema.json``.

Uso: ``uv run python -m contratos.exportar``. O resultado é determinístico, o
que permite ao CI confirmar que os ficheiros gerados estão atualizados.
"""

import json
import sys
from pathlib import Path
from typing import Any

from pydantic.json_schema import models_json_schema

from contratos.base import VERSAO_ESQUEMA
from contratos.registo import MODELOS

DESTINO = Path(__file__).resolve().parents[2] / "json" / "contratos.schema.json"


def gerar_esquema() -> dict[str, Any]:
    """Devolve o JSON Schema combinado de todos os contratos registados.

    Usa o modo de serialização: descreve os ficheiros tal como o pipeline os
    publica, que é o que o site e a API consomem.
    """
    _, esquema = models_json_schema(
        [(modelo, "serialization") for modelo in MODELOS],
        ref_template="#/$defs/{model}",
    )
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": f"https://github.com/tpereira2005/intercalares-eua-2026/contratos/{VERSAO_ESQUEMA}",
        "title": "Contratos",
        "description": "Contratos de dados da plataforma Intercalares EUA 2026.",
        **esquema,
    }


def main(destino: Path = DESTINO) -> None:
    destino.parent.mkdir(parents=True, exist_ok=True)
    texto = json.dumps(gerar_esquema(), ensure_ascii=False, indent=2, sort_keys=True)
    destino.write_text(texto + "\n", encoding="utf-8")
    sys.stdout.write(f"Esquema escrito em {destino}\n")


if __name__ == "__main__":
    main()
