import type { Metadata } from "next";
import { SeccaoEmPreparacao } from "@/components/layout/SeccaoEmPreparacao.tsx";
import { PaginaResultados } from "@/components/resultados/PaginaResultados.tsx";
import { t } from "@/lib/mensagens.ts";
import { carregarResultados } from "@/lib/resultados/carregar.ts";

export const metadata: Metadata = { title: t("seccoes.resultados.titulo") };

export default function Pagina() {
  // Lido e validado no build; sem contagem publicada, a página fica em preparação.
  const vista = carregarResultados();
  if (!vista) {
    return (
      <SeccaoEmPreparacao
        titulo={t("seccoes.resultados.titulo")}
        descricao={t("seccoes.resultados.descricao")}
      />
    );
  }
  return <PaginaResultados vista={vista} />;
}
