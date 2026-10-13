"""Erros do pipeline. Um erro de formato de fonte impede sempre a publicação."""


class ErroPipeline(Exception):  # noqa: N818 (nome em português)
    """Base de todos os erros do pipeline."""


class ErroFormatoFonte(ErroPipeline):
    """A fonte mudou de formato ou trouxe dados que falham a validação."""


class ErroDescarga(ErroPipeline):
    """Não foi possível obter um ficheiro da fonte."""


class ErroBloqueio(ErroDescarga):
    """A fonte respondeu com um desafio anti-robô (AWS WAF, Cloudflare). Não o
    contornamos: o estado fica sem dados desta fonte e o erro diz porquê."""
