import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { PaginaAvaliacao } from "@/components/previsao/PaginaAvaliacao.tsx";
import { metadadosPagina } from "@/lib/metadados.ts";
import { t } from "@/lib/mensagens.ts";
import { avaliarPrevisao } from "@/lib/previsao/avaliacao.ts";
import { carregarPrevisao } from "@/lib/previsao/carregar.ts";
import { construirChamadas } from "@/lib/resultados/chamadas.ts";
import { carregarChamadas } from "@/lib/resultados/carregar.ts";

export const metadata: Metadata = metadadosPagina({
  titulo: t("previsao.avaliacao.titulo"),
  descricao: t("previsao.avaliacao.descricao"),
  caminho: "/previsao/avaliacao/",
  cartao: "previsao.png",
});

export default function Pagina() {
  const dados = carregarPrevisao();
  // Sem previsão não há nada para avaliar; a página da previsão explica porquê.
  if (!dados) redirect("/previsao/");
  const chamadas = construirChamadas(carregarChamadas(), dados.previsao.ano);
  return (
    <PaginaAvaliacao
      vista={dados.previsao}
      avaliacao={avaliarPrevisao(dados.previsao, chamadas, dados.prognosticos)}
      prognosticos={dados.prognosticos}
    />
  );
}
