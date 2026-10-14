import type { Metadata } from "next";
import { SeccaoEmPreparacao } from "@/components/layout/SeccaoEmPreparacao.tsx";
import { PaginaCorridaSondagens } from "@/components/sondagens/Paginas.tsx";
import { metadadosPagina } from "@/lib/metadados.ts";
import { t } from "@/lib/mensagens.ts";
import { carregarSondagens } from "@/lib/sondagens/carregar.ts";
import { nomeCorrida } from "@/lib/sondagens/vista.ts";

export const dynamicParams = false;

/** Uma página por corrida com sondagens; sem ficheiro, só a da Carolina do Norte, em preparação. */
export function generateStaticParams(): { corrida: string }[] {
  const corridas = carregarSondagens()?.corridas ?? [];
  return corridas.length > 0
    ? corridas.map((c) => ({ corrida: c.id.toLowerCase() }))
    : [{ corrida: "nc-s" }];
}

function encontrar(corrida: string) {
  const vista = carregarSondagens();
  const c = vista?.corridas.find((x) => x.id.toLowerCase() === corrida);
  return vista && c ? { vista, corrida: c } : null;
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ corrida: string }>;
}): Promise<Metadata> {
  const corrida = (await params).corrida;
  const encontrada = encontrar(corrida);
  return metadadosPagina({
    titulo: encontrada
      ? `${t("seccoes.sondagens.titulo")} · ${nomeCorrida(encontrada.corrida)}`
      : t("seccoes.sondagens.titulo"),
    descricao: t("seccoes.sondagens.descricao"),
    caminho: `/sondagens/${corrida}/`,
    cartao: "sondagens.png",
  });
}

export default async function Pagina({ params }: { params: Promise<{ corrida: string }> }) {
  const encontrada = encontrar((await params).corrida);
  if (!encontrada) {
    return (
      <SeccaoEmPreparacao
        titulo={t("seccoes.sondagens.titulo")}
        descricao={t("seccoes.sondagens.descricao")}
      />
    );
  }
  return <PaginaCorridaSondagens vista={encontrada.vista} corrida={encontrada.corrida} />;
}
