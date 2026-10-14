import type { Metadata } from "next";
import { SeccaoEmPreparacao } from "@/components/layout/SeccaoEmPreparacao.tsx";
import { PaginaSondagens } from "@/components/sondagens/Paginas.tsx";
import { metadadosPagina } from "@/lib/metadados.ts";
import { t } from "@/lib/mensagens.ts";
import { carregarSondagens } from "@/lib/sondagens/carregar.ts";

export const metadata: Metadata = metadadosPagina({
  titulo: t("seccoes.sondagens.titulo"),
  descricao: t("seccoes.sondagens.descricao"),
  caminho: "/sondagens/",
  cartao: "sondagens.png",
});

export default function Pagina() {
  // Lido e validado no build; sem ficheiro, a página fica em preparação.
  const vista = carregarSondagens();
  if (!vista) {
    return (
      <SeccaoEmPreparacao
        titulo={t("seccoes.sondagens.titulo")}
        descricao={t("seccoes.sondagens.descricao")}
      />
    );
  }
  return <PaginaSondagens vista={vista} />;
}
