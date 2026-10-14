import { Hono } from "hono";
import { secureHeaders } from "hono/secure-headers";
import { LeitorAoVivo, type Leitura, type Origem } from "./ao-vivo.ts";
import type { Env } from "./env.ts";
import {
  ChamadasRedacoes,
  HistoricoNoite,
  ProjecaoNoite,
  ResultadosParciais,
} from "./gerado/validadores.js";

export const app = new Hono<{ Bindings: Env }>().basePath("/api");

/** Cópias em memória deste isolate; os testes substituem-no com `definirLeitor`. */
let leitor = new LeitorAoVivo();

export function definirLeitor(novo: LeitorAoVivo): void {
  leitor = novo;
}

/** Cache no browser e em proxies: o browser consulta a cada 60 s. */
const CACHE_AO_VIVO = "public, max-age=15";
const ORDEM_ORIGEM: Origem[] = ["memoria", "fonte", "copia-antiga"];

type Dados = Extract<Leitura, { tipo: "dados" }>;

/**
 * Resposta com os ficheiros tal como chegaram da fonte (já validados), sem os voltar
 * a serializar: poupa CPU, que no plano gratuito é de 10 ms por pedido.
 */
function respostaAoVivo(principal: Dados, campos: Record<string, Leitura>): Response {
  const lidos = Object.values(campos).filter((l): l is Dados => l.tipo === "dados");
  const origem = lidos.reduce<Origem>(
    (pior, l) => (ORDEM_ORIGEM.indexOf(l.origem) > ORDEM_ORIGEM.indexOf(pior) ? l.origem : pior),
    principal.origem,
  );
  const confirmada = Math.min(...lidos.map((l) => l.confirmadaEm));
  const corpo = [
    `"origem":${JSON.stringify(origem)}`,
    `"confirmadoEm":${JSON.stringify(new Date(confirmada).toISOString())}`,
    ...Object.entries(campos).map(
      ([nome, l]) => `${JSON.stringify(nome)}:${l.tipo === "dados" ? l.texto : "null"}`,
    ),
  ];
  return new Response(`{${corpo.join(",")}}`, {
    headers: {
      "Content-Type": "application/json; charset=UTF-8",
      "Cache-Control": CACHE_AO_VIVO,
      "X-Origem": origem,
    },
  });
}

function semDados(leitura: Exclude<Leitura, Dados>): Response {
  return leitura.tipo === "ausente"
    ? Response.json({ erro: "Ainda não há dados publicados." }, { status: 404 })
    : Response.json({ erro: "A fonte não respondeu e não há cópia." }, { status: 503 });
}

app.use(
  "*",
  secureHeaders({
    crossOriginResourcePolicy: "cross-origin",
  }),
);

app.use("*", async (c, next) => {
  await next();
  if (!c.res.headers.has("Cache-Control")) {
    c.header("Cache-Control", "no-store");
  }
});

/** Verificação de estado usada pela monitorização e pelos testes de fumo. */
app.get("/saude", (c) => c.json({ estado: "ok", ambiente: c.env.AMBIENTE }));

/**
 * Contagem oficial (contrato ResultadosParciais) e chamadas das redações
 * (ChamadasRedacoes, `null` sem nenhuma), da Release `resultados-2026`.
 */
app.get("/resultados", async (c) => {
  const [parciais, chamadas] = await Promise.all([
    leitor.ler({ url: c.env.URL_PARCIAIS, validar: ResultadosParciais }),
    leitor.ler({ url: c.env.URL_CHAMADAS, validar: ChamadasRedacoes }),
  ]);
  if (parciais.tipo !== "dados") return semDados(parciais);
  return respostaAoVivo(parciais, { parciais, chamadas });
});

/** Projeção do modelo e a sua evolução (ProjecaoNoite e HistoricoNoite), de `dados-noite`. */
app.get("/noite", async (c) => {
  const [projecao, historico] = await Promise.all([
    leitor.ler({ url: c.env.URL_PROJECAO_NOITE, validar: ProjecaoNoite }),
    leitor.ler({ url: c.env.URL_HISTORICO_NOITE, validar: HistoricoNoite }),
  ]);
  if (projecao.tipo !== "dados") return semDados(projecao);
  return respostaAoVivo(projecao, { projecao, historico });
});

app.notFound((c) => c.json({ erro: "Recurso não encontrado." }, 404));

app.onError((erro, c) => {
  console.error("Erro não tratado na API", erro);
  return c.json({ erro: "Erro interno." }, 500);
});
