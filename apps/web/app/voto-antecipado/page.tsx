import type { Metadata } from "next";
import { SeccaoEmPreparacao } from "@/components/layout/SeccaoEmPreparacao.tsx";
import { PaginaEstado } from "@/components/voto-antecipado/PaginaEstado.tsx";
import { t } from "@/lib/mensagens.ts";
import { PaginaAgregado } from "@/components/voto-antecipado/PaginaAgregado.tsx";
import { carregarTodas } from "@/lib/voto-antecipado/carregar.ts";
import { resumirTodos } from "@/lib/voto-antecipado/resumo.ts";

export const metadata: Metadata = { title: t("seccoes.votoAntecipado.titulo") };

export default function Pagina() {
  // Lido e validado no build; o site é reconstruído a cada atualização de dados.
  // A Carolina do Norte é o estado com a análise por idade mais completa.
  const todas = carregarTodas();
  const estados = resumirTodos(todas).map((r) => r.estado);
  const principal = todas.individuais.find((v) => v.estado === "NC") ?? todas.individuais[0];
  const agregado = todas.agregados[0];
  if (!principal && agregado) return <PaginaAgregado vista={agregado} estados={estados} />;
  if (!principal) {
    return (
      <SeccaoEmPreparacao
        titulo={t("seccoes.votoAntecipado.titulo")}
        descricao={t("seccoes.votoAntecipado.descricao")}
      />
    );
  }
  return <PaginaEstado vista={principal} estados={estados} />;
}
