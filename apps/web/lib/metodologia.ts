/**
 * Documentos de metodologia (docs/metodologia/*.md), lidos e convertidos em HTML no build.
 *
 * Os documentos são a fonte única: o site mostra-os tal como estão no repositório, para
 * que a página e o GitHub nunca digam coisas diferentes. Só se ajustam as ligações entre
 * documentos (para as páginas do site) e as tabelas (para deslizarem dentro de si no
 * telemóvel, sem deslocar a página).
 */

import { existsSync, readFileSync } from "node:fs";
import path from "node:path";
import { Marked } from "marked";

export const DOCUMENTOS = [
  "voto-antecipado",
  "voto-antecipado-estados",
  "previsao",
  "noite-eleitoral",
  "resultados",
] as const;
export type Documento = (typeof DOCUMENTOS)[number];

export const REPOSITORIO = "https://github.com/tpereira2005/intercalares-eua-2026/blob/main";

/** Pasta dos documentos, relativa a apps/web (onde corre o build). */
const PASTA = "../../docs/metodologia";

export function caminhoMetodologia(documento: Documento, ancora?: string): string {
  return `/metodologia/${documento}/${ancora ? `#${ancora}` : ""}`;
}

/** Âncora ao estilo do GitHub: "4. Sondagens do Senado" → "4-sondagens-do-senado". */
export function ancora(texto: string): string {
  return texto
    .toLowerCase()
    .trim()
    .replace(/<[^>]+>/g, "")
    .replace(/[^\p{L}\p{N}\s_-]/gu, "")
    .replace(/\s/g, "-");
}

function eDocumento(nome: string): nome is Documento {
  return (DOCUMENTOS as readonly string[]).includes(nome);
}

/** Ligações a outros .md: para a página do site, se for metodologia, ou para o GitHub. */
export function reescreverLigacao(href: string): string {
  if (/^[a-z]+:/i.test(href) || href.startsWith("#")) return href;
  const [caminho = "", fragmento] = href.split("#");
  if (!caminho.endsWith(".md")) return href;
  const nome = path.posix.basename(caminho, ".md");
  const dentro = !caminho.includes("/") || caminho.startsWith("./");
  if (dentro && eDocumento(nome)) return caminhoMetodologia(nome, fragmento);
  const absoluto = path.posix.normalize(path.posix.join("docs/metodologia", caminho));
  return `${REPOSITORIO}/${absoluto}${fragmento ? `#${fragmento}` : ""}`;
}

function escapar(texto: string): string {
  return texto
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

export interface SeccaoDocumento {
  id: string;
  titulo: string;
}

export interface DocumentoMetodologia {
  documento: Documento;
  titulo: string;
  /** Primeiro parágrafo, para o índice e os metadados. */
  resumo: string;
  seccoes: SeccaoDocumento[];
  html: string;
  fonte: string;
}

export function converter(
  documento: Documento,
  texto: string,
  rotuloTabela: string,
): DocumentoMetodologia {
  const primeiro = /^#\s+(.+)$/m.exec(texto);
  // "Metodologia: previsão..." repete a secção do site; fica só o assunto, com maiúscula.
  const bruto = (primeiro?.[1] ?? documento).trim().replace(/^Metodologia:\s*/i, "");
  const titulo = bruto.charAt(0).toUpperCase() + bruto.slice(1);
  const corpo = primeiro ? texto.replace(primeiro[0], "") : texto;
  const seccoes: SeccaoDocumento[] = [];
  const marked = new Marked({ gfm: true });
  marked.use({
    renderer: {
      heading(h) {
        const conteudo = this.parser.parseInline(h.tokens);
        const id = ancora(h.text);
        // O título do documento é o h1 da página; os outros títulos ficam entre h2 e h4.
        const nivel = String(Math.min(Math.max(h.depth, 2), 4));
        if (h.depth === 2) seccoes.push({ id, titulo: h.text.replace(/[*`]/g, "") });
        return `<h${nivel} id="${escapar(id)}">${conteudo}</h${nivel}>\n`;
      },
      link(l) {
        const href = reescreverLigacao(l.href);
        const externo = /^https?:/.test(href);
        const texto = this.parser.parseInline(l.tokens);
        return `<a href="${escapar(href)}"${externo ? ' rel="noopener noreferrer"' : ""}>${texto}</a>`;
      },
    },
  });
  // As tabelas deslizam dentro de si no telemóvel, com foco de teclado para as percorrer.
  const html = marked
    .parse(corpo, { async: false })
    .replaceAll(
      "<table>",
      `<div class="tabela-deslizante" tabindex="0" role="region" aria-label="${escapar(rotuloTabela)}"><table>`,
    )
    .replaceAll("</table>", "</table></div>");
  const resumo =
    corpo
      .split(/\n\s*\n/)
      .map((b) => b.trim())
      .find((b) => b !== "" && !b.startsWith("#") && !b.startsWith("|") && !b.startsWith("```")) ??
    "";
  return {
    documento,
    titulo,
    resumo: resumo.replace(/\[([^\]]+)\]\([^)]+\)/g, "$1").replace(/[*`]/g, ""),
    seccoes,
    html,
    fonte: `${REPOSITORIO}/docs/metodologia/${documento}.md`,
  };
}

export function lerDocumento(
  documento: Documento,
  rotuloTabela: string,
): DocumentoMetodologia | null {
  const ficheiro = path.resolve(process.cwd(), PASTA, `${documento}.md`);
  if (!existsSync(ficheiro)) return null;
  return converter(documento, readFileSync(ficheiro, "utf-8"), rotuloTabela);
}
