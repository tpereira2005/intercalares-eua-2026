import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { PaginaCenarios } from "@/components/previsao/PaginaCenarios.tsx";
import { metadadosPagina } from "@/lib/metadados.ts";
import { t } from "@/lib/mensagens.ts";
import { carregarPrevisao } from "@/lib/previsao/carregar.ts";

export const metadata: Metadata = metadadosPagina({
  titulo: t("previsao.cenarios.titulo"),
  descricao: t("previsao.cenarios.descricao"),
  caminho: "/previsao/cenarios/",
  cartao: "previsao.png",
});

export default function Pagina() {
  const dados = carregarPrevisao();
  // Sem cenários do mesmo corte, a página da previsão explica o que há.
  if (!dados?.cenarios) redirect("/previsao/");
  return <PaginaCenarios dados={dados} cenarios={dados.cenarios} />;
}
