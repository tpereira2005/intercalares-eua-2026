import { Hono, type Context } from "hono";
import { secureHeaders } from "hono/secure-headers";
import { LeitorAoVivo, type Leitura, type Origem } from "./ao-vivo.ts";
import type { Env } from "./env.ts";
import {
  ChamadasRedacoes,
  HistoricoNoite,
  ProjecaoNoite,
  ResultadosParciais,
  SaudeRecolha,
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
type EsperarDepois = ((p: Promise<unknown>) => void) | undefined;

/** Grupo de ficheiros de uma rota: o principal decide se há resposta. */
interface Grupo {
  principal: Leitura;
  campos: Record<string, Leitura>;
}

interface CorpoAoVivo {
  corpo: string;
  origem: Origem;
}

const PIOR_ORIGEM = (pior: Origem, origem: Origem): Origem =>
  ORDEM_ORIGEM.indexOf(origem) > ORDEM_ORIGEM.indexOf(pior) ? origem : pior;

/**
 * Corpo com os ficheiros tal como chegaram da fonte (já validados), sem os voltar a
 * serializar: poupa CPU, que no plano gratuito é de 10 ms por pedido. `null` sem o
 * ficheiro principal.
 */
function corpoAoVivo({ principal, campos }: Grupo): CorpoAoVivo | null {
  if (principal.tipo !== "dados") return null;
  const lidos = Object.values(campos).filter((l): l is Dados => l.tipo === "dados");
  const origem = lidos.reduce<Origem>((pior, l) => PIOR_ORIGEM(pior, l.origem), principal.origem);
  const confirmada = Math.min(...lidos.map((l) => l.confirmadaEm));
  const partes = [
    `"origem":${JSON.stringify(origem)}`,
    `"confirmadoEm":${JSON.stringify(new Date(confirmada).toISOString())}`,
    ...Object.entries(campos).map(
      ([nome, l]) => `${JSON.stringify(nome)}:${l.tipo === "dados" ? l.texto : "null"}`,
    ),
  ];
  return { corpo: `{${partes.join(",")}}`, origem };
}

function cabecalhosAoVivo(origem: Origem): Record<string, string> {
  return {
    "Content-Type": "application/json; charset=UTF-8",
    "Cache-Control": CACHE_AO_VIVO,
    "X-Origem": origem,
  };
}

function semDados(leitura: Leitura): Response {
  return leitura.tipo === "ausente"
    ? Response.json({ erro: "Ainda não há dados publicados." }, { status: 404 })
    : Response.json({ erro: "A fonte não respondeu e não há cópia." }, { status: 503 });
}

function respostaGrupo(grupo: Grupo): Response {
  const feito = corpoAoVivo(grupo);
  return feito
    ? new Response(feito.corpo, { headers: cabecalhosAoVivo(feito.origem) })
    : semDados(grupo.principal);
}

async function lerResultados(env: Env, depois: EsperarDepois): Promise<Grupo> {
  const [parciais, chamadas, saude] = await Promise.all([
    leitor.ler({ url: env.URL_PARCIAIS, validar: ResultadosParciais }, depois),
    leitor.ler({ url: env.URL_CHAMADAS, validar: ChamadasRedacoes }, depois),
    leitor.ler({ url: env.URL_SAUDE, validar: SaudeRecolha }, depois),
  ]);
  return { principal: parciais, campos: { parciais, chamadas, saude } };
}

async function lerNoite(env: Env, depois: EsperarDepois): Promise<Grupo> {
  const [projecao, historico] = await Promise.all([
    leitor.ler({ url: env.URL_PROJECAO_NOITE, validar: ProjecaoNoite }, depois),
    leitor.ler({ url: env.URL_HISTORICO_NOITE, validar: HistoricoNoite }, depois),
  ]);
  return { principal: projecao, campos: { projecao, historico } };
}

/**
 * Entrega a `waitUntil` do pedido, para a renovação da cópia acabar depois da resposta.
 * Fora do Workers (testes do Hono) não há contexto de execução.
 */
function esperarDepoisDe(c: Context): EsperarDepois {
  try {
    return c.executionCtx.waitUntil.bind(c.executionCtx);
  } catch {
    return undefined;
  }
}

export const INTERVALO_S_OMISSAO = 60;
const INTERVALO_S_MIN = 30;
const INTERVALO_S_MAX = 600;

/** Lê `INTERVALO_S` e limita-o a 30-600 s; valor em falta ou inválido dá 60. */
export function intervaloSugerido(valor: string | undefined): number {
  const numero = valor === undefined || valor.trim() === "" ? NaN : Number(valor);
  if (!Number.isFinite(numero)) return INTERVALO_S_OMISSAO;
  return Math.min(INTERVALO_S_MAX, Math.max(INTERVALO_S_MIN, Math.round(numero)));
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
 * Contagem oficial (contrato ResultadosParciais), chamadas das redações
 * (ChamadasRedacoes, `null` sem nenhuma) e estado da recolha por estado (SaudeRecolha,
 * `null` sem ficheiro), da Release `resultados-2026`. Não confundir com `/api/saude`,
 * que é a verificação do próprio Worker.
 */
app.get("/resultados", async (c) => respostaGrupo(await lerResultados(c.env, esperarDepoisDe(c))));

/** Projeção do modelo e a sua evolução (ProjecaoNoite e HistoricoNoite), de `dados-noite`. */
app.get("/noite", async (c) => respostaGrupo(await lerNoite(c.env, esperarDepoisDe(c))));

/**
 * As duas rotas anteriores num só pedido (um por leitor e por intervalo, em vez de dois):
 * `{"resultados": <corpo de /api/resultados ou null>, "noite": <corpo de /api/noite ou
 * null>, "intervaloS": n}`. 200 com pelo menos uma parte, 404 se nenhuma foi publicada,
 * 503 nos restantes casos.
 */
app.get("/ao-vivo", async (c) => {
  const depois = esperarDepoisDe(c);
  const [grupoResultados, grupoNoite] = await Promise.all([
    lerResultados(c.env, depois),
    lerNoite(c.env, depois),
  ]);
  const resultados = corpoAoVivo(grupoResultados);
  const noite = corpoAoVivo(grupoNoite);
  if (!resultados && !noite) {
    const ambasAusentes =
      grupoResultados.principal.tipo === "ausente" && grupoNoite.principal.tipo === "ausente";
    return semDados(ambasAusentes ? grupoResultados.principal : { tipo: "erro", erro: "" });
  }
  const origem = [resultados, noite].reduce<Origem>(
    (pior, parte) => (parte ? PIOR_ORIGEM(pior, parte.origem) : pior),
    "memoria",
  );
  const corpo =
    `{"resultados":${resultados?.corpo ?? "null"},"noite":${noite?.corpo ?? "null"},` +
    `"intervaloS":${intervaloSugerido(c.env.INTERVALO_S)}}`;
  return new Response(corpo, { headers: cabecalhosAoVivo(origem) });
});

app.notFound((c) => c.json({ erro: "Recurso não encontrado." }, 404));

app.onError((erro, c) => {
  console.error("Erro não tratado na API", erro);
  return c.json({ erro: "Erro interno." }, 500);
});
