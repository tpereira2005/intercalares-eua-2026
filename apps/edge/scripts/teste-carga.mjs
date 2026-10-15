/**
 * Teste de carga local do Worker para a noite eleitoral (docs/teste-carga-noite.md).
 *
 * Arranca uma fonte falsa (servidor HTTP local com os ficheiros de exemplo do site), o
 * Worker em `wrangler dev --local` apontado para ela e N "browsers" simulados que
 * consultam /api/resultados e /api/noite a cada INTERVALO segundos, como o site. Não toca
 * em nenhum serviço externo nem no Worker de produção.
 *
 * Uso (na pasta apps/edge, depois de `pnpm install`):
 *   node scripts/teste-carga.mjs [--browsers 500] [--intervalo 60] [--porta 8799]
 *
 * O tempo NÃO é comprimido: os 20 s de frescura e os 8 s de limite do Worker são reais,
 * por isso o ensaio completo demora cerca de 8 minutos. Termina com código 1 se alguma
 * verificação falhar. Fica um resumo em JSON no fim da saída.
 */

import { spawn } from "node:child_process";
import { mkdtempSync, readFileSync, rmSync } from "node:fs";
import { createServer } from "node:http";
import { tmpdir } from "node:os";
import path from "node:path";
import { setTimeout as esperar } from "node:timers/promises";
import { fileURLToPath } from "node:url";

const AQUI = path.dirname(fileURLToPath(import.meta.url));
const RAIZ_EDGE = path.resolve(AQUI, "..");
const FIXTURES = path.resolve(RAIZ_EDGE, "../web/test/fixtures");

function argumento(nome, omissao) {
  const i = process.argv.indexOf(`--${nome}`);
  return i >= 0 ? Number(process.argv[i + 1]) : omissao;
}
const BROWSERS = argumento("browsers", 500);
const INTERVALO_MS = argumento("intervalo", 60) * 1000;
const PORTA = argumento("porta", 8799);
const PORTA_FONTE = PORTA + 1;
const FRESCURA_MS = 20_000; // espelha FRESCURA_MS de src/ao-vivo.ts

// Linha do tempo do cenário contínuo (segundos desde o início da carga).
const FASES = [
  { ate: 120, modo: "ok" },
  { ate: 180, modo: "500" },
  { ate: 240, modo: "429" },
  { ate: 300, modo: "pendurado" },
  { ate: 360, modo: "ok" },
];
const DURACAO_S = FASES[FASES.length - 1].ate;

const ler = (rel) => readFileSync(path.join(FIXTURES, rel), "utf-8");
const FICHEIROS = {
  "/parciais.json": ler("resultados/parciais.json"),
  "/chamadas.json": ler("resultados/chamadas.json"),
  "/projecao.json": ler("noite/projecao.json"),
  "/historico.json": ler("noite/historico.json"),
};

// ---------------------------------------------------------------- fonte falsa

const fonte = {
  modo: "ok",
  /** Pedidos recebidos: { t, caminho, estado }. */
  pedidos: [],
  /** O ETag muda a cada 30 s, como a publicação real, para haver 200 e 304. */
  etag: () => `"v${Math.floor(Date.now() / 30_000)}"`,
};
const pendurados = new Set();

const servidorFonte = createServer((req, res) => {
  const caminho = req.url ?? "";
  const registo = { t: Date.now(), caminho, estado: 0 };
  fonte.pedidos.push(registo);
  const corpo = FICHEIROS[caminho];
  if (!corpo) return void ((registo.estado = 404), res.writeHead(404).end());
  if (fonte.modo === "500") return void ((registo.estado = 500), res.writeHead(500).end("erro"));
  if (fonte.modo === "429") {
    registo.estado = 429;
    return void res.writeHead(429, { "Retry-After": "60" }).end("limite");
  }
  if (fonte.modo === "pendurado") {
    registo.estado = 0; // nunca responde: o Worker desiste ao fim de 8 s
    pendurados.add(res);
    return;
  }
  const etag = fonte.etag();
  if (req.headers["if-none-match"] === etag) {
    registo.estado = 304;
    return void res.writeHead(304, { ETag: etag }).end();
  }
  registo.estado = 200;
  res.writeHead(200, { "Content-Type": "application/json", ETag: etag }).end(corpo);
});

// ------------------------------------------------------------------- Worker

let worker;
let pastaTemporaria;

