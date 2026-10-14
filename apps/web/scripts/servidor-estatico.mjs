/**
 * Servidor estático mínimo sobre a pasta exportada (apps/web/out), partilhado pelos
 * scripts de auditoria e de fluxos. Tudo o que não existe responde 404, incluindo /api/*,
 * tal como acontece sem o Worker.
 */

import { createReadStream } from "node:fs";
import { stat } from "node:fs/promises";
import { createServer } from "node:http";
import path from "node:path";
import { fileURLToPath } from "node:url";

export const RAIZ = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "out");

const TIPOS = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript",
  ".css": "text/css",
  ".json": "application/json",
  ".svg": "image/svg+xml",
  ".woff2": "font/woff2",
  ".woff": "font/woff",
  ".txt": "text/plain; charset=utf-8",
};

export function servir() {
  const servidor = createServer(async (pedido, resposta) => {
    const caminho = decodeURIComponent(new URL(pedido.url ?? "/", "http://x").pathname);
    let ficheiro = path.join(RAIZ, caminho);
    if (!ficheiro.startsWith(RAIZ)) {
      resposta.writeHead(403).end();
      return;
    }
    try {
      if ((await stat(ficheiro)).isDirectory()) ficheiro = path.join(ficheiro, "index.html");
      await stat(ficheiro);
    } catch {
      resposta.writeHead(404).end();
      return;
    }
    resposta.writeHead(200, {
      "Content-Type": TIPOS[path.extname(ficheiro)] ?? "application/octet-stream",
    });
    createReadStream(ficheiro).pipe(resposta);
  });
  return new Promise((resolver) => {
    servidor.listen(0, "127.0.0.1", () => {
      const endereco = servidor.address();
      resolver({ servidor, base: `http://127.0.0.1:${String(endereco.port)}` });
    });
  });
}
