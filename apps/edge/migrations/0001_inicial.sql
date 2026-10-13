-- Migração inicial: regista a versão do esquema da base de dados.
-- As tabelas de snapshots chegam com a API de dados ao vivo (Fase 1).
CREATE TABLE IF NOT EXISTS meta (
  chave TEXT PRIMARY KEY NOT NULL,
  valor TEXT NOT NULL
);

INSERT OR IGNORE INTO meta (chave, valor) VALUES ('versao_esquema', '1');