async function arrancarWorker() {
  pastaTemporaria = mkdtempSync(path.join(tmpdir(), "teste-carga-"));
  const base = `http://127.0.0.1:${PORTA_FONTE}`;
  const argumentos = [
    "exec",
    "wrangler",
    "dev",
    "--local",
    "--ip",
    "127.0.0.1",
    "--port",
    String(PORTA),
    "--inspector-port",
    String(PORTA + 2),
    "--persist-to",
    path.join(pastaTemporaria, "estado"),
    "--assets",
    pastaTemporaria,
    "--var",
    `URL_PARCIAIS:${base}/parciais.json`,
    `URL_PROJECAO_NOITE:${base}/projecao.json`,
    `URL_HISTORICO_NOITE:${base}/historico.json`,
    `URL_CHAMADAS:${base}/chamadas.json`,
  ];
  worker = spawn("pnpm", argumentos, {
    cwd: RAIZ_EDGE,
    env: { ...process.env, WRANGLER_SEND_METRICS: "false", CI: "1", NO_COLOR: "1" },
    stdio: ["ignore", "pipe", "pipe"],
    detached: true,
  });
  let registo = "";
  worker.stdout.on("data", (d) => (registo += d));
  worker.stderr.on("data", (d) => (registo += d));
  for (let i = 0; i < 120; i++) {
    await esperar(500);
    try {
      const r = await fetch(`http://127.0.0.1:${PORTA}/api/saude`);
      if (r.ok) return;
    } catch {
      /* ainda a arrancar */
    }
    if (worker.exitCode !== null) break;
  }
  throw new Error(`O Worker não arrancou:\n${registo.slice(-2000)}`);
}

function terminar() {
  for (const res of pendurados) res.destroy();
  try {
    if (worker?.pid) process.kill(-worker.pid, "SIGTERM");
  } catch {
    /* já terminou */
  }
  servidorFonte.closeAllConnections();
  servidorFonte.close();
  if (pastaTemporaria) rmSync(pastaTemporaria, { recursive: true, force: true });
}

// ------------------------------------------------------------------- medição

const percentil = (valores, p) => {
  if (valores.length === 0) return null;
  const ordenados = [...valores].sort((a, b) => a - b);
  return ordenados[Math.min(ordenados.length - 1, Math.ceil((p / 100) * ordenados.length) - 1)];
};
const resumoLatencia = (v) => ({
  n: v.length,
  p50: percentil(v, 50),
  p95: percentil(v, 95),
  p99: percentil(v, 99),
  max: v.length ? Math.max(...v) : null,
});

const falhas = [];
const verificar = (condicao, mensagem) => {
  console.log(`  ${condicao ? "OK    " : "FALHA "} ${mensagem}`);
  if (!condicao) falhas.push(mensagem);
};

/** Um pedido à API; devolve a medição e nunca lança. */
async function pedir(rota) {
  const inicio = performance.now();
  try {
    const r = await fetch(`http://127.0.0.1:${PORTA}${rota}`, {
      signal: AbortSignal.timeout(30_000),
    });
    const texto = await r.text();
    const ms = performance.now() - inicio;
    let corpo = null;
    try {
      corpo = JSON.parse(texto);
    } catch {
      /* corpo não JSON */
    }
    return {
      rota,
      t: Date.now(),
      ms,
      estado: r.status,
      cache: r.headers.get("cache-control"),
      origem: r.headers.get("x-origem"),
      confirmadoEm: corpo?.confirmadoEm ?? null,
      bytes: texto.length,
      completo:
        corpo !== null &&
        (rota === "/api/resultados"
          ? "parciais" in corpo && "chamadas" in corpo
          : "projecao" in corpo && "historico" in corpo),
    };
  } catch (erro) {
    return { rota, t: Date.now(), ms: performance.now() - inicio, estado: 0, erro: String(erro) };
  }
}

const contar = (lista, chave) => {
  const m = {};
  for (const x of lista) m[String(chave(x))] = (m[String(chave(x))] ?? 0) + 1;
  return m;
};

// ------------------------------------------------------------------ cenários

async function cenarioArranqueFrio() {
  console.log("\n[0] Fonte em baixo sem nenhuma cópia (arranque a frio)");
  fonte.modo = "500";
  const r = await pedir("/api/resultados");
  verificar(r.estado === 503, `sem cópia e fonte a 500 responde 503 (obtido ${r.estado})`);
  verificar(r.cache === "no-store", `o 503 leva Cache-Control no-store (obtido ${r.cache})`);
  fonte.modo = "ok";
  await esperar(FRESCURA_MS + 1500); // a fonte em baixo não é consultada antes de 20 s
  const s = await pedir("/api/resultados");
  verificar(s.estado === 200 && s.origem === "fonte", `recupera sozinha (${s.estado} ${s.origem})`);
}

