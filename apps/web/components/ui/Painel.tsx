import type { ReactNode } from "react";
import { t } from "@/lib/mensagens.ts";

export interface ReferenciaFonte {
  nome: string;
  url?: string;
}

interface PainelProps {
  titulo: string;
  sobrelinha?: string;
  descricao?: string;
  /** Selos ou controlos alinhados à direita do título. */
  acessorio?: ReactNode;
  fontes?: readonly ReferenciaFonte[];
  metodo?: string;
  /** "h1" quando o painel é o conteúdo principal da página (secções em preparação, 404). */
  nivelTitulo?: "h1" | "h2";
  children?: ReactNode;
  className?: string;
}

/** Painel do painel de instrumentos: título, conteúdo e rodapé de fonte e método. */
export function Painel({
  titulo,
  sobrelinha,
  descricao,
  acessorio,
  fontes,
  metodo,
  nivelTitulo = "h2",
  children,
  className = "",
}: PainelProps) {
  const Titulo = nivelTitulo;
  const temRodape = (fontes?.length ?? 0) > 0 || metodo !== undefined;
  return (
    <section
      className={`flex min-w-0 flex-col gap-3 rounded-md border border-rule bg-sheet px-[18px] pt-[18px] pb-3.5 ${className}`}
    >
      <header className="flex flex-wrap items-start justify-between gap-x-3.5 gap-y-2">
        <div className="min-w-0">
          {sobrelinha ? <p className="rotulo mb-1">{sobrelinha}</p> : null}
          <Titulo className="font-display text-[27px] leading-[1.02] font-bold">{titulo}</Titulo>
          {descricao ? <p className="mt-1 max-w-[62ch] text-sm text-ink-2">{descricao}</p> : null}
        </div>
        {acessorio}
      </header>
      {children}
      {temRodape ? (
        <footer className="flex flex-wrap justify-between gap-x-3.5 gap-y-1.5 border-t border-rule-2 pt-2 font-mono text-[11px] leading-snug text-ink-3">
          {fontes && fontes.length > 0 ? (
            <span>
              {t("comum.fonte")}:{" "}
              {fontes.map((fonte, indice) => (
                <span key={fonte.nome}>
                  {indice > 0 ? "; " : null}
                  {fonte.url ? (
                    <a
                      href={fonte.url}
                      className="text-ink-2 underline decoration-rule underline-offset-[3px]"
                      rel="noopener noreferrer"
                    >
                      {fonte.nome}
                    </a>
                  ) : (
                    fonte.nome
                  )}
                </span>
              ))}
            </span>
          ) : null}
          {metodo ? (
            <span>
              {t("comum.metodo")}: {metodo}
            </span>
          ) : null}
        </footer>
      ) : null}
    </section>
  );
}
