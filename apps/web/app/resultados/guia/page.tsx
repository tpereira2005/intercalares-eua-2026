import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { GuiaNoite } from "@/components/noite/GuiaNoite.tsx";
import { metadadosPagina } from "@/lib/metadados.ts";
import { t } from "@/lib/mensagens.ts";
import { construirGuia } from "@/lib/noite/guia.ts";
import { carregarPrevisao } from "@/lib/previsao/carregar.ts";

export const metadata: Metadata = metadadosPagina({
  titulo: t("guia.titulo"),
  descricao: t("guia.descricao"),
  caminho: "/resultados/guia/",
  cartao: "resultados.png",
});

export default function Pagina() {
  const dados = carregarPrevisao();
  // Sem previsão não há corridas a seguir; os horários de fecho estão na noite eleitoral.
  if (!dados) redirect("/resultados/");
  return (
    <GuiaNoite
      guia={construirGuia(dados.previsao, dados.prognosticos)}
      prognosticos={dados.prognosticos}
    />
  );
}
