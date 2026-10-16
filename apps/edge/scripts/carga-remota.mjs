/**
 * Carga sobre o Worker de ensaio na Cloudflare (docs/teste-carga-noite.md, secção
 * "Ensaio na Cloudflare"). Simula leitores com a página da noite aberta: cada um pede
 * /api/ao-vivo a cada INTERVALO segundos, como o site, durante DURACAO minutos.
 *
 * O limite de 100 000 pedidos diários ao código do Worker é da conta inteira e partilhado
 * com a produção. Por isso o total de pedidos é calculado antes de começar e o script
 * recusa-se a passar de 30 000.
 *
 * Uso: node scripts/carga-remota.mjs --url https://<worker de ensaio> \
 *        [--leitores 200] [--intervalo 60] [--duracao 30]
 * Termina com código 1 se mais de 1% dos pedidos falharem ou se o percentil 95 da
 * latência passar de 1500 ms. Escreve um resumo em Markdown na saída padrão.
 */

import { setTimeout as esperar } from "node:timers/promises";

export const MAXIMO_PEDIDOS = 30_000;

function argumento(nome, omissao) {
  const i = process.argv.indexOf(`--${nome}`);
  return i >= 0 ? (process.argv[i + 1] ?? omissao) : omissao;
}

export function percentil(ordenados, p) {
  if (ordenados.length === 0) return null;
  const i = Math.min(ordenados.length - 1, Math.ceil((p / 100) * ordenados.length) - 1);
  return ordenados[Math.max(0, i)];
}

export function planear({ leitores, intervaloS, duracaoMin }) {
  const porLeitor = Math.floor((duracaoMin * 60) / intervaloS);
  return { porLeitor, total: porLeitor * leitores };
}

async function pedir(url) {
  const inicio = performance.now();
  try {
    const r = await fetch(url, { headers: { "User-Agent": "Escrutinio-ensaio-carga/1.0" } });
    await r.arrayBuffer();
    return { estado: r.status, ms: performance.now() - inicio };
  } catch {
    return { estado: 0, ms: performance.now() - inicio };
  }
}

async function main() {
  const base = argumento("url", "");
  if (!/^https:\/\/intercalares-eua-2026-ensaio\./.test(base)) {
    throw new Error("--url tem de ser o Worker de ensaio (intercalares-eua-2026-ensaio.*)");
  }
  const leitores = Number(argumento("leitores", "200"));
  const intervaloS = Number(argumento("intervalo", "60"));
  const duracaoMin = Number(argumento("duracao", "30"));
  const { porLeitor, total } = planear({ leitores, intervaloS, duracaoMin });
  if (!(total > 0) || total > MAXIMO_PEDIDOS) {
    throw new Error(`Plano com ${total} pedidos: tem de ficar entre 1 e ${MAXIMO_PEDIDOS}`);
  }
  const url = new URL("/api/ao-vivo", base).toString();
  const resultados = [];
  const leitor = async () => {
    // Fase aleatória, como os browsers reais.
    await esperar(Math.random() * intervaloS * 1000);
    for (let n = 0; n < porLeitor; n++) {
      const inicio = Date.now();
      resultados.push(await pedir(url));
      await esperar(Math.max(0, intervaloS * 1000 - (Date.now() - inicio)));
    }
  };
  console.error(`${leitores} leitores, ${total} pedidos a ${url}`);
  await Promise.all(Array.from({ length: leitores }, leitor));

  const ms = resultados.map((r) => r.ms).sort((a, b) => a - b);
  const falhas = resultados.filter((r) => r.estado !== 200).length;
  const porEstado = new Map();
  for (const r of resultados) porEstado.set(r.estado, (porEstado.get(r.estado) ?? 0) + 1);
  const p95 = percentil(ms, 95) ?? Infinity;
  const fmt = (v) => (v === null ? "—" : `${Math.round(v)} ms`);
  console.log(
    [
      "## Carga no Worker de ensaio",
      "",
      `- Leitores: ${leitores}, um pedido a cada ${intervaloS} s durante ${duracaoMin} min`,
      `- Pedidos: ${resultados.length}; falhas: ${falhas} (${((100 * falhas) / resultados.length).toFixed(2)}%)`,
      `- Estados: ${[...porEstado].map(([e, n]) => `${e === 0 ? "erro de rede" : e} × ${n}`).join(", ")}`,
      `- Latência: mediana ${fmt(percentil(ms, 50))}, p95 ${fmt(p95)}, p99 ${fmt(percentil(ms, 99))}, máximo ${fmt(ms.at(-1) ?? null)}`,
    ].join("\n"),
  );
  if (falhas / resultados.length > 0.01 || p95 > 1500) process.exitCode = 1;
}

if (import.meta.url === `file://${process.argv[1]}`) await main();
