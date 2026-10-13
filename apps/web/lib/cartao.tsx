/**
 * Cartões para redes sociais (Open Graph, 1200 × 630), gerados no build com next/og.
 *
 * As cores vêm de styles/tokens.css (tema claro) e as letras são as do sistema
 * visual, em woff (o gerador não lê woff2): Big Shoulders Display e IBM Plex Mono.
 */

import { readFileSync } from "node:fs";
import path from "node:path";
import { ImageResponse } from "next/og";
import { TAMANHO_CARTAO } from "./cartao-tamanho.ts";
import { t } from "./mensagens.ts";

/** Ficheiro de letra de um pacote @fontsource, lido no build a partir de apps/web. */
function letra(pacote: string, ficheiro: string): Buffer {
  return readFileSync(path.join(process.cwd(), "node_modules", pacote, "files", ficheiro));
}

/** Valor de um token do tema claro (o primeiro bloco :root de tokens.css). */
export function lerToken(css: string, nome: string): string {
  const valor = new RegExp(`--${nome}:\\s*([^;]+);`).exec(css)?.[1]?.trim();
  if (!valor) throw new Error(`Token em falta em tokens.css: --${nome}`);
  return valor;
}

let tokens: Record<"paper" | "sheet" | "ink" | "ink2" | "rule" | "signal", string> | undefined;

function cores() {
  if (!tokens) {
    const css = readFileSync(path.resolve(process.cwd(), "styles/tokens.css"), "utf-8");
    tokens = {
      paper: lerToken(css, "paper"),
      sheet: lerToken(css, "sheet"),
      ink: lerToken(css, "ink"),
      ink2: lerToken(css, "ink-2"),
      rule: lerToken(css, "rule"),
      signal: lerToken(css, "signal"),
    };
  }
  return tokens;
}

export interface ConteudoCartao {
  sobrelinha: string;
  titulo: string;
  /** Número ou frase em destaque (opcional). */
  destaque?: string;
  texto?: string;
}

/** Cartão com a marca, uma sobrelinha, o título e, opcionalmente, um destaque. */
export function cartao({ sobrelinha, titulo, destaque, texto }: ConteudoCartao): ImageResponse {
  const c = cores();
  return new ImageResponse(
    <div
      style={{
        width: "100%",
        height: "100%",
        display: "flex",
        flexDirection: "column",
        background: c.paper,
        padding: 40,
      }}
    >
      <div
        style={{
          flex: 1,
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          background: c.sheet,
          border: `2px solid ${c.rule}`,
          borderRadius: 10,
          padding: "44px 56px",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 18 }}>
          <div
            style={{
              width: 52,
              height: 32,
              borderRadius: "50%",
              border: `4px solid ${c.ink}`,
              display: "flex",
              padding: 4,
            }}
          >
            <div style={{ flex: 1, borderRadius: "50%", background: c.signal }} />
          </div>
          <span
            style={{
              fontFamily: "Display",
              fontSize: 52,
              fontWeight: 800,
              letterSpacing: 2,
              color: c.ink,
            }}
          >
            {t("site.nome").toUpperCase()}
          </span>
          <span
            style={{
              fontFamily: "Mono",
              fontSize: 22,
              color: c.ink2,
              borderLeft: `2px solid ${c.rule}`,
              paddingLeft: 18,
              letterSpacing: 1,
            }}
          >
            {t("site.subtitulo").toUpperCase()}
          </span>
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          <span style={{ fontFamily: "Mono", fontSize: 24, color: c.ink2, letterSpacing: 2 }}>
            {sobrelinha.toUpperCase()}
          </span>
          <span
            style={{
              fontFamily: "Display",
              fontSize: 84,
              fontWeight: 800,
              lineHeight: 1,
              color: c.ink,
            }}
          >
            {titulo}
          </span>
          {destaque ? (
            <span
              style={{
                fontFamily: "Display",
                fontSize: 64,
                fontWeight: 900,
                lineHeight: 1,
                color: c.ink,
                borderLeft: `10px solid ${c.signal}`,
                paddingLeft: 20,
                marginTop: 8,
              }}
            >
              {destaque}
            </span>
          ) : null}
          {texto ? (
            <span style={{ fontFamily: "Mono", fontSize: 26, color: c.ink2, lineHeight: 1.35 }}>
              {texto}
            </span>
          ) : null}
        </div>
      </div>
    </div>,
    {
      ...TAMANHO_CARTAO,
      fonts: [
        {
          name: "Display",
          data: letra(
            "@fontsource/big-shoulders-display",
            "big-shoulders-display-latin-800-normal.woff",
          ),
          weight: 800,
        },
        {
          name: "Display",
          data: letra(
            "@fontsource/big-shoulders-display",
            "big-shoulders-display-latin-900-normal.woff",
          ),
          weight: 900,
        },
        {
          name: "Mono",
          data: letra("@fontsource/ibm-plex-mono", "ibm-plex-mono-latin-500-normal.woff"),
          weight: 500,
        },
      ],
    },
  );
}
