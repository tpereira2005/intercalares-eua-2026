/**
 * Leitura dos ficheiros da noite eleitoral publicados nas Releases do GitHub.
 *
 * Os workflows da noite publicam a contagem e a projeção a cada 30 s, mas não voltam
 * a implantar o site; esta API é o caminho por onde os dados chegam ao browser
 * durante a noite (docs/api-ao-vivo.md). Cada isolate do Worker guarda em memória a
 * última cópia válida de cada ficheiro e só volta à fonte passados FRESCURA_MS, com
 * pedidos condicionais (ETag e Last-Modified). Um ficheiro que não cumpre o contrato
 * nunca é servido: fica a cópia anterior.
 */

import type { Validador } from "./gerado/validadores.js";

/** Tempo durante o qual uma cópia em memória se serve sem perguntar à fonte. */
export const FRESCURA_MS = 20_000;
/** Tempo máximo de espera por uma resposta da fonte. */
export const LIMITE_PEDIDO_MS = 8_000;
export const USER_AGENT = "Escrutinio/0.1 (+https://github.com/tpereira2005/intercalares-eua-2026)";

export interface Fonte {
  url: string;
  validar: Validador;
}

/**
 * - `memoria`: cópia confirmada há menos de FRESCURA_MS;
 * - `fonte`: acabada de confirmar ou de descarregar;
 * - `copia-antiga`: a fonte falhou e serve-se a última cópia válida.
 */
export type Origem = "memoria" | "fonte" | "copia-antiga";

export type Leitura =
  | { tipo: "dados"; texto: string; origem: Origem; confirmadaEm: number }
  /** A fonte respondeu 404 e nunca houve cópia: ainda não há ficheiro publicado. */
  | { tipo: "ausente" }
  /** A fonte falhou e não há cópia para servir. */
  | { tipo: "erro"; erro: string };

interface Copia {
  texto: string;
  etag: string | null;
  modificado: string | null;
}

interface EstadoFonte {
  copia: Copia | null;
  /** Última vez que se perguntou à fonte (com sucesso ou não). */
  verificadaEm: number;
  /** Última vez que a fonte confirmou a cópia. */
  confirmadaEm: number;
  ausente: boolean;
  erro: string | null;
  pedido: Promise<void> | null;
}

export class LeitorAoVivo {
  private readonly estados = new Map<string, EstadoFonte>();

  constructor(
    private readonly buscar: typeof fetch = (pedido, opcoes) => fetch(pedido, opcoes),
    private readonly agora: () => number = Date.now,
  ) {}

  async ler(fonte: Fonte): Promise<Leitura> {
    const estado = this.estados.get(fonte.url) ?? {
      copia: null,
      verificadaEm: -Infinity,
      confirmadaEm: -Infinity,
      ausente: false,
      erro: null,
      pedido: null,
    };
    this.estados.set(fonte.url, estado);
    let origem: Origem = "memoria";
    if (this.agora() - estado.verificadaEm >= FRESCURA_MS) {
      // Pedidos simultâneos no mesmo isolate partilham uma só ida à fonte.
      estado.pedido ??= this.atualizar(fonte, estado).finally(() => {
        estado.pedido = null;
      });
      await estado.pedido;
      origem = "fonte";
    }
    if (estado.copia) {
      return {
        tipo: "dados",
        texto: estado.copia.texto,
        origem: estado.erro === null ? origem : "copia-antiga",
        confirmadaEm: estado.confirmadaEm,
      };
    }
    if (estado.ausente) return { tipo: "ausente" };
    return { tipo: "erro", erro: estado.erro ?? "Sem dados." };
  }

  private async atualizar(fonte: Fonte, estado: EstadoFonte): Promise<void> {
    const cabecalhos = new Headers({ "User-Agent": USER_AGENT, Accept: "application/json" });
    if (estado.copia?.etag) cabecalhos.set("If-None-Match", estado.copia.etag);
    if (estado.copia?.modificado) cabecalhos.set("If-Modified-Since", estado.copia.modificado);
    try {
      const resposta = await this.buscar(fonte.url, {
        headers: cabecalhos,
        signal: AbortSignal.timeout(LIMITE_PEDIDO_MS),
      });
      if (resposta.status === 304 && estado.copia) {
        this.sucesso(estado);
        return;
      }
      if (resposta.status === 404 && !estado.copia) {
        this.sucesso(estado);
        estado.ausente = true;
        return;
      }
      if (!resposta.ok) throw new Error(`HTTP ${resposta.status}`);
      const texto = await resposta.text();
      let dados: unknown;
      try {
        dados = JSON.parse(texto);
      } catch {
        throw new Error("JSON inválido");
      }
      if (!fonte.validar(dados)) {
        const [primeiro] = fonte.validar.errors ?? [];
        throw new Error(
          `Não cumpre o contrato: ${primeiro?.instancePath ?? ""} ${primeiro?.message ?? ""}`.trim(),
        );
      }
      estado.copia = {
        texto,
        etag: resposta.headers.get("ETag"),
        modificado: resposta.headers.get("Last-Modified"),
      };
      this.sucesso(estado);
      estado.ausente = false;
    } catch (erro) {
      // Não se insiste antes de FRESCURA_MS: a fonte em baixo não recebe um pedido por visita.
      estado.verificadaEm = this.agora();
      estado.erro = erro instanceof Error ? erro.message : String(erro);
      console.warn(JSON.stringify({ evento: "fonte-falhou", url: fonte.url, erro: estado.erro }));
    }
  }

  private sucesso(estado: EstadoFonte): void {
    estado.verificadaEm = this.agora();
    estado.confirmadaEm = estado.verificadaEm;
    estado.erro = null;
  }
}
