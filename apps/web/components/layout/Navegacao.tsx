"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { t, type ChaveMensagem } from "@/lib/mensagens.ts";

interface Seccao {
  href: string;
  rotulo: ChaveMensagem;
  marca?: ChaveMensagem;
}

export const SECCOES: readonly Seccao[] = [
  { href: "/", rotulo: "navegacao.inicio" },
  {
    href: "/voto-antecipado/",
    rotulo: "navegacao.votoAntecipado",
    marca: "navegacao.votoAntecipadoMarca",
  },
  { href: "/mapa/", rotulo: "navegacao.mapa" },
  { href: "/previsao/", rotulo: "navegacao.previsao" },
  { href: "/sondagens/", rotulo: "navegacao.sondagens" },
  { href: "/resultados/", rotulo: "navegacao.resultados" },
  { href: "/metodologia/", rotulo: "navegacao.metodologia" },
];

/** Secção do caminho atual, ou null em páginas fora da navegação (ex.: /sistema/). */
export function seccaoAtiva(caminho: string): string | null {
  const normalizado = caminho.endsWith("/") ? caminho : `${caminho}/`;
  if (normalizado === "/") return "/";
  // As páginas de cada corrida pertencem à previsão.
  if (normalizado.startsWith("/corridas/")) return "/previsao/";
  return (
    SECCOES.find((seccao) => seccao.href !== "/" && normalizado.startsWith(seccao.href))?.href ??
    null
  );
}

export function Navegacao() {
  const ativa = seccaoAtiva(usePathname());
  return (
    <nav aria-label={t("navegacao.aria")} className="border-b border-rule bg-sheet">
      <ul className="contentor flex gap-1 overflow-x-auto [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
        {SECCOES.map((seccao) => {
          const atual = seccao.href === ativa;
          return (
            <li key={seccao.href} className="flex-none">
              <Link
                href={seccao.href}
                aria-current={atual ? "page" : undefined}
                className={`inline-block border-b-[3px] px-3 pt-3 pb-2.5 text-sm leading-none font-semibold whitespace-nowrap no-underline ${
                  atual ? "border-signal text-ink" : "border-transparent text-ink-2 hover:text-ink"
                }`}
              >
                {t(seccao.rotulo)}
                {seccao.marca ? (
                  <span className="ml-1.5 font-mono text-[10px] leading-none font-medium tracking-[0.04em] text-ink-3 uppercase">
                    {t(seccao.marca)}
                  </span>
                ) : null}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
