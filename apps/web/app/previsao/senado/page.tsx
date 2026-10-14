import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { PaginaCamara } from "@/components/previsao/PaginaCamara.tsx";
import { metadadosPagina } from "@/lib/metadados.ts";
import { t } from "@/lib/mensagens.ts";
import { carregarPrevisao } from "@/lib/previsao/carregar.ts";

export const metadata: Metadata = metadadosPagina({
  titulo: t("previsao.paginas.senado.titulo"),
  descricao: t("previsao.paginas.senado.descricao"),
  caminho: "/previsao/senado/",
  cartao: "previsao.png",
});

export default function Pagina() {
  const dados = carregarPrevisao();
  // Sem previsão publicada, a página das duas câmaras explica o que falta.
  if (!dados) redirect("/previsao/");
  return <PaginaCamara dados={dados} camara="senado" />;
}
