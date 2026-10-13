import type { Metadata } from "next";
import { SeccaoEmPreparacao } from "@/components/layout/SeccaoEmPreparacao.tsx";
import { PaginaAgregado } from "@/components/voto-antecipado/PaginaAgregado.tsx";
import { PaginaEstado } from "@/components/voto-antecipado/PaginaEstado.tsx";
import { nomeEstado } from "@/lib/estados.ts";
import { metadadosPagina } from "@/lib/metadados.ts";
import { t } from "@/lib/mensagens.ts";
import { carregarTodas } from "@/lib/voto-antecipado/carregar.ts";
import { resumirTodos } from "@/lib/voto-antecipado/resumo.ts";

export const dynamicParams = false;

/** Estados com página, do que tem mais votos para o que tem menos. */
function estadosComDados() {
  return resumirTodos(carregarTodas()).map((r) => r.estado);
}

/** Uma página por estado com dados; sem dados, só a da Carolina do Norte, em preparação. */
export function generateStaticParams(): { estado: string }[] {
  const estados = estadosComDados();
  return estados.length > 0
    ? estados.map((e) => ({ estado: e.toLowerCase() }))
    : [{ estado: "nc" }];
}

function vistaDe(estado: string) {
  const { individuais, agregados } = carregarTodas();
  const individual = individuais.find((v) => v.estado.toLowerCase() === estado);
  if (individual) return { tipo: "individual" as const, vista: individual };
  const agregado = agregados.find((v) => v.estado.toLowerCase() === estado);
  return agregado ? { tipo: "agregado" as const, vista: agregado } : undefined;
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ estado: string }>;
}): Promise<Metadata> {
  const estado = (await params).estado;
  const encontrada = vistaDe(estado);
  if (!encontrada) {
    return metadadosPagina({
      titulo: t("seccoes.votoAntecipado.titulo"),
      descricao: t("seccoes.votoAntecipado.descricao"),
      caminho: "/voto-antecipado/",
      cartao: "voto-antecipado.png",
    });
  }
  const nome = nomeEstado(encontrada.vista.estado);
  return metadadosPagina({
    titulo: `${t("seccoes.votoAntecipado.titulo")} · ${nome}`,
    descricao: t("cartoes.votoAntecipado.descricao", { estado: nome }),
    caminho: `/voto-antecipado/${estado}/`,
    cartao: `voto-antecipado-${estado}.png`,
  });
}

export default async function Pagina({ params }: { params: Promise<{ estado: string }> }) {
  const encontrada = vistaDe((await params).estado);
  if (!encontrada) {
    return (
      <SeccaoEmPreparacao
        titulo={t("seccoes.votoAntecipado.titulo")}
        descricao={t("seccoes.votoAntecipado.descricao")}
      />
    );
  }
  const estados = estadosComDados();
  return encontrada.tipo === "individual" ? (
    <PaginaEstado vista={encontrada.vista} estados={estados} />
  ) : (
    <PaginaAgregado vista={encontrada.vista} estados={estados} />
  );
}
