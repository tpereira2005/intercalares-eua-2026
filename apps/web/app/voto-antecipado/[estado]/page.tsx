import type { Metadata } from "next";
import { SeccaoEmPreparacao } from "@/components/layout/SeccaoEmPreparacao.tsx";
import { PaginaEstado } from "@/components/voto-antecipado/PaginaEstado.tsx";
import { nomeEstado } from "@/lib/estados.ts";
import { t } from "@/lib/mensagens.ts";
import { carregarVistas } from "@/lib/voto-antecipado/carregar.ts";

export const dynamicParams = false;

/** Uma página por estado com dados; sem dados, só a da Carolina do Norte, em preparação. */
export function generateStaticParams(): { estado: string }[] {
  const vistas = carregarVistas();
  return vistas.length > 0
    ? vistas.map((v) => ({ estado: v.estado.toLowerCase() }))
    : [{ estado: "nc" }];
}

function vistaDe(estado: string) {
  return carregarVistas().find((v) => v.estado.toLowerCase() === estado);
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ estado: string }>;
}): Promise<Metadata> {
  const vista = vistaDe((await params).estado);
  return {
    title: vista
      ? `${t("seccoes.votoAntecipado.titulo")} · ${nomeEstado(vista.estado)}`
      : t("seccoes.votoAntecipado.titulo"),
  };
}

export default async function Pagina({ params }: { params: Promise<{ estado: string }> }) {
  const vista = vistaDe((await params).estado);
  if (!vista) {
    return (
      <SeccaoEmPreparacao
        titulo={t("seccoes.votoAntecipado.titulo")}
        descricao={t("seccoes.votoAntecipado.descricao")}
      />
    );
  }
  return <PaginaEstado vista={vista} estados={carregarVistas().map((v) => v.estado)} />;
}
