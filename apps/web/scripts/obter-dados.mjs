/**
 * Descarrega os agregados publicados pelo pipeline para apps/web/dados/, antes
 * do build. A origem por omissão é a Release pública fixa do repositório; uma
 * variável de ambiente permite apontar para outro endereço ou ficheiro local.
 *
 * Uso: pnpm --filter @intercalares/web dados:obter
 *   URL_DADOS_VOTO_ANTECIPADO=https://... ou =caminho/local/nc.json
 *
 * Sem rede ou sem Release, o script avisa e termina sem erro: a página mostra
 * "em preparação". A validação contra o contrato é feita no build.
 */

import { copyFile, mkdir, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const RAIZ_WEB = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const DESTINO = path.join(RAIZ_WEB, "dados", "voto-antecipado", "nc.json");
const ORIGEM_POR_OMISSAO =
  "https://github.com/tpereira2005/intercalares-eua-2026/releases/download/dados-voto-antecipado/nc.json";
const ORIGEM = process.env.URL_DADOS_VOTO_ANTECIPADO ?? ORIGEM_POR_OMISSAO;
const LIMITE_BYTES = 20 * 1024 * 1024;

async function obter() {
  await mkdir(path.dirname(DESTINO), { recursive: true });
  if (!/^https?:\/\//.test(ORIGEM)) {
    await copyFile(path.resolve(ORIGEM), DESTINO);
    return;
  }
  const resposta = await fetch(ORIGEM, {
    headers: {
      "User-Agent": "Escrutinio/0.1 (+https://github.com/tpereira2005/intercalares-eua-2026)",
    },
    redirect: "follow",
    signal: AbortSignal.timeout(60_000),
  });
  if (!resposta.ok) throw new Error(`${ORIGEM} respondeu ${resposta.status}`);
  const corpo = Buffer.from(await resposta.arrayBuffer());
  if (corpo.length > LIMITE_BYTES) throw new Error(`${ORIGEM} tem mais de 20 MB`);
  JSON.parse(corpo.toString("utf-8"));
  await writeFile(DESTINO, corpo);
}

try {
  await obter();
  console.log(`Dados do voto antecipado em ${path.relative(process.cwd(), DESTINO)}`);
} catch (erro) {
  console.warn(`Sem dados do voto antecipado (${String(erro)}); a página fica em preparação.`);
}
