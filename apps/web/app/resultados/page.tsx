import type { Metadata } from "next";
import { SeccaoEmPreparacao } from "@/components/layout/SeccaoEmPreparacao.tsx";
import { HorariosFecho } from "@/components/noite/HorariosFecho.tsx";
import { PaginaResultados } from "@/components/resultados/PaginaResultados.tsx";
import { metadadosPagina } from "@/lib/metadados.ts";
import { carregarPrevisao } from "@/lib/previsao/carregar.ts";
import { t } from "@/lib/mensagens.ts";
import { carregarResultados } from "@/lib/resultados/carregar.ts";

export const metadata: Metadata = metadadosPagina({
  titulo: t("seccoes.resultados.titulo"),
  descricao: t("seccoes.resultados.descricao"),
  caminho: "/resultados/",
  cartao: "resultados.png",
});

export default function Pagina() {
  // Lidos e validados no build; sem contagem nem projeção, a página fica em preparação.
  const dados = carregarResultados();
  const horarios = <HorariosFecho previsao={carregarPrevisao()?.previsao ?? null} />;
  if (!dados) {
    return (
      <>
        <SeccaoEmPreparacao
          titulo={t("seccoes.resultados.titulo")}
          descricao={t("seccoes.resultados.descricao")}
        />
        {horarios}
      </>
    );
  }
  return (
    <>
      <PaginaResultados resultados={dados.resultados} noite={dados.noite} />
      {horarios}
    </>
  );
}
