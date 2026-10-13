import importlib

import pytest

MODULOS = [
    "pipeline",
    "pipeline.connectors",
    "pipeline.connectors.early_vote",
    "pipeline.connectors.results",
    "pipeline.connectors.polls",
    "pipeline.connectors.fec",
    "pipeline.transform",
    "pipeline.publish",
    "pipeline.jobs",
]


@pytest.mark.parametrize("nome", MODULOS)
def test_modulos_importam(nome: str) -> None:
    assert importlib.import_module(nome).__doc__
