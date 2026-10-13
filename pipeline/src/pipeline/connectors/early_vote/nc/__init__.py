"""Conector de voto antecipado da Carolina do Norte (NC State Board of Elections).

Fontes públicas e gratuitas (G.S. 132-1 e 163-82.10), publicadas em
``https://dl.ncsbe.gov``:

* ``ENRS/<data>/absentee_<data>.zip``: um registo por boletim de voto antecipado (correio e
  presencial), com idade, partido, raça, etnia, género, condado, distrito e datas.
  Atualizado diariamente durante o período eleitoral; os anos anteriores ficam com a
  versão final.
* ``data/ncvoter_Statewide.zip``: ficheiro de eleitores atual (semanal).
* ``data/ncvhis_Statewide.zip``: histórico de voto individual dos últimos dez anos (semanal).
* ``data/Snapshots/VR_Snapshot_<data>.zip``: retrato do recenseamento no dia de cada
  eleição, usado para os denominadores dos anos anteriores.

Os ficheiros contêm nomes e moradas. Este módulo lê só as colunas necessárias para a
análise e nunca escreve dados pessoais: o identificador ``ncid`` serve apenas para cruzar
ficheiros em memória ou na cache local ignorada pelo git.
"""