/** Cenário contínuo: N browsers, fases da fonte, medição por minuto. */
async function cenarioContinuo() {
  console.log(
    `\n[1] ${BROWSERS} browsers, 2 pedidos de ${INTERVALO_MS / 1000} s, ${DURACAO_S} s, ` +
      `fonte: ${FASES.map((f) => `${f.modo} até ${f.ate} s`).join(", ")}`,
  );
  const medicoes = [];
  const inicio = Date.now();
  const fim = inicio + DURACAO_S * 1000;
  fonte.pedidos.length = 0;

  const fasePorTempo = () => {
    const s = (Date.now() - inicio) / 1000;
    return FASES.find((f) => s < f.ate)?.modo ?? "ok";
  };
  const controlador = (async () => {
    while (Date.now() < fim) {
      const modo = fasePorTempo();
      if (modo !== fonte.modo) {
        if (fonte.modo === "pendurado") for (const res of pendurados) res.destroy();
        pendurados.clear();
        fonte.modo = modo;
        console.log(`  t=${Math.round((Date.now() - inicio) / 1000)} s: fonte passa a "${modo}"`);
      }
      await esperar(250);
    }
  })();

  // Cada browser tem a sua fase aleatória; o período é INTERVALO_MS + latência, como no site.
  const browsers = Array.from({ length: BROWSERS }, async () => {
    await esperar(Math.random() * INTERVALO_MS);
    while (Date.now() < fim) {
      const par = await Promise.all([pedir("/api/resultados"), pedir("/api/noite")]);
      medicoes.push(...par);
      await esperar(INTERVALO_MS);
    }
  });
  await Promise.all([controlador, ...browsers]);
  fonte.modo = "ok";
  return { medicoes, inicio };
}

function analisarContinuo({ medicoes, inicio }) {
  const seg = (m) => (m.t - inicio) / 1000;
  const faseDe = (m) => FASES.find((f) => seg(m) < f.ate)?.modo ?? "ok";

  console.log("\nResultados do cenário contínuo");
  verificar(
    medicoes.every((m) => m.estado === 200),
    `todos os ${medicoes.length} pedidos responderam 200 ` +
      `(estados: ${JSON.stringify(contar(medicoes, (m) => m.estado))})`,
  );
  verificar(
    medicoes.every((m) => m.cache === "public, max-age=15" && m.completo),
    "todos levam Cache-Control public, max-age=15 e os campos esperados",
  );
  const origens = contar(medicoes, (m) => m.origem);
  console.log(`  X-Origem: ${JSON.stringify(origens)}`);

  // Cópia antiga: durante o erro serve-se a última cópia com a hora da última confirmação.
  const bomAntes = medicoes.filter((m) => seg(m) < 120 && m.confirmadoEm);
  const ultimaBoa = bomAntes.reduce((a, m) => (m.confirmadoEm > a ? m.confirmadoEm : a), "");
  const noErro = medicoes.filter((m) => seg(m) >= 120 + 30 && seg(m) < 300 - 5);
  const antigas = noErro.filter((m) => m.origem === "copia-antiga");
  verificar(
    noErro.length > 0 && antigas.length / noErro.length > 0.95,
    `com a fonte em erro, ${antigas.length}/${noErro.length} respostas são copia-antiga`,
  );
  const horasErro = new Set(antigas.map((m) => m.confirmadoEm));
  verificar(
    [...horasErro].every((h) => h <= new Date(inicio + 121_000).toISOString()),
    `confirmadoEm não avança durante o erro (valores distintos: ${horasErro.size}; última boa antes: ${ultimaBoa})`,
  );

  // Recuperação
  const depois = medicoes.filter((m) => seg(m) >= 300 + 30);
  const recuperadas = depois.filter((m) => m.origem !== "copia-antiga");
  verificar(
    depois.length > 0 && recuperadas.length === depois.length,
    `depois do erro todas voltam a fonte/memoria (${recuperadas.length}/${depois.length})`,
  );

  // Latência
  const porFase = {};
  for (const f of ["ok", "500", "429", "pendurado"]) {
    porFase[f] = resumoLatencia(medicoes.filter((m) => faseDe(m) === f).map((m) => m.ms));
  }
  const global = resumoLatencia(medicoes.map((m) => m.ms));
  console.log(`  Latência global (ms): ${JSON.stringify(global)}`);
  for (const [f, v] of Object.entries(porFase))
    console.log(`  Latência fase ${f}: ${JSON.stringify(v)}`);

  // Pedidos à fonte por minuto
  const minutos = Math.ceil(DURACAO_S / 60);
  const porMinuto = [];
  for (let k = 0; k < minutos; k++) {
    const dentro = fonte.pedidos.filter(
      (p) => p.t >= inicio + k * 60_000 && p.t < inicio + (k + 1) * 60_000,
    );
    porMinuto.push({
      minuto: k + 1,
      total: dentro.length,
      porFicheiro: contar(dentro, (p) => p.caminho),
      estados: contar(dentro, (p) => p.estado),
    });
    console.log(
      `  minuto ${k + 1}: ${dentro.length} pedidos à fonte ${JSON.stringify(contar(dentro, (p) => p.estado))}`,
    );
  }
  // Limite teórico por minuto: 4 ficheiros x ceil(60 s / 20 s) = 12 (mais 1 por ficheiro na fronteira).
  const maximo = Math.max(...porMinuto.map((p) => p.total));
  verificar(
    maximo <= 16,
    `no máximo ${maximo} pedidos/min à fonte (limite pela frescura: 12, tolerância de fronteira 16), com ${BROWSERS} browsers`,
  );
  const pedidosPorMinutoPorBrowser = (BROWSERS * 2).toFixed(0);
  console.log(`  Pedidos ao Worker por minuto (aprox.): ${pedidosPorMinutoPorBrowser}`);
  return { global, porFase, origens, porMinuto, totalPedidosWorker: medicoes.length };
}

