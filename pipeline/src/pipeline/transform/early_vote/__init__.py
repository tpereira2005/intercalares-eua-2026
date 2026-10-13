"""Transformações do voto antecipado, iguais para todos os estados e todos os anos.

O fluxo é sempre o mesmo:

1. ``painel``: uma linha por eleitor recenseado, com o que fez até agora (se votou, como e
   quando) e o que fez na eleição de referência. Fica só na cache local.
2. ``cubos``: o painel agregado em contagens. Os cubos não têm dados pessoais e são o que
   se guarda e publica.
3. ``indicadores``: composição, participação, decomposição, esperado, reserva e geografia,
   calculados sobre os cubos para um dia do ciclo.
"""
