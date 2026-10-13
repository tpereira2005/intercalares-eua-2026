import type { Metadata } from "next";
import { SeccaoEmPreparacao } from "@/components/layout/SeccaoEmPreparacao.tsx";
import { PaginaEstado } from "@/components/voto-antecipado/PaginaEstado.tsx";
import { t } from "@/lib/mensagens.ts";
import { carregarVistas } from "@/lib/voto-antecipado/carregar.ts";

export const metadata: Metadata = { title: t("seccoes.votoAntecipado.titulo") };

export default function Pagina() {
  // Lido e validado no build; o site é reconstruído a cada atualização de dados.
  const vistas = carregarVistas();
  const principal = vistas.find((v) => v.estado === "NC") ?? vistas[0];
  if (!principal) {
    return (
      <SeccaoEmPreparacao
        titulo={t("seccoes.votoAntecipado.titulo")}
        descricao={t("seccoes.votoAntecipado.descricao")}
      />
    );
  }
  return <PaginaEstado vista={principal} estados={vistas.map((v) => v.estado)} />;
}