async function cenarioRajada() {
  console.log(`\n[2] Rajada: ${BROWSERS} browsers a pedir os dois ficheiros ao mesmo tempo`);
  const resultados = [];
  for (let ronda = 1; ronda <= 3; ronda++) {
    // Espera que a cópia fique velha para a rajada apanhar a ida à fonte.
    if (ronda > 1) await esperar(FRESCURA_MS + 500);
    const antes = fonte.pedidos.length;
    const t0 = performance.now();
    const medicoes = (
      await Promise.all(
        Array.from({ length: BROWSERS }, () =>
          Promise.all([pedir("/api/resultados"), pedir("/api/noite")]),
        ),
      )
    ).flat();
    const duracao = performance.now() - t0;
    const aFonte = fonte.pedidos.length - antes;
    const ok = medicoes.filter((m) => m.estado === 200).length;
    const lat = resumoLatencia(medicoes.map((m) => m.ms));
    console.log(
      `  ronda ${ronda}: ${medicoes.length} pedidos em ${duracao.toFixed(0)} ms, ` +
        `${ok} com 200, ${aFonte} idas à fonte, latência ${JSON.stringify(lat)}`,
    );
    verificar(ok === medicoes.length, `ronda ${ronda}: todos os pedidos da rajada deram 200`);
    verificar(
      aFonte <= 4,
      `ronda ${ronda}: ${aFonte} idas à fonte para ${medicoes.length} pedidos (esperado <= 4)`,
    );
    resultados.push({
      ronda,
      pedidos: medicoes.length,
      duracaoMs: Math.round(duracao),
      aFonte,
      latencia: lat,
    });
  }
  return resultados;
}

// ---------------------------------------------------------------------- main

let saida = 1;
try {
  await new Promise((ok) => servidorFonte.listen(PORTA_FONTE, "127.0.0.1", ok));
  console.log(
    `Fonte falsa em :${PORTA_FONTE}; a arrancar o Worker (wrangler dev --local) em :${PORTA}...`,
  );
  await arrancarWorker();
  console.log("Worker pronto.");

  await cenarioArranqueFrio();
  const continuo = await cenarioContinuo();
  const analise = analisarContinuo(continuo);
  const rajada = await cenarioRajada();

  console.log("\nResumo JSON");
  console.log(
    JSON.stringify(
      { browsers: BROWSERS, intervaloS: INTERVALO_MS / 1000, analise, rajada },
      null,
      2,
    ),
  );
  console.log(
    falhas.length === 0
      ? "\nTodas as verificações passaram."
      : `\n${falhas.length} verificação(ões) falharam.`,
  );
  saida = falhas.length === 0 ? 0 : 1;
} catch (erro) {
  console.error(erro);
} finally {
  terminar();
}
process.exit(saida);
