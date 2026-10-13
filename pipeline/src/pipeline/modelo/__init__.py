"""Modelo de previsão da Câmara e do Senado (Modelo A do plano).

O fluxo é: fontes (Wikipedia, resultados históricos) → tabelas de referência versionadas
em ``data/reference/modelo/`` → estimação dos parâmetros nos ciclos anteriores →
simulação com erros correlacionados → contrato ``PrevisaoCongresso``.
"""
