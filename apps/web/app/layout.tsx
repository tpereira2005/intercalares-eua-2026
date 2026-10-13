import "./globals.css";

import type { Metadata, Viewport } from "next";
import type { ReactNode } from "react";
import { PadroesSvg } from "@/components/charts/PadroesSvg.tsx";
import { Cabecalho } from "@/components/layout/Cabecalho.tsx";
import { Navegacao } from "@/components/layout/Navegacao.tsx";
import { Rodape } from "@/components/layout/Rodape.tsx";
import { metadadosPagina } from "@/lib/metadados.ts";
import { t } from "@/lib/mensagens.ts";
import { URL_SITE } from "@/lib/site.ts";
import { SCRIPT_TEMA } from "@/lib/tema.ts";

export const metadata: Metadata = {
  ...metadadosPagina({
    titulo: null,
    descricao: t("site.descricao"),
    caminho: null,
    cartao: "inicio.png",
  }),
  metadataBase: URL_SITE,
  title: {
    default: `${t("site.nome")} · ${t("site.subtitulo")}`,
    template: `%s · ${t("site.nome")}`,
  },
};

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#ffffff" },
    { media: "(prefers-color-scheme: dark)", color: "#151920" },
  ],
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    // O script de tema altera data-theme antes da hidratação.
    <html lang="pt-PT" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: SCRIPT_TEMA }} />
      </head>
      <body className="min-h-dvh antialiased">
        <a
          href="#conteudo"
          className="sr-only focus:not-sr-only focus:absolute focus:top-2 focus:left-2 focus:z-10 focus:rounded-sm focus:bg-sheet focus:px-3 focus:py-2"
        >
          {t("site.irParaConteudo")}
        </a>
        <PadroesSvg />
        <Cabecalho />
        <Navegacao />
        <main id="conteudo" className="contentor flex flex-col gap-4 pt-[18px] pb-10">
          {children}
        </main>
        <Rodape />
      </body>
    </html>
  );
}
